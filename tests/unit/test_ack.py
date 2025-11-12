"""
Unit tests for POST /inbox/ack handler (ack.py).

Tests batch acknowledgment, idempotency, tenant isolation, validation, and error handling.
Uses moto to mock AWS services.
"""
import os
import json
import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone

from src.handlers.ack import lambda_handler
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
        'body': json.dumps({
            'event_ids': []
        })
    }


# Test successful acknowledgment
def test_ack_success_single(mock_infrastructure, lambda_event, sample_events):
    """Test successful acknowledgment of single event."""
    lambda_event['body'] = json.dumps({
        'event_ids': [sample_events[0]['id']]
    })
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['acknowledged']) == 1
    assert body['acknowledged'][0] == sample_events[0]['id']
    assert len(body['failed']) == 0


def test_ack_success_batch(mock_infrastructure, lambda_event, sample_events):
    """Test successful batch acknowledgment."""
    event_ids = [event['id'] for event in sample_events]
    lambda_event['body'] = json.dumps({
        'event_ids': event_ids
    })
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['acknowledged']) == 3
    assert len(body['failed']) == 0


# Test idempotency
def test_ack_idempotent(mock_infrastructure, lambda_event, sample_events):
    """Test idempotent acknowledgment (safe to acknowledge twice)."""
    event_id = sample_events[0]['id']
    lambda_event['body'] = json.dumps({
        'event_ids': [event_id]
    })
    
    # First acknowledgment
    response1 = lambda_handler(lambda_event, None)
    assert response1['statusCode'] == 200
    body1 = json.loads(response1['body'])
    assert len(body1['acknowledged']) == 1
    
    # Second acknowledgment (should still succeed)
    response2 = lambda_handler(lambda_event, None)
    assert response2['statusCode'] == 200
    body2 = json.loads(response2['body'])
    assert len(body2['acknowledged']) == 1  # Still succeeds


# Test partial success
def test_ack_partial_success(mock_infrastructure, lambda_event, sample_events):
    """Test partial success (some events fail)."""
    from src.lib.storage import generate_event_id
    nonexistent_id = generate_event_id()  # Valid format but doesn't exist
    event_ids = [sample_events[0]['id'], nonexistent_id]
    lambda_event['body'] = json.dumps({
        'event_ids': event_ids
    })
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['acknowledged']) == 1
    assert len(body['failed']) == 1
    assert body['failed'][0]['event_id'] == nonexistent_id


# Test validation errors
def test_ack_empty_event_ids(mock_infrastructure, lambda_event):
    """Test validation error for empty event_ids."""
    lambda_event['body'] = json.dumps({
        'event_ids': []
    })
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'


def test_ack_too_many_event_ids(mock_infrastructure, lambda_event):
    """Test validation error for too many event_ids (max 100)."""
    event_ids = [generate_event_id() for _ in range(101)]
    lambda_event['body'] = json.dumps({
        'event_ids': event_ids
    })
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'


def test_ack_invalid_event_id_format(mock_infrastructure, lambda_event):
    """Test validation error for invalid event_id format."""
    lambda_event['body'] = json.dumps({
        'event_ids': ['invalid_event_id']
    })
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'


def test_ack_invalid_json(mock_infrastructure, lambda_event):
    """Test error for invalid JSON."""
    lambda_event['body'] = 'invalid json'
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 400
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'VALIDATION_ERROR'


# Test authentication errors
def test_ack_missing_api_key(mock_infrastructure, lambda_event):
    """Test 401 error for missing API key."""
    del lambda_event['headers']['x-api-key']
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 401
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'AUTHENTICATION_ERROR'


def test_ack_invalid_api_key(mock_infrastructure, lambda_event):
    """Test 401 error for invalid API key."""
    lambda_event['headers']['x-api-key'] = 'ak_invalid_key_12345'
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 401
    error_body = json.loads(response['body'])
    assert error_body['error']['code'] == 'AUTHENTICATION_ERROR'


# Test not found events
def test_ack_event_not_found(mock_infrastructure, lambda_event):
    """Test acknowledgment of non-existent event."""
    from src.lib.storage import generate_event_id
    nonexistent_id = generate_event_id()  # Valid format but doesn't exist
    lambda_event['body'] = json.dumps({
        'event_ids': [nonexistent_id]
    })
    
    response = lambda_handler(lambda_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['acknowledged']) == 0
    assert len(body['failed']) == 1
    assert body['failed'][0]['event_id'] == nonexistent_id

