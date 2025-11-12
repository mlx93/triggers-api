"""
Unit tests for storage operations module.

Tests DynamoDB/S3 operations, lease management, cursor generation/parsing, and idempotency.
Uses moto to mock DynamoDB and S3.
"""
import os
import json
import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

from src.lib.storage import (
    generate_event_id,
    generate_cursor,
    parse_cursor,
    check_idempotency,
    put_large_payload,
    get_large_payload,
    store_event,
    get_event,
    query_events,
    update_event_lease,
    acknowledge_events
)


def create_test_event_id(suffix: str = "") -> str:
    """Create a valid test event ID in format evt_{base64url_32chars}."""
    import secrets
    if suffix:
        # Use suffix to make IDs predictable but still valid format
        random_part = secrets.token_urlsafe(24)[:32-len(suffix)]
        return f"evt_{random_part}{suffix}"
    else:
        return generate_event_id()


# Test fixtures
@pytest.fixture
def events_table_name():
    """Get events table name."""
    return "zapier-triggers-events-test"


@pytest.fixture
def events_bucket_name():
    """Get events bucket name."""
    return "zapier-triggers-events-test-bucket"


@pytest.fixture
def tenant_id():
    """Generate a valid tenant ID for testing."""
    return "tenant_550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def event_id():
    """Generate a valid event ID for testing."""
    return "evt_abc123xyz789def456uvw012rst345"


@pytest.fixture
def mock_dynamodb_table(events_table_name):
    """Create a mocked DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName=events_table_name,
            KeySchema=[
                {'AttributeName': 'pk', 'KeyType': 'HASH'},
                {'AttributeName': 'sk', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'pk', 'AttributeType': 'S'},
                {'AttributeName': 'sk', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        os.environ['EVENTS_TABLE'] = events_table_name
        yield table


@pytest.fixture
def mock_s3_bucket(events_bucket_name):
    """Create a mocked S3 bucket."""
    with mock_aws():
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket=events_bucket_name)
        os.environ['EVENTS_BUCKET'] = events_bucket_name
        yield s3_client


@pytest.fixture
def sample_event_data(event_id):
    """Create sample event data."""
    return {
        'id': event_id,
        'event_type': 'player.projection.created',
        'timestamp': '2025-11-11T15:30:45Z',
        'data': {'player_id': '12345', 'score': 100}
    }


# Test generate_event_id
def test_generate_event_id():
    """Test event ID generation."""
    event_id = generate_event_id()
    assert event_id.startswith('evt_')
    assert len(event_id) == 36  # evt_ + 32 chars


# Test generate_cursor
def test_generate_cursor():
    """Test cursor generation."""
    timestamp = 1699712345
    event_id = "evt_abc123"
    cursor = generate_cursor(timestamp, event_id)
    assert cursor == "1699712345_evt_abc123"


# Test parse_cursor
def test_parse_cursor_valid():
    """Test parsing valid cursor."""
    now = datetime.now(timezone.utc)
    timestamp = int(now.timestamp())
    event_id = "evt_abc123"
    cursor = generate_cursor(timestamp, event_id)
    
    result = parse_cursor(cursor)
    assert result['timestamp'] == timestamp
    assert result['event_id'] == event_id


def test_parse_cursor_expired():
    """Test parsing expired cursor."""
    # Create cursor 25 hours ago
    old_timestamp = int((datetime.now(timezone.utc) - timedelta(hours=25)).timestamp())
    event_id = "evt_abc123"
    cursor = generate_cursor(old_timestamp, event_id)
    
    with pytest.raises(ValueError, match="expired"):
        parse_cursor(cursor)


def test_parse_cursor_invalid_format():
    """Test parsing invalid cursor format."""
    with pytest.raises(ValueError, match="Invalid cursor format"):
        parse_cursor("invalid_cursor")


def test_parse_cursor_future_timestamp():
    """Test parsing cursor with future timestamp."""
    future_timestamp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    event_id = "evt_abc123"
    cursor = generate_cursor(future_timestamp, event_id)
    
    with pytest.raises(ValueError, match="future"):
        parse_cursor(cursor)


# Test S3 operations
def test_put_large_payload(mock_s3_bucket, events_bucket_name):
    """Test S3 payload storage."""
    key = "events/tenant_123/evt_abc.json"
    payload = {'test': 'data', 'value': 123}
    
    result = put_large_payload(events_bucket_name, key, payload)
    assert result == key
    
    # Verify object exists
    s3_client = boto3.client('s3', region_name='us-east-1')
    response = s3_client.get_object(Bucket=events_bucket_name, Key=key)
    data = json.loads(response['Body'].read().decode('utf-8'))
    assert data == payload


def test_get_large_payload(mock_s3_bucket, events_bucket_name):
    """Test S3 payload retrieval."""
    key = "events/tenant_123/evt_abc.json"
    payload = {'test': 'data', 'value': 123}
    
    # Store payload first
    s3_client = boto3.client('s3', region_name='us-east-1')
    s3_client.put_object(
        Bucket=events_bucket_name,
        Key=key,
        Body=json.dumps(payload).encode('utf-8')
    )
    
    # Retrieve payload
    result = get_large_payload(events_bucket_name, key)
    assert result == payload


# Test store_event
def test_store_event_small_payload(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test storing small payload in DynamoDB."""
    payload_size = 1000  # < 400KB
    
    result = store_event(tenant_id, sample_event_data, payload_size)
    
    assert result['event_id'] == sample_event_data['id']
    assert result['storage_type'] == 'dynamodb'
    assert result['s3_key'] is None
    
    # Verify event in DynamoDB
    pk = f"TENANT#{tenant_id}"
    sk = f"EVENT#{sample_event_data['id']}#{sample_event_data['timestamp']}"
    
    response = mock_dynamodb_table.get_item(Key={'pk': pk, 'sk': sk})
    assert 'Item' in response
    item = response['Item']
    assert item['id'] == sample_event_data['id']
    assert item['data'] == sample_event_data['data']
    assert item['s3_key'] is None


def test_store_event_large_payload(mock_dynamodb_table, mock_s3_bucket, tenant_id, sample_event_data, events_bucket_name):
    """Test storing large payload in S3."""
    payload_size = 500000  # >= 400KB
    
    result = store_event(tenant_id, sample_event_data, payload_size)
    
    assert result['event_id'] == sample_event_data['id']
    assert result['storage_type'] == 's3'
    assert result['s3_key'] is not None
    
    # Verify S3 object exists
    s3_client = boto3.client('s3', region_name='us-east-1')
    response = s3_client.get_object(Bucket=events_bucket_name, Key=result['s3_key'])
    data = json.loads(response['Body'].read().decode('utf-8'))
    assert data == sample_event_data['data']
    
    # Verify DynamoDB item has s3_key
    pk = f"TENANT#{tenant_id}"
    sk = f"EVENT#{sample_event_data['id']}#{sample_event_data['timestamp']}"
    
    db_response = mock_dynamodb_table.get_item(Key={'pk': pk, 'sk': sk})
    assert 'Item' in db_response
    item = db_response['Item']
    assert item['s3_key'] == result['s3_key']
    assert item.get('data') is None


def test_store_event_idempotency(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test idempotency - duplicate event_id should fail."""
    payload_size = 1000
    
    # Store event first time
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Try to store again - should raise ConditionalCheckFailedException
    with pytest.raises(ClientError) as exc_info:
        store_event(tenant_id, sample_event_data, payload_size)
    
    assert exc_info.value.response['Error']['Code'] == 'ConditionalCheckFailedException'


def test_store_event_s3_fallback(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test S3 failure fallback to DynamoDB."""
    payload_size = 500000  # >= 400KB
    
    # Don't create S3 bucket - should fallback to DynamoDB
    os.environ.pop('EVENTS_BUCKET', None)
    
    # Should still succeed (fallback to DynamoDB)
    result = store_event(tenant_id, sample_event_data, payload_size)
    
    assert result['event_id'] == sample_event_data['id']
    assert result['storage_type'] == 'dynamodb'  # Fallback
    assert result['s3_key'] is None


# Test get_event
def test_get_event(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test retrieving event from DynamoDB."""
    payload_size = 1000
    
    # Store event first
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Retrieve event
    result = get_event(tenant_id, sample_event_data['id'])
    
    assert result is not None
    assert result['id'] == sample_event_data['id']
    assert result['data'] == sample_event_data['data']


def test_get_event_with_s3(mock_dynamodb_table, mock_s3_bucket, tenant_id, sample_event_data, events_bucket_name):
    """Test retrieving event with S3 payload."""
    payload_size = 500000
    
    # Store event in S3
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Retrieve event
    result = get_event(tenant_id, sample_event_data['id'])
    
    assert result is not None
    assert result['id'] == sample_event_data['id']
    assert result['data'] == sample_event_data['data']


def test_get_event_not_found(mock_dynamodb_table, tenant_id):
    """Test retrieving non-existent event."""
    result = get_event(tenant_id, "evt_nonexistent")
    assert result is None


# Test query_events
def test_query_events_basic(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test basic event query."""
    payload_size = 1000
    
    # Store event
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Query events
    events, next_cursor = query_events(tenant_id, filters=None, cursor=None, limit=25)
    
    assert len(events) == 1
    assert events[0]['id'] == sample_event_data['id']
    assert next_cursor is None  # Only one event


def test_query_events_with_filters(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test query with event_type filter."""
    payload_size = 1000
    
    # Store event
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Query with event_type filter
    filters = {'event_type': 'player.projection.created'}
    events, _ = query_events(tenant_id, filters=filters, cursor=None, limit=25)
    
    assert len(events) == 1
    
    # Query with wrong event_type filter
    filters = {'event_type': 'wrong.type'}
    events, _ = query_events(tenant_id, filters=filters, cursor=None, limit=25)
    
    assert len(events) == 0


def test_query_events_lease_exclusion(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test that events with active leases are excluded."""
    payload_size = 1000
    
    # Store event
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Query events (should set lease)
    events1, _ = query_events(tenant_id, filters=None, cursor=None, limit=25)
    assert len(events1) == 1
    
    # Query again immediately (should exclude due to active lease)
    events2, _ = query_events(tenant_id, filters=None, cursor=None, limit=25)
    assert len(events2) == 0  # Excluded by lease


def test_query_events_pagination(mock_dynamodb_table, tenant_id):
    """Test pagination with cursor."""
    payload_size = 1000
    
    # Store multiple events
    for i in range(5):
        event_data = {
            'id': create_test_event_id(f"{i:02d}"),
            'event_type': 'test.event',
            'timestamp': f'2025-11-11T15:30:{45+i}Z',
            'data': {'index': i}
        }
        store_event(tenant_id, event_data, payload_size)
    
    # Query with limit
    events, next_cursor = query_events(tenant_id, filters=None, cursor=None, limit=2)
    
    assert len(events) == 2
    assert next_cursor is not None


# Test update_event_lease
def test_update_event_lease(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test updating event lease."""
    payload_size = 1000
    
    # Store event
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Update lease
    result = update_event_lease(tenant_id, sample_event_data['id'], lease_duration_minutes=5)
    
    assert result is True
    
    # Verify lease was updated
    event = get_event(tenant_id, sample_event_data['id'])
    assert event['in_flight_until'] is not None
    assert event['attempt_count'] == 1


def test_update_event_lease_not_found(mock_dynamodb_table, tenant_id):
    """Test updating lease for non-existent event."""
    result = update_event_lease(tenant_id, "evt_nonexistent")
    assert result is False


# Test acknowledge_events
def test_acknowledge_events_success(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test successful event acknowledgment."""
    payload_size = 1000
    
    # Store event
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Acknowledge event
    result = acknowledge_events(tenant_id, [sample_event_data['id']])
    
    assert len(result['acknowledged']) == 1
    assert result['acknowledged'][0] == sample_event_data['id']
    assert len(result['failed']) == 0
    
    # Verify status updated
    event = get_event(tenant_id, sample_event_data['id'])
    assert event['status'] == 'acknowledged'
    assert event.get('in_flight_until') is None


def test_acknowledge_events_idempotent(mock_dynamodb_table, tenant_id, sample_event_data):
    """Test idempotent acknowledgment."""
    payload_size = 1000
    
    # Store event
    store_event(tenant_id, sample_event_data, payload_size)
    
    # Acknowledge twice
    result1 = acknowledge_events(tenant_id, [sample_event_data['id']])
    result2 = acknowledge_events(tenant_id, [sample_event_data['id']])
    
    # Both should succeed (idempotent)
    assert len(result1['acknowledged']) == 1
    assert len(result2['acknowledged']) == 1


def test_acknowledge_events_not_found(mock_dynamodb_table, tenant_id):
    """Test acknowledging non-existent event."""
    result = acknowledge_events(tenant_id, ["evt_nonexistent"])
    
    assert len(result['acknowledged']) == 0
    assert len(result['failed']) == 1
    assert result['failed'][0]['event_id'] == "evt_nonexistent"


def test_acknowledge_events_batch(mock_dynamodb_table, tenant_id):
    """Test batch acknowledgment."""
    payload_size = 1000
    
    # Store multiple events
    event_ids = []
    for i in range(3):
        event_data = {
            'id': create_test_event_id(f"{i:02d}"),
            'event_type': 'test.event',
            'timestamp': f'2025-11-11T15:30:{45+i}Z',
            'data': {'index': i}
        }
        store_event(tenant_id, event_data, payload_size)
        event_ids.append(event_data['id'])
    
    # Acknowledge batch
    result = acknowledge_events(tenant_id, event_ids)
    
    assert len(result['acknowledged']) == 3
    assert len(result['failed']) == 0

