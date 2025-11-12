# Zapier Triggers API - Product Requirements Document

**Version:** 1.0  
**Date:** November 11, 2025  
**Organization:** Zapier  
**Project ID:** K1oUUDeoZrvJkVZafqHL_1761943818847  
**Document Type:** Product Requirements (PRD 1 of 2)

---

## 1. Executive Summary

The Zapier Triggers API is a unified, serverless REST API that enables real-time, event-driven automation on the Zapier platform. This MVP provides a public, reliable, and developer-friendly interface for any system to send events into Zapier, allowing users to create workflows that react to events in real time rather than relying solely on scheduled or manual triggers.

**Core Value Proposition:**
- **For Developers:** Send events via simple REST API with minimal integration effort
- **For Automation Specialists:** Build workflows that automatically react to incoming events
- **For Business Analysts:** Access real-time event data for trend analysis and process optimization

**MVP Scope:** Pull-based event delivery with durable storage, focusing on simplicity and reliability over advanced features.

---

## 2. Problem Statement

Currently, triggers in Zapier are defined within individual integrations, creating several limitations:

**Current Challenges:**
1. **Limited Flexibility:** Each integration must implement its own trigger mechanism
2. **Scalability Constraints:** No centralized method to accept events from diverse sources
3. **Real-Time Gaps:** Scheduled polling introduces latency and resource inefficiency
4. **Developer Friction:** High barrier to entry for new integrations

**Impact:**
- Developers spend excessive time on boilerplate trigger code
- Real-time use cases are difficult or impossible to implement
- Platform growth is constrained by integration complexity

---

## 3. Goals & Success Metrics

**Primary Goal:** Reliable prototype for event ingestion, storage, and delivery with demonstrable latency improvements.

| Category | Target Metric |
|----------|---------------|
| **Reliability** | 99.9% ingestion success, zero data loss, <0.1% error rate |
| **Performance** | <100ms ingestion (P95), <200ms retrieval (P95), 50% latency reduction vs polling |
| **Developer Experience** | 4+/5 satisfaction, <30min to first event, <5% need support |
| **Adoption** | 10% integration adoption in 6mo, 50+ beta testers, 5+ production integrations in month 1 |

---

## 4. Target Users & Personas

**Integration Developer (Primary):** Backend dev building Zapier integrations; needs simple auth, reliable delivery, clear errors, minimal setup.

**Automation Specialist (Secondary):** Technical business user; needs instant event reactions, visibility, reliable execution.

**Business Analyst (Tertiary):** Data-driven decision maker; needs real-time metrics, event trend analysis, analytics integration.

---

## 5. User Stories

### Critical Path (P0)

**Story 1: Event Ingestion**
```
As an Integration Developer
I want to send events to Zapier via a simple REST API
So that I can integrate my application with minimal effort
```
**Acceptance Criteria:**
- API accepts POST requests with JSON payloads
- Returns acknowledgment with event ID within 100ms
- Handles errors gracefully with clear messages
- Supports payloads up to 10MB

**Story 2: Event Retrieval**
```
As an Integration Developer
I want to retrieve undelivered events from an inbox
So that my workflows can process events reliably
```
**Acceptance Criteria:**
- GET /inbox returns paginated list of pending events
- Supports filtering by timestamp range and event type
- Returns events in order of creation
- Includes pagination cursors for large result sets

**Story 3: Event Acknowledgment**
```
As an Integration Developer
I want to acknowledge processed events
So that they don't get delivered multiple times
```
**Acceptance Criteria:**
- POST /inbox/ack accepts batch of event IDs
- Updates event status to acknowledged
- Returns success/failure for each event
- Is idempotent (safe to retry)

### Enhanced Experience (P1)

**Story 4: Event Lease Management**
```
As an Integration Developer
I want events to automatically become available again if not acknowledged
So that transient failures don't result in lost events
```
**Acceptance Criteria:**
- Events fetched from inbox have 5-minute lease
- Un-acknowledged events reappear after lease expires
- Attempt count tracks delivery retries
- Prevents duplicate processing during lease period

**Story 5: API Health Monitoring**
```
As a Platform Administrator
I want to monitor API health and performance
So that I can ensure reliability for all users
```
**Acceptance Criteria:**
- /health endpoint reports system status
- CloudWatch metrics track latency and errors
- Dashboard visualizes key performance indicators
- Alerts trigger on threshold violations

### Nice to Have (P2)

**Story 6: Developer Testing**
```
As an Integration Developer
I want example code and interactive API documentation
So that I can integrate quickly without trial and error
```
**Acceptance Criteria:**
- Swagger UI provides interactive API exploration
- Python sample client demonstrates integration
- curl examples show common operations
- OpenAPI spec is complete and accurate

---

## 6. Functional Requirements

### P0: Must-Have (MVP)

#### FR-1: Event Ingestion Endpoint
**Endpoint:** `POST /events`

**Requirements:**
- Accept JSON payloads with required fields: `id`, `event_type`, `timestamp`, `data`
- Validate schema and return 400 for invalid requests
- Generate unique event ID if not provided
- **Enforce idempotency: reject duplicate event IDs with 409 Conflict**
- Store small payloads (<400KB) in DynamoDB
- Store large payloads (≥400KB) in S3 with reference in DynamoDB
- Return 201 with event ID on success
- Return structured error on failure
- Complete within 100ms (P95)

**Input Schema:**
```json
{
  "id": "evt_unique_identifier",          // optional, generated if missing
  "event_type": "resource.action.status",  // required, dot-notation
  "timestamp": "2025-11-11T15:30:45Z",     // required, ISO 8601
  "data": {                                // required, arbitrary JSON
    "key": "value"
  }
}
```

**Output Schema (Success):**
```json
{
  "id": "evt_abc123xyz789",
  "status": "accepted",
  "created_at": "2025-11-11T15:30:45.123Z"
}
```

#### FR-2: Event Persistence
**Requirements:**
- Store events durably in DynamoDB with 30-day TTL
- Use tenant_id (derived from API key) as partition key
- Store event metadata: id, type, timestamp, status, attempt_count
- Store small payloads inline in `data` field
- Store large payload references in `s3_key` field
- Enable automatic cleanup via DynamoDB TTL
- Ensure write durability (multi-AZ replication)

#### FR-3: Event Retrieval Endpoint
**Endpoint:** `GET /inbox`

**Requirements:**
- Return pending events for authenticated tenant
- Support cursor-based pagination (limit + next_cursor)
- **Enforce cursor TTL:** Reject cursors older than 24 hours with 400 Bad Request
- Filter by: timestamp range, event_type, status
- Exclude events with active leases (in_flight_until > now)
- Update events with 5-minute lease on retrieval
- Increment attempt_count for each retrieval
- Return events in created_at ascending order
- Complete within 200ms (P95)

**Query Parameters:**
```
limit=25                    // default 25, max 100
cursor=timestamp_id         // pagination cursor
after=2025-11-11T00:00:00Z  // filter events after timestamp
before=2025-11-11T23:59:59Z // filter events before timestamp
event_type=resource.action  // filter by exact event type
status=pending              // filter by status (pending/acknowledged)
```

**Output Schema:**
```json
{
  "events": [
    {
      "id": "evt_123",
      "event_type": "player.projection.created",
      "timestamp": "2025-11-11T15:30:45Z",
      "data": { "player_id": "12345" },
      "created_at": "2025-11-11T15:30:45.123Z",
      "attempt_count": 1
    }
  ],
  "pagination": {
    "next_cursor": "1699712345_evt_123",
    "has_more": true
  }
}
```

#### FR-4: Event Acknowledgment Endpoint
**Endpoint:** `POST /inbox/ack`

**Requirements:**
- Accept array of event IDs to acknowledge
- Update status to 'acknowledged' in DynamoDB
- Clear in_flight_until timestamp
- Validate events belong to authenticated tenant
- Return success/failure for each event ID
- Be idempotent (acknowledging twice is safe)
- Support batch size up to 100 events

**Input Schema:**
```json
{
  "event_ids": ["evt_123", "evt_456", "evt_789"]
}
```

**Output Schema:**
```json
{
  "acknowledged": ["evt_123", "evt_456"],
  "failed": [
    {
      "event_id": "evt_789",
      "error": "event not found or already acknowledged"
    }
  ]
}
```

#### FR-5: Health Check Endpoint
**Endpoint:** `GET /health`

**Requirements:**
- Return 200 if system is operational
- Check DynamoDB connectivity
- Check S3 connectivity
- Return degraded status if dependencies fail
- Include timestamp and version information
- Complete within 50ms

**Output Schema:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T15:30:45Z",
  "version": "1.0.0",
  "dependencies": {
    "dynamodb": "healthy",
    "s3": "healthy"
  }
}
```

### P1: Should-Have

#### FR-6: Lease Mechanism
**Requirements:**
- Set in_flight_until to now + 5 minutes when event retrieved
- Automatically make events available after lease expires
- Prevent concurrent delivery to same tenant
- Log warning when attempt_count exceeds 10
- Allow lease duration configuration via environment variable

#### FR-7: Structured Error Responses
**Requirements:**
- Return consistent error format for all failures
- Include error code, message, and details
- Use standard HTTP status codes appropriately
- Provide actionable error messages

**Error Schema:**
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

**Status Codes:**
- 200: Success (GET)
- 201: Created (POST /events)
- 400: Validation error
- 401: Authentication failed
- 404: Resource not found
- 409: Duplicate/idempotency conflict
- 422: Semantic validation error
- 429: Rate limit exceeded
- 500: Internal server error
- 503: Service unavailable

#### FR-8: API Documentation
**Requirements:**
- OpenAPI 3.1 specification
- Swagger UI for interactive testing
- **Comprehensive examples:** All endpoints include both success and error response examples
- Example requests and responses for all status codes (200, 201, 400, 401, 404, 409, 422, 500)
- Authentication documentation
- Error code reference with troubleshooting guidance

### P2: Nice-to-Have

#### FR-9: Sample Client
**Requirements:**
- Python client library with examples
- Demonstrates authentication, ingestion, retrieval, acknowledgment
- Includes error handling examples
- curl command examples for quick testing

#### FR-10: Metrics Dashboard
**Requirements:**
- CloudWatch dashboard with key metrics
- P50/P95/P99 latency charts
- Error rate graphs
- Event volume over time
- **Per-tenant metrics:** All metrics include TenantId dimension for isolation and debugging
- Event type distribution
- Storage pattern tracking (DynamoDB vs S3)

---

## 7. Non-Functional Requirements

### NFR-1: Performance
- **Ingestion Latency:** <100ms P95 response time
- **Retrieval Latency:** <200ms P95 response time
- **Throughput:** Support 1000+ events/second per tenant
- **Concurrency:** Handle 100+ simultaneous requests

### NFR-2: Reliability
- **Availability:** 99.9% uptime (8.76 hours downtime/year)
- **Data Durability:** 99.999999999% (11 nines via DynamoDB/S3)
- **Error Rate:** <0.1% of requests result in 5xx errors
- **Zero Data Loss:** All accepted events are persisted durably

### NFR-3: Scalability
- **Auto-Scaling:** Serverless components scale automatically
- **No Hard Limits:** Support unlimited tenants and events (within AWS quotas)
- **Storage Growth:** S3 and DynamoDB scale horizontally
- **Regional Expansion:** Architecture supports multi-region deployment

### NFR-4: Security
- **Authentication:** API key-based authentication for all endpoints
- **Encryption in Transit:** TLS 1.2+ for all API communication
- **Encryption at Rest:** Server-side encryption for DynamoDB and S3
- **Tenant Isolation:** Complete data isolation between tenants
- **API Key Security:** Keys hashed in database, never logged in plaintext
- **Input Validation:** Strict schema validation prevents injection attacks

### NFR-5: Maintainability
- **Code Quality:** Python type hints, linting (pylint, black)
- **Testing Coverage:** >80% unit test coverage
- **Logging:** Structured JSON logs for all operations
- **Monitoring:** CloudWatch metrics and alarms
- **Documentation:** Inline code documentation and API specs

### NFR-6: Compliance
- **Data Retention:** 30-day automatic deletion via TTL
- **GDPR Compliance:** Data deletion capabilities, tenant isolation
- **Audit Logging:** CloudWatch logs for all API operations
- **Data Residency:** Configurable AWS region deployment

---

## 8. User Experience & API Design Considerations

### Design Principles
1. **Simplicity:** Minimal required fields, clear naming conventions
2. **Predictability:** Consistent patterns across all endpoints
3. **Idempotency:** Safe to retry operations without side effects
4. **Discoverability:** Self-documenting via OpenAPI and examples
5. **Error Clarity:** Actionable error messages with specific guidance

### API Conventions
- **Base URL:** `https://api.zapier.com/triggers/v1`
- **Authentication:** Header-based `X-API-Key: {key}`
- **Content Type:** `application/json` for all requests/responses
- **Timestamps:** ISO 8601 format with timezone (UTC preferred)
- **IDs:** Prefixed strings (e.g., `evt_`, `tenant_`) for type safety
- **Pagination:** Cursor-based to handle large result sets efficiently
- **Filtering:** Query parameters with clear naming

### Developer Journey
1. **Registration:** User signs up → receives API key
2. **First Event:** Uses curl or sample client to send test event
3. **Verification:** Retrieves event from /inbox to confirm delivery
4. **Acknowledgment:** Acknowledges event to complete cycle
5. **Integration:** Integrates into production system
6. **Monitoring:** Uses dashboard to track performance

---

## 9. Testing Requirements

### Unit Testing
**Framework:** pytest with moto for AWS mocking

**Coverage Requirements:**
- >80% code coverage
- Test all validation logic
- Test error handling paths
- Test edge cases (empty lists, large payloads, expired leases)

**Focus Areas:**
- Input validation and schema enforcement
- Authentication and authorization logic
- Event lifecycle state transitions
- Pagination cursor generation and parsing
- Lease expiration logic
- Attempt counter incrementation

### Integration Testing
**Framework:** pytest with SAM Local or LocalStack

**Test Scenarios:**
- End-to-end event flow (ingest → retrieve → ack)
- Multi-tenant isolation (tenant A cannot see tenant B events)
- Large payload handling (S3 fallback)
- Lease timeout and redelivery
- Error handling and recovery
- Pagination with various page sizes
- Filtering by timestamp and event type

### Load Testing
**Framework:** k6

**Test Scenarios:**
- Ingestion load: 1000 events/second sustained
- Concurrent retrievals: 100 simultaneous /inbox requests
- Mixed workload: 70% ingest, 30% retrieve
- Large payload handling: 1MB+ events
- Burst traffic: 5000 events in 10 seconds

**Success Criteria:**
- <100ms P95 latency for /events under load
- <200ms P95 latency for /inbox under load
- <0.1% error rate under sustained load
- No data loss or corruption

### API Contract Testing
**Framework:** OpenAPI validation

**Requirements:**
- All responses match OpenAPI schema
- All documented endpoints are implemented
- All error codes are documented
- Example requests/responses are valid

---

## 10. Success Criteria

**Launch Readiness:** All P0 requirements implemented, >80% test coverage, integration/load tests passing, OpenAPI complete, Swagger UI live, Python client working, CloudWatch dashboard + alarms configured.

**Week 1:** 10+ integrations, zero critical bugs, 99%+ uptime, 4+/5 satisfaction, <10% support contacts.

**Month 1:** 50+ active developers, 5+ production integrations, 99.9% uptime, <100ms P95 latency maintained.

**Month 6:** 10% integration adoption, 50% latency reduction vs polling, 99.9% reliability, v2 features prioritized.

---

## 11. Appendix

### Out of Scope (MVP)
Push webhooks, SNS/SQS fan-out, advanced filtering/transformation, analytics dashboard, long-term archival, DLQ UI, rate limiting UI, webhook signatures, event replay, multi-region, custom leases, priority queuing, batch ingestion, GraphQL.

### Assumptions & Dependencies
- Developers familiar with REST/JSON
- AWS infrastructure available (API Gateway, Lambda, DynamoDB, S3, CloudWatch)
- 30-day retention sufficient for MVP
- API key auth acceptable
- Pull-based delivery meets initial needs

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| DynamoDB throttling | On-demand billing, exponential backoff |
| Lambda cold starts | Provision concurrency for critical functions |
| API key leakage | Hash keys, provide rotation mechanism |
| Cost overruns | AWS budgets, alerts, anomaly detection |

### Glossary
**Event:** Discrete occurrence as JSON. **Tenant:** Isolated namespace per API key. **Lease:** Temporary lock preventing duplicate delivery. **Acknowledgment:** Confirmation of successful processing. **Attempt Count:** Retrieval counter. **TTL:** Auto-expiration. **Cursor:** Pagination token. **Idempotent:** Safe to repeat.

---

**Document Status:** Final for MVP Implementation  
**Next Steps:** Review Technical Specification PRD (PRD 2 of 2)
