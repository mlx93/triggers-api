"""
Unit tests for authentication module.

Tests API key validation, tenant_id extraction, and DynamoDB lookups.
Uses moto to mock DynamoDB.
"""
import os
import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone
from src.lib.auth import (
    hash_api_key,
    extract_api_key_from_event,
    validate_api_key_format,
    validate_api_key,
    get_tenant_id_from_event,
    AuthenticationError
)


# Test fixtures
@pytest.fixture
def api_key():
    """Generate a valid API key for testing."""
    return "ak_" + "a" * 32


@pytest.fixture
def hashed_api_key(api_key):
    """Get hashed version of API key."""
    return hash_api_key(api_key)


@pytest.fixture
def tenant_id():
    """Generate a valid tenant ID for testing."""
    return "tenant_550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def api_keys_table_name():
    """Get API keys table name."""
    return "zapier-triggers-api-keys-test"


@pytest.fixture
def mock_dynamodb_table(api_keys_table_name, hashed_api_key, tenant_id):
    """Create a mocked DynamoDB table with test data."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName=api_keys_table_name,
            KeySchema=[
                {'AttributeName': 'hashed_key', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'hashed_key', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Insert test API key
        now = datetime.now(timezone.utc).isoformat()
        table.put_item(
            Item={
                'hashed_key': hashed_api_key,
                'tenant_id': tenant_id,
                'created_at': now,
                'last_used_at': now,
                'is_active': True
            }
        )
        
        # Set environment variable
        os.environ['API_KEYS_TABLE'] = api_keys_table_name
        
        yield table
        
        # Cleanup
        if 'API_KEYS_TABLE' in os.environ:
            del os.environ['API_KEYS_TABLE']


class TestHashApiKey:
    """Tests for hash_api_key function."""
    
    def test_hash_api_key_returns_hex_string(self, api_key):
        """Test that hash_api_key returns a hexadecimal string."""
        hashed = hash_api_key(api_key)
        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA-256 hex digest is 64 chars
        assert all(c in '0123456789abcdef' for c in hashed)
    
    def test_hash_api_key_deterministic(self, api_key):
        """Test that hashing the same key produces the same hash."""
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)
        assert hash1 == hash2
    
    def test_hash_api_key_different_keys_different_hashes(self):
        """Test that different keys produce different hashes."""
        key1 = "ak_" + "a" * 32
        key2 = "ak_" + "b" * 32
        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)
        assert hash1 != hash2


class TestExtractApiKeyFromEvent:
    """Tests for extract_api_key_from_event function."""
    
    def test_extract_api_key_lowercase_header(self):
        """Test extraction from lowercase header name."""
        event = {
            'headers': {
                'x-api-key': 'ak_' + 'a' * 32
            }
        }
        api_key = extract_api_key_from_event(event)
        assert api_key == 'ak_' + 'a' * 32
    
    def test_extract_api_key_uppercase_header(self):
        """Test extraction from uppercase header name."""
        event = {
            'headers': {
                'X-API-Key': 'ak_' + 'a' * 32
            }
        }
        api_key = extract_api_key_from_event(event)
        assert api_key == 'ak_' + 'a' * 32
    
    def test_extract_api_key_missing_header(self):
        """Test that missing header returns None."""
        event = {'headers': {}}
        api_key = extract_api_key_from_event(event)
        assert api_key is None
    
    def test_extract_api_key_no_headers(self):
        """Test that event without headers returns None."""
        event = {}
        api_key = extract_api_key_from_event(event)
        assert api_key is None
    
    def test_extract_api_key_none_headers(self):
        """Test that event with None headers returns None."""
        event = {'headers': None}
        api_key = extract_api_key_from_event(event)
        assert api_key is None


class TestValidateApiKeyFormat:
    """Tests for validate_api_key_format function."""
    
    def test_valid_api_key_format(self, api_key):
        """Test that valid API key format passes."""
        assert validate_api_key_format(api_key) is True
    
    def test_invalid_prefix(self):
        """Test that wrong prefix fails."""
        assert validate_api_key_format("bk_" + "a" * 32) is False
    
    def test_too_short(self):
        """Test that too short key fails."""
        assert validate_api_key_format("ak_" + "a" * 31) is False
    
    def test_too_long(self):
        """Test that too long key fails."""
        assert validate_api_key_format("ak_" + "a" * 33) is False
    
    def test_non_alphanumeric_suffix(self):
        """Test that non-alphanumeric suffix fails."""
        assert validate_api_key_format("ak_" + "a" * 31 + "@") is False
    
    def test_empty_string(self):
        """Test that empty string fails."""
        assert validate_api_key_format("") is False
    
    def test_none_value(self):
        """Test that None fails."""
        assert validate_api_key_format(None) is False
    
    def test_non_string(self):
        """Test that non-string fails."""
        assert validate_api_key_format(12345) is False


class TestValidateApiKey:
    """Tests for validate_api_key function."""
    
    def test_valid_api_key(self, mock_dynamodb_table, api_key, tenant_id):
        """Test that valid API key returns tenant_id."""
        result = validate_api_key(api_key)
        assert result['tenant_id'] == tenant_id
        assert result['is_active'] is True
        assert 'created_at' in result
        assert 'last_used_at' in result
    
    def test_invalid_api_key_format(self):
        """Test that invalid format raises AuthenticationError."""
        os.environ['API_KEYS_TABLE'] = 'test-table'
        with pytest.raises(AuthenticationError, match="Invalid API key format"):
            validate_api_key("invalid_key")
        del os.environ['API_KEYS_TABLE']
    
    def test_api_key_not_found(self, mock_dynamodb_table):
        """Test that non-existent API key raises AuthenticationError."""
        unknown_key = "ak_" + "z" * 32
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            validate_api_key(unknown_key)
    
    def test_inactive_api_key(self, mock_dynamodb_table, api_keys_table_name, hashed_api_key, tenant_id):
        """Test that inactive API key raises AuthenticationError."""
        # Update existing key to inactive
        now = datetime.now(timezone.utc).isoformat()
        mock_dynamodb_table.put_item(
            Item={
                'hashed_key': hashed_api_key,
                'tenant_id': tenant_id,
                'created_at': now,
                'last_used_at': now,
                'is_active': False
            }
        )
        
        api_key = "ak_" + "a" * 32
        with pytest.raises(AuthenticationError, match="API key is inactive"):
            validate_api_key(api_key)
    
    def test_missing_tenant_id(self, mock_dynamodb_table, api_keys_table_name, hashed_api_key):
        """Test that API key without tenant_id raises AuthenticationError."""
        # Update existing key to remove tenant_id
        now = datetime.now(timezone.utc).isoformat()
        mock_dynamodb_table.put_item(
            Item={
                'hashed_key': hashed_api_key,
                'created_at': now,
                'is_active': True
            }
        )
        
        api_key = "ak_" + "a" * 32
        with pytest.raises(AuthenticationError, match="API key missing tenant_id"):
            validate_api_key(api_key)
    
    def test_missing_table_env_var(self):
        """Test that missing API_KEYS_TABLE raises AuthenticationError."""
        if 'API_KEYS_TABLE' in os.environ:
            del os.environ['API_KEYS_TABLE']
        
        api_key = "ak_" + "a" * 32
        with pytest.raises(AuthenticationError, match="API_KEYS_TABLE environment variable"):
            validate_api_key(api_key)


class TestGetTenantIdFromEvent:
    """Tests for get_tenant_id_from_event function."""
    
    def test_valid_event(self, mock_dynamodb_table, api_key, tenant_id):
        """Test that valid event returns tenant_id."""
        event = {
            'headers': {
                'x-api-key': api_key
            }
        }
        result_tenant_id = get_tenant_id_from_event(event)
        assert result_tenant_id == tenant_id
    
    def test_missing_api_key(self):
        """Test that missing API key raises AuthenticationError."""
        event = {'headers': {}}
        with pytest.raises(AuthenticationError, match="Missing X-API-Key header"):
            get_tenant_id_from_event(event)
    
    def test_invalid_api_key(self):
        """Test that invalid API key raises AuthenticationError."""
        os.environ['API_KEYS_TABLE'] = 'test-table'
        event = {
            'headers': {
                'x-api-key': 'invalid_key'
            }
        }
        with pytest.raises(AuthenticationError):
            get_tenant_id_from_event(event)
        del os.environ['API_KEYS_TABLE']

