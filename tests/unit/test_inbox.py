"""
Unit tests for GET /inbox handler (inbox.py).

Tests event retrieval, filters, pagination, cursor validation, lease mechanism, and error handling.
Uses moto to mock AWS services.
"""
import os
import json
import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone, timedelta

from src.handlers.inbox import lambda_handler
from src.lib.auth import AuthenticationError
from src.lib.storage import store_event, generate_event_id


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
def api_key():
    """Generate a valid API key for testing."""
    return "ak_" + "a" * 32


@pytest.fixture
def tenant_id():
    """Generate a valid tenant ID for testing."""
    return "tenant_550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def mock_infrastructure(events_table_name, events_bucket_name, api_keys_table_name, api_key, tenant_id):
    """Create mocked AWS infrastructure."""
    with mock_aws():
        # Create DynamoDB tables
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Events table
        events_table = dynamodb.create_table(
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
        import hashlib
        hashed_key = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
        api_keys_table = dynamodb.create_table(
            TableName=api_keys_table_name,
            KeySchema=[
                {'AttributeName': 'hashed_key', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'hashed_key', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Add API key to table
        api_keys_table.put_item(
            Item={
                'hashed_key': hashed_key,
                'tenant_id': tenant_id,
                'is_active': True,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Create S3 bucket
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket=events_bucket_name)
        
        # Set environment variables
        os.environ['EVENTS_TABLE'] = events_table_name
        os.environ['EVENTS_BUCKET'] = events_bucket_name
        os.environ['API_KEYS_TABLE'] = api_keys_table_name
        
        yield {
            'events_table': events_table,
            'api_keys_table': api_keys_table,
            's3_client': s3_client,
            'api_key': api_key,
            'tenant_id': tenant_id
        }


@pytest.fixture
def sample_events(mock_infrastructure, tenant_id):
    """Create sample events for testing."""
    events = []
    for i in range(3):
        event_data = {
            'id': generate_event_id(),
            'event_type': 'player.projection.created',
            'timestamp': f'2025-11-11T15:30:{45+i}Z',
            'data': {'player_id': f'player{i}', 'score': 100 + i}
        }
        store_event(tenant_id, event_data, 1000)
        events.append(event_data)
    return events


@pytest.fixture
def lambda_event(api_key):
    """Create Lambda event dictionary."""
    return {
        'headers': {
            'x-api-key': api_key
        },
        'queryStringParameters': {}
    }


# Test successful retrieval
def test_inbox_success(mock_infrastructure, lambda_event, sample_events):
    """Test successful event retrieval."""
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'events' in body
    assert len(body['events']) > 0
    assert 'pagination' in body


def test_inbox_empty(mock_infrastructure, lambda_event):
    """Test retrieval with no events."""
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['events']) == 0


# Test filters
def test_inbox_filter_by_event_type(mock_infrastructure, lambda_event, tenant_id):
    """Test filtering by event_type."""
    # Create events with different types
    event1 = {
        'id': generate_event_id(),
        'event_type': 'player.projection.created',
        'timestamp': '2025-11-11T15:30:45Z',
        'data': {'test': 1}
    }
    event2 = {
        'id': generate_event_id(),
        'event_type': 'player.projection.updated',
        'timestamp': '2025-11-11T15:30:46Z',
        'data': {'test': 2}
    }
    store_event(tenant_id, event1, 1000)
    store_event(tenant_id, event2, 1000)
    
    lambda_event['queryStringParameters'] = {'event_type': 'player.projection.created'}
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['events']) == 1
    assert body['events'][0]['event_type'] == 'player.projection.created'


def test_inbox_filter_by_timestamp_range(mock_infrastructure, lambda_event, tenant_id):
    """Test filtering by timestamp range."""
    event1 = {
        'id': generate_event_id(),
        'event_type': 'player.projection.created',
        'timestamp': '2025-11-11T15:30:45Z',
        'data': {'test': 1}
    }
    store_event(tenant_id, event1, 1000)
    
    lambda_event['queryStringParameters'] = {
        'after': '2025-11-11T15:30:44Z',
        'before': '2025-11-11T15:30:46Z'
    }
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['events']) >= 1


# Test pagination
def test_inbox_pagination(mock_infrastructure, lambda_event, tenant_id):
    """Test pagination with limit."""
    # Create multiple events
    for i in range(5):
        event_data = {
            'id': generate_event_id(),
            'event_type': 'player.projection.created',
            'timestamp': f'2025-11-11T15:30:{45+i}Z',
            'data': {'index': i}
        }
        store_event(tenant_id, event_data, 1000)
    
    lambda_event['queryStringParameters'] = {'limit': '2'}
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['events']) == 2
    assert body['pagination']['has_more'] is True


# Test cursor validation
def test_inbox_valid_cursor(mock_infrastructure, lambda_event, sample_events):
    """Test valid cursor."""
    # Get first page
    response1 = lambda_handler(lambda_event, None)
    body1 = json.loads(response1['body'])
    
    if body1['pagination'].get('next_cursor'):
        lambda_event['queryStringParameters'] = {'cursor': body1['pagination']['next_cursor']}
        response2 = lambda_handler(lambda_event, None)
        
        assert response2['statusCode'] == 200


def test_inbox_expired_cursor(mock_infrastructure, lambda_event):
    """Test expired cursor returns 400."""
    # Create cursor 25 hours ago
    old_timestamp = int((datetime.now(timezone.utc) - timedelta(hours=25)).timestamp())
    expired_cursor = f"{old_timestamp}_evt_abc123"
    
    lambda_event['queryStringParameters'] = {'cursor': expired_cursor}
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'


def test_inbox_invalid_cursor_format(mock_infrastructure, lambda_event):
    """Test invalid cursor format returns 400."""
    lambda_event['queryStringParameters'] = {'cursor': 'invalid_cursor'}
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'


# Test lease mechanism
def test_inbox_lease_exclusion(mock_infrastructure, lambda_event, tenant_id):
    """Test that events with active leases are excluded."""
    event_data = {
        'id': generate_event_id(),
        'event_type': 'player.projection.created',
        'timestamp': '2025-11-11T15:30:45Z',
        'data': {'test': 1}
    }
    store_event(tenant_id, event_data, 1000)
    
    # First query should return event and set lease
    response1 = lambda_handler(lambda_event, None)
    body1 = json.loads(response1['body'])
    assert len(body1['events']) == 1
    
    # Second query immediately should exclude event (active lease)
    response2 = lambda_handler(lambda_event, None)
    body2 = json.loads(response2['body'])
    assert len(body2['events']) == 0


# Test authentication errors
def test_inbox_missing_api_key(mock_infrastructure, lambda_event):
    """Test 401 error for missing API key."""
    del lambda_event['headers']['x-api-key']
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 401
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'AUTHENTICATION_ERROR'


def test_inbox_invalid_api_key(mock_infrastructure, lambda_event):
    """Test 401 error for invalid API key."""
    lambda_event['headers']['x-api-key'] = 'ak_invalid_key_12345'
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 401
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'AUTHENTICATION_ERROR'


# Test validation errors
def test_inbox_invalid_limit(mock_infrastructure, lambda_event):
    """Test validation error for invalid limit."""
    lambda_event['queryStringParameters'] = {'limit': '200'}  # Max is 100
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'


def test_inbox_invalid_timestamp_filter(mock_infrastructure, lambda_event):
    """Test validation error for invalid timestamp filter."""
    lambda_event['queryStringParameters'] = {'after': 'invalid-timestamp'}
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'

