# System Patterns: Architecture & Design Decisions

**Date:** November 11, 2025  
**Status:** Patterns Established

---

## Architecture Patterns

### Serverless Architecture
- **Pattern:** AWS Lambda + API Gateway + DynamoDB + S3
- **Rationale:** Zero infrastructure management, auto-scaling, pay-per-use
- **Implementation:** SAM template defines all resources, Lambda functions are stateless

### Multi-Tenant Isolation
- **Pattern:** Tenant isolation via DynamoDB partition keys
- **Implementation:** Partition key format `TENANT#{tenant_id}`, API keys scoped to single tenant
- **Security:** No cross-tenant data access, tenant_id extracted from API key

### Event-Driven Design
- **Pattern:** Asynchronous processing, decoupled components
- **Implementation:** Lambda functions invoke DynamoDB/S3, no direct function-to-function calls
- **Future:** DynamoDB Streams for event processing extensions

---

## Data Storage Patterns

### DynamoDB Schema Design
- **Partition Key:** `TENANT#{tenant_id}` - Ensures tenant isolation
- **Sort Key:** `EVENT#{event_id}#{timestamp}` - Enables time-ordered queries
- **TTL:** 30-day expiration on `ttl` attribute
- **Billing:** On-Demand (auto-scaling)

### S3 Storage Strategy
- **Threshold:** 400KB (payloads ≥400KB stored in S3, <400KB inline in DynamoDB)
- **Object Key Pattern:** `events/{tenant_id}/{event_id}.json`
- **Lifecycle:** 30-day deletion (matches DynamoDB TTL)
- **Encryption:** SSE-S3 (AES256)

### Idempotency Pattern
- **Current:** Query-then-insert (not atomic, acceptable for MVP)
- **Implementation:** Check for existing event_id before insertion, return 409 Conflict if duplicate
- **Future Enhancement:** Use GSI on event_id for atomic conditional writes

---

## Authentication & Authorization Patterns

### API Key Authentication
- **Format:** `ak_{32chars}` (35 characters total)
- **Storage:** SHA-256 hash in DynamoDB `api-keys` table
- **Lookup:** Hash incoming key, query DynamoDB by `hashed_key`
- **Tenant Extraction:** API key → tenant_id mapping stored in api-keys table

### Error Handling Pattern
- **Structured Errors:** ErrorResponse schema with code, message, details
- **Status Codes:** 400 (Validation), 401 (Unauthorized), 409 (Conflict), 413 (Payload Too Large), 500 (Internal Error)
- **Enhancement Opportunity:** Add field-level validation errors and specific error codes

---

## Handler Patterns

### Request Processing Flow
1. Extract API key from event → validate → extract tenant_id
2. Parse and validate request body/query params using Pydantic models
3. Execute business logic (storage operations)
4. Return structured response (success or error)

### Error Handling Flow
1. Catch exceptions (AuthenticationError, ValidationError, etc.)
2. Create ErrorResponse with appropriate code and message
3. Return Lambda response with statusCode and JSON body
4. Log error with context (tenant_id, event_id, error details)

### Lease Mechanism Pattern
- **Duration:** 5 minutes (`in_flight_until` timestamp)
- **Update:** Set `in_flight_until = now + 5 minutes` on retrieval
- **Exclusion:** Events with `in_flight_until > now` excluded from queries
- **Auto-Return:** Events automatically reappear after lease expires
- **Tracking:** `attempt_count` increments on each retrieval

---

## Testing Patterns

### Unit Testing
- **Framework:** pytest
- **Mocking:** moto (mock_aws) for DynamoDB and S3
- **Coverage Target:** >80% (currently ~85%)
- **Test Structure:** One test file per module, fixtures for reusable test data

### Test Organization
- `tests/unit/test_auth.py` - Authentication tests (27 tests)
- `tests/unit/test_validation.py` - Validation tests (58 tests)
- `tests/unit/test_storage.py` - Storage operation tests (25 tests)
- `tests/unit/test_ingest.py` - Ingestion handler tests (15 tests)
- `tests/unit/test_inbox.py` - Inbox handler tests (12 tests)
- `tests/unit/test_ack.py` - Acknowledgment handler tests (13 tests)

---

## Code Organization Patterns

### Directory Structure
```
src/
  handlers/     # Lambda handler functions
  lib/          # Shared libraries (auth, validation, storage, metrics, logging)
  models/       # Pydantic schema models
tests/
  unit/         # Unit tests
  integration/  # Integration tests (pending)
  load/         # Load tests (pending)
config/         # Environment configuration files
```

### Module Responsibilities
- **handlers/:** Lambda entry points, request/response handling
- **lib/auth.py:** API key authentication, tenant_id extraction
- **lib/validation.py:** Input validation functions
- **lib/storage.py:** DynamoDB/S3 operations, lease management
- **models/schemas.py:** Pydantic models for all request/response schemas

---

## Validation Patterns

### Input Validation
- **Schema Level:** Pydantic models with field validators
- **Function Level:** Validation functions for complex rules (event_type regex, cursor format)
- **Error Format:** Structured ErrorResponse with code, message, details

### Validation Rules
- **Event Type:** Regex `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` (3-100 chars, dot-notation)
- **Timestamp:** ISO 8601 format (timezone-aware or naive)
- **Cursor:** Format `{unix_timestamp}_{event_id}` with 24-hour TTL
- **Payload Size:** 10MB maximum
- **Event ID:** Format `evt_{base64url_32chars}`

---

## Logging Patterns

### Current (Basic)
- **Format:** Standard Python logging (logger.info, logger.error)
- **Context:** tenant_id, event_id logged in handlers
- **Enhancement:** Sub-Agent 4 will add structured JSON logging

### Future (Structured JSON)
- **Format:** JSON logs with python-json-logger
- **Context Fields:** event_id, tenant_id, event_type, payload_size, storage_type
- **Purpose:** CloudWatch Logs Insights queryable, better correlation

---

## Metrics Patterns

### Planned (Sub-Agent 4)
- **Namespace:** `ZapierTriggers`
- **Dimensions:** TenantId, EventType (when applicable), Environment
- **Key Metrics:** EventIngested, InboxRetrieved, EventAcknowledged, EventLatency
- **Latency:** P50/P95/P99 percentiles (calculated by CloudWatch)

---

## Deployment Patterns

### CI/CD Pipeline
- **Trigger:** Push to `develop` (dev deploy) or `main` (prod deploy with approval)
- **Stages:** Test → Validate → Deploy
- **Testing:** pytest, black, pylint
- **Deployment:** `sam deploy` with environment parameters

### Environment Configuration
- **Files:** `config/dev.yaml`, `config/prod.yaml`
- **Values:** Table names, bucket names, region, log level, API settings
- **Usage:** Loaded by Lambda functions via environment variables

---

**Document Status:** ✅ Complete  
**Last Updated:** November 11, 2025

