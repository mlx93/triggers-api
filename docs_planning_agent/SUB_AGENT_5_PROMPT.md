# Sub-Agent 5: Documentation & Testing Agent - Prompt

**Date:** November 11, 2025  
**Agent:** Documentation & Testing Agent  
**Status:** Ready for Execution  
**Estimated Time:** ~4 hours

---

## Charter

Create OpenAPI 3.1 specification, Swagger UI, integration tests, load tests, and comprehensive project documentation that complete the Zapier Triggers API MVP and enable developers to integrate with the API effectively.

---

## Inputs

**Primary Sources of Truth (CRITICAL - Reference Extensively):**
- `PRD_Product_Reqs_v2.md` - OpenAPI requirements (FR-8), example responses, all endpoint specifications, error codes, authentication documentation
- `PRD_Tech_v2.md` - OpenAPI 3.1 spec requirements, Swagger UI hosting (Section 7), API endpoint details (Section 3), schemas (Section 4)

**Dependencies (Must Be Complete First):**
- ✅ Sub-Agent 1: Infrastructure complete (all endpoints exist, API Gateway configured)
- ✅ Sub-Agent 2: All schemas available (EventInput, EventOutput, InboxResponse, AckRequest, AckResponse, HealthResponse, ErrorResponse)
- ✅ Sub-Agent 3: All handlers implemented (POST /events, GET /inbox, POST /inbox/ack)
- ✅ Sub-Agent 4: Health endpoint implemented, metrics/logging ready

**Supporting Documents:**
- `docs_planning_agent/SUB_AGENT_1_COMPLETION.md` - Infrastructure details, API Gateway routes
- `docs_planning_agent/SUB_AGENT_2_COMPLETION.md` - Schema details, validation rules
- `docs_planning_agent/SUB_AGENT_3_COMPLETION.md` - Handler implementation details, endpoint behavior
- `docs_planning_agent/SUB_AGENT_4_COMPLETION.md` - Health endpoint details, metrics/logging details
- `docs/cloudwatch-alarms.md` - CloudWatch alarms documentation (for API docs integration)
- `docs/cloudwatch-dashboard.md` - CloudWatch dashboard documentation (for API docs integration)

**Key PRD Sections to Reference:**
- **PRD_Product_Reqs_v2.md FR-8:** API Documentation requirements (OpenAPI 3.1, Swagger UI, comprehensive examples, all status codes)
- **PRD_Product_Reqs_v2.md FR-9:** Sample Client requirements (Python client, curl examples)
- **PRD_Product_Reqs_v2.md Section 6:** All endpoint specifications (FR-1 through FR-5), request/response schemas, error codes
- **PRD_Product_Reqs_v2.md Section 7:** Authentication requirements (API key format, X-API-Key header)
- **PRD_Tech_v2.md Section 7:** Swagger UI hosting (static S3 + CloudFront or API Gateway stage)
- **PRD_Tech_v2.md Section 3:** Handler logic and endpoint details

---

## Outputs

**Required Deliverables:**

1. **`docs/openapi.yaml`** - OpenAPI 3.1 specification:
   - All 4 endpoints: POST /events, GET /inbox, POST /inbox/ack, GET /health
   - All request/response schemas matching Sub-Agent 2's Pydantic models
   - All status codes: 200, 201, 400, 401, 404, 409, 413, 422, 429, 500, 503
   - Comprehensive examples for success and error cases
   - Authentication documentation (API key in X-API-Key header)
   - Error code reference with troubleshooting guidance
   - Server URLs (dev/prod environments)
   - Tags and descriptions for all endpoints

2. **`docs/swagger-ui/`** - Swagger UI static files (or hosting configuration):
   - Swagger UI HTML files configured to load OpenAPI spec
   - Custom branding (Zapier Triggers API)
   - Deep linking enabled
   - Standalone layout
   - OR: Documentation for hosting via API Gateway stage or S3 + CloudFront

3. **`tests/integration/test_api_flow.py`** - Integration tests:
   - End-to-end flow: ingest → retrieve → ack → verify
   - Multi-tenant isolation test
   - Large payload test (S3 storage)
   - Lease expiry test (events reappear after 5 minutes)
   - Idempotency test (duplicate event_id returns 409)
   - Cursor pagination test
   - Error handling tests (401, 400, 409, 413)
   - Use moto or sam local for testing

4. **`tests/load/ingest-load.js`** - k6 load test script:
   - Target: 1000 events/sec, 100 concurrent users
   - Performance target: <100ms P95 latency
   - Test scenarios: ingestion, retrieval, acknowledgment
   - Metrics collection (latency, error rate, throughput)
   - Ramp-up and steady-state phases

5. **`README.md`** - Project documentation:
   - Project overview and purpose
   - Quick start guide
   - Setup instructions (Python, SAM CLI, AWS configuration)
   - Local development guide (`sam local start-api`)
   - Deployment instructions (`sam deploy`)
   - Testing instructions (unit tests, integration tests, load tests)
   - API usage examples (curl commands)
   - Architecture overview
   - Contributing guidelines
   - Troubleshooting section

6. **`docs/API.md`** - API usage guide:
   - Authentication guide (API key format, header usage)
   - Endpoint documentation with examples
   - Request/response schemas
   - Error handling guide (all error codes explained)
   - Best practices
   - Rate limiting information
   - Monitoring and observability (CloudWatch metrics, logs, dashboard)

7. **`examples/python_client.py`** (Optional, P2):
   - Python client class with methods: `send_event()`, `get_inbox()`, `acknowledge()`
   - Handles authentication headers
   - Error handling examples
   - Usage examples in docstrings

---

## Dependencies

**Completed:**
- ✅ Sub-Agent 1: Infrastructure complete (all endpoints exist, API Gateway configured)
- ✅ Sub-Agent 2: All schemas available (12 Pydantic models matching PRD exactly)
- ✅ Sub-Agent 3: All handlers implemented and tested (145 unit tests passing)
- ✅ Sub-Agent 4: Health endpoint implemented, metrics/logging ready (164 total tests passing)

**Note:** This is the final sub-agent. After completion, Master Orchestrator will perform final integration testing and deployment.

---

## Key Tasks

1. **Create OpenAPI 3.1 Specification (`docs/openapi.yaml`):**
   - Define all 4 endpoints with correct paths, methods, and operation IDs
   - Include all request/response schemas (reference Sub-Agent 2's schemas.py for exact structure)
   - Add comprehensive examples:
     - Success cases: 200, 201 responses with example payloads
     - Error cases: 400, 401, 404, 409, 413, 422, 429, 500, 503 with example error responses
   - Document authentication: API key in X-API-Key header, format `ak_{32chars}`
   - Include all query parameters for GET /inbox (limit, cursor, after, before, event_type, status)
   - Document all response headers (Content-Type, etc.)
   - Add server URLs for dev/prod environments
   - Add tags, descriptions, and summaries for all endpoints
   - Validate spec in Swagger Editor or online validator

2. **Set Up Swagger UI (`docs/swagger-ui/` or hosting config):**
   - Option A: Create static Swagger UI files configured to load `docs/openapi.yaml`
   - Option B: Document hosting via API Gateway stage or S3 + CloudFront
   - Configure SwaggerUIBundle with:
     - API URL pointing to OpenAPI spec
     - Deep linking enabled
     - Standalone layout
     - Custom branding (Zapier Triggers API title/logo)
   - Test Swagger UI renders correctly with all endpoints

3. **Write Integration Tests (`tests/integration/test_api_flow.py`):**
   - **End-to-End Flow:** POST /events → GET /inbox → POST /inbox/ack → verify event acknowledged
   - **Multi-Tenant Isolation:** Verify tenant A cannot access tenant B's events
   - **Large Payload:** Test S3 storage for payloads ≥400KB
   - **Lease Expiry:** Test events reappear in inbox after 5-minute lease expires
   - **Idempotency:** Test duplicate event_id returns 409 Conflict
   - **Cursor Pagination:** Test pagination with cursor, verify 24-hour TTL validation
   - **Error Handling:** Test 401 (invalid API key), 400 (invalid cursor), 409 (duplicate event), 413 (payload too large)
   - Use moto for AWS mocking or sam local for real Lambda testing
   - Ensure tests are isolated and can run independently

4. **Create k6 Load Test Script (`tests/load/ingest-load.js`):**
   - **Target:** 1000 events/sec, 100 concurrent users
   - **Performance Target:** <100ms P95 latency for ingestion
   - **Scenarios:**
     - Ingestion load test (POST /events)
     - Retrieval load test (GET /inbox)
     - Acknowledgment load test (POST /inbox/ack)
   - **Metrics:** Collect latency (P50/P95/P99), error rate, throughput
   - **Phases:** Ramp-up (gradual increase), steady-state (sustained load)
   - Include proper authentication (API key in headers)
   - Handle rate limiting (429 responses)

5. **Write README (`README.md`):**
   - **Project Overview:** Purpose, value proposition, architecture overview
   - **Quick Start:** Minimal steps to get started
   - **Setup Instructions:**
     - Python 3.12+ installation
     - SAM CLI installation
     - AWS configuration
     - Docker setup (for sam local)
   - **Local Development:**
     - Virtual environment setup
     - Dependency installation
     - Running `sam local start-api`
     - Testing locally
   - **Deployment:**
     - First deployment (`sam deploy --guided`)
     - Subsequent deployments (`sam deploy`)
     - Environment configuration (dev/prod)
   - **Testing:**
     - Unit tests (`pytest tests/unit/`)
     - Integration tests (`pytest tests/integration/`)
     - Load tests (`k6 run tests/load/ingest-load.js`)
   - **API Usage:** Link to API.md or include basic examples
   - **Architecture:** High-level architecture diagram or description
   - **Contributing:** Guidelines for contributing
   - **Troubleshooting:** Common issues and solutions

6. **Write API Usage Guide (`docs/API.md`):**
   - **Authentication:**
     - API key format (`ak_{32chars}`)
     - X-API-Key header usage
     - How to obtain API keys (reference admin script)
   - **Endpoints:**
     - POST /events: Request/response examples, idempotency, S3 routing
     - GET /inbox: Query parameters, pagination, filters, lease mechanism
     - POST /inbox/ack: Batch acknowledgment, idempotency
     - GET /health: Status codes, dependency checks
   - **Error Handling:**
     - All error codes explained (400, 401, 404, 409, 413, 422, 429, 500, 503)
     - Error response format (ErrorResponse schema)
     - Troubleshooting guide for common errors
   - **Best Practices:**
     - Event ID generation
     - Pagination usage
     - Lease management
     - Error handling and retries
   - **Rate Limiting:** API Gateway throttling (1000 req/sec, 2000 burst)
   - **Monitoring:** CloudWatch metrics, logs, dashboard (reference Sub-Agent 4 docs)

7. **Create Python Sample Client (`examples/python_client.py`)** (Optional, P2):
   - Python class `ZapierTriggersClient` with methods:
     - `__init__(api_key, base_url)` - Initialize client with API key
     - `send_event(event_type, timestamp, data, event_id=None)` - POST /events
     - `get_inbox(limit=25, cursor=None, **filters)` - GET /inbox
     - `acknowledge(event_ids)` - POST /inbox/ack
     - `health_check()` - GET /health
   - Handles authentication (X-API-Key header)
   - Error handling (raises exceptions for 4XX/5XX errors)
   - JSON serialization/deserialization
   - Usage examples in docstrings
   - Example usage script

---

## Success Criteria

**All of the following must be true:**

- ✅ OpenAPI spec validates in Swagger Editor or online validator
- ✅ OpenAPI spec includes all 4 endpoints with correct schemas
- ✅ OpenAPI spec includes examples for all status codes (200, 201, 400, 401, 404, 409, 413, 422, 429, 500, 503)
- ✅ Swagger UI renders correctly with all endpoints visible and interactive
- ✅ Integration tests pass (end-to-end flow works: ingest → retrieve → ack)
- ✅ Integration tests cover: multi-tenant isolation, large payloads, lease expiry, idempotency, pagination
- ✅ Load tests meet performance targets (<100ms P95 for ingestion, 1000 events/sec)
- ✅ README is complete with setup, deployment, and usage instructions
- ✅ API.md includes comprehensive endpoint documentation and error handling guide
- ✅ Python sample client (if implemented) works correctly with examples

---

## Implementation Guidelines

**CRITICAL: Reference PRDs Extensively**

- **OpenAPI Spec:** Use PRD_Product_Reqs_v2.md FR-8 for requirements, include all examples from PRD Section 6
- **Schemas:** Match Sub-Agent 2's Pydantic models exactly (EventInput, EventOutput, InboxResponse, etc.)
- **Error Codes:** Include all status codes from PRD_Product_Reqs_v2.md FR-7 (400, 401, 404, 409, 413, 422, 429, 500, 503)
- **Authentication:** Document API key format `ak_{32chars}` and X-API-Key header per PRD_Product_Reqs_v2.md Section 7
- **Swagger UI:** Follow PRD_Tech_v2.md Section 7 for hosting configuration
- **Load Test Targets:** 1000 events/sec, <100ms P95 from PRD_Product_Reqs_v2.md Section 3

**Code Quality:**
- OpenAPI spec should be valid YAML and pass validation
- Integration tests should be isolated and repeatable
- Load tests should include proper ramp-up and steady-state phases
- Documentation should be clear, accurate, and actionable

**Testing:**
- Integration tests can use moto for AWS mocking or sam local for real Lambda testing
- Load tests should target actual deployed API or sam local endpoint
- Ensure tests are deterministic and don't depend on external state

---

## Notes

- **OpenAPI Spec:** Reference Sub-Agent 2's `src/models/schemas.py` for exact schema structures
- **Handler Details:** Reference Sub-Agent 3's completion report for endpoint behavior details
- **Health Endpoint:** Reference Sub-Agent 4's completion report for health endpoint details
- **Metrics/Logging:** Reference Sub-Agent 4's docs for CloudWatch integration details
- **Swagger UI:** Can be hosted statically (S3 + CloudFront) or via API Gateway stage - document approach
- **Integration Tests:** Can use moto (faster) or sam local (more realistic) - choose based on needs
- **Load Tests:** Should target deployed API for accurate performance measurement

---

## Completion Report Format

When you complete your work, provide a summary report that includes:

1. **Status:** ✅ Complete or ⚠️ Partial (with blockers)
2. **Deliverables Created:** List all files created with paths
3. **OpenAPI Validation:** Result of OpenAPI spec validation
4. **Test Results:** Integration test and load test results
5. **Key Decisions:** Any implementation decisions made (e.g., Swagger UI hosting approach, test framework choice)
6. **Blockers:** Any issues preventing completion
7. **Next Steps:** What Master Orchestrator needs to know (ready for final integration testing and deployment)

---

**Document Status:** Ready for Sub-Agent 5 Execution  
**Next Step:** Sub-Agent 5 completes documentation and testing, then Master Orchestrator performs final integration and deployment

