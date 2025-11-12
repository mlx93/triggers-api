# Sub-Agent 3: Storage & Event Handlers Agent - Prompt

**Date:** November 11, 2025  
**Agent:** Storage & Event Handlers Agent  
**Status:** Ready for Execution  
**Estimated Time:** ~6 hours

---

## Charter

Implement DynamoDB/S3 storage operations and core Lambda handlers (POST /events, GET /inbox, POST /inbox/ack) that form the business logic layer for event ingestion, retrieval, and acknowledgment in the Zapier Triggers API MVP.

---

## Inputs

**Primary Sources of Truth (CRITICAL - Reference Extensively):**
- `PRD_Product_Reqs_v2.md` - Endpoint requirements (FR-1, FR-2, FR-3, FR-4), storage logic, idempotency rules, lease mechanism (FR-6), error handling (FR-7)
- `PRD_Tech_v2.md` - DynamoDB schema (Section 4), S3 operations (Section 5), handler logic (Section 3), partition/sort key formats, TTL configuration

**Dependencies (Must Be Complete First):**
- ✅ Sub-Agent 1: Infrastructure ready (DynamoDB tables, S3 bucket, Lambda functions defined in SAM template)
- ✅ Sub-Agent 2: Authentication (`src/lib/auth.py`), validation (`src/lib/validation.py`), Pydantic schemas (`src/models/schemas.py`) - **COMPLETE** (see SUB_AGENT_2_COMPLETION.md)

**Supporting Documents:**
- `docs_planning_agent/OPEN_QUESTIONS.md` - Resolved decisions: 30-day TTL (Q5), 5-minute leases (FR-6), 400KB S3 threshold, 10MB max payload (Q8), cursor format `{timestamp}_{event_id}` with 24-hour TTL (Q4), event_id format `evt_{base64url}` (Q3)
- `docs_planning_agent/SUB_AGENT_1_COMPLETION.md` - Confirms infrastructure: DynamoDB events table exists, S3 bucket exists, Lambda handlers are placeholders ready for replacement
- `docs_planning_agent/SUB_AGENT_2_COMPLETION.md` - **REVIEW THIS** - Confirms auth/validation complete with actual function names, import patterns, and implementation details

**Key PRD Sections to Reference:**
- **PRD_Product_Reqs_v2.md FR-1:** POST /events endpoint (idempotency, S3 fallback ≥400KB, 409 Conflict for duplicates)
- **PRD_Product_Reqs_v2.md FR-2:** Event Persistence (DynamoDB schema, partition key TENANT#{tenant_id}, sort key EVENT#{event_id}#{timestamp}, 30-day TTL)
- **PRD_Product_Reqs_v2.md FR-3:** GET /inbox endpoint (pagination, filters, cursor validation, lease mechanism, attempt_count)
- **PRD_Product_Reqs_v2.md FR-4:** POST /inbox/ack endpoint (batch acknowledgment, idempotent)
- **PRD_Product_Reqs_v2.md FR-6:** Lease Mechanism (5-minute in_flight_until, auto-return after expiry)
- **PRD_Tech_v2.md Section 3:** Handler Logic (detailed step-by-step for each endpoint)
- **PRD_Tech_v2.md Section 4:** DynamoDB Schema (exact attribute names, types, partition/sort key formats)
- **PRD_Tech_v2.md Section 5:** S3 Storage Strategy (bucket naming, object key pattern, lifecycle rules)

---

## Outputs

**Required Deliverables:**

1. **`src/lib/storage.py`** - Storage operations module:
   - Function: `store_event(tenant_id, event_data, payload_size) -> dict` - Store event in DynamoDB or S3 based on size threshold (400KB)
   - Function: `get_event(tenant_id, event_id) -> dict` - Retrieve event from DynamoDB (fetch S3 if s3_key present)
   - Function: `query_events(tenant_id, filters, cursor, limit) -> tuple` - Query DynamoDB with filters, pagination, lease updates
   - Function: `update_event_lease(tenant_id, event_id, lease_duration_minutes) -> bool` - Update in_flight_until and increment attempt_count
   - Function: `acknowledge_events(tenant_id, event_ids) -> dict` - Batch update events to acknowledged status, clear leases
   - Function: `check_idempotency(tenant_id, event_id) -> bool` - Check if event_id already exists (for conditional writes)
   - Function: `generate_cursor(timestamp, event_id) -> str` - Generate pagination cursor `{timestamp}_{event_id}`
   - Function: `parse_cursor(cursor) -> dict` - Parse cursor and validate 24-hour TTL
   - S3 operations: `put_large_payload(bucket, key, payload) -> str`, `get_large_payload(bucket, key) -> dict`
   - Handle S3 write failures gracefully (fallback to DynamoDB, log error, return success)

2. **`src/handlers/ingest.py`** - POST /events Lambda handler:
   - Replace placeholder with full implementation
   - Extract API key from event, validate via `auth.validate_api_key()`
   - Parse and validate request body using `EventInput` Pydantic model
   - Generate event_id if not provided (format `evt_{base64url}` using secrets.token_urlsafe(24))
   - Check payload size, route to DynamoDB (<400KB) or S3 (≥400KB)
   - Enforce idempotency: conditional write, return 409 Conflict if duplicate
   - Handle S3 write failures: fallback to DynamoDB, log error, still return 201
   - Return `EventOutput` response with 201 status
   - Handle all error cases: 400 Validation, 401 Unauthorized, 409 Conflict, 413 Payload Too Large, 500 Internal Error

3. **`src/handlers/inbox.py`** - GET /inbox Lambda handler:
   - Replace placeholder with full implementation
   - Extract API key, validate via `auth.validate_api_key()`
   - Parse query parameters using `InboxQueryParams` Pydantic model
   - Validate cursor (if provided): parse format, check 24-hour TTL, return 400 if expired/invalid
   - Query DynamoDB: filter by tenant_id, status=pending, exclude active leases (in_flight_until > now)
   - Apply filters: event_type, timestamp range (after/before), status
   - Update events: set in_flight_until = now + 5 minutes, increment attempt_count
   - Fetch S3 payloads if s3_key present
   - Generate next_cursor if has_more
   - Return `InboxResponse` with events array and pagination
   - Handle all error cases: 400 Bad Request (invalid cursor), 401 Unauthorized, 500 Internal Error

4. **`src/handlers/ack.py`** - POST /inbox/ack Lambda handler:
   - Replace placeholder with full implementation
   - Extract API key, validate via `auth.validate_api_key()`
   - Parse request body using `AckRequest` Pydantic model (validate max 100 event_ids)
   - For each event_id: validate belongs to tenant, update status to acknowledged, clear in_flight_until
   - Use conditional updates (idempotent: safe to acknowledge twice)
   - Return `AckResponse` with acknowledged and failed arrays
   - Handle all error cases: 400 Validation, 401 Unauthorized, 500 Internal Error

5. **`tests/unit/test_storage.py`** - Storage operation unit tests:
   - Test DynamoDB write operations (small payloads <400KB)
   - Test S3 write operations (large payloads ≥400KB)
   - Test S3 write failure fallback to DynamoDB
   - Test idempotency checking (duplicate event_id detection)
   - Test query operations (filters, pagination, cursor)
   - Test lease updates (in_flight_until, attempt_count increment)
   - Test batch acknowledgment (success and failure cases)
   - Test cursor generation and parsing
   - Use moto to mock DynamoDB and S3
   - Achieve >80% coverage

6. **`tests/unit/test_ingest.py`** - Ingestion handler unit tests:
   - Test successful event ingestion (small payload)
   - Test successful event ingestion (large payload → S3)
   - Test idempotency (duplicate event_id → 409 Conflict)
   - Test validation errors (400 Bad Request)
   - Test authentication errors (401 Unauthorized)
   - Test payload size limit (413 Payload Too Large)
   - Test S3 write failure fallback
   - Test event_id generation when not provided
   - Use moto to mock AWS services
   - Achieve >80% coverage

7. **`tests/unit/test_inbox.py`** - Inbox handler unit tests:
   - Test successful retrieval (no filters)
   - Test filtering (event_type, timestamp range, status)
   - Test pagination (cursor, limit)
   - Test cursor validation (valid, expired, malformed)
   - Test lease mechanism (events excluded during lease, reappear after expiry)
   - Test attempt_count increment
   - Test S3 payload retrieval
   - Test authentication errors (401 Unauthorized)
   - Use moto to mock AWS services
   - Achieve >80% coverage

8. **`tests/unit/test_ack.py`** - Acknowledgment handler unit tests:
   - Test successful batch acknowledgment
   - Test partial success (some events fail)
   - Test idempotency (acknowledging twice is safe)
   - Test tenant isolation (cannot acknowledge other tenant's events)
   - Test validation errors (400 Bad Request, max 100 event_ids)
   - Test authentication errors (401 Unauthorized)
   - Use moto to mock AWS services
   - Achieve >80% coverage

---

## Dependencies

**Completed:**
- ✅ Sub-Agent 1: Infrastructure ready (DynamoDB tables, S3 bucket, Lambda functions in SAM template)
- ✅ Sub-Agent 2: Authentication (`src/lib/auth.py`), validation (`src/lib/validation.py`), schemas (`src/models/schemas.py`)

**Note:** Sub-Agent 4 depends on your handlers being complete (needs to add metrics/logging).

---

## Key Tasks

1. **Implement DynamoDB Storage Operations (`src/lib/storage.py`):**
   - **store_event():** Write event to DynamoDB with conditional write (reject duplicates → idempotency)
   - Use partition key: `TENANT#{tenant_id}`, sort key: `EVENT#{event_id}#{timestamp}` (from PRD_Tech_v2.md Section 4)
   - Set TTL attribute: `ttl` = now + 30 days (from OPEN_QUESTIONS.md Q5)
   - Store small payloads (<400KB) inline in `data` field, set `s3_key=null`
   - Store large payloads (≥400KB) reference in `s3_key` field, set `data=null`
   - Handle conditional write failures (409 Conflict for duplicates)

2. **Implement S3 Storage Operations (`src/lib/storage.py`):**
   - **put_large_payload():** Write payload to S3 with key pattern `events/{tenant_id}/{event_id}.json`
   - **get_large_payload():** Read payload from S3 using s3_key
   - Handle S3 write failures gracefully: log error, store event in DynamoDB with `s3_key=null`, return success (from OPEN_QUESTIONS.md Q5)
   - Use SSE-S3 encryption (default)

3. **Implement GET /inbox Query Logic (`src/lib/storage.py`):**
   - **query_events():** Query DynamoDB by partition key `TENANT#{tenant_id}`
   - Filter: status=pending, exclude events where in_flight_until > now (active leases)
   - Apply filters: event_type (exact match), timestamp range (after/before), status
   - Sort by created_at ascending (use sort key timestamp component)
   - Limit results to query parameter limit (default 25, max 100)
   - Parse cursor if provided: validate format `{timestamp}_{event_id}`, check 24-hour TTL
   - Update events: set in_flight_until = now + 5 minutes, increment attempt_count
   - Return events array and next_cursor (if has_more)

4. **Implement Lease Mechanism (`src/lib/storage.py`):**
   - **update_event_lease():** Set in_flight_until = now + 5 minutes (from PRD_Product_Reqs_v2.md FR-6)
   - Increment attempt_count on each retrieval
   - Events with active leases (in_flight_until > now) are excluded from queries
   - After lease expires, events automatically reappear in inbox

5. **Implement POST /inbox/ack Batch Updates (`src/lib/storage.py`):**
   - **acknowledge_events():** Batch update multiple events
   - For each event_id: validate belongs to tenant, update status to acknowledged, clear in_flight_until
   - Use conditional updates (idempotent: safe to acknowledge twice)
   - Return acknowledged array (successful) and failed array (with error messages)

6. **Implement Cursor Generation and Parsing (`src/lib/storage.py`):**
   - **generate_cursor():** Create cursor `{unix_timestamp}_{event_id}` (from OPEN_QUESTIONS.md Q4)
   - **parse_cursor():** Parse cursor, validate format, check timestamp is within 24 hours
   - Return error if cursor expired or malformed

7. **Implement POST /events Handler (`src/handlers/ingest.py`):**
   - Replace placeholder with full implementation
   - Use `get_tenant_id_from_event(event)` from `src.lib.auth` to extract tenant_id (handles auth automatically)
   - Catch `AuthenticationError` from `src.lib.auth` for 401 responses
   - Parse request body using `EventInput` Pydantic model (validation happens automatically)
   - Use `get_payload_size_bytes(payload)` from `src.lib.validation` to check payload size
   - Generate event_id if not provided: `evt_{secrets.token_urlsafe(24)}` (from OPEN_QUESTIONS.md Q3)
   - Check payload size: <400KB → DynamoDB, ≥400KB → S3
   - Enforce idempotency: conditional write, return 409 Conflict if duplicate event_id
   - Handle S3 write failures: fallback to DynamoDB, log error, return 201 (event persisted)
   - Return `EventOutput` response with 201 Created status
   - Use `ErrorResponse.create(ErrorCode.VALIDATION_ERROR, ...)` for structured error responses
   - Handle errors: 400 Validation, 401 Unauthorized, 409 Conflict, 413 Payload Too Large, 500 Internal Error

8. **Implement GET /inbox Handler (`src/handlers/inbox.py`):**
   - Replace placeholder with full implementation
   - Use `get_tenant_id_from_event(event)` from `src.lib.auth` to extract tenant_id
   - Catch `AuthenticationError` for 401 responses
   - Parse query parameters using `InboxQueryParams` Pydantic model (validation happens automatically)
   - Use `validate_cursor(cursor)` from `src.lib.validation` to validate cursor format and 24-hour TTL
   - Query DynamoDB via `storage.query_events()` with filters
   - Fetch S3 payloads if s3_key present
   - Generate next_cursor if has_more events
   - Return `InboxResponse` with events array and `PaginationInfo` (pagination object)
   - Handle errors: 400 Bad Request (invalid cursor), 401 Unauthorized, 500 Internal Error

9. **Implement POST /inbox/ack Handler (`src/handlers/ack.py`):**
   - Replace placeholder with full implementation
   - Use `get_tenant_id_from_event(event)` from `src.lib.auth` to extract tenant_id
   - Catch `AuthenticationError` for 401 responses
   - Parse request body using `AckRequest` Pydantic model (validation happens automatically, max 100 event_ids)
   - Call `storage.acknowledge_events()` for batch updates
   - Return `AckResponse` with acknowledged and failed arrays
   - Handle errors: 400 Validation, 401 Unauthorized, 500 Internal Error

10. **Write Comprehensive Unit Tests:**
    - **test_storage.py:** Test all storage operations (DynamoDB, S3, queries, leases, acknowledgment)
    - **test_ingest.py:** Test POST /events handler (happy path, idempotency, validation, errors)
    - **test_inbox.py:** Test GET /inbox handler (filters, pagination, cursor, leases)
    - **test_ack.py:** Test POST /inbox/ack handler (batch acknowledgment, idempotency, errors)
    - Use moto to mock DynamoDB and S3
    - Test both happy path and error cases
    - Achieve >80% code coverage for all handlers and storage module
    - Use pytest fixtures for common test data

---

## Success Criteria

**All of the following must be true:**

- ✅ All handlers match PRD endpoint specifications (reference PRD_Product_Reqs_v2.md Section 6)
- ✅ POST /events enforces idempotency (duplicate event_id returns 409 Conflict)
- ✅ POST /events routes large payloads (≥400KB) to S3, small payloads (<400KB) to DynamoDB
- ✅ POST /events handles S3 write failures gracefully (fallback to DynamoDB, return 201)
- ✅ GET /inbox filters events correctly (event_type, timestamp range, status)
- ✅ GET /inbox implements pagination with cursor validation (24-hour TTL)
- ✅ GET /inbox implements lease mechanism (5-minute in_flight_until, attempt_count increment)
- ✅ GET /inbox excludes events with active leases, events reappear after expiry
- ✅ POST /inbox/ack supports batch acknowledgment (up to 100 events)
- ✅ POST /inbox/ack is idempotent (safe to acknowledge twice)
- ✅ Storage operations handle DynamoDB/S3 correctly
- ✅ Cursor generation/parsing works correctly (`{timestamp}_{event_id}` format, 24-hour TTL)
- ✅ Unit tests cover happy path and error cases
- ✅ Unit tests achieve >80% coverage for handlers and storage module
- ✅ All tests pass (`pytest tests/unit/test_storage.py tests/unit/test_ingest.py tests/unit/test_inbox.py tests/unit/test_ack.py`)

---

## Implementation Guidelines

**CRITICAL: Reference PRDs Extensively**

- **DynamoDB Schema:** Use exact attribute names from PRD_Tech_v2.md Section 4 (pk, sk, id, event_type, timestamp, tenant_id, status, in_flight_until, attempt_count, s3_key, data, created_at, ttl)
- **Partition/Sort Keys:** `TENANT#{tenant_id}` and `EVENT#{event_id}#{timestamp}` from PRD_Tech_v2.md Section 4
- **S3 Threshold:** 400KB from PRD_Product_Reqs_v2.md FR-1 and OPEN_QUESTIONS.md Q8
- **Max Payload:** 10MB from OPEN_QUESTIONS.md Q8
- **TTL:** 30 days from OPEN_QUESTIONS.md Q5
- **Lease Duration:** 5 minutes from PRD_Product_Reqs_v2.md FR-6
- **Cursor Format:** `{unix_timestamp}_{event_id}` with 24-hour TTL from OPEN_QUESTIONS.md Q4
- **Event ID Format:** `evt_{base64url_32chars}` from OPEN_QUESTIONS.md Q3
- **Idempotency:** Conditional writes, return 409 Conflict for duplicates from PRD_Product_Reqs_v2.md FR-1
- **S3 Failure Handling:** Fallback to DynamoDB, log error, return 201 from OPEN_QUESTIONS.md Q5

**Code Quality:**
- Import and use Sub-Agent 2's schemas, auth, and validation modules (see SUB_AGENT_2_COMPLETION.md for exact import patterns)
- Use boto3 for DynamoDB and S3 operations
- Add type hints to all functions
- Follow Python 3.12 best practices
- Use structured logging (prepare for Sub-Agent 4)
- Handle all error cases gracefully
- Return proper HTTP status codes and error responses

**Testing:**
- Use moto to mock DynamoDB and S3
- Test both happy path and error cases
- Test idempotency, lease mechanism, cursor validation
- Achieve >80% coverage
- Use pytest fixtures for reusable test data

---

## Notes

- Replace placeholder handlers created by Sub-Agent 1
- **Import Sub-Agent 2's modules using these exact patterns:**
  ```python
  from src.lib.auth import get_tenant_id_from_event, AuthenticationError
  from src.lib.validation import (
      validate_cursor, get_payload_size_bytes, validate_event_type, validate_timestamp
  )
  from src.models.schemas import (
      EventInput, EventOutput, InboxQueryParams, InboxResponse, PaginationInfo,
      AckRequest, AckResponse, HealthResponse, ErrorResponse, ErrorCode
  )
  ```
- **Use convenience functions:** Prefer `get_tenant_id_from_event(event)` over calling `validate_api_key()` directly
- **Use helper functions:** Use `get_payload_size_bytes(payload)` for size checks
- **Error handling:** Catch `AuthenticationError` for 401 responses, use `ErrorResponse.create(ErrorCode.XXX, ...)` for structured errors
- **Pagination:** `InboxResponse` uses `PaginationInfo` model for pagination object
- Your handlers will be instrumented by Sub-Agent 4 (metrics/logging)
- Focus on correctness: idempotency, lease mechanism, cursor validation are critical
- Ensure all handlers return proper Lambda response format (statusCode, body, headers)
- Error responses must use Sub-Agent 2's ErrorResponse schema

---

## Completion Report Format

When you complete your work, provide a summary report that includes:

1. **Status:** ✅ Complete or ⚠️ Partial (with blockers)
2. **Deliverables Created:** List all files created/modified with paths
3. **Test Results:** Coverage percentage and test pass/fail status for each test file
4. **Key Decisions:** Any implementation decisions made (e.g., error handling approach)
5. **Blockers:** Any issues preventing completion
6. **Next Steps:** What Sub-Agent 4 needs to know (handlers ready for instrumentation, etc.)

---

**Document Status:** Ready for Sub-Agent 3 Execution  
**Next Step:** Sub-Agent 3 completes handlers, then Sub-Agent 4 (Health & Observability) can proceed

