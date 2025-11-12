"""
Storage operations module for Zapier Triggers API.

Handles DynamoDB and S3 operations for event storage, retrieval, and management.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Get environment variables
EVENTS_TABLE_NAME = os.environ.get('EVENTS_TABLE', 'zapier-triggers-events-dev')
EVENTS_BUCKET_NAME = os.environ.get('EVENTS_BUCKET', 'zapier-triggers-events-dev')
SIZE_THRESHOLD_BYTES = int(os.environ.get('SIZE_THRESHOLD_BYTES', '400000'))
LEASE_DURATION_MINUTES = int(os.environ.get('LEASE_DURATION_MINUTES', '5'))
EVENT_TTL_DAYS = 30

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')


def get_events_table():
    """Get events table (lazy initialization for testing)."""
    table_name = os.environ.get('EVENTS_TABLE', EVENTS_TABLE_NAME)
    return dynamodb.Table(table_name)


def generate_event_id() -> str:
    """
    Generate a unique event ID in format evt_{base64url_32chars}.
    
    Returns:
        Event ID string
    """
    import secrets
    # Generate 24 bytes (32 base64url chars after encoding)
    random_bytes = secrets.token_urlsafe(24)
    return f"evt_{random_bytes}"


def generate_cursor(timestamp: int, event_id: str) -> str:
    """
    Generate pagination cursor in format {timestamp}_{event_id}.
    
    Args:
        timestamp: Unix timestamp (seconds)
        event_id: Event identifier
        
    Returns:
        Cursor string
    """
    return f"{timestamp}_{event_id}"


def parse_cursor(cursor: str) -> Dict[str, Any]:
    """
    Parse cursor and validate 24-hour TTL.
    
    Args:
        cursor: Cursor string in format {timestamp}_{event_id}
        
    Returns:
        Dictionary with 'timestamp' and 'event_id'
        
    Raises:
        ValueError: If cursor is invalid or expired
    """
    import re
    
    # Parse cursor format: {unix_timestamp}_{event_id}
    cursor_pattern = re.compile(r'^(\d+)_(evt_.+)$')
    match = cursor_pattern.match(cursor)
    
    if not match:
        raise ValueError("Invalid cursor format: expected {timestamp}_{event_id}")
    
    timestamp_str, event_id = match.groups()
    
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise ValueError("Invalid cursor timestamp: must be integer")
    
    # Check TTL: cursor must be less than 24 hours old
    current_timestamp = int(datetime.now(timezone.utc).timestamp())
    age_seconds = current_timestamp - timestamp
    
    if age_seconds < 0:
        raise ValueError("Cursor timestamp is in the future")
    
    if age_seconds > 24 * 60 * 60:  # 24 hours
        raise ValueError("Cursor expired: must be less than 24 hours old")
    
    return {
        'timestamp': timestamp,
        'event_id': event_id
    }


def check_idempotency(tenant_id: str, event_id: str) -> bool:
    """
    Check if event_id already exists for tenant (for idempotency).
    
    Args:
        tenant_id: Tenant identifier
        event_id: Event identifier
        
    Returns:
        True if event exists, False otherwise
    """
    try:
        # Query by partition key and check if event exists
        # We need to query with a filter on the sort key prefix
        pk = f"TENANT#{tenant_id}"
        
        # Use query to check if event exists
        # Since we don't have the timestamp, we'll use a query with begins_with
        response = get_events_table().query(
            KeyConditionExpression='pk = :pk',
            FilterExpression='id = :event_id',
            ExpressionAttributeValues={
                ':pk': pk,
                ':event_id': event_id
            },
            Limit=1
        )
        
        return len(response.get('Items', [])) > 0
    except Exception as e:
        logger.error(f"Error checking idempotency: {e}")
        return False


def get_events_bucket_name() -> str:
    """Get events bucket name (lazy initialization for testing)."""
    return os.environ.get('EVENTS_BUCKET', EVENTS_BUCKET_NAME)


def put_large_payload(bucket: str, key: str, payload: Dict[str, Any]) -> str:
    """
    Write large payload to S3.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        payload: JSON payload dictionary
        
    Returns:
        S3 key string
        
    Raises:
        ClientError: If S3 write fails
    """
    json_str = json.dumps(payload, separators=(',', ':'))
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json_str.encode('utf-8'),
        ContentType='application/json',
        ServerSideEncryption='AES256'
    )
    return key


def get_large_payload(bucket: str, key: str) -> Dict[str, Any]:
    """
    Read large payload from S3.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        JSON payload dictionary
        
    Raises:
        ClientError: If S3 read fails
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    json_str = response['Body'].read().decode('utf-8')
    return json.loads(json_str)


def store_event(
    tenant_id: str,
    event_data: Dict[str, Any],
    payload_size: int
) -> Dict[str, Any]:
    """
    Store event in DynamoDB or S3 based on size threshold.
    
    Args:
        tenant_id: Tenant identifier
        event_data: Event data dictionary with id, event_type, timestamp, data
        payload_size: Size of payload in bytes
        
    Returns:
        Dictionary with storage details:
        {
            'event_id': str,
            'storage_type': 'dynamodb' | 's3',
            's3_key': Optional[str]
        }
        
    Raises:
        ClientError: If DynamoDB write fails (for idempotency conflicts)
    """
    event_id = event_data['id']
    event_type = event_data['event_type']
    timestamp = event_data['timestamp']
    data = event_data['data']
    
    # Calculate TTL: 30 days from now
    now = datetime.now(timezone.utc)
    ttl_timestamp = int((now + timedelta(days=EVENT_TTL_DAYS)).timestamp())
    
    # Create partition and sort keys
    pk = f"TENANT#{tenant_id}"
    sk = f"EVENT#{event_id}#{timestamp}"
    
    # Determine storage strategy
    use_s3 = payload_size >= SIZE_THRESHOLD_BYTES
    
    s3_key = None
    dynamodb_data = None
    
    if use_s3:
        # Store in S3
        s3_key = f"events/{tenant_id}/{event_id}.json"
        try:
            put_large_payload(get_events_bucket_name(), s3_key, data)
            storage_type = 's3'
        except Exception as e:
            # Fallback to DynamoDB on S3 failure
            logger.error(f"S3 write failed, falling back to DynamoDB: {e}")
            dynamodb_data = data
            s3_key = None
            storage_type = 'dynamodb'
    else:
        # Store inline in DynamoDB
        dynamodb_data = data
        storage_type = 'dynamodb'
    
    # Prepare DynamoDB item
    item = {
        'pk': pk,
        'sk': sk,
        'id': event_id,
        'event_type': event_type,
        'timestamp': timestamp,
        'tenant_id': tenant_id,
        'status': 'pending',
        'in_flight_until': None,
        'attempt_count': 0,
        's3_key': s3_key,
        'data': dynamodb_data,
        'created_at': now.isoformat(),
        'ttl': ttl_timestamp
    }
    
    # Check idempotency: query if event_id already exists for this tenant
    # Filter client-side since FilterExpression can be unreliable
    existing_response = get_events_table().query(
        KeyConditionExpression='pk = :pk',
        ExpressionAttributeValues={
            ':pk': pk
        }
    )
    
    # Filter by event_id client-side
    existing_items = [item for item in existing_response.get('Items', []) if item.get('id') == event_id]
    
    if existing_items:
        # Event already exists - idempotency conflict
        raise ClientError(
            {
                'Error': {
                    'Code': 'ConditionalCheckFailedException',
                    'Message': 'Event already exists'
                }
            },
            'PutItem'
        )
    
    # Insert event
    get_events_table().put_item(Item=item)
    
    return {
        'event_id': event_id,
        'storage_type': storage_type,
        's3_key': s3_key
    }


def get_event(tenant_id: str, event_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve event from DynamoDB (fetch S3 if s3_key present).
    
    Args:
        tenant_id: Tenant identifier
        event_id: Event identifier
        
    Returns:
        Event dictionary if found, None otherwise
    """
    pk = f"TENANT#{tenant_id}"
    
    # Query to find event (filter client-side since FilterExpression can be unreliable)
    response = get_events_table().query(
        KeyConditionExpression='pk = :pk',
        ExpressionAttributeValues={
            ':pk': pk
        }
    )
    
    # Filter by event_id client-side
    items = [item for item in response.get('Items', []) if item.get('id') == event_id]
    if not items:
        return None
    
    item = items[0]
    
    # Fetch S3 payload if s3_key present
    if item.get('s3_key'):
        try:
            s3_data = get_large_payload(get_events_bucket_name(), item['s3_key'])
            item['data'] = s3_data
        except Exception as e:
            logger.error(f"Failed to fetch S3 payload: {e}")
            # Return item without data if S3 fetch fails
            item['data'] = None
    
    return item


def query_events(
    tenant_id: str,
    filters: Optional[Dict[str, Any]] = None,
    cursor: Optional[str] = None,
    limit: int = 25
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Query DynamoDB for events with filters, pagination, and lease updates.
    
    Args:
        tenant_id: Tenant identifier
        filters: Optional filters dict with:
            - event_type: str
            - after: str (ISO 8601 timestamp)
            - before: str (ISO 8601 timestamp)
            - status: str ('pending' | 'acknowledged')
        cursor: Optional pagination cursor
        limit: Maximum number of events to return (default 25, max 100)
        
    Returns:
        Tuple of (events_list, next_cursor)
    """
    pk = f"TENANT#{tenant_id}"
    now = datetime.now(timezone.utc)
    
    # Build filter expression
    filter_expressions = []
    expression_values = {':pk': pk}
    expression_names = {}
    
    # Filter: status=pending (default for inbox)
    # Use ExpressionAttributeNames to escape reserved keyword 'status'
    if filters and filters.get('status'):
        filter_expressions.append('#status = :status')
        expression_names['#status'] = 'status'
        expression_values[':status'] = filters['status']
    else:
        filter_expressions.append('#status = :status')
        expression_names['#status'] = 'status'
        expression_values[':status'] = 'pending'
    
    # Filter: exclude events with active leases
    # Note: We'll filter client-side for lease exclusion to avoid issues with attribute_not_exists
    # For now, we'll query all and filter in Python
    expression_values[':now'] = now.isoformat()
    
    # Filter: event_type
    if filters and filters.get('event_type'):
        filter_expressions.append('event_type = :event_type')
        expression_values[':event_type'] = filters['event_type']
    
    # Filter: timestamp range (timestamp is a reserved keyword)
    if filters and filters.get('after'):
        filter_expressions.append('#timestamp >= :after')
        expression_names['#timestamp'] = 'timestamp'
        expression_values[':after'] = filters['after']
    
    if filters and filters.get('before'):
        filter_expressions.append('#timestamp <= :before')
        expression_names['#timestamp'] = 'timestamp'
        expression_values[':before'] = filters['before']
    
    # Handle cursor pagination
    exclusive_start_key = None
    if cursor:
        try:
            cursor_data = parse_cursor(cursor)
            # Use cursor to set exclusive start key
            # We need to construct the sort key from cursor data
            # Since cursor has timestamp and event_id, we can query from that point
            cursor_timestamp = cursor_data['timestamp']
            cursor_event_id = cursor_data['event_id']
            # Note: We can't directly use cursor for exclusive_start_key without the full sort key
            # For now, we'll query and filter client-side (not ideal, but works for MVP)
            pass
        except ValueError:
            # Invalid cursor - will be handled by handler
            pass
    
    # Query DynamoDB
    query_params = {
        'KeyConditionExpression': 'pk = :pk',
        'FilterExpression': ' AND '.join(f'({expr})' for expr in filter_expressions),
        'ExpressionAttributeValues': expression_values,
        'Limit': min(limit * 2, 200)  # Fetch more to account for filtering
    }
    
    if expression_names:
        query_params['ExpressionAttributeNames'] = expression_names
    
    if exclusive_start_key:
        query_params['ExclusiveStartKey'] = exclusive_start_key
    
    response = get_events_table().query(**query_params)
    
    items = response.get('Items', [])
    
    # Filter out events with active leases (client-side filtering)
    filtered_items = []
    for item in items:
        in_flight_until = item.get('in_flight_until')
        if in_flight_until is None:
            # No lease - include
            filtered_items.append(item)
        else:
            # Check if lease expired
            try:
                lease_expiry = datetime.fromisoformat(in_flight_until.replace('Z', '+00:00'))
                if lease_expiry < now:
                    # Lease expired - include
                    filtered_items.append(item)
                # else: lease still active - exclude
            except Exception:
                # If parsing fails, include the item (safer)
                filtered_items.append(item)
    
    items = filtered_items
    
    # Sort by created_at ascending
    items.sort(key=lambda x: x.get('created_at', ''))
    
    # Apply cursor filtering if needed (client-side for MVP)
    if cursor:
        try:
            cursor_data = parse_cursor(cursor)
            cursor_timestamp = cursor_data['timestamp']
            cursor_event_id = cursor_data['event_id']
            
            # Filter items after cursor
            filtered_items = []
            found_cursor = False
            for item in items:
                if found_cursor:
                    filtered_items.append(item)
                elif item['id'] == cursor_event_id:
                    found_cursor = True
                    # Skip the cursor item itself
                else:
                    # Check if item is after cursor timestamp
                    try:
                        item_created = datetime.fromisoformat(item.get('created_at', '').replace('Z', '+00:00'))
                        cursor_dt = datetime.fromtimestamp(cursor_timestamp, tz=timezone.utc)
                        if item_created > cursor_dt:
                            filtered_items.append(item)
                    except Exception:
                        # If timestamp parsing fails, skip item
                        pass
            
            items = filtered_items
        except Exception:
            # If cursor parsing fails, return empty (handler will return 400)
            items = []
    
    # Limit results
    items = items[:limit]
    
    # Update leases: set in_flight_until = now + 5 minutes, increment attempt_count
    lease_expiry = (now + timedelta(minutes=LEASE_DURATION_MINUTES)).isoformat()
    
    for item in items:
        event_id = item['id']
        current_attempt_count = item.get('attempt_count', 0)
        
        try:
            get_events_table().update_item(
                Key={
                    'pk': pk,
                    'sk': item['sk']
                },
                UpdateExpression='SET in_flight_until = :lease, attempt_count = :count',
                ExpressionAttributeValues={
                    ':lease': lease_expiry,
                    ':count': current_attempt_count + 1
                }
            )
            item['in_flight_until'] = lease_expiry
            item['attempt_count'] = current_attempt_count + 1
        except Exception as e:
            logger.error(f"Failed to update lease for event {event_id}: {e}")
    
    # Fetch S3 payloads if needed
    for item in items:
        if item.get('s3_key'):
            try:
                s3_data = get_large_payload(get_events_bucket_name(), item['s3_key'])
                item['data'] = s3_data
            except Exception as e:
                logger.error(f"Failed to fetch S3 payload for {item.get('s3_key')}: {e}")
                # Don't set data to None - skip this item or use fallback
                # For now, we'll skip items where S3 fetch fails
                item['data'] = None
    
    # Generate next_cursor if has_more
    next_cursor = None
    has_more = 'LastEvaluatedKey' in response or len(items) == limit
    
    if has_more and items:
        last_item = items[-1]
        # Extract timestamp from sort key or use created_at
        try:
            # Parse timestamp from sort key: EVENT#{event_id}#{timestamp}
            sk_parts = last_item['sk'].split('#')
            if len(sk_parts) >= 3:
                timestamp_str = sk_parts[2]
                # Convert ISO timestamp to unix timestamp for cursor
                timestamp_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                unix_timestamp = int(timestamp_dt.timestamp())
            else:
                # Fallback to created_at
                created_at_dt = datetime.fromisoformat(last_item['created_at'].replace('Z', '+00:00'))
                unix_timestamp = int(created_at_dt.timestamp())
        except Exception:
            # Fallback to current timestamp
            unix_timestamp = int(now.timestamp())
        
        next_cursor = generate_cursor(unix_timestamp, last_item['id'])
    
    return items, next_cursor


def update_event_lease(
    tenant_id: str,
    event_id: str,
    lease_duration_minutes: int = None
) -> bool:
    """
    Update event lease (in_flight_until and increment attempt_count).
    
    Args:
        tenant_id: Tenant identifier
        event_id: Event identifier
        lease_duration_minutes: Lease duration in minutes (defaults to LEASE_DURATION_MINUTES)
        
    Returns:
        True if update successful, False otherwise
    """
    if lease_duration_minutes is None:
        lease_duration_minutes = LEASE_DURATION_MINUTES
    
    pk = f"TENANT#{tenant_id}"
    now = datetime.now(timezone.utc)
    lease_expiry = (now + timedelta(minutes=lease_duration_minutes)).isoformat()
    
    # Find event first (filter client-side)
    response = get_events_table().query(
        KeyConditionExpression='pk = :pk',
        ExpressionAttributeValues={
            ':pk': pk
        }
    )
    
    # Filter by event_id client-side
    items = [item for item in response.get('Items', []) if item.get('id') == event_id]
    if not items:
        return False
    
    item = items[0]
    current_attempt_count = item.get('attempt_count', 0)
    
    try:
        get_events_table().update_item(
            Key={
                'pk': pk,
                'sk': item['sk']
            },
            UpdateExpression='SET in_flight_until = :lease, attempt_count = :count',
            ExpressionAttributeValues={
                ':lease': lease_expiry,
                ':count': current_attempt_count + 1
            }
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update lease for event {event_id}: {e}")
        return False


def acknowledge_events(
    tenant_id: str,
    event_ids: List[str]
) -> Dict[str, Any]:
    """
    Batch update events to acknowledged status, clear leases.
    
    Args:
        tenant_id: Tenant identifier
        event_ids: List of event IDs to acknowledge
        
    Returns:
        Dictionary with 'acknowledged' and 'failed' arrays
    """
    pk = f"TENANT#{tenant_id}"
    acknowledged = []
    failed = []
    
    for event_id in event_ids:
        try:
            # Find event by scanning partition and filtering client-side
            # (FilterExpression on non-key attributes can be unreliable in some DynamoDB implementations)
            response = get_events_table().query(
                KeyConditionExpression='pk = :pk',
                ExpressionAttributeValues={
                    ':pk': pk
                }
            )
            
            # Filter by event_id client-side
            items = [item for item in response.get('Items', []) if item.get('id') == event_id]
            
            if not items:
                failed.append({
                    'event_id': event_id,
                    'error': 'Event not found'
                })
                continue
            
            item = items[0]
            
            # Validate event belongs to tenant
            if item.get('tenant_id') != tenant_id:
                failed.append({
                    'event_id': event_id,
                    'error': 'Event does not belong to tenant'
                })
                continue
            
            # Update status to acknowledged and clear lease
            # Note: status is a reserved keyword, so we use ExpressionAttributeNames
            get_events_table().update_item(
                Key={
                    'pk': pk,
                    'sk': item['sk']
                },
                UpdateExpression='SET #status = :status REMOVE in_flight_until',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': 'acknowledged'
                }
            )
            
            acknowledged.append(event_id)
        except Exception as e:
            logger.error(f"Failed to acknowledge event {event_id}: {e}")
            failed.append({
                'event_id': event_id,
                'error': str(e)
            })
    
    return {
        'acknowledged': acknowledged,
        'failed': failed
    }

