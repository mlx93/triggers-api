# Technical Context: Technologies & Setup

**Date:** November 11, 2025  
**Status:** Environment Configured

---

## Technology Stack

### Runtime & Language
- **Python:** 3.13.7 (exceeds 3.12+ requirement)
- **Virtual Environment:** `/Users/mylessjs/venv`
- **Package Manager:** pip 25.3

### Infrastructure as Code
- **SAM CLI:** 1.146.0 (exceeds 1.100+ requirement)
- **Template Format:** YAML (SAM/CloudFormation)
- **Deployment:** `sam deploy --guided` (first time), `sam deploy` (subsequent)

### AWS Services
- **API Gateway:** HTTP API (not REST API)
- **Lambda:** Python 3.12 runtime, 30-second timeout, 256MB memory
- **DynamoDB:** On-demand billing, TTL enabled, SSE-KMS encryption
- **S3:** SSE-S3 encryption, lifecycle rules, versioning disabled
- **CloudWatch:** Logs (30-day retention), Metrics, Alarms, Dashboard

### Development Tools
- **Testing:** pytest 7.4.0+, moto 5.0.0+ (AWS mocking)
- **Code Quality:** black 23.0.0+ (formatting), pylint 3.0.0+ (linting)
- **Load Testing:** k6 1.4.0+
- **Docker:** Required for `sam local` testing

### CI/CD
- **Platform:** GitHub Actions
- **Workflow:** `.github/workflows/deploy.yml`
- **Secrets:** AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION

---

## Dependencies

### Production (`requirements.txt`)
- `boto3>=1.34.0` - AWS SDK
- `pydantic>=2.0.0` - Data validation and schema models
- `aws-lambda-powertools>=2.0.0` - Lambda utilities (metrics, logging)

### Development (`requirements-dev.txt`)
- `pytest>=7.4.0` - Testing framework
- `moto>=5.0.0` - AWS service mocking
- `black>=23.0.0` - Code formatting
- `pylint>=3.0.0` - Linting
- `pytest-cov>=4.1.0` - Coverage reporting

---

## AWS Configuration

### Account & Region
- **Account ID:** 971422717446
- **Region:** `us-east-1`
- **IAM User:** `myles93@sbcglobal.net`
- **Profile:** Default

### IAM Permissions
All required policies attached:
- `AWSLambda_FullAccess`
- `AmazonAPIGatewayAdministrator`
- `AmazonDynamoDBFullAccess`
- `AmazonS3FullAccess`
- `CloudWatchFullAccess`
- `IAMFullAccess`

### AWS CLI
- **Version:** 2.31.32
- **Status:** Configured and authenticated
- **Verification:** `aws sts get-caller-identity` succeeds

---

## Development Environment

### Local Setup
- **OS:** macOS (darwin 25.1.0)
- **Shell:** zsh
- **Working Directory:** `/Users/mylessjs/Desktop/TriggersAPI`
- **Python:** 3.13.7 (venv activated)

### Repository
- **URL:** https://github.com/mlx93/triggers-api
- **Branch:** `main`
- **Remote:** `origin` → `https://github.com/mlx93/triggers-api.git`

### GitHub Actions Secrets
- `AWS_ACCESS_KEY_ID` ✅
- `AWS_SECRET_ACCESS_KEY` ✅
- `AWS_REGION` ✅ (set to `us-east-1`)

---

## Project Structure

```
TriggersAPI/
├── src/
│   ├── handlers/        # Lambda handlers (ingest, inbox, ack, health)
│   ├── lib/             # Shared libraries (auth, validation, storage)
│   └── models/          # Pydantic schemas
├── tests/
│   ├── unit/            # Unit tests (145 tests passing)
│   ├── integration/     # Integration tests (pending)
│   └── load/            # Load tests (pending)
├── config/              # Environment configs (dev.yaml, prod.yaml)
├── docs_planning_agent/ # Planning documents, completion reports
├── memory-bank/         # Project memory and context
├── template.yaml        # SAM template
├── requirements.txt     # Production dependencies
└── requirements-dev.txt # Development dependencies
```

---

## Configuration Values

### Environment Variables (Lambda)
- `EVENTS_TABLE` - DynamoDB events table name
- `API_KEYS_TABLE` - DynamoDB api-keys table name
- `EVENTS_BUCKET` - S3 bucket name
- `ENVIRONMENT` - dev or prod
- `LOG_LEVEL` - INFO or DEBUG
- `LEASE_DURATION_MINUTES` - 5
- `SIZE_THRESHOLD_BYTES` - 400000 (400KB)
- `AWS_REGION` - Automatically provided by Lambda runtime

### Config Files (`config/dev.yaml`, `config/prod.yaml`)
- Environment-specific table/bucket names
- API configuration (lease duration, size thresholds, pagination limits)
- Log level and region settings

---

## Testing Setup

### Unit Testing
- **Framework:** pytest
- **Mocking:** moto (mock_aws) for DynamoDB and S3
- **Coverage:** pytest-cov for coverage reporting
- **Command:** `pytest tests/unit/ --cov=src`

### Local Testing
- **SAM Local:** `sam local start-api` (requires Docker)
- **Docker:** Running and verified
- **Purpose:** Test Lambda functions locally before deployment

### Load Testing
- **Tool:** k6 1.4.0+
- **Scripts:** `tests/load/` directory
- **Targets:** 1000 events/sec, 100 concurrent users, <100ms P95

---

## Deployment Process

### First Deployment
```bash
sam deploy --guided
```
- Prompts for stack name, region, parameters
- Creates all AWS resources automatically

### Subsequent Deployments
```bash
sam deploy
```
- Uses saved configuration from first deployment

### CI/CD Deployment
- **Dev:** Auto-deploys on push to `develop` branch
- **Prod:** Deploys on push to `main` branch (with manual approval)

---

## Known Constraints

### AWS Limits
- **API Gateway:** 10MB payload limit (enforced)
- **Lambda:** 30-second timeout (configured)
- **DynamoDB:** 400KB item size limit (handled via S3 fallback)

### MVP Limitations
- **Idempotency:** Non-atomic (query-then-insert) - acceptable for MVP
- **Filtering:** Client-side filtering for leases - acceptable for MVP
- **Rate Limiting:** Configured via AWS Console (not in SAM template)

---

## Troubleshooting

### Common Issues
1. **SAM CLI not found:** Install via Homebrew (`brew install aws-sam-cli`)
2. **Docker not running:** Start Docker Desktop, verify `docker ps` works
3. **AWS credentials error:** Run `aws configure`, verify IAM permissions
4. **Python version mismatch:** Use `python3.12` explicitly

### Validation Commands
- `sam validate` - Validate SAM template syntax
- `pytest tests/unit/` - Run unit tests
- `black --check src/` - Check code formatting
- `pylint src/` - Run linting

---

**Document Status:** ✅ Complete  
**Last Updated:** November 11, 2025

