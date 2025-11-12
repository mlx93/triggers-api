#!/usr/bin/env python3
"""
Setup script to create test API keys in DynamoDB for local testing.

Usage:
    python scripts/setup-test-api-key.py
    python scripts/setup-test-api-key.py --table-name zapier-triggers-api-keys-dev
"""
import argparse
import hashlib
import boto3
import os
from datetime import datetime, timezone

def hash_api_key(api_key: str) -> str:
    """Hash API key using SHA-256."""
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

def create_test_api_key(
    api_key: str,
    tenant_id: str,
    table_name: str,
    region: str = 'us-east-1'
):
    """Create a test API key in DynamoDB."""
    dynamodb = boto3.client('dynamodb', region_name=region)
    hashed_key = hash_api_key(api_key)
    
    try:
        dynamodb.put_item(
            TableName=table_name,
            Item={
                'hashed_key': {'S': hashed_key},
                'tenant_id': {'S': tenant_id},
                'is_active': {'BOOL': True},
                'created_at': {'S': datetime.now(timezone.utc).isoformat()}
            }
        )
        print(f"✅ Created API key: {api_key}")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   Hashed Key: {hashed_key}")
        return True
    except Exception as e:
        print(f"❌ Failed to create API key: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Create test API keys in DynamoDB')
    parser.add_argument(
        '--table-name',
        default=os.environ.get('API_KEYS_TABLE', 'zapier-triggers-api-keys-dev'),
        help='DynamoDB table name for API keys'
    )
    parser.add_argument(
        '--region',
        default=os.environ.get('AWS_REGION', 'us-east-1'),
        help='AWS region'
    )
    parser.add_argument(
        '--api-key',
        default='ak_test123456789012345678901234567890',
        help='API key to create'
    )
    parser.add_argument(
        '--tenant-id',
        default='tenant_550e8400-e29b-41d4-a716-446655440000',
        help='Tenant ID for the API key'
    )
    
    args = parser.parse_args()
    
    print(f"Creating test API key in table: {args.table_name}")
    print(f"Region: {args.region}")
    print()
    
    success = create_test_api_key(
        api_key=args.api_key,
        tenant_id=args.tenant_id,
        table_name=args.table_name,
        region=args.region
    )
    
    if success:
        print()
        print("✅ Test API key created successfully!")
        print(f"You can now use this API key for local testing: {args.api_key}")
    else:
        print()
        print("❌ Failed to create API key. Make sure:")
        print("  1. DynamoDB table exists")
        print("  2. AWS credentials are configured")
        print("  3. You have write permissions to the table")
        exit(1)

if __name__ == '__main__':
    main()

