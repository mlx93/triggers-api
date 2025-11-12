# Scripts Directory

Helper scripts for local development and testing.

## setup-test-api-key.py

Creates test API keys in DynamoDB for local testing with SAM Local.

### Usage

```bash
# Create default test API key
python scripts/setup-test-api-key.py

# Create custom API key
python scripts/setup-test-api-key.py \
  --api-key ak_your_custom_key_here \
  --tenant-id tenant_your_tenant_id \
  --table-name zapier-triggers-api-keys-dev
```

### Default Test API Key

- **API Key**: `ak_test123456789012345678901234567890`
- **Tenant ID**: `tenant_550e8400-e29b-41d4-a716-446655440000`

This matches the API key used in:
- Integration tests
- Load tests
- README examples

### Prerequisites

- AWS credentials configured (`aws configure`)
- DynamoDB table exists (created by `sam deploy` or manually)
- Python 3.12+ with boto3 installed

### For SAM Local Testing

When using `sam local start-api`, the Lambda functions connect to real AWS services (DynamoDB, S3). You need to:

1. **Create the API keys table** (if not already created):
   ```bash
   aws dynamodb create-table \
     --table-name zapier-triggers-api-keys-dev \
     --attribute-definitions AttributeName=hashed_key,AttributeType=S \
     --key-schema AttributeName=hashed_key,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
   ```

2. **Create test API key**:
   ```bash
   python scripts/setup-test-api-key.py
   ```

3. **Run SAM local**:
   ```bash
   sam local start-api --port 3000
   ```

4. **Test with the API key**:
   ```bash
   curl http://localhost:3000/health -H "X-API-Key: ak_test123456789012345678901234567890"
   ```

