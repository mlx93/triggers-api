"""
Authentication module for Zapier Triggers API.

Handles API key validation, tenant_id extraction, and DynamoDB lookups.
"""
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError


# API key format: ak_{32chars}
API_KEY_PREFIX = "ak_"
API_KEY_LENGTH = 35  # "ak_" + 32 chars = 35 total


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using SHA-256.
    
    Args:
        api_key: Plaintext API key (format: ak_{32chars})
        
    Returns:
        SHA-256 hash as hexadecimal string
    """
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()


def extract_api_key_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract X-API-Key header from Lambda event.
    
    Args:
        event: Lambda event dictionary
        
    Returns:
        API key string if found, None otherwise
    """
    headers = event.get('headers', {}) or {}
    
    # API Gateway HTTP API uses lowercase header names
    api_key = headers.get('x-api-key') or headers.get('X-API-Key')
    
    return api_key


def validate_api_key_format(api_key: str) -> bool:
    """
    Validate API key format: ak_{32chars}.
    
    Args:
        api_key: API key to validate
        
    Returns:
        True if format is valid, False otherwise
    """
    if not api_key or not isinstance(api_key, str):
        return False
    
    if not api_key.startswith(API_KEY_PREFIX):
        return False
    
    if len(api_key) != API_KEY_LENGTH:
        return False
    
    # Check that characters after prefix are alphanumeric
    suffix = api_key[len(API_KEY_PREFIX):]
    if not suffix.isalnum():
        return False
    
    return True


def validate_api_key(api_key: str) -> Dict[str, Any]:
    """
    Validate API key and return tenant_id and metadata.
    
    This function:
    1. Validates API key format
    2. Hashes the API key
    3. Looks up in DynamoDB api-keys table
    4. Validates is_active flag
    5. Returns tenant_id and metadata
    
    Args:
        api_key: Plaintext API key
        
    Returns:
        Dictionary with tenant_id and metadata:
        {
            'tenant_id': str,
            'created_at': str,
            'last_used_at': str,
            'is_active': bool
        }
        
    Raises:
        AuthenticationError: If API key is invalid, missing, or inactive
    """
    # Validate format
    if not validate_api_key_format(api_key):
        raise AuthenticationError("Invalid API key format")
    
    # Hash the API key
    hashed_key = hash_api_key(api_key)
    
    # Get table name from environment
    table_name = os.environ.get('API_KEYS_TABLE')
    if not table_name:
        raise AuthenticationError("API_KEYS_TABLE environment variable not set")
    
    # Query DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        response = table.get_item(
            Key={'hashed_key': hashed_key}
        )
        
        if 'Item' not in response:
            raise AuthenticationError("Invalid API key")
        
        item = response['Item']
        
        # Check if key is active
        if not item.get('is_active', False):
            raise AuthenticationError("API key is inactive")
        
        # Extract tenant_id and metadata
        tenant_id = item.get('tenant_id')
        if not tenant_id:
            raise AuthenticationError("API key missing tenant_id")
        
        # Update last_used_at asynchronously (fire and forget)
        # This is a best-effort update, failures won't block the request
        try:
            now = datetime.now(timezone.utc).isoformat()
            table.update_item(
                Key={'hashed_key': hashed_key},
                UpdateExpression='SET last_used_at = :now',
                ExpressionAttributeValues={
                    ':now': now
                }
            )
        except Exception:
            # Log but don't fail the request if update fails
            pass
        
        return {
            'tenant_id': tenant_id,
            'created_at': item.get('created_at', ''),
            'last_used_at': item.get('last_used_at', ''),
            'is_active': item.get('is_active', True)
        }
        
    except ClientError as e:
        raise AuthenticationError(f"DynamoDB error: {str(e)}")
    except AuthenticationError:
        raise
    except Exception as e:
        raise AuthenticationError(f"Unexpected error during authentication: {str(e)}")


def get_tenant_id_from_event(event: Dict[str, Any]) -> str:
    """
    Extract and validate API key from Lambda event, return tenant_id.
    
    Convenience function that combines extraction and validation.
    
    Args:
        event: Lambda event dictionary
        
    Returns:
        tenant_id string
        
    Raises:
        AuthenticationError: If API key is missing or invalid
    """
    api_key = extract_api_key_from_event(event)
    
    if not api_key:
        raise AuthenticationError("Missing X-API-Key header")
    
    auth_result = validate_api_key(api_key)
    return auth_result['tenant_id']

