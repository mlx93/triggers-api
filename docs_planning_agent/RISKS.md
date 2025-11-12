# RISKS.md
## Delivery Risks and Mitigations

**Date:** November 11, 2025  
**Timeline:** 2-day MVP implementation  
**Risk Assessment:** Medium-High (tight timeline, complex system)

---

## Risk 1: DynamoDB Throttling Under Load

**Risk Level:** 🟡 Medium  
**Impact:** High (API latency spikes, failed requests)  
**Probability:** Medium (on-demand billing helps, but burst traffic possible)

**Description:**  
DynamoDB may throttle requests during traffic spikes, causing 429 errors and degraded performance. On-demand billing reduces risk but doesn't eliminate it.

**Mitigation:**
- Use DynamoDB On-Demand billing mode (auto-scaling)
- Implement exponential backoff retry logic in Lambda handlers
- Add CloudWatch alarm for `ThrottledRequests` metric
- Monitor `ConsumedReadCapacityUnits` and `ConsumedWriteCapacityUnits`
- Consider provisioned capacity for production if throttling occurs

**Contingency:**  
If throttling persists, switch to Provisioned mode with auto-scaling (requires capacity planning).

---

## Risk 2: Lambda Cold Starts Affecting Latency

**Risk Level:** 🟡 Medium  
**Impact:** Medium (P95 latency may exceed 100ms target)  
**Probability:** Medium (Python 3.12 helps, but first request per container is slow)

**Description:**  
Lambda cold starts can add 500ms-2s to first request, breaking <100ms P95 target. Python 3.12 reduces cold start time but doesn't eliminate it.

**Mitigation:**
- Use Provisioned Concurrency for critical functions (POST /events, GET /inbox)
- Optimize Lambda package size (remove unused dependencies)
- Use Lambda SnapStart if available (Java/Kotlin only, not Python)
- Implement CloudWatch alarm for cold start frequency
- Consider warming strategy (scheduled CloudWatch Events ping)

**Contingency:**  
If cold starts persist, increase provisioned concurrency or accept higher P95 latency (document as known limitation).

---

## Risk 3: S3 Write Failures During Event Ingestion

**Risk Level:** 🟡 Medium  
**Impact:** Medium (large payloads may fail, but DynamoDB fallback exists)  
**Probability:** Low (S3 is highly reliable, but network issues possible)

**Description:**  
If S3 write fails during large payload ingestion, event may be lost or stored incorrectly. Current design stores in DynamoDB even if S3 fails, but this isn't optimal.

**Mitigation:**
- Implement retry logic for S3 PutObject (3 retries with exponential backoff)
- Store event in DynamoDB first, then attempt S3 write (idempotent)
- If S3 fails, log error but return 201 (event persisted in DynamoDB)
- Add CloudWatch alarm for S3 write failures
- Monitor S3 error rate metrics

**Contingency:**  
If S3 failures are frequent, investigate network/VPC configuration or increase retry attempts.

---

## Risk 4: API Key Leakage or Security Breach

**Risk Level:** 🔴 High  
**Impact:** Critical (tenant data exposure, unauthorized access)  
**Probability:** Low (but high impact if occurs)

**Description:**  
API keys may be leaked via logs, error messages, or client-side exposure. Hashed storage helps but doesn't prevent key reuse if leaked.

**Mitigation:**
- Never log API keys in plaintext (validate all logging statements)
- Hash keys with SHA-256 before storage (already specified)
- Implement key rotation mechanism (admin script for MVP)
- Add CloudWatch alarm for unusual API key usage patterns
- Document key security best practices in README
- Use AWS Secrets Manager for key storage (v2 enhancement)

**Contingency:**  
If key leaked, immediately revoke key in DynamoDB (`is_active=false`), notify tenant, generate new key.

---

## Risk 5: Cursor Parsing/Validation Edge Cases

**Risk Level:** 🟢 Low  
**Impact:** Medium (pagination may break, user confusion)  
**Probability:** Low (simple format, but edge cases exist)

**Description:**  
Cursor format (`{timestamp}_{event_id}`) may have edge cases: duplicate timestamps, special characters in event_id, expired cursors, malformed strings.

**Mitigation:**
- Validate cursor format with regex before parsing
- Reject expired cursors (>24 hours) with clear error message
- Handle duplicate timestamps by including event_id in sort key
- Test edge cases: empty cursor, invalid format, expired cursor
- Return 400 Bad Request with actionable error message

**Contingency:**  
If cursor issues persist, simplify format or add cursor versioning.

---

## Risk 6: Schema Validation Gaps

**Risk Level:** 🟡 Medium  
**Impact:** Medium (invalid data stored, downstream processing issues)  
**Probability:** Medium (Pydantic helps, but edge cases exist)

**Description:**  
Event schema validation may miss edge cases: nested JSON depth, Unicode handling, timestamp format variations, event_type format violations.

**Mitigation:**
- Use Pydantic for strict schema validation (already specified)
- Test with malformed payloads: missing fields, wrong types, invalid formats
- Validate event_type with regex: `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$`
- Validate timestamp as ISO 8601 with timezone
- Return 400 with specific field-level error messages

**Contingency:**  
If validation gaps found, add more comprehensive tests and update Pydantic models.

---

## Risk 7: Cost Overruns (AWS Bill)

**Risk Level:** 🟡 Medium  
**Impact:** Medium (budget exceeded, project approval issues)  
**Probability:** Low (serverless scales with usage, but unexpected traffic possible)

**Description:**  
Unexpected traffic or misconfiguration may cause AWS costs to exceed budget. On-demand DynamoDB can be expensive at scale.

**Mitigation:**
- Set AWS budget alert at $50/month (safety threshold)
- Use On-Demand billing (pay per use, no idle costs)
- Monitor CloudWatch Billing metrics daily
- Implement cost alerts in CloudWatch
- Document expected costs in MANUAL_SETUP.md
- Review DynamoDB item sizes (stay under 400KB to avoid S3)

**Contingency:**  
If costs spike, investigate CloudWatch metrics, review DynamoDB usage, consider provisioned capacity if predictable.

---

## Risk 8: Integration Testing Complexity

**Risk Level:** 🟡 Medium  
**Impact:** Medium (bugs found late, rework needed)  
**Probability:** Medium (serverless testing requires mocking or LocalStack)

**Description:**  
Integration testing with DynamoDB/S3/Lambda requires AWS mocking (moto) or LocalStack, which may not perfectly replicate production behavior.

**Mitigation:**
- Use moto for unit tests (fast, reliable mocking)
- Use SAM Local for integration tests (closer to production)
- Consider LocalStack for full AWS stack testing (optional)
- Test end-to-end flow: ingest → retrieve → ack → verify deletion
- Test multi-tenant isolation (tenant A can't see tenant B events)
- Test error paths: invalid API key, expired cursor, duplicate event

**Contingency:**  
If integration tests fail in production, add more comprehensive test coverage and use staging environment.

---

## Risk 9: OpenAPI Spec Completeness

**Risk Level:** 🟢 Low  
**Impact:** Low (documentation gaps, developer confusion)  
**Probability:** Low (PRDs specify comprehensive examples)

**Description:**  
OpenAPI spec may miss error response examples, status codes, or schema details, leading to incomplete Swagger UI documentation.

**Mitigation:**
- Include all status codes in OpenAPI spec: 200, 201, 400, 401, 404, 409, 422, 429, 500, 503
- Add example requests/responses for each endpoint
- Validate OpenAPI spec with Swagger Editor
- Test Swagger UI rendering before deployment
- Review PRD requirements for examples (comprehensive examples specified)

**Contingency:**  
If OpenAPI gaps found, update spec and regenerate Swagger UI.

---

## Risk 10: Timeline Pressure (2-Day MVP)

**Risk Level:** 🔴 High  
**Impact:** Critical (incomplete features, technical debt)  
**Probability:** High (2 days is aggressive for full implementation)

**Description:**  
2-day timeline is tight for implementing all P0 requirements, tests, documentation, and deployment. May require cutting corners or deferring features.

**Mitigation:**
- Prioritize P0 features only (POST /events, GET /inbox, POST /inbox/ack, GET /health)
- Defer P1/P2 features if timeline slips (lease mechanism, Swagger UI, Python client)
- Use SAM template for rapid infrastructure deployment
- Leverage existing AWS patterns (don't reinvent authentication)
- Focus on core functionality first, polish later
- Accept 80% test coverage if needed (target is >80%)

**Contingency:**  
If timeline slips, communicate early, prioritize critical path, defer non-essential features to v2.

---

## Risk Summary Matrix

| Risk | Level | Impact | Probability | Mitigation Status |
|------|-------|--------|-------------|-------------------|
| DynamoDB Throttling | 🟡 Medium | High | Medium | ✅ Mitigated |
| Lambda Cold Starts | 🟡 Medium | Medium | Medium | ✅ Mitigated |
| S3 Write Failures | 🟡 Medium | Medium | Low | ✅ Mitigated |
| API Key Leakage | 🔴 High | Critical | Low | ✅ Mitigated |
| Cursor Edge Cases | 🟢 Low | Medium | Low | ✅ Mitigated |
| Schema Validation | 🟡 Medium | Medium | Medium | ✅ Mitigated |
| Cost Overruns | 🟡 Medium | Medium | Low | ✅ Mitigated |
| Integration Testing | 🟡 Medium | Medium | Medium | ⚠️ Partial |
| OpenAPI Completeness | 🟢 Low | Low | Low | ✅ Mitigated |
| Timeline Pressure | 🔴 High | Critical | High | ⚠️ Monitor |

---

## Top 3 Critical Risks (Focus Areas)

1. **Timeline Pressure (2-Day MVP)** - Most likely to impact delivery
2. **API Key Security** - Highest impact if breached
3. **DynamoDB Throttling** - Most likely technical risk

---

## Risk Monitoring

**Daily Checkpoints:**
- AWS cost alerts (CloudWatch Billing)
- Lambda error rates (CloudWatch Metrics)
- DynamoDB throttling (CloudWatch Metrics)
- Integration test pass rate (CI/CD pipeline)

**Weekly Review:**
- Risk register update
- Mitigation effectiveness assessment
- New risk identification

---

**Document Status:** ✅ Complete  
**Next Step:** Monitor risks during implementation, update as needed.

