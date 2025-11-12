# Sub-Agent 4: Health & Observability Agent - Prompt

**Date:** November 11, 2025  
**Agent:** Health & Observability Agent  
**Status:** Ready for Execution  
**Estimated Time:** ~2 hours

---

## Charter

Implement health endpoint, CloudWatch metrics emission, structured JSON logging, CloudWatch alarms, and CloudWatch dashboard that provide comprehensive observability for the Zapier Triggers API MVP.

---

## Inputs

**Primary Sources of Truth (CRITICAL - Reference Extensively):**
- `PRD_Product_Reqs_v2.md` - Health endpoint requirements (FR-5), monitoring requirements (FR-7), error handling
- `PRD_Tech_v2.md` - CloudWatch configuration (Section 12), logging format (Section 12), metrics namespace and dimensions

**Dependencies (Must Be Complete First):**
- ✅ Sub-Agent 1: Infrastructure ready (CloudWatch permissions in IAM roles, log groups configured)
- ✅ Sub-Agent 2: HealthResponse schema available, ErrorResponse schema available
- ✅ Sub-Agent 3: Handlers implemented with basic logging, ready for metrics instrumentation

**Supporting Documents:**
- `docs_planning_agent/OPEN_QUESTIONS.md` - Resolved decisions: Health endpoint status (200 for healthy/degraded, 503 for unhealthy) from Q7, log retention 30 days from Q10
- `docs_planning_agent/SUB_AGENT_1_COMPLETION.md` - Confirms infrastructure: CloudWatch log groups with 30-day retention configured
- `docs_planning_agent/SUB_AGENT_2_COMPLETION.md` - Confirms HealthResponse schema available, ErrorResponse schema available
- `docs_planning_agent/SUB_AGENT_3_COMPLETION.md` - **REVIEW THIS** - Confirms handlers implemented with logging statements, error handling ready, health.py placeholder exists

**Key PRD Sections to Reference:**
- **PRD_Product_Reqs_v2.md FR-5:** GET /health endpoint (check DynamoDB/S3 connectivity, return healthy/degraded/unhealthy, 200 for healthy/degraded, 503 for unhealthy)
- **PRD_Product_Reqs_v2.md FR-7:** Error handling and status codes
- **PRD_Tech_v2.md Section 12:** CloudWatch Metrics (namespace `ZapierTriggers`, dimensions TenantId/EventType/Environment, metrics: EventIngested, InboxRetrieved, EventAcknowledged, EventLatency)
- **PRD_Tech_v2.md Section 12:** CloudWatch Alarms (high error rate >10 5XX in 5min, high latency P95 >200ms)
- **PRD_Tech_v2.md Section 12:** Structured Logging (JSON format with pythonjsonlogger, include event_id, tenant_id, event_type, payload_size, storage_type)
- **PRD_Tech_v2.md Section 12:** Dashboard (event ingestion rate, API latency P50/P95/P99, error rates, event volume, per-tenant breakdowns)

---

## Outputs

**Required Deliverables:**

1. **`src/handlers/health.py`** - GET /health Lambda handler:
   - Replace placeholder with full implementation
   - Check DynamoDB connectivity (describe_table or simple query)
   - Check S3 connectivity (head_bucket or head_object)
   - Return `HealthResponse` schema (status: healthy/degraded/unhealthy, dependencies: dynamodb/s3 status)
   - Return 200 for healthy/degraded, 503 for unhealthy (from OPEN_QUESTIONS.md Q7)
   - Complete within 50ms (timeout checks, don't wait too long)
   - Include timestamp and version information

2. **`src/lib/metrics.py`** - CloudWatch metrics emission module:
   - Function: `emit_metric(metric_name, value, unit, dimensions)` - Emit custom CloudWatch metric
   - Function: `emit_event_ingested(tenant_id, event_type, latency_ms, payload_size)` - Emit EventIngested metric
   - Function: `emit_inbox_retrieved(tenant_id, event_count, latency_ms)` - Emit InboxRetrieved metric
   - Function: `emit_event_acknowledged(tenant_id, event_count, latency_ms)` - Emit EventAcknowledged metric
   - Function: `emit_latency(tenant_id, endpoint, latency_ms)` - Emit latency metric (P50/P95/P99 calculated by CloudWatch)
   - Namespace: `ZapierTriggers`
   - Dimensions: `TenantId`, `EventType` (when applicable), `Environment`
   - Use boto3 CloudWatch client or aws-lambda-powertools metrics

3. **`src/lib/logging.py`** - Structured JSON logging configuration:
   - Configure python-json-logger for structured JSON output
   - Set up logger with appropriate log level (from environment variable)
   - Add context fields: event_id, tenant_id, event_type, payload_size, storage_type
   - Format: JSON with timestamp, level, message, and context fields
   - Ensure CloudWatch Logs can parse JSON format

4. **CloudWatch Alarms Configuration:**
   - **High Error Rate Alarm:** Trigger if 5XXError count >10 in 5-minute window
   - **High Latency Alarm:** Trigger if P95 latency >200ms in 5-minute window
   - Can be added to SAM template or created via AWS CLI/Console (document approach)
   - Alarm actions: SNS topic (optional for MVP) or CloudWatch dashboard notification

5. **CloudWatch Dashboard JSON:**
   - Dashboard name: `ZapierTriggers-API-Dashboard`
   - Widgets:
     - Event ingestion rate (EventIngested count over time)
     - API latency (P50/P95/P99 percentiles)
     - Error rates (4XX/5XX counts)
     - Event volume over time
     - Per-tenant breakdown (top tenants by event volume)
   - Can be created via AWS CLI/Console or included as CloudFormation resource
   - Document creation method

6. **Handler Instrumentation Updates:**
   - Add metrics emission to `src/handlers/ingest.py` (EventIngested, latency)
   - Add metrics emission to `src/handlers/inbox.py` (InboxRetrieved, latency)
   - Add metrics emission to `src/handlers/ack.py` (EventAcknowledged, latency)
   - Enhance logging context in handlers (ensure tenant_id, event_id are logged)
   - Add latency measurement (start/end timestamps)

7. **`tests/unit/test_health.py`** - Health endpoint unit tests:
   - Test healthy status (both DynamoDB and S3 healthy)
   - Test degraded status (one dependency failing)
   - Test unhealthy status (DynamoDB down)
   - Test timeout handling (dependency check times out)
   - Use moto to mock DynamoDB and S3
   - Achieve >80% coverage

---

## Dependencies

**Completed:**
- ✅ Sub-Agent 1: Infrastructure ready (CloudWatch log groups, IAM permissions)
- ✅ Sub-Agent 2: HealthResponse schema available, ErrorResponse schema available
- ✅ Sub-Agent 3: Handlers implemented with basic logging, ready for instrumentation

**Note:** Sub-Agent 5 depends on your outputs (health endpoint, metrics, logging) for documentation and integration testing.

---

## Key Tasks

1. **Implement GET /health Handler (`src/handlers/health.py`):**
   - Replace placeholder with full implementation
   - Check DynamoDB connectivity: Use `describe_table()` or simple `get_item()` query with timeout (5-10 seconds max)
   - Check S3 connectivity: Use `head_bucket()` or `head_object()` with timeout (5-10 seconds max)
   - Determine status:
     - **Healthy:** Both DynamoDB and S3 responding within 100ms
     - **Degraded:** One dependency failing or slow (>500ms), but core functionality (DynamoDB) works
     - **Unhealthy:** DynamoDB unavailable (core dependency)
   - Return 200 for healthy/degraded (with status in body), 503 for unhealthy (from OPEN_QUESTIONS.md Q7)
   - Use `HealthResponse` schema from Sub-Agent 2
   - Include timestamp and version ("1.0.0")
   - Complete within 50ms (use timeouts, don't block)

2. **Create CloudWatch Metrics Module (`src/lib/metrics.py`):**
   - Use boto3 CloudWatch client or aws-lambda-powertools metrics (recommended: aws-lambda-powertools for simplicity)
   - Namespace: `ZapierTriggers`
   - Emit metrics with dimensions: `TenantId`, `EventType` (when applicable), `Environment`
   - Implement helper functions:
     - `emit_event_ingested(tenant_id, event_type, latency_ms, payload_size)` - Count metric with TenantId/EventType dimensions
     - `emit_inbox_retrieved(tenant_id, event_count, latency_ms)` - Count metric with TenantId dimension
     - `emit_event_acknowledged(tenant_id, event_count, latency_ms)` - Count metric with TenantId dimension
     - `emit_latency(tenant_id, endpoint, latency_ms)` - Latency metric (CloudWatch calculates percentiles)
   - Use CloudWatch PutMetricData API or powertools metrics.add_metric()

3. **Configure Structured JSON Logging (`src/lib/logging.py`):**
   - Install python-json-logger if not in requirements.txt
   - Configure JSON formatter with pythonjsonlogger
   - Set up logger with log level from environment variable (default: INFO)
   - Add context fields to log records: event_id, tenant_id, event_type, payload_size, storage_type
   - Ensure logs are parseable by CloudWatch Logs Insights
   - Export logger instance for use in handlers

4. **Instrument Handlers with Metrics:**
   - **ingest.py:** Add `emit_event_ingested()` call after successful event storage, measure latency
   - **inbox.py:** Add `emit_inbox_retrieved()` call after successful query, measure latency
   - **ack.py:** Add `emit_event_acknowledged()` call after successful acknowledgment, measure latency
   - Add latency measurement: capture start time at handler entry, end time before return, calculate delta
   - Emit latency metrics for all endpoints

5. **Enhance Handler Logging:**
   - Ensure all handlers log with context: tenant_id, event_id, event_type (when available)
   - Add structured logging context using logger's extra parameter
   - Log errors with full context (tenant_id, event_id, error details)
   - Ensure payload_size and storage_type are logged in ingest handler

6. **Enhance Error Response Details (Optional but Recommended):**
   - ⚠️ **Enhancement Opportunity:** Per Sub-Agent 3 completion report, error responses use ErrorResponse schema but could include more actionable details per PRD_Product_Reqs_v2.md FR-7
   - Consider enhancing error `details` field in handler error responses to include:
     - **Field-level validation errors:** Extract Pydantic validation errors and format as `{"field": "timestamp", "issue": "must be ISO 8601 format"}` (Pydantic already provides this via `errors()` method)
     - **Specific DynamoDB error codes:** Include ConditionalCheckFailedException details, specific error messages (e.g., "Event ID already exists" for idempotency conflicts)
   - This aligns with PRD requirement for "actionable error messages" and improves developer experience
   - See SUB_AGENT_3_COMPLETION.md Recommendations section for details

7. **Create CloudWatch Alarms:**
   - **High Error Rate:** Alarm on 5XXError count >10 in 5-minute window
     - Metric: Sum of 5XX errors across all Lambda functions
     - Threshold: 10
     - Evaluation period: 5 minutes
   - **High Latency:** Alarm on P95 latency >200ms in 5-minute window
     - Metric: P95 latency across all endpoints
     - Threshold: 200ms
     - Evaluation period: 5 minutes
   - Can be added to SAM template as CloudWatch::Alarm resources or documented for manual creation
   - Document alarm creation method

8. **Create CloudWatch Dashboard:**
   - Dashboard name: `ZapierTriggers-API-Dashboard`
   - Create widgets for:
     - Event ingestion rate (line chart: EventIngested count over time)
     - API latency (line chart: P50/P95/P99 percentiles)
     - Error rates (bar chart: 4XX/5XX counts)
     - Event volume over time (line chart: total events)
     - Per-tenant breakdown (pie chart or bar chart: top 10 tenants by event volume)
   - Can be created via AWS CLI/Console or CloudFormation resource
   - Document dashboard creation method and provide JSON if possible

9. **Write Health Endpoint Tests:**
   - Test healthy status (both dependencies healthy)
   - Test degraded status (S3 slow/unavailable, DynamoDB healthy)
   - Test unhealthy status (DynamoDB unavailable)
   - Test timeout handling (dependency check exceeds timeout)
   - Use moto to mock DynamoDB and S3
   - Test response format matches HealthResponse schema
   - Achieve >80% coverage

---

## Success Criteria

**All of the following must be true:**

- ✅ Health endpoint returns correct status (healthy/degraded/unhealthy) matching OPEN_QUESTIONS.md Q7
- ✅ Health endpoint returns 200 for healthy/degraded, 503 for unhealthy
- ✅ Health endpoint checks DynamoDB and S3 connectivity with timeouts
- ✅ All handlers emit CloudWatch metrics (EventIngested, InboxRetrieved, EventAcknowledged, latency)
- ✅ Metrics include TenantId dimension (and EventType when applicable)
- ✅ Structured JSON logging configured and used in all handlers
- ✅ Logs include context: event_id, tenant_id, event_type, payload_size, storage_type
- ✅ CloudWatch alarms configured (high error rate, high latency) or documented
- ✅ CloudWatch dashboard created or documented with widget specifications
- ✅ Health endpoint tests achieve >80% coverage
- ✅ All tests pass

---

## Implementation Guidelines

**CRITICAL: Reference PRDs Extensively**

- **Health Endpoint:** Use PRD_Product_Reqs_v2.md FR-5 for requirements, OPEN_QUESTIONS.md Q7 for status logic (200 degraded vs 503 unhealthy)
- **Metrics Namespace:** `ZapierTriggers` from PRD_Tech_v2.md Section 12
- **Metrics Dimensions:** TenantId, EventType (when applicable), Environment from PRD_Tech_v2.md Section 12
- **Key Metrics:** EventIngested, InboxRetrieved, EventAcknowledged, EventLatency from PRD_Tech_v2.md Section 12
- **Alarm Thresholds:** >10 5XX errors in 5min, P95 >200ms from PRD_Tech_v2.md Section 12
- **Logging Format:** JSON with pythonjsonlogger, include event_id, tenant_id, event_type, payload_size, storage_type from PRD_Tech_v2.md Section 12
- **Log Retention:** 30 days from OPEN_QUESTIONS.md Q10 (already configured in SAM template)

**Code Quality:**
- Use aws-lambda-powertools for metrics if available (simpler than raw boto3)
- Use python-json-logger for structured logging
- Add type hints to all functions
- Follow Python 3.12 best practices
- Handle timeouts gracefully in health checks
- Don't block health endpoint on slow dependency checks

**Testing:**
- Use moto to mock DynamoDB and S3 for health endpoint tests
- Test all status scenarios (healthy, degraded, unhealthy)
- Test timeout handling
- Achieve >80% coverage for health endpoint

**Integration:**
- Handlers from Sub-Agent 3 already have logging statements - enhance them with structured context
- Handlers already return proper Lambda response format - add metrics emission
- Use HealthResponse schema from Sub-Agent 2

---

## Notes

- **Health Endpoint:** Already exists as placeholder from Sub-Agent 1 - replace with full implementation
- **Handler Logging:** Sub-Agent 3 added basic logging - enhance with structured JSON logging and context fields
- **Metrics:** Use aws-lambda-powertools if available (already in requirements.txt), otherwise use boto3 CloudWatch client
- **Alarms/Dashboard:** Can be created manually via AWS Console/CLI or added to SAM template - document approach
- **Latency Measurement:** Measure handler execution time (start time at entry, end time before return)
- **Error Handling:** Ensure metrics/logging don't break handler execution if CloudWatch is unavailable

---

## Completion Report Format

When you complete your work, provide a summary report that includes:

1. **Status:** ✅ Complete or ⚠️ Partial (with blockers)
2. **Deliverables Created:** List all files created/modified with paths
3. **Test Results:** Coverage percentage and test pass/fail status for health endpoint tests
4. **Key Decisions:** Any implementation decisions made (e.g., metrics library choice, alarm creation method)
5. **Blockers:** Any issues preventing completion
6. **Next Steps:** What Sub-Agent 5 needs to know (health endpoint ready, metrics/logging ready, etc.)

---

**Document Status:** Ready for Sub-Agent 4 Execution  
**Next Step:** Sub-Agent 4 completes observability, then Sub-Agent 5 (Documentation & Testing) can proceed

