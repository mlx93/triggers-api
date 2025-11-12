# AGENT_FLOW.md
## Sub-Agent Orchestration Plan

**Date:** November 11, 2025  
**Purpose:** Define how work will be divided among sub-agents for Master Orchestrator  
**Total Sub-Agents:** 4-5 (as per requirements)

---

## Master Orchestrator Overview

The Master Orchestrator Agent coordinates sub-agents to implement the Triggers API MVP. Each sub-agent has a focused charter, clear inputs/outputs, and defined dependencies.

---

## Sub-Agent 1: Infrastructure & Core Setup Agent

**Charter:** Create SAM template, AWS infrastructure, project structure, and core configuration files.

**Inputs:**
- PRD_Tech_v2.md (architecture, SAM requirements)
- MANUAL_SETUP.md (AWS resource names, environment config)
- OPEN_QUESTIONS.md (default recommendations for config values)

**Outputs:**
- `template.yaml` (SAM template with API Gateway, Lambda functions, DynamoDB tables, S3 bucket)
- `requirements.txt` (Python dependencies: boto3, pydantic, aws-lambda-powertools)
- `requirements-dev.txt` (dev dependencies: pytest, moto, black, pylint)
- `config/dev.yaml` (development configuration)
- `config/prod.yaml` (production configuration)
- `.github/workflows/deploy.yml` (CI/CD pipeline)
- Project directory structure (`src/`, `tests/`, `docs/`)

**Dependencies:**
- None (first agent, creates foundation)

**Key Tasks:**
1. Create SAM template with 4 Lambda functions (ingest, inbox, ack, health)
2. Define DynamoDB tables (events, api-keys) with correct schema
3. Create S3 bucket configuration with lifecycle rules
4. Set up API Gateway HTTP API with routes
5. Configure IAM roles and permissions
6. Create environment variable mappings
7. Set up GitHub Actions workflow for CI/CD
8. Create project directory structure

**Success Criteria:**
- `sam validate` passes
- All AWS resources defined in template
- CI/CD workflow file created
- Project structure matches PRD file layout

---

## Sub-Agent 2: Authentication & Validation Agent

**Charter:** Implement API key authentication, request validation, and Pydantic schema models.

**Inputs:**
- PRD_Product_Reqs_v2.md (authentication requirements, validation rules)
- PRD_Tech_v2.md (API key format, hashing logic)
- OPEN_QUESTIONS.md (default recommendations for validation)

**Outputs:**
- `src/lib/auth.py` (API key validation, tenant_id extraction)
- `src/lib/validation.py` (schema validation, event_type regex, timestamp parsing)
- `src/models/schemas.py` (Pydantic models: EventInput, EventOutput, InboxResponse, AckRequest, etc.)
- `tests/unit/test_auth.py` (authentication tests)
- `tests/unit/test_validation.py` (schema validation tests)

**Dependencies:**
- Sub-Agent 1 (project structure, requirements.txt)

**Key Tasks:**
1. Implement API key hashing (SHA-256) and DynamoDB lookup
2. Create Pydantic models for all request/response schemas
3. Implement event_type validation (dot-notation, regex)
4. Implement timestamp validation (ISO 8601)
5. Create error response models (structured errors)
6. Write unit tests for auth and validation logic
7. Handle edge cases: invalid keys, malformed payloads, expired cursors

**Success Criteria:**
- All Pydantic models match PRD schemas
- Authentication logic extracts tenant_id correctly
- Validation rejects invalid inputs with clear errors
- Unit tests achieve >80% coverage for auth/validation

---

## Sub-Agent 3: Storage & Event Handlers Agent

**Charter:** Implement DynamoDB/S3 storage operations and core Lambda handlers (POST /events, GET /inbox, POST /inbox/ack).

**Inputs:**
- PRD_Product_Reqs_v2.md (endpoint requirements, storage logic)
- PRD_Tech_v2.md (DynamoDB schema, S3 operations, handler logic)
- Sub-Agent 2 outputs (auth, validation, schemas)

**Outputs:**
- `src/lib/storage.py` (DynamoDB operations, S3 operations, lease management)
- `src/handlers/ingest.py` (POST /events handler)
- `src/handlers/inbox.py` (GET /inbox handler)
- `src/handlers/ack.py` (POST /inbox/ack handler)
- `tests/unit/test_storage.py` (storage operation tests)
- `tests/unit/test_ingest.py` (ingestion handler tests)
- `tests/unit/test_inbox.py` (inbox handler tests)
- `tests/unit/test_ack.py` (acknowledgment handler tests)

**Dependencies:**
- Sub-Agent 1 (infrastructure, SAM template)
- Sub-Agent 2 (authentication, validation, schemas)

**Key Tasks:**
1. Implement DynamoDB write operations (conditional writes for idempotency)
2. Implement S3 PutObject/GetObject for large payloads (≥400KB threshold)
3. Implement GET /inbox query logic (filters, pagination, cursor validation)
4. Implement lease mechanism (5-minute in_flight_until, attempt_count increment)
5. Implement POST /inbox/ack batch updates (idempotent acknowledgment)
6. Handle S3 write failures gracefully (fallback to DynamoDB)
7. Implement cursor generation and parsing (24-hour TTL validation)
8. Write comprehensive unit tests with moto (AWS mocking)

**Success Criteria:**
- All handlers match PRD endpoint specifications
- Storage operations handle DynamoDB/S3 correctly
- Lease mechanism works (events reappear after expiry)
- Idempotency enforced (duplicate event IDs return 409)
- Unit tests cover happy path and error cases

---

## Sub-Agent 4: Health & Observability Agent

**Charter:** Implement health endpoint, CloudWatch metrics, logging, alarms, and dashboard.

**Inputs:**
- PRD_Product_Reqs_v2.md (health endpoint, monitoring requirements)
- PRD_Tech_v2.md (CloudWatch configuration, logging format)
- Sub-Agent 3 outputs (handlers to instrument)

**Outputs:**
- `src/handlers/health.py` (GET /health handler with dependency checks)
- `src/lib/metrics.py` (CloudWatch metric emission with TenantId dimension)
- `src/lib/logging.py` (structured JSON logging configuration)
- CloudWatch alarms configuration (in SAM template or separate file)
- CloudWatch dashboard JSON (or Terraform/CDK if not SAM)
- `tests/unit/test_health.py` (health endpoint tests)

**Dependencies:**
- Sub-Agent 1 (infrastructure, CloudWatch permissions)
- Sub-Agent 3 (handlers to add metrics/logging)

**Key Tasks:**
1. Implement GET /health endpoint (check DynamoDB, S3 connectivity)
2. Add structured JSON logging to all handlers (python-json-logger)
3. Emit CloudWatch metrics: EventIngested, InboxRetrieved, EventAcknowledged (with TenantId)
4. Emit latency metrics (P50/P95/P99)
5. Create CloudWatch alarms: high error rate, high latency
6. Create CloudWatch dashboard (event volume, latency, errors, per-tenant breakdown)
7. Add logging context: event_id, tenant_id, event_type, payload_size

**Success Criteria:**
- Health endpoint returns correct status (healthy/degraded/unhealthy)
- All handlers emit metrics and logs
- CloudWatch dashboard displays key metrics
- Alarms trigger on threshold violations

---

## Sub-Agent 5: Documentation & Testing Agent

**Charter:** Create OpenAPI spec, Swagger UI, integration tests, load tests, and project documentation.

**Inputs:**
- PRD_Product_Reqs_v2.md (OpenAPI requirements, example responses)
- PRD_Tech_v2.md (OpenAPI 3.1 spec, Swagger UI hosting)
- All previous sub-agent outputs (complete API implementation)

**Outputs:**
- `docs/openapi.yaml` (OpenAPI 3.1 specification with all endpoints, examples, error responses)
- `docs/swagger-ui/` (Swagger UI static files, or hosting config)
- `tests/integration/test_api_flow.py` (end-to-end integration tests)
- `tests/load/ingest-load.js` (k6 load test script)
- `README.md` (project documentation, setup instructions)
- `docs/API.md` (API usage guide, examples)
- Python sample client (optional, P2): `examples/python_client.py`

**Dependencies:**
- All previous sub-agents (complete API implementation)

**Key Tasks:**
1. Create OpenAPI 3.1 spec with all endpoints, schemas, examples
2. Include all status codes: 200, 201, 400, 401, 404, 409, 422, 429, 500, 503
3. Add example requests/responses for success and error cases
4. Set up Swagger UI (static hosting or API Gateway stage)
5. Write integration tests: ingest → retrieve → ack → verify
6. Write integration tests: multi-tenant isolation, large payloads, lease expiry
7. Create k6 load test script (1000 events/sec, 100 concurrent users)
8. Write README with setup, deployment, usage instructions
9. Document API usage with curl examples

**Success Criteria:**
- OpenAPI spec validates in Swagger Editor
- Swagger UI renders correctly with all endpoints
- Integration tests pass (end-to-end flow works)
- Load tests meet performance targets (<100ms P95)
- README is complete and accurate

---

## Agent Sequencing & Dependencies

### Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MASTER ORCHESTRATOR AGENT                             │
│                    (Coordinates All Sub-Agents)                         │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │  Sub-Agent 1: Infrastructure & Setup  │
        │  • SAM template                        │
        │  • Project structure                  │
        │  • CI/CD pipeline                     │
        │  ⏱️  ~2 hours                         │
        └──────────────┬─────────────────────────┘
                       │
                       ├──────────────────────────┐
                       │                          │
                       ▼                          ▼
        ┌──────────────────────────┐  ┌──────────────────────────────┐
        │ Sub-Agent 2:             │  │ Sub-Agent 3:                  │
        │ Auth & Validation        │  │ Storage & Handlers           │
        │ • API key auth           │  │ • DynamoDB/S3 ops            │
        │ • Pydantic schemas       │  │ • Lambda handlers             │
        │ • Input validation      │  │ • Event lifecycle             │
        │ ⏱️  ~2 hours             │  │ ⏱️  ~6 hours                  │
        └──────────┬───────────────┘  └───────────┬──────────────────┘
                   │                              │
                   │                              │
                   │                              ▼
                   │              ┌──────────────────────────────────────┐
                   │              │ Sub-Agent 4:                          │
                   │              │ Health & Observability                │
                   │              │ • /health endpoint                   │
                   │              │ • CloudWatch metrics                  │
                   │              │ • Logging & alarms                    │
                   │              │ ⏱️  ~2 hours                          │
                   │              └───────────┬──────────────────────────┘
                   │                          │
                   └──────────────────────────┼──────────────────────────┐
                                              │                          │
                                              ▼                          │
                           ┌─────────────────────────────────────────────┐
                           │ Sub-Agent 5:                                │
                           │ Documentation & Testing                     │
                           │ • OpenAPI spec                             │
                           │ • Integration tests                        │
                           │ • Load tests (k6)                          │
                           │ • README & examples                        │
                           │ ⏱️  ~4 hours                               │
                           └─────────────────────────────────────────────┘
                                              │
                                              ▼
                           ┌─────────────────────────────────────────────┐
                           │         HANDOFF TO MASTER ORCHESTRATOR      │
                           │         (Integration & Deployment)         │
                           └─────────────────────────────────────────────┘
```

### Dependency Matrix

| Sub-Agent | Depends On | Can Start After | Parallel With |
|-----------|------------|-----------------|----------------|
| **1. Infrastructure** | None | Immediately | - |
| **2. Auth & Validation** | Sub-Agent 1 | Infrastructure complete | Sub-Agent 3 (after Sub-Agent 1) |
| **3. Storage & Handlers** | Sub-Agent 1, Sub-Agent 2 | Auth/Validation complete | Sub-Agent 2 (after Sub-Agent 1) |
| **4. Health & Observability** | Sub-Agent 3 | Handlers complete | - |
| **5. Documentation & Testing** | All (1-4) | All sub-agents complete | - |

### Execution Timeline

```
Time →  0h    2h    4h    6h    8h    10h   12h   14h   16h
         │     │     │     │     │     │     │     │     │
Agent 1  ████████
Agent 2         ████████
Agent 3              ████████████████████████
Agent 4                                    ████████
Agent 5                                          ████████████
         │     │     │     │     │     │     │     │     │
         └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────
         Critical Path: 1 → 2 → 3 → 4 → 5
```

**Parallel Execution Notes:**
- ✅ **Sub-Agent 2** can start immediately after Sub-Agent 1 completes (no dependency on Sub-Agent 3)
- ✅ **Sub-Agent 3** can start after Sub-Agent 2 completes (needs auth/validation schemas)
- ✅ **Sub-Agent 4** can start after Sub-Agent 3 completes (needs handlers to instrument)
- ⚠️ **Sub-Agent 5** must wait for all others (needs complete API to document/test)

**Critical Path:**
1. Infrastructure (Sub-Agent 1) → 2 hours
2. Auth & Validation (Sub-Agent 2) → 2 hours
3. Storage & Handlers (Sub-Agent 3) → 6 hours
4. Health & Observability (Sub-Agent 4) → 2 hours
5. Documentation & Testing (Sub-Agent 5) → 4 hours

**Total Estimated Time:** ~16 hours (2 days with parallel work)

---

## Handoff to Master Orchestrator Agent

**Trigger Conditions:**
1. ✅ All 5 sub-agents have completed their deliverables
2. ✅ All unit tests pass (`pytest tests/unit/`)
3. ✅ All integration tests pass (`pytest tests/integration/`)
4. ✅ SAM template validates (`sam validate`)
5. ✅ OpenAPI spec validates (Swagger Editor)
6. ✅ Code coverage >80% (`pytest --cov`)
7. ✅ Linting passes (`pylint src/`, `black --check src/`)

**Master Orchestrator Responsibilities:**
1. **Orchestrate Sub-Agents:** Assign tasks, coordinate dependencies, review outputs
2. **Integration:** Ensure sub-agents' code integrates correctly (imports, function calls)
3. **End-to-End Testing:** Run full API flow locally (`sam local start-api`)
4. **Deployment:** Deploy to AWS dev environment (`sam deploy --guided`)
5. **Validation:** Verify deployed API works (curl tests, Swagger UI)
6. **Bug Fixes:** Resolve integration issues, fix failing tests
7. **Final Review:** Ensure all P0 requirements met, documentation complete

**Master Orchestrator Inputs:**
- All 5 sub-agent outputs (code, tests, docs)
- RECONCILIATION.md (requirements reference)
- OPEN_QUESTIONS.md (resolved questions or defaults)
- MANUAL_SETUP.md (AWS setup verification)
- RISKS.md (risk monitoring)

**Master Orchestrator Outputs:**
- Fully integrated codebase
- Deployed API (dev environment)
- Passing test suite
- Complete documentation
- Deployment runbook

**Success Criteria for Handoff:**
- ✅ API deployed and accessible
- ✅ All endpoints functional (POST /events, GET /inbox, POST /inbox/ack, GET /health)
- ✅ Authentication works (API key validation)
- ✅ Storage works (DynamoDB + S3 fallback)
- ✅ Monitoring works (CloudWatch metrics, logs, dashboard)
- ✅ Documentation complete (OpenAPI, README)
- ✅ Tests passing (>80% coverage)

---

## Sub-Agent Communication Protocol

**Shared Context:**
- All sub-agents read PRD documents (shared understanding)
- Sub-Agent outputs are committed to repository (version control)
- Sub-Agent 1 creates project structure (others follow)

**Conflict Resolution:**
- If two sub-agents modify same file: Master Orchestrator resolves merge
- If schema mismatch: Sub-Agent 2 (Auth & Validation) is source of truth
- If infrastructure mismatch: Sub-Agent 1 (Infrastructure) is source of truth

**Progress Tracking:**
- Each sub-agent updates TODO list when complete
- Master Orchestrator monitors TODO status
- Blockers communicated immediately

---

**Document Status:** ✅ Ready for Master Orchestrator  
**Next Step:** Master Orchestrator reviews this plan and begins sub-agent coordination.

