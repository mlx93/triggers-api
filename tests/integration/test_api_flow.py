"""
Integration tests for Zapier Triggers API end-to-end flows.

Tests complete API workflows including:
- End-to-end event lifecycle (ingest → retrieve → ack)
- Multi-tenant isolation
- Large payload handling (S3 storage)
- Lease expiry mechanism
- Idempotency enforcement
- Cursor pagination
- Error handling scenarios

Uses moto to mock AWS services for isolated, repeatable tests.
"""
import os
import json
import pytest
import boto3
import hashlib
import time
from moto import mock_aws
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from src.handlers.ingest import lambda_handler as ingest_handler
from src.handlers.inbox import lambda_handler as inbox_handler
from src.handlers.ack import lambda_handler as ack_handler
from src.lib.storage import generate_event_id


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
def api_keys_table_name():
    """Get API keys table name."""
    return "zapier-triggers-api-keys-test"


@pytest.fixture
def api_key_tenant_a():
    """Generate API key for tenant A."""
    return "ak_" + "a" * 32


@pytest.fixture
def api_key_tenant_b():
    """Generate API key for tenant B."""
    return "ak_" + "b" * 32


@pytest.fixture
def tenant_id_a():
    """Generate tenant ID for tenant A."""
    return "tenant_550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def tenant_id_b():
    """Generate tenant ID for tenant B."""
    return "tenant_660e8400-e29b-41d4-a716-446655440001"


@pytest.fixture
def mock_infrastructure(events_table_name, events_bucket_name, api_keys_table_name,
                       api_key_tenant_a, api_key_tenant_b, tenant_id_a, tenant_id_b):
    """Set up mock AWS infrastructure."""
    with mock_aws():
        # Set environment variables
        os.environ['EVENTS_TABLE'] = events_table_name
        os.environ['EVENTS_BUCKET'] = events_bucket_name
        os.environ['API_KEYS_TABLE'] = api_keys_table_name
        os.environ['ENVIRONMENT'] = 'test'
        os.environ['LOG_LEVEL'] = 'INFO'
        os.environ['LEASE_DURATION_MINUTES'] = '5'
        os.environ['SIZE_THRESHOLD_BYTES'] = '400000'
        
        # Create DynamoDB tables
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        
        # Events table
        dynamodb.create_table(
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
        
        # API keys table
        dynamodb.create_table(
            TableName=api_keys_table_name,
            KeySchema=[
                {'AttributeName': 'hashed_key', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'hashed_key', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create S3 bucket
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=events_bucket_name)
        
        # Create API key records
        hashed_key_a = hashlib.sha256(api_key_tenant_a.encode()).hexdigest()
        hashed_key_b = hashlib.sha256(api_key_tenant_b.encode()).hexdigest()
        
        dynamodb.put_item(
            TableName=api_keys_table_name,
            Item={
                'hashed_key': {'S': hashed_key_a},
                'tenant_id': {'S': tenant_id_a},
                'is_active': {'BOOL': True},
                'created_at': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        
        dynamodb.put_item(
            TableName=api_keys_table_name,
            Item={
                'hashed_key': {'S': hashed_key_b},
                'tenant_id': {'S': tenant_id_b},
                'is_active': {'BOOL': True},
                'created_at': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        
        yield {
            'events_table': events_table_name,
            'events_bucket': events_bucket_name,
            'api_keys_table': api_keys_table_name,
            'api_key_a': api_key_tenant_a,
            'api_key_b': api_key_tenant_b,
            'tenant_id_a': tenant_id_a,
            'tenant_id_b': tenant_id_b
        }


def create_lambda_event(method, path, body=None, headers=None, query_params=None):
    """Create a Lambda event dictionary for API Gateway."""
    query_params = query_params or {}
    event = {
        'requestContext': {
            'http': {
                'method': method,
                'path': path
            }
        },
        'headers': headers or {},
        'rawPath': path,
        'rawQueryString': '&'.join([f'{k}={v}' for k, v in query_params.items()]),
        'queryStringParameters': query_params if query_params else None,
        'isBase64Encoded': False
    }
    
    if body:
        event['body'] = json.dumps(body) if isinstance(body, dict) else body
    
    return event


class TestEndToEndFlow:
    """Test complete event lifecycle: ingest → retrieve → ack."""
    
    def test_complete_event_lifecycle(self, mock_infrastructure):
        """Test complete flow: ingest event → retrieve from inbox → acknowledge."""
        infra = mock_infrastructure
        
        # Step 1: Ingest event
        event_data = {
            'event_type': 'user.account.created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': '12345',
                'email': 'user@example.com'
            }
        }
        
        ingest_event = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response = ingest_handler(ingest_event, None)
        assert ingest_response['statusCode'] == 201
        
        ingest_body = json.loads(ingest_response['body'])
        event_id = ingest_body['id']
        assert event_id.startswith('evt_')
        assert ingest_body['status'] == 'accepted'
        
        # Step 2: Retrieve from inbox
        inbox_event = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']},
            query_params={'limit': '25'}
        )
        
        inbox_response = inbox_handler(inbox_event, None)
        assert inbox_response['statusCode'] == 200
        
        inbox_body = json.loads(inbox_response['body'])
        assert len(inbox_body['events']) == 1
        assert inbox_body['events'][0]['id'] == event_id
        assert inbox_body['events'][0]['event_type'] == 'user.account.created'
        assert inbox_body['events'][0]['attempt_count'] == 1  # Lease updated
        
        # Step 3: Acknowledge event
        ack_event = create_lambda_event(
            'POST',
            '/inbox/ack',
            body={'event_ids': [event_id]},
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ack_response = ack_handler(ack_event, None)
        assert ack_response['statusCode'] == 200
        
        ack_body = json.loads(ack_response['body'])
        assert event_id in ack_body['acknowledged']
        assert len(ack_body['failed']) == 0
        
        # Step 4: Verify event no longer in inbox
        inbox_response2 = inbox_handler(inbox_event, None)
        assert inbox_response2['statusCode'] == 200
        
        inbox_body2 = json.loads(inbox_response2['body'])
        assert len(inbox_body2['events']) == 0  # Event acknowledged, not returned


class TestMultiTenantIsolation:
    """Test tenant isolation - tenant A cannot access tenant B's events."""
    
    def test_tenant_isolation(self, mock_infrastructure):
        """Test that tenant A cannot see tenant B's events."""
        infra = mock_infrastructure
        
        # Tenant A ingests event
        event_data_a = {
            'event_type': 'user.account.created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {'user_id': 'tenant_a_user'}
        }
        
        ingest_event_a = create_lambda_event(
            'POST',
            '/events',
            body=event_data_a,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response_a = ingest_handler(ingest_event_a, None)
        assert ingest_response_a['statusCode'] == 201
        event_id_a = json.loads(ingest_response_a['body'])['id']
        
        # Tenant B ingests event
        event_data_b = {
            'event_type': 'user.account.created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {'user_id': 'tenant_b_user'}
        }
        
        ingest_event_b = create_lambda_event(
            'POST',
            '/events',
            body=event_data_b,
            headers={'X-API-Key': infra['api_key_b']}
        )
        
        ingest_response_b = ingest_handler(ingest_event_b, None)
        assert ingest_response_b['statusCode'] == 201
        event_id_b = json.loads(ingest_response_b['body'])['id']
        
        # Tenant A retrieves inbox - should only see their own event
        inbox_event_a = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        inbox_response_a = inbox_handler(inbox_event_a, None)
        assert inbox_response_a['statusCode'] == 200
        
        inbox_body_a = json.loads(inbox_response_a['body'])
        assert len(inbox_body_a['events']) == 1
        assert inbox_body_a['events'][0]['id'] == event_id_a
        assert event_id_b not in [e['id'] for e in inbox_body_a['events']]
        
        # Tenant B retrieves inbox - should only see their own event
        inbox_event_b = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_b']}
        )
        
        inbox_response_b = inbox_handler(inbox_event_b, None)
        assert inbox_response_b['statusCode'] == 200
        
        inbox_body_b = json.loads(inbox_response_b['body'])
        assert len(inbox_body_b['events']) == 1
        assert inbox_body_b['events'][0]['id'] == event_id_b
        assert event_id_a not in [e['id'] for e in inbox_body_b['events']]
        
        # Tenant A cannot acknowledge tenant B's event
        ack_event_a = create_lambda_event(
            'POST',
            '/inbox/ack',
            body={'event_ids': [event_id_b]},  # Trying to ack tenant B's event
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ack_response_a = ack_handler(ack_event_a, None)
        assert ack_response_a['statusCode'] == 200
        
        ack_body_a = json.loads(ack_response_a['body'])
        assert event_id_b in [f['event_id'] for f in ack_body_a['failed']]  # Should fail
        assert len(ack_body_a['acknowledged']) == 0


class TestLargePayloadS3Storage:
    """Test S3 storage for large payloads (≥400KB)."""
    
    def test_large_payload_stored_in_s3(self, mock_infrastructure):
        """Test that payloads ≥400KB are stored in S3."""
        infra = mock_infrastructure
        
        # Create large payload (400KB+)
        large_data = {'data': 'x' * 400000}  # 400KB of data
        
        event_data = {
            'event_type': 'data.large.event',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': large_data
        }
        
        ingest_event = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response = ingest_handler(ingest_event, None)
        assert ingest_response['statusCode'] == 201
        
        event_id = json.loads(ingest_response['body'])['id']
        
        # Retrieve event and verify data is correct
        inbox_event = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        inbox_response = inbox_handler(inbox_event, None)
        assert inbox_response['statusCode'] == 200
        
        inbox_body = json.loads(inbox_response['body'])
        assert len(inbox_body['events']) == 1
        retrieved_event = inbox_body['events'][0]
        assert retrieved_event['id'] == event_id
        assert 'data' in retrieved_event
        assert len(retrieved_event['data']['data']) == 400000  # Data retrieved correctly


class TestLeaseExpiry:
    """Test lease expiry mechanism - events reappear after 5 minutes."""
    
    def test_lease_expiry(self, mock_infrastructure, monkeypatch):
        """Test that events reappear in inbox after lease expires."""
        infra = mock_infrastructure
        
        # Ingest event
        event_data = {
            'event_type': 'user.account.created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {'user_id': '12345'}
        }
        
        ingest_event = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response = ingest_handler(ingest_event, None)
        event_id = json.loads(ingest_response['body'])['id']
        
        # Retrieve event (sets lease)
        inbox_event = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        inbox_response = inbox_handler(inbox_event, None)
        assert inbox_response['statusCode'] == 200
        inbox_body = json.loads(inbox_response['body'])
        assert len(inbox_body['events']) == 1
        
        # Retrieve again immediately - should not see event (lease active)
        inbox_response2 = inbox_handler(inbox_event, None)
        assert inbox_response2['statusCode'] == 200
        inbox_body2 = json.loads(inbox_response2['body'])
        assert len(inbox_body2['events']) == 0  # Event leased, not returned
        
        # Mock time to be 6 minutes in the future (lease expired)
        future_time = datetime.now(timezone.utc) + timedelta(minutes=6)
        
        # We need to patch the time in storage module
        # For this test, we'll manually update the lease in DynamoDB to simulate expiry
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        
        # Query to find the event
        response = dynamodb.query(
            TableName=infra['events_table'],
            KeyConditionExpression='pk = :pk',
            ExpressionAttributeValues={
                ':pk': {'S': f"TENANT#{infra['tenant_id_a']}"}
            }
        )
        
        # Update lease to expired time
        for item in response['Items']:
            if item.get('id', {}).get('S') == event_id:
                dynamodb.update_item(
                    TableName=infra['events_table'],
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    },
                    UpdateExpression='SET #in_flight = :expired',
                    ExpressionAttributeNames={'#in_flight': 'in_flight_until'},
                    ExpressionAttributeValues={
                        ':expired': {'S': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}
                    }
                )
                break
        
        # Retrieve again - event should reappear (lease expired)
        inbox_response3 = inbox_handler(inbox_event, None)
        assert inbox_response3['statusCode'] == 200
        inbox_body3 = json.loads(inbox_response3['body'])
        assert len(inbox_body3['events']) == 1  # Event reappeared
        assert inbox_body3['events'][0]['id'] == event_id


class TestIdempotency:
    """Test idempotency enforcement - duplicate event_id returns 409."""
    
    def test_duplicate_event_id_returns_409(self, mock_infrastructure):
        """Test that duplicate event_id returns 409 Conflict."""
        infra = mock_infrastructure
        
        event_id = generate_event_id()  # Generate valid event ID
        
        event_data = {
            'id': event_id,
            'event_type': 'user.account.created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {'user_id': '12345'}
        }
        
        # First ingestion - should succeed
        ingest_event1 = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response1 = ingest_handler(ingest_event1, None)
        assert ingest_response1['statusCode'] == 201
        
        # Second ingestion with same event_id - should return 409
        ingest_event2 = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response2 = ingest_handler(ingest_event2, None)
        assert ingest_response2['statusCode'] == 409
        
        error_body = json.loads(ingest_response2['body'])
        assert error_body['error']['code'] == 'CONFLICT'
        assert 'already exists' in error_body['error']['message'].lower()


class TestCursorPagination:
    """Test cursor-based pagination."""
    
    def test_cursor_pagination(self, mock_infrastructure):
        """Test pagination with cursor."""
        infra = mock_infrastructure
        
        # Ingest multiple events
        event_ids = []
        for i in range(5):
            event_data = {
                'event_type': 'user.account.created',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data': {'user_id': f'user_{i}'}
            }
            
            ingest_event = create_lambda_event(
                'POST',
                '/events',
                body=event_data,
                headers={'X-API-Key': infra['api_key_a']}
            )
            
            ingest_response = ingest_handler(ingest_event, None)
            event_ids.append(json.loads(ingest_response['body'])['id'])
            time.sleep(0.1)  # Ensure different timestamps
        
        # Retrieve first page (limit 2)
        inbox_event1 = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']},
            query_params={'limit': '2'}
        )
        
        inbox_response1 = inbox_handler(inbox_event1, None)
        assert inbox_response1['statusCode'] == 200
        
        inbox_body1 = json.loads(inbox_response1['body'])
        assert len(inbox_body1['events']) == 2
        assert inbox_body1['pagination']['has_more'] is True
        assert inbox_body1['pagination']['next_cursor'] is not None
        
        # Retrieve second page using cursor
        cursor = inbox_body1['pagination']['next_cursor']
        inbox_event2 = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']},
            query_params={'limit': '2', 'cursor': cursor}
        )
        
        inbox_response2 = inbox_handler(inbox_event2, None)
        assert inbox_response2['statusCode'] == 200
        
        inbox_body2 = json.loads(inbox_response2['body'])
        assert len(inbox_body2['events']) >= 1  # At least 1 more event
        
        # Verify no duplicate events across pages
        page1_ids = {e['id'] for e in inbox_body1['events']}
        page2_ids = {e['id'] for e in inbox_body2['events']}
        assert len(page1_ids & page2_ids) == 0  # No duplicates
    
    def test_expired_cursor_returns_400(self, mock_infrastructure):
        """Test that expired cursor (24+ hours old) returns 400."""
        infra = mock_infrastructure
        
        # Create expired cursor (25 hours ago) with valid event ID format
        expired_timestamp = int((datetime.now(timezone.utc) - timedelta(hours=25)).timestamp())
        valid_event_id = generate_event_id()
        expired_cursor = f"{expired_timestamp}_{valid_event_id}"
        
        inbox_event = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']},
            query_params={'cursor': expired_cursor}
        )
        
        inbox_response = inbox_handler(inbox_event, None)
        assert inbox_response['statusCode'] == 400
        
        error_body = json.loads(inbox_response['body'])
        assert error_body['error']['code'] == 'VALIDATION_ERROR'
        assert 'expired' in error_body['error']['message'].lower() or 'invalid' in error_body['error']['message'].lower()


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_401_invalid_api_key(self, mock_infrastructure):
        """Test 401 for invalid API key."""
        infra = mock_infrastructure
        
        event_data = {
            'event_type': 'user.account.created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {'user_id': '12345'}
        }
        
        ingest_event = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': 'ak_invalid_key_12345678901234567890'}
        )
        
        ingest_response = ingest_handler(ingest_event, None)
        assert ingest_response['statusCode'] == 401
        
        error_body = json.loads(ingest_response['body'])
        assert error_body['error']['code'] == 'AUTHENTICATION_ERROR'
    
    def test_400_invalid_cursor(self, mock_infrastructure):
        """Test 400 for invalid cursor format."""
        infra = mock_infrastructure
        
        inbox_event = create_lambda_event(
            'GET',
            '/inbox',
            headers={'X-API-Key': infra['api_key_a']},
            query_params={'cursor': 'invalid_cursor_format'}
        )
        
        inbox_response = inbox_handler(inbox_event, None)
        assert inbox_response['statusCode'] == 400
        
        error_body = json.loads(inbox_response['body'])
        assert error_body['error']['code'] == 'VALIDATION_ERROR'
    
    def test_409_duplicate_event(self, mock_infrastructure):
        """Test 409 for duplicate event (already tested in TestIdempotency, but verify error format)."""
        infra = mock_infrastructure
        
        event_id = generate_event_id()  # Generate valid event ID
        event_data = {
            'id': event_id,
            'event_type': 'user.account.created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {'user_id': '12345'}
        }
        
        # First ingestion
        ingest_event1 = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        ingest_handler(ingest_event1, None)
        
        # Duplicate ingestion
        ingest_event2 = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response2 = ingest_handler(ingest_event2, None)
        assert ingest_response2['statusCode'] == 409
        
        error_body = json.loads(ingest_response2['body'])
        assert error_body['error']['code'] == 'CONFLICT'
    
    def test_413_payload_too_large(self, mock_infrastructure):
        """Test 413 for payload exceeding 10MB limit."""
        infra = mock_infrastructure
        
        # Create payload > 10MB
        large_data = {'data': 'x' * (11 * 1024 * 1024)}  # 11MB
        
        event_data = {
            'event_type': 'data.large.event',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': large_data
        }
        
        ingest_event = create_lambda_event(
            'POST',
            '/events',
            body=event_data,
            headers={'X-API-Key': infra['api_key_a']}
        )
        
        ingest_response = ingest_handler(ingest_event, None)
        assert ingest_response['statusCode'] == 413
        
        error_body = json.loads(ingest_response['body'])
        assert error_body['error']['code'] == 'VALIDATION_ERROR'
        assert '10MB' in error_body['error']['message'] or 'size' in error_body['error']['message'].lower()

