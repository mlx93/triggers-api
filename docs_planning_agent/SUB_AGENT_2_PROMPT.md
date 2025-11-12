# Sub-Agent 2: Authentication & Validation Agent - Prompt

**Date:** November 11, 2025  
**Agent:** Authentication & Validation Agent  
**Status:** Ready for Execution  
**Estimated Time:** ~2 hours

---

## Charter

Implement API key authentication, request validation, and Pydantic schema models that form the core validation layer for all API endpoints in the Zapier Triggers API MVP.

---

## Inputs

**Primary Sources of Truth (CRITICAL - Reference Extensively):**
- `PRD_Product_Reqs_v2.md` - Authentication requirements (Section 7), validation rules (Section 6), request/response schemas (Section 6), error schemas (FR-7), status codes (FR-7)
- `PRD_Tech_v2.md` - API key format (`ak_{32chars}`), hashing logic (SHA-256), DynamoDB API keys table schema (Section 4), validation patterns

**Supporting Documents:**
- `docs_planning_agent/OPEN_QUESTIONS.md` - Resolved decisions: API key format `ak_{32chars}`, tenant_id UUID v4, event_id `evt_{base64url}`, cursor format `{timestamp}_{event_id}`, event_type regex `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` (3-100 chars)
- `docs_planning_agent/SUB_AGENT_1_COMPLETION.md` - Confirms infrastructure ready: DynamoDB api-keys table exists, project structure in place, requirements.txt includes pydantic

**Key PRD Sections to Reference:**
- **PRD_Product_Reqs_v2.md Section 7:** Authentication (API key format, X-API-Key header, tenant_id extraction)
- **PRD_Product_Reqs_v2.md Section 6 FR-1:** Event Input Schema (id, event_type, timestamp, data fields)
- **PRD_Product_Reqs_v2.md Section 6 FR-3:** Inbox Query Parameters (limit, cursor, after, before, event_type, status)
- **PRD_Product_Reqs_v2.md Section 6 FR-4:** Ack Request Schema (event_ids array)
- **PRD_Product_Reqs_v2.md Section 6 FR-7:** Error Schema (code, message, details structure)
- **PRD_Tech_v2.md Section 4:** API Keys Table Schema (hashed_key, tenant_id, is_active)
- **PRD_Tech_v2.md Section 3:** Event Type Validation (dot-notation regex from OPEN_QUESTIONS.md Q9)

---

## Outputs

**Required Deliverables:**

1. **`src/lib/auth.py`** - Authentication module:
   - Function: `validate_api_key(api_key: str) -> dict` - Validates API key, returns tenant_id and metadata
   - Function: `extract_api_key_from_event(event: dict) -> str` - Extracts X-API-Key from Lambda event
   - Function: `hash_api_key(api_key: str) -> str` - SHA-256 hash of API key
   - DynamoDB lookup logic (query api-keys table by hashed_key)
   - Error handling: 401 Unauthorized for invalid/missing keys
   - Update last_used_at timestamp (async/background)

2. **`src/lib/validation.py`** - Validation module:
   - Function: `validate_event_type(event_type: str) -> bool` - Regex validation `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` (3-100 chars)
   - Function: `validate_timestamp(timestamp: str) -> bool` - ISO 8601 validation
   - Function: `validate_cursor(cursor: str) -> tuple` - Parse and validate cursor format `{timestamp}_{event_id}`, check 24-hour TTL
   - Function: `validate_payload_size(payload: dict) -> bool` - Check 10MB maximum (from OPEN_QUESTIONS.md Q8)
   - Function: `validate_event_id(event_id: str) -> bool` - Validate format `evt_{base64url_32chars}` (from OPEN_QUESTIONS.md Q3)
   - Function: `validate_tenant_id(tenant_id: str) -> bool` - Validate UUID v4 format (from OPEN_QUESTIONS.md Q2)

3. **`src/models/schemas.py`** - Pydantic models for all request/response schemas:
   - **EventInput** - POST /events request schema (id optional, event_type required, timestamp required ISO 8601, data required dict)
   - **EventOutput** - POST /events response schema (id, status="accepted", created_at)
   - **InboxQueryParams** - GET /inbox query parameters (limit default 25 max 100, cursor optional, after/before optional ISO 8601, event_type optional, status optional)
   - **InboxEvent** - Individual event in inbox response (id, event_type, timestamp, data, created_at, attempt_count)
   - **InboxResponse** - GET /inbox response schema (events array, pagination with next_cursor and has_more)
   - **AckRequest** - POST /inbox/ack request schema (event_ids array, max 100 items)
   - **AckFailure** - Failed acknowledgment item (event_id, error message)
   - **AckResponse** - POST /inbox/ack response schema (acknowledged array, failed array)
   - **HealthResponse** - GET /health response schema (status, timestamp, version, dependencies dict)
   - **ErrorResponse** - Structured error schema (error.code, error.message, error.details)
   - All models must match PRD schemas exactly (reference PRD_Product_Reqs_v2.md Section 6)

4. **`tests/unit/test_auth.py`** - Authentication unit tests:
   - Test valid API key lookup
   - Test invalid API key (401)
   - Test missing API key (401)
   - Test inactive API key (401)
   - Test tenant_id extraction
   - Test API key hashing (SHA-256)
   - Test last_used_at update
   - Use moto to mock DynamoDB api-keys table
   - Achieve >80% coverage

5. **`tests/unit/test_validation.py`** - Validation unit tests:
   - Test event_type validation (valid/invalid formats, length limits)
   - Test timestamp validation (valid/invalid ISO 8601)
   - Test cursor validation (valid format, expired cursor, invalid format)
   - Test payload size validation (10MB limit)
   - Test event_id validation (format `evt_{base64url}`)
   - Test tenant_id validation (UUID v4 format)
   - Test edge cases: empty strings, null values, wrong types
   - Achieve >80% coverage

---

## Dependencies

**Completed:**
- ✅ Sub-Agent 1: Project structure exists, requirements.txt includes pydantic, DynamoDB api-keys table defined in SAM template

**Note:** Sub-Agent 3 depends on your outputs (schemas, auth, validation), so complete your work before Sub-Agent 3 can proceed.

---

## Key Tasks

1. **Implement API Key Authentication (`src/lib/auth.py`):**
   - Create `hash_api_key()` function using SHA-256 (reference PRD_Tech_v2.md Section 4)
   - Create `extract_api_key_from_event()` to get X-API-Key header from Lambda event
   - Create `validate_api_key()` function that:
     - Hashes incoming API key
     - Queries DynamoDB api-keys table by hashed_key
     - Validates is_active flag
     - Returns tenant_id and metadata
     - Raises 401 Unauthorized for invalid/missing keys
   - Update last_used_at timestamp (can be async/background operation)
   - Handle edge cases: missing header, invalid format, inactive key

2. **Create Pydantic Schema Models (`src/models/schemas.py`):**
   - **EventInput:** id (optional, generated if missing), event_type (required, validated), timestamp (required ISO 8601), data (required dict)
   - **EventOutput:** id, status="accepted", created_at (ISO 8601)
   - **InboxQueryParams:** limit (default 25, max 100), cursor (optional), after/before (optional ISO 8601), event_type (optional), status (optional)
   - **InboxEvent:** id, event_type, timestamp, data, created_at, attempt_count
   - **InboxResponse:** events (array of InboxEvent), pagination (next_cursor, has_more)
   - **AckRequest:** event_ids (array, max 100 items, min 1)
   - **AckFailure:** event_id, error (string)
   - **AckResponse:** acknowledged (array of strings), failed (array of AckFailure)
   - **HealthResponse:** status ("healthy"/"degraded"/"unhealthy"), timestamp, version, dependencies (dict with dynamodb/s3 status)
   - **ErrorResponse:** error.code, error.message, error.details (optional dict)
   - Reference PRD_Product_Reqs_v2.md Section 6 for exact schema definitions

3. **Implement Event Type Validation (`src/lib/validation.py`):**
   - Regex pattern: `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` (from OPEN_QUESTIONS.md Q9)
   - Length: 3-100 characters
   - Format: dot-notation (namespace.resource.action minimum)
   - Return clear error message if validation fails

4. **Implement Timestamp Validation (`src/lib/validation.py`):**
   - ISO 8601 format validation
   - Parse and validate timestamp is valid datetime
   - Handle timezone-aware and timezone-naive formats
   - Return clear error message if validation fails

5. **Implement Cursor Validation (`src/lib/validation.py`):**
   - Parse cursor format: `{unix_timestamp}_{event_id}` (from OPEN_QUESTIONS.md Q4)
   - Validate timestamp component is within 24 hours (from PRD_Product_Reqs_v2.md FR-3)
   - Validate event_id component format
   - Return tuple: (is_valid: bool, parsed_data: dict or None, error: str or None)
   - Return 400 Bad Request for expired or malformed cursors

6. **Create Error Response Models:**
   - Implement structured error format matching PRD_Product_Reqs_v2.md FR-7
   - Error codes: VALIDATION_ERROR, AUTHENTICATION_ERROR, NOT_FOUND, CONFLICT, RATE_LIMIT_EXCEEDED, INTERNAL_ERROR, SERVICE_UNAVAILABLE
   - Include error.message and error.details (field-specific errors)

7. **Write Comprehensive Unit Tests:**
   - **test_auth.py:** Test all authentication scenarios (valid, invalid, missing, inactive keys)
   - **test_validation.py:** Test all validation functions (event_type, timestamp, cursor, payload size, event_id, tenant_id)
   - Use moto to mock DynamoDB for auth tests
   - Test edge cases: empty strings, null values, wrong types, boundary conditions
   - Achieve >80% code coverage for auth.py and validation.py
   - Use pytest fixtures for common test data

8. **Handle Edge Cases:**
   - Invalid API key format (doesn't match `ak_{32chars}`)
   - Expired cursors (>24 hours old)
   - Malformed cursors (wrong format)
   - Invalid event_type (doesn't match regex, wrong length)
   - Invalid timestamp (not ISO 8601, invalid date)
   - Payload size >10MB (reject with 413 Payload Too Large)

---

## Success Criteria

**All of the following must be true:**

- ✅ All Pydantic models match PRD schemas exactly (reference PRD_Product_Reqs_v2.md Section 6)
- ✅ Authentication logic extracts tenant_id correctly from API key
- ✅ API key validation returns 401 for invalid/missing/inactive keys
- ✅ Event type validation uses regex `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` with 3-100 char length
- ✅ Timestamp validation accepts ISO 8601 format
- ✅ Cursor validation checks 24-hour TTL and format `{timestamp}_{event_id}`
- ✅ Payload size validation enforces 10MB maximum
- ✅ Error responses use structured format (code, message, details)
- ✅ Unit tests achieve >80% coverage for auth.py and validation.py
- ✅ All tests pass (`pytest tests/unit/test_auth.py tests/unit/test_validation.py`)
- ✅ Code follows Python 3.12 best practices with type hints

---

## Implementation Guidelines

**CRITICAL: Reference PRDs Extensively**

- **API Key Format:** Use `ak_{32chars}` format from PRD_Tech_v2.md and OPEN_QUESTIONS.md Q1
- **Hashing:** SHA-256 hash as specified in PRD_Tech_v2.md Section 4
- **Tenant ID:** UUID v4 format from OPEN_QUESTIONS.md Q2
- **Event ID:** `evt_{base64url_32chars}` format from OPEN_QUESTIONS.md Q3
- **Event Type Regex:** `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` from OPEN_QUESTIONS.md Q9
- **Cursor Format:** `{unix_timestamp}_{event_id}` with 24-hour TTL from OPEN_QUESTIONS.md Q4
- **Error Schema:** Match PRD_Product_Reqs_v2.md FR-7 exactly
- **Status Codes:** Use mapping from PRD_Product_Reqs_v2.md FR-7 (400, 401, 404, 409, 422, 429, 500, 503)

**Code Quality:**
- Use Pydantic v2 for all schema models
- Add type hints to all functions
- Follow Python 3.12 best practices
- Use structured logging (prepare for Sub-Agent 4)
- Handle all edge cases gracefully

**Testing:**
- Use moto to mock DynamoDB for auth tests
- Test both happy path and error cases
- Achieve >80% coverage
- Use pytest fixtures for reusable test data

---

## Notes

- Your schemas will be imported by Sub-Agent 3 for handler implementations
- Your auth module will be imported by all handlers
- Your validation functions will be used by handlers for input validation
- Focus on correctness and completeness—Sub-Agent 3 depends on your work
- Ensure all Pydantic models are serializable to JSON (for API responses)
- Error messages should be clear and actionable for API consumers

---

## Completion Report Format

When you complete your work, provide a summary report that includes:

1. **Status:** ✅ Complete or ⚠️ Partial (with blockers)
2. **Deliverables Created:** List all files created with paths
3. **Test Results:** Coverage percentage and test pass/fail status
4. **Key Decisions:** Any implementation decisions made (e.g., error message wording)
5. **Blockers:** Any issues preventing completion
6. **Next Steps:** What Sub-Agent 3 needs to know (schemas available, auth ready, etc.)

---

**Document Status:** Ready for Sub-Agent 2 Execution  
**Next Step:** Sub-Agent 2 completes auth/validation, then Sub-Agent 3 (Storage & Handlers) can proceed

