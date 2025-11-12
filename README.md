# Zapier Triggers API

A serverless REST API for real-time event ingestion and delivery on the Zapier platform. This MVP provides a public, reliable, and developer-friendly interface for any system to send events into Zapier, enabling workflows that react to events in real time.

## Features

- **Event Ingestion**: Send events via simple REST API with idempotency support
- **Event Retrieval**: Pull-based delivery with pagination and filtering
- **Lease Mechanism**: 5-minute leases prevent duplicate delivery during processing
- **Large Payload Support**: Automatic S3 routing for payloads ≥400KB
- **Multi-Tenant Isolation**: Complete data isolation per API key
- **Automatic Cleanup**: 30-day TTL for automatic event deletion

## Quick Start

### Prerequisites

- Python 3.12+
- AWS SAM CLI 1.100+
- Docker (for local testing)
- AWS account with appropriate permissions

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd TriggersAPI
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Configure AWS:**
   ```bash
   aws configure
   ```

5. **Validate SAM template:**
   ```bash
   sam validate
   ```

## Local Development

### Running Locally

Start the API locally using SAM Local:

```bash
sam local start-api --port 3000
```

The API will be available at `http://localhost:3000`.

### Testing Locally

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run all tests with coverage
pytest tests/ --cov=src --cov-report=html
```

### Example API Call

```bash
# Send an event
curl -X POST http://localhost:3000/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_test123456789012345678901234567890" \
  -d '{
    "event_type": "user.created",
    "timestamp": "2025-11-11T15:30:45Z",
    "data": {
      "user_id": "12345",
      "email": "user@example.com"
    }
  }'
```

## Deployment

### First Deployment

Deploy to AWS using SAM CLI:

```bash
sam deploy --guided
```

Follow the prompts to:
- Set stack name (e.g., `zapier-triggers-api-dev`)
- Choose AWS region (e.g., `us-east-1`)
- Confirm parameter overrides
- Allow SAM CLI to create IAM roles

### Subsequent Deployments

```bash
sam deploy
```

### Environment-Specific Deployment

```bash
# Deploy to dev
sam deploy --parameter-overrides Environment=dev

# Deploy to prod
sam deploy --parameter-overrides Environment=prod
```

### Get API Endpoint URL

After deployment, get the API Gateway URL:

```bash
aws cloudformation describe-stacks \
  --stack-name zapier-triggers-api-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text
```

## Testing

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_ingest.py -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=term-missing
```

### Integration Tests

```bash
# Run integration tests
pytest tests/integration/ -v

# Run specific integration test
pytest tests/integration/test_api_flow.py::TestEndToEndFlow -v
```

### Load Tests

Load tests use k6. Install k6 first:

```bash
# macOS
brew install k6

# Linux
# See https://grafana.com/docs/k6/latest/set-up/install-k6/
```

Run load tests:

```bash
# Set environment variables
export API_URL="https://api.zapier.com/triggers/v1"
export API_KEY="ak_your_api_key_here"

# Run load test
k6 run tests/load/ingest-load.js
```

For local testing:

```bash
k6 run --env API_URL=http://localhost:3000 --env API_KEY=ak_test123456789012345678901234567890 tests/load/ingest-load.js
```

See `tests/load/LOAD_TESTING.md` for detailed load testing documentation.

## API Usage

### Authentication

All endpoints require API key authentication via the `X-API-Key` header:

```bash
curl -H "X-API-Key: ak_your_api_key_here" ...
```

API keys are in the format `ak_{32 random characters}`.

### Endpoints

#### POST /events

Ingest a new event:

```bash
curl -X POST https://api.zapier.com/triggers/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_your_api_key" \
  -d '{
    "event_type": "user.created",
    "timestamp": "2025-11-11T15:30:45Z",
    "data": {
      "user_id": "12345",
      "email": "user@example.com"
    }
  }'
```

#### GET /inbox

Retrieve pending events:

```bash
curl -X GET "https://api.zapier.com/triggers/v1/inbox?limit=25" \
  -H "X-API-Key: ak_your_api_key"
```

#### POST /inbox/ack

Acknowledge processed events:

```bash
curl -X POST https://api.zapier.com/triggers/v1/inbox/ack \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_your_api_key" \
  -d '{
    "event_ids": ["evt_abc123", "evt_def456"]
  }'
```

#### GET /health

Check system health:

```bash
curl -X GET https://api.zapier.com/triggers/v1/health \
  -H "X-API-Key: ak_your_api_key"
```

### Python Client

A Python client library is available in `examples/python_client.py`:

```python
from examples.python_client import ZapierTriggersClient

client = ZapierTriggersClient(
    api_key="ak_your_api_key",
    base_url="https://api.zapier.com/triggers/v1"
)

# Send event
response = client.send_event(
    event_type="user.created",
    timestamp="2025-11-11T15:30:45Z",
    data={"user_id": "12345"}
)

# Retrieve inbox
inbox = client.get_inbox(limit=25)

# Acknowledge events
client.acknowledge(["evt_abc123", "evt_def456"])
```

See `docs/API.md` for comprehensive API documentation.

## Architecture

### High-Level Architecture

```
┌─────────────┐
│ API Clients │
└──────┬──────┘
       │ HTTPS
       ▼
┌──────────────────┐
│  API Gateway     │
│  (HTTP API)      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Lambda          │
│  Functions       │
│  (Python 3.12)   │
└──────┬───────────┘
       │
       ├──────────────┐
       ▼              ▼
┌──────────┐    ┌──────────┐
│ DynamoDB │    │    S3    │
└──────────┘    └──────────┘
```

### Components

- **API Gateway**: HTTP API with TLS termination and API key validation
- **Lambda Functions**: 4 serverless functions (ingest, inbox, ack, health)
- **DynamoDB**: Event storage with 30-day TTL
- **S3**: Large payload storage (≥400KB)
- **CloudWatch**: Logging, metrics, alarms, and dashboards

### Data Flow

1. **Ingestion**: Client sends event → API Gateway → Lambda → DynamoDB/S3
2. **Retrieval**: Client requests inbox → Lambda queries DynamoDB → Returns events
3. **Acknowledgment**: Client acknowledges events → Lambda updates status → Event removed from inbox

## Project Structure

```
TriggersAPI/
├── src/
│   ├── handlers/          # Lambda handlers
│   │   ├── ingest.py      # POST /events
│   │   ├── inbox.py       # GET /inbox
│   │   ├── ack.py         # POST /inbox/ack
│   │   └── health.py      # GET /health
│   ├── lib/               # Shared libraries
│   │   ├── auth.py        # Authentication
│   │   ├── storage.py     # DynamoDB/S3 operations
│   │   ├── validation.py  # Input validation
│   │   ├── logging.py     # Structured logging
│   │   └── metrics.py     # CloudWatch metrics
│   └── models/            # Pydantic schemas
│       └── schemas.py
├── tests/
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── load/              # Load tests (k6)
├── docs/
│   ├── openapi.yaml       # OpenAPI 3.1 specification
│   ├── API.md             # API usage guide
│   ├── swagger-ui/        # Swagger UI files
│   ├── cloudwatch-alarms.md
│   └── cloudwatch-dashboard.md
├── config/
│   ├── dev.yaml           # Development config
│   └── prod.yaml          # Production config
├── examples/
│   └── python_client.py   # Python client library
├── template.yaml          # SAM template
├── requirements.txt       # Production dependencies
└── requirements-dev.txt   # Development dependencies
```

## Configuration

### Environment Variables

Lambda functions use the following environment variables:

- `EVENTS_TABLE`: DynamoDB events table name
- `API_KEYS_TABLE`: DynamoDB API keys table name
- `EVENTS_BUCKET`: S3 bucket name for large payloads
- `ENVIRONMENT`: Deployment environment (dev/prod)
- `LOG_LEVEL`: Logging level (INFO/DEBUG)
- `LEASE_DURATION_MINUTES`: Lease duration (default: 5)
- `SIZE_THRESHOLD_BYTES`: S3 threshold (default: 400000)

### Configuration Files

- `config/dev.yaml`: Development environment configuration
- `config/prod.yaml`: Production environment configuration

## Monitoring

### CloudWatch Metrics

All handlers emit CloudWatch metrics with namespace `ZapierTriggers`:

- `EventIngested`: Event ingestion count (dimensions: TenantId, EventType)
- `InboxRetrieved`: Inbox retrieval count (dimensions: TenantId)
- `EventAcknowledged`: Acknowledgment count (dimensions: TenantId)
- `EventLatency`: Request latency (P50/P95/P99 percentiles)

### CloudWatch Alarms

Configure alarms for:
- High error rate (>10 5XX errors in 5 minutes)
- High latency (P95 >200ms in 5 minutes)

See `docs/cloudwatch-alarms.md` for alarm configuration.

### CloudWatch Dashboard

Create a dashboard with widgets for:
- Event ingestion rate
- API latency (P50/P95/P99)
- Error rates (4XX/5XX)
- Event volume over time
- Per-tenant breakdowns

See `docs/cloudwatch-dashboard.md` for dashboard configuration.

## API Documentation

### OpenAPI Specification

The complete OpenAPI 3.1 specification is available at `docs/openapi.yaml`.

### Swagger UI

View interactive API documentation:

1. **Local**: Open `docs/swagger-ui/index.html` in a browser
2. **Production**: Deploy Swagger UI to S3 + CloudFront (see `docs/swagger-ui/HOSTING.md`)

### API Usage Guide

See `docs/API.md` for:
- Authentication guide
- Endpoint documentation with examples
- Error handling guide
- Best practices
- Rate limiting information
- Monitoring and observability

## Error Handling

All errors return a structured `ErrorResponse`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid event payload",
    "details": {
      "field": "timestamp",
      "issue": "must be ISO 8601 format"
    }
  }
}
```

### Error Codes

- `VALIDATION_ERROR`: Invalid request payload (400)
- `AUTHENTICATION_ERROR`: Invalid or missing API key (401)
- `NOT_FOUND`: Resource not found (404)
- `CONFLICT`: Duplicate event ID (409)
- `RATE_LIMIT_EXCEEDED`: Too many requests (429)
- `INTERNAL_ERROR`: Internal server error (500)
- `SERVICE_UNAVAILABLE`: Service unavailable (503)

## Rate Limiting

API Gateway throttling:
- **Default**: 1000 requests/second
- **Burst**: 2000 requests

Configure via AWS Console or usage plans.

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and add tests
3. Run tests: `pytest tests/`
4. Format code: `black src/ tests/`
5. Lint code: `pylint src/`
6. Commit changes: `git commit -m "Add feature"`
7. Push to branch: `git push origin feature/my-feature`
8. Create pull request

### Code Style

- Python: Follow PEP 8, use type hints
- Formatting: Use `black` (line length 100)
- Linting: Use `pylint` (score >8.0)
- Testing: Aim for >80% coverage

## Troubleshooting

### Common Issues

**SAM Local not starting:**
- Ensure Docker is running: `docker ps`
- Check port availability: `lsof -i :3000`

**Deployment fails:**
- Verify AWS credentials: `aws sts get-caller-identity`
- Check IAM permissions
- Review CloudFormation stack events

**Tests failing:**
- Ensure virtual environment is activated
- Install dependencies: `pip install -r requirements-dev.txt`
- Check Python version: `python3 --version` (should be 3.12+)

**API returns 401:**
- Verify API key format: `ak_{32chars}`
- Check API key is active in DynamoDB
- Ensure `X-API-Key` header is set

**High latency:**
- Check Lambda cold starts (consider provisioned concurrency)
- Monitor DynamoDB capacity
- Review CloudWatch metrics

## License

Proprietary - Zapier Internal Use Only

## Support

For issues and questions:
- **API Support**: api-support@zapier.com
- **Documentation**: See `docs/API.md`
- **OpenAPI Spec**: `docs/openapi.yaml`

## Related Documentation

- [API Usage Guide](docs/API.md)
- [OpenAPI Specification](docs/openapi.yaml)
- [CloudWatch Alarms](docs/cloudwatch-alarms.md)
- [CloudWatch Dashboard](docs/cloudwatch-dashboard.md)
- [Load Testing Guide](tests/load/LOAD_TESTING.md)
- [Product Requirements](PRD_Product_Reqs_v2.md)
- [Technical Specification](PRD_Tech_v2.md)

