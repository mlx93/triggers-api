# Zapier Triggers API - Technical Specification

**Version:** 1.0  
**Date:** November 11, 2025  
**Organization:** Zapier  
**Project ID:** K1oUUDeoZrvJkVZafqHL_1761943818847  
**Document Type:** Technical Specification (PRD 2 of 2)

---

## 1. System Architecture Overview

### High-Level Architecture

```
┌─────────────────┐
│   API Clients   │
│  (External Devs)│
└────────┬────────┘
         │
         │ HTTPS
         ▼
┌─────────────────────────────────────────┐
│      AWS API Gateway (HTTP API)         │
│  - TLS 1.2+ Termination                │
│  - API Key Validation                   │
│  - Request/Response Mapping             │
└────────┬────────────────────────────────┘
         │
         │ Invoke
         ▼
┌─────────────────────────────────────────┐
│        AWS Lambda Functions             │
│  ┌─────────────────────────────────┐   │
│  │  POST /events Handler           │   │
│  │  - Validate payload             │   │
│  │  - Check size                   │   │
│  │  - Store to DynamoDB/S3         │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  GET /inbox Handler             │   │
│  │  - Query DynamoDB               │   │
│  │  - Apply filters & pagination   │   │
│  │  - Update leases                │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  POST /inbox/ack Handler        │   │
│  │  - Batch update status          │   │
│  │  - Clear leases                 │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  GET /health Handler            │   │
│  │  - Check dependencies           │   │
│  └─────────────────────────────────┘   │
└────────┬───────────┬────────────────────┘
         │           │
         │           │
         ▼           ▼
┌────────────────┐  ┌────────────────┐
│   DynamoDB     │  │   S3 Bucket    │
│  - Event Data  │  │  - Large       │
│  - Metadata    │  │    Payloads    │
│  - TTL: 30d    │  │  - Lifecycle   │
└────────────────┘  └────────────────┘
         │
         │ Streams (optional)
         ▼
┌────────────────────┐
│   CloudWatch       │
│  - Logs            │
│  - Metrics         │
│  - Alarms          │
│  - Dashboard       │
└────────────────────┘
```

### Architecture Principles

**Serverless-First:**
- Zero infrastructure management
- Auto-scaling by default
- Pay-per-use pricing model
- Built-in high availability

**Event-Driven:**
- Asynchronous processing where possible
- Decoupled components via AWS services
- DynamoDB Streams for future extensibility

**Multi-Tenant:**
- Tenant isolation via partition keys
- API keys scoped to single tenant
- No cross-tenant data access

**Stateless:**
- Lambda functions store no local state
- All state persisted in DynamoDB
- Enables horizontal scaling

---

## 2. Technology Stack

### Core Services

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| API Layer | AWS API Gateway (HTTP API) | Latest | Low latency, cost-effective, native Lambda integration |
| Compute | AWS Lambda | Python 3.12 | Serverless, auto-scaling, familiar language |
| Database | AWS DynamoDB | On-Demand | NoSQL, key-value access, TTL, auto-scaling |
| Storage | AWS S3 | Standard | Durable object storage for large payloads |
| Observability | AWS CloudWatch | Latest | Native AWS integration, logs/metrics/alarms |
| IaC | AWS SAM | 1.100+ | Lambda-native, simple CloudFormation wrapper |

### Development Tools

| Tool | Purpose | Version |
|------|---------|---------|
| Python | Lambda runtime | 3.12+ |
| SAM CLI | Local development | 1.100+ |
| pytest | Unit testing | Latest |
| moto | AWS mocking | Latest |
| k6 | Load testing | Latest |
| OpenAPI Generator | API docs | 3.1 |
| Docker | Local services | Latest |
| GitHub Actions | CI/CD | N/A |

### Python Libraries

```
# Core Dependencies
boto3>=1.34.0              # AWS SDK
pydantic>=2.5.0            # Schema validation
python-json-logger>=2.0.7  # Structured logging
aws-lambda-powertools>=2.35.0  # Lambda utilities

# Development Dependencies
pytest>=7.4.0
pytest-cov>=4.1.0
moto>=4.2.0
black>=23.12.0
pylint>=3.0.0
mypy>=1.7.0
```

---

## 3. API Specifications

### Base Configuration

```yaml
# OpenAPI 3.1 Specification
openapi: 3.1.0
info:
  title: Zapier Triggers API
  version: 1.0.0
  description: Real-time event ingestion and delivery API
servers:
  - url: https://api.zapier.com/triggers/v1
    description: Production
  - url: https://api-dev.zapier.com/triggers/v1
    description: Development
security:
  - ApiKeyAuth: []

# Note: All endpoints must include comprehensive examples for both success 
# and error responses (200, 201, 400, 401, 404, 409, 422, 429, 500, 503)
# to ensure clear developer documentation and testing.
```

### Authentication Scheme

```yaml
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: API key for tenant authentication
```

### Endpoint: POST /events

**Purpose:** Ingest new event

**Request:** POST with headers `X-API-Key`, `Content-Type: application/json`. Body: `{id?, event_type, timestamp, data}`

**Responses:**
- 201: `{id, status: "accepted", created_at}`
- 400: Validation error (missing/invalid fields)
- 409: Duplicate event_id
- 401: Invalid/missing API key

**Logic:**
1. Authenticate via X-API-Key → get tenant_id
2. Validate schema (event_type, timestamp, data required)
3. Generate event_id if missing
4. If <400KB: DynamoDB conditional write (reject duplicates → 409)
5. If ≥400KB: S3 write + DynamoDB reference (conditional, cleanup S3 on duplicate)
6. Return 201 with event_id

### Endpoint: GET /inbox

**Purpose:** Retrieve pending events for processing

**Request:**
**Request:** GET with query params: `limit` (1-100), `cursor`, `after`, `before`, `event_type`, `status`. Header: `X-API-Key`

**Response:** `{events: [{id, event_type, timestamp, data, created_at, attempt_count}], pagination: {next_cursor, has_more}}`

**Logic:**
1. Auth → tenant_id
2. Validate cursor: age <24h, reject expired (400)
3. Query DynamoDB: status=pending, lease expired/null
4. Apply filters: event_type, time range
5. Update: lease=now+5min, attempt_count++
6. Fetch S3 data if needed
7. Return events + cursor

### Endpoint: POST /inbox/ack

**Purpose:** Acknowledge processed events

**Request:** POST with `{event_ids: [...]}` (max 100), header `X-API-Key`

**Response:** `{acknowledged: [...], failed: [{event_id, error}]}`

**Logic:** Auth → conditional update each event (status=acknowledged, clear lease) → return results

### Endpoint: GET /health

**Purpose:** Health check

**Response:** `{status: "healthy"|"degraded", timestamp, version, dependencies: {dynamodb, s3}}`

**Logic:** Check DynamoDB + S3 connectivity → return overall status

---

## 4. Database Schema (DynamoDB)

### Table Design

**Table Name:** `zapier-triggers-events`

**Billing Mode:** On-Demand (auto-scaling)

**Primary Key Design:**
- **Partition Key (pk):** `TENANT#{tenant_id}` - Ensures tenant isolation
- **Sort Key (sk):** `EVENT#{event_id}#{timestamp}` - Enables time-ordered queries

**Attributes:**
```
pk                  String     HASH    (Partition Key)
sk                  String     RANGE   (Sort Key)
id                  String             Unique event identifier
event_type          String             Event category (e.g., "player.created")
timestamp           String             Event occurrence time (ISO 8601)
tenant_id           String             Owning tenant
status              String             "pending" | "acknowledged"
in_flight_until     String             ISO timestamp when lease expires (nullable)
attempt_count       Number             Retrieval attempt counter
s3_key              String             S3 path for large payloads (nullable)
data                Map                Inline event payload (nullable if s3_key set)
created_at          String             System ingestion time (ISO 8601)
ttl                 Number             Unix timestamp for auto-deletion (30 days)
```

**TTL Configuration:**
- **Attribute:** `ttl`
- **Enabled:** Yes
- **Auto-deletion:** Events deleted ~48 hours after TTL expiration

**Global Secondary Indexes (GSI):**

None required for MVP. Future consideration:
- GSI on `event_type` for cross-tenant analytics (admin use)
- GSI on `status` for operational queries

**Example Item Structure:**
- Small event: inline `data` field, `s3_key=null`
- Large event: `data=null`, `s3_key=events/{tenant_id}/{event_id}.json`
- All items include: pk, sk, id, event_type, timestamp, tenant_id, status, in_flight_until, attempt_count, created_at, ttl

### API Keys Table

**Table:** `zapier-triggers-api-keys`, partition key `hashed_key` (SHA-256)

**Attributes:** hashed_key, tenant_id, created_at, last_used_at, is_active

**Usage:** Hash incoming API key → lookup in table → validate is_active → return tenant_id → update last_used_at async

---

## 5. Storage Strategy (S3)

**Bucket:** `zapier-triggers-events-{env}`, SSE-S3 encryption, 30-day lifecycle expiration, versioning disabled

**Object Keys:** `events/{tenant_id}/{event_id}.json`

**Threshold:** Use S3 for payloads ≥400KB, otherwise store inline in DynamoDB

### S3 Operations

**Put Object:** Store JSON to `events/{tenant_id}/{event_id}.json` with SSE-AES256 encryption.

**Get Object:** Retrieve and parse JSON from S3 key stored in DynamoDB `s3_key` field.

---

## 6. Authentication & Security

### API Key Management

**Key Generation:** Format `ak_{random_32_chars}`, store SHA-256 hash in DynamoDB `api-keys` table with `tenant_id`, never store plaintext.

**Tenant Creation:** Generate `tenant_{uuid}`, create API key, store hashed mapping, return plaintext key once.

### Request Authentication

**Logic:** Extract `X-API-Key` header → validate format (`ak_` prefix) → hash with SHA-256 → lookup in `api-keys` table → verify `is_active` → return `tenant_id` → attach to request context.

### Input Validation

**Schema Validation:** Use Pydantic models for JSON validation. Required fields: `event_type` (lowercase dot-notation), `timestamp` (ISO 8601), `data` (dict). Optional: `id` (pattern `evt_*`).

### Rate Limiting

**Strategy:** API Gateway usage plans (1000 req/sec, 2000 burst capacity).

---

## 7. Frontend Architecture (Swagger UI)

**Deployment:** Static S3 + CloudFront hosting with Swagger UI, OpenAPI 3.1 spec (JSON), custom branding.

**Configuration:** SwaggerUIBundle with API URL, deep linking, standalone layout.

---

## 8. Deployment Plan

### Infrastructure as Code (SAM)

**Template Structure:** SAM template defines API Gateway HTTP API, 4 Lambda functions (ingest, inbox, ack, health), 2 DynamoDB tables (events with TTL, api-keys), S3 bucket (30-day lifecycle), environment variables, IAM roles.

**Key Resources:**
- API Gateway: HTTP API with CORS, routes to Lambdas
- Lambdas: Python 3.12, 30s timeout, env vars for table/bucket names
- DynamoDB: On-demand billing, pk/sk keys, TTL enabled
- S3: Lifecycle rule for 30-day expiration, public access blocked

**Deployment:** Automated via `sam deploy` with environment parameters (dev/prod).

### CI/CD Pipeline (GitHub Actions)

**Workflow:** Push to `develop` → test (pytest, coverage, black, pylint) → deploy to dev. Push to `main` → test → manual approval → deploy to prod.

**Stages:** test → deploy-dev (on develop branch) / deploy-prod (on main branch with approval).

---

## 9. Environment Configuration

### Environment Variables

```bash
EVENTS_TABLE=zapier-triggers-events-{env}
API_KEYS_TABLE=zapier-triggers-api-keys-{env}
EVENTS_BUCKET=zapier-triggers-events-{env}
ENVIRONMENT=dev|prod
LOG_LEVEL=INFO|DEBUG
LEASE_DURATION_MINUTES=5
SIZE_THRESHOLD_BYTES=400000
AWS_REGION=us-east-1
```

**Config Files:** YAML configs per environment (dev/prod) with AWS resource names, API settings, logging config.

---

## 10. Development Workflow

### Local Development

**Prerequisites:** Python 3.12, SAM CLI, Docker

**Setup:** Create venv, install requirements, use SAM Local for Lambda testing (`sam local start-api`), optional LocalStack for AWS mocking.

### Testing

**Unit:** pytest with moto for AWS mocking, >80% coverage target  
**Integration:** SAM local or moto stubs for end-to-end flows  
**Load:** k6 targets (1000 events/sec, 100 concurrent users, <100ms P95)  
**Code Quality:** black (formatting), pylint (linting), mypy (type checking)

---

## 11. Integration Points

### Zapier Platform Integration

**Polling Trigger:** Call GET /inbox with API key auth, filter by event_type, return events array. Acknowledge with POST /inbox/ack after processing.

### External System Integration

**Sample Client:** Python class with methods: `send_event()`, `get_inbox()`, `acknowledge()`. Handles auth headers, error handling, JSON serialization.

---

## 12. Monitoring & Observability

### CloudWatch Metrics

**Emit Function:** Send metrics to CloudWatch with namespace `ZapierTriggers`, include dimensions: `TenantId`, `EventType`, `Environment`.

**Key Metrics:** EventIngested, InboxRetrieved, EventAcknowledged (all with TenantId), EventLatency, PayloadSize, AttemptCount.

### CloudWatch Alarms

**High Error Rate:** Trigger if 5XXError >10 in 5min window  
**High Latency:** Trigger if P95 latency >200ms

### Structured Logging

**Format:** JSON logs with pythonjsonlogger. Include: event_id, tenant_id, event_type, payload_size, storage_type in all operations.

### Dashboard

**Widgets:** Event ingestion rate, API latency (P50/P95/P99), error rates (4XX/5XX), event volume over time, per-tenant breakdowns.

---

## Appendix: File Structure

```
zapier-triggers-api/
├── src/
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── ingest.py          # POST /events handler
│   │   ├── inbox.py            # GET /inbox handler
│   │   ├── ack.py              # POST /inbox/ack handler
│   │   └── health.py           # GET /health handler
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── auth.py             # Authentication logic
│   │   ├── storage.py          # DynamoDB/S3 operations
│   │   ├── validation.py       # Schema validation
│   │   └── utils.py            # Helper functions
│   └── models/
│       ├── __init__.py
│       └── schemas.py          # Pydantic models
├── tests/
│   ├── unit/
│   │   ├── test_ingest.py
│   │   ├── test_inbox.py
│   │   └── test_ack.py
│   ├── integration/
│   │   └── test_api_flow.py
│   └── load/
│       └── ingest-load.js
├── config/
│   ├── dev.yaml
│   └── prod.yaml
├── docs/
│   ├── openapi.yaml
│   └── API.md
├── .github/
│   └── workflows/
│       └── deploy.yml
├── template.yaml              # SAM template
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Dev dependencies
├── pytest.ini                 # Pytest config
├── .pylintrc                  # Linting config
└── README.md                  # Project documentation
```

---

**Document Status:** Final for MVP Implementation  
**Implementation Ready:** Yes - All technical specifications defined  
**Next Steps:** Begin development using this specification with Cursor/Claude Code
