# OPEN_QUESTIONS.md
## Questions for Product Owner

**Date:** November 11, 2025  
**Status:** ✅ All Questions Answered  
**Max Questions:** 10 (as per requirements)  
**Response Date:** November 11, 2025

---

## Question 1: API Key Provisioning

**Question:** How should API keys be generated and provisioned for the MVP? Is there an admin script/endpoint needed, or will keys be manually created in DynamoDB?

**Why it matters:**  
- Technical PRD mentions API key generation format (`ak_{32chars}`) but doesn't specify provisioning mechanism
- Product PRD mentions "manual provisioning via admin script" in demo Q&A but this isn't in scope
- Need to know if MVP requires a key management endpoint or if manual DynamoDB inserts are acceptable

**Default Recommendation if Unanswered:**  
- Create a simple admin CLI script (`scripts/create_api_key.py`) that generates key, hashes it, stores in DynamoDB, and returns plaintext key once
- No API endpoint for key creation in MVP (manual admin operation)
- Document key creation process in README

**✅ Approved Answer:**  
- Keys will be generated manually for the MVP using a small admin CLI script (`scripts/create_api_key.py`) that inserts a hashed key into DynamoDB
- No admin endpoint is needed; document the process in the README
- **Rationale:** Safer, faster to implement, avoids building extra surface area that will be deprecated once a real Admin API exists

---

## Question 2: Tenant ID Generation

**Question:** How should `tenant_id` values be generated? Should they be UUIDs, sequential IDs, or derived from another system?

**Why it matters:**  
- Both PRDs reference `tenant_id` but don't specify generation format
- Affects DynamoDB partition key design (`TENANT#{tenant_id}`)
- May impact future integration with Zapier's existing tenant/user system

**Default Recommendation if Unanswered:**  
- Use UUID v4 format: `tenant_{uuid}` (e.g., `tenant_550e8400-e29b-41d4-a716-446655440000`)
- Generate during API key creation
- Store mapping in api-keys table: `hashed_key → tenant_id`

**✅ Approved Answer:**  
- Use UUID v4 identifiers (`tenant_{uuid}`) generated alongside API keys
- Each key mapped to its tenant in the api_keys table
- **Status:** Full alignment with default recommendation

---

## Question 3: Event ID Generation Format

**Question:** What format should auto-generated event IDs use? PRDs show `evt_abc123xyz789` but don't specify generation algorithm.

**Why it matters:**  
- Affects idempotency checking and uniqueness guarantees
- Need to ensure collision probability is negligible
- Format impacts storage and query patterns

**Default Recommendation if Unanswered:**  
- Format: `evt_{base64url_32chars}` (e.g., `evt_aBc123XyZ789...`)
- Generate using `secrets.token_urlsafe(24)` (32 chars after `evt_` prefix)
- Ensures URL-safe, collision-resistant IDs

**✅ Approved Answer:**  
- Follow the proposed `evt_{base64url_32chars}` format using `secrets.token_urlsafe(24)` to ensure globally unique, URL-safe IDs
- **Status:** Full alignment with default recommendation

---

## Question 4: Cursor Format and Validation

**Question:** What exact format should pagination cursors use? PRDs show `timestamp_id` format but need specifics for parsing/validation.

**Why it matters:**  
- Cursor format affects parsing logic in GET /inbox handler
- Need to validate cursor structure before DynamoDB query
- 24-hour TTL validation requires parsing timestamp component

**Default Recommendation if Unanswered:**  
- Format: `{unix_timestamp}_{event_id}` (e.g., `1699712345_evt_abc123`)
- Parse: split on last `_`, validate timestamp is within 24 hours
- Return error 400 if cursor format invalid or expired

**✅ Approved Answer:**  
- Adopt the `{unix_timestamp}_{event_id}` format
- Validate structure and timestamp freshness (<24h) on every /inbox request
- Expired or malformed cursors return 400 Bad Request
- **Status:** Full alignment with default recommendation

---

## Question 5: S3 Lifecycle Policy Details

**Question:** Should S3 lifecycle policy delete objects immediately after 30 days, or should there be a grace period? What about failed S3 writes during event ingestion?

**Why it matters:**  
- S3 lifecycle rules run asynchronously (can take 24-48 hours)
- Need to handle S3 write failures gracefully (don't lose event if DynamoDB write succeeds)
- Cleanup strategy affects cost and data retention compliance

**Default Recommendation if Unanswered:**  
- S3 lifecycle: Delete objects after 30 days (matches DynamoDB TTL)
- On S3 write failure: Store event in DynamoDB with `s3_key=null`, log error, return 201 (event persisted, just not optimized)
- Add CloudWatch alarm for S3 write failures

**✅ Approved Answer:**  
- Match DynamoDB's 30-day TTL with S3 object expiration after 30 days
- On S3 write failure: Log the error and persist the event in DynamoDB (with `s3_key=null`) so ingestion still succeeds
- **Rationale:** Keeps storage behavior consistent and cost-bounded; indefinite retention has no MVP value

---

## Question 6: Rate Limiting Strategy

**Question:** Product PRD mentions API Gateway usage plans (1000 req/sec, 2000 burst) but Technical PRD doesn't specify implementation. Should rate limiting be per-tenant or global?

**Why it matters:**  
- Affects API Gateway configuration and cost
- Per-tenant limits require usage plan per key (complex)
- Global limits are simpler but may not prevent tenant abuse

**Default Recommendation if Unanswered:**  
- **MVP:** Global rate limiting via API Gateway (1000 req/sec, 2000 burst)
- **Per-tenant:** Track in CloudWatch metrics, add per-tenant limits in v2 if needed
- Return 429 Too Many Requests with `Retry-After` header

**✅ Approved Answer:**  
- Use global API Gateway throttling (1000 RPS, 2000 burst) for MVP simplicity
- Add per-tenant usage tracking via CloudWatch metrics for future refinement
- **Rationale:** Per-tenant rate limiting in Lambda is overkill for MVP. Use API Gateway's native throttling first; layer in per-tenant counters later when traffic justifies it

---

## Question 7: Health Endpoint Dependency Failures

**Question:** If DynamoDB is healthy but S3 is degraded, should `/health` return "degraded" or "healthy"? What's the threshold for "degraded" status?

**Why it matters:**  
- Affects monitoring and alerting behavior
- Determines when to trigger CloudWatch alarms
- Impacts operational runbooks

**Default Recommendation if Unanswered:**  
- **Healthy:** All dependencies (DynamoDB, S3) responding within 100ms
- **Degraded:** One dependency failing or slow (>500ms), but core functionality (DynamoDB) works
- **Unhealthy:** DynamoDB unavailable (core dependency)
- Return 200 for healthy/degraded, 503 for unhealthy

**✅ Approved Answer:**  
- Return 200 for healthy/degraded (with `"status": "degraded"` body if S3 is slow/unavailable)
- Return 503 if DynamoDB is down
- **Rationale:** This matches sensible operational semantics for monitoring. Allows monitoring dashboards to show partial degradation instead of hard failures for transient S3 issues

---

## Question 8: Large Payload Size Limit

**Question:** PRDs specify 10MB max payload size in user story but 400KB threshold for S3. What's the actual maximum payload size, and what happens if payload exceeds 10MB?

**Why it matters:**  
- Affects API Gateway payload size limits (default 10MB)
- Need to validate payload size before processing
- Error message clarity for developers

**Default Recommendation if Unanswered:**  
- **Maximum:** 10MB (API Gateway limit)
- **S3 Threshold:** 400KB (as specified)
- **Validation:** Reject payloads >10MB with 413 Payload Too Large
- **Error Message:** "Payload exceeds 10MB limit. Maximum size: 10485760 bytes"

**✅ Approved Answer:**  
- Enforce a 10 MB absolute maximum (API Gateway limit) and store anything >400 KB in S3
- Reject payloads over 10 MB with 413 Payload Too Large and a clear error message
- **Status:** Full alignment with default recommendation

---

## Question 9: Event Type Validation Rules

**Question:** PRDs mention "dot-notation" for event_type (e.g., `player.projection.created`) but don't specify validation rules. What characters are allowed? Minimum/maximum length?

**Why it matters:**  
- Affects input validation logic
- Prevents injection attacks and malformed data
- Ensures consistent event type naming

**Default Recommendation if Unanswered:**  
- **Format:** `{namespace}.{resource}.{action}` (minimum 3 segments)
- **Characters:** Lowercase letters, numbers, dots, underscores
- **Length:** 3-100 characters
- **Pattern:** `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$`
- Return 400 if validation fails

**✅ Approved Answer:**  
- Enforce the regex `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` with lowercase dot-notation (`namespace.resource.action`)
- Length 3–100 chars
- Reject anything outside that pattern with 400 Bad Request
- **Rationale:** Added explicit regex to prevent messy, unsearchable event names once integrations grow

---

## Question 10: CloudWatch Log Retention

**Question:** How long should CloudWatch logs be retained? PRDs mention structured logging but don't specify retention policy.

**Why it matters:**  
- Affects AWS costs (log storage charges)
- Impacts compliance and audit requirements
- Determines how far back we can debug issues

**Default Recommendation if Unanswered:**  
- **Retention:** 30 days (matches event TTL)
- **Cost:** ~$0.50/GB/month (minimal for MVP)
- **Configuration:** Set in SAM template via `RetentionInDays` property
- Can extend to 90 days in production if needed

**✅ Approved Answer:**  
- Retain logs for 30 days (aligned with event TTL) using the `RetentionInDays` property in the SAM template
- Increase to 90 days post-MVP if compliance requires longer storage
- **Rationale:** 30 days aligns with TTL and MVP compliance target; extend later if auditing requires

---

## Summary

**Total Questions:** 10  
**Critical for MVP:** All 10 (blocking implementation decisions)  
**Status:** ✅ **All Questions Answered** (November 11, 2025)

**Answer Summary:**
- **Full Alignment (6 questions):** Questions 2, 3, 4, 8 - Default recommendations approved as-is
- **Minor Adjustments (4 questions):** Questions 1, 5, 6, 7, 9, 10 - Approved with practical MVP simplifications

**Key Adjustments Made:**
1. **API Key Provisioning:** CLI script only (no admin endpoint) - safer, faster
2. **S3 Lifecycle:** 30-day match with DynamoDB (not indefinite) - cost-bounded
3. **Rate Limiting:** Global API Gateway only (not per-tenant Lambda) - simpler MVP
4. **Health Check:** 200 degraded vs 503 down split - better operational semantics
5. **Event Type Validation:** Explicit regex enforced - prevents messy names
6. **Log Retention:** 30 days (not 90) - aligns with TTL, extend later if needed

**Net Result:** No fundamental disagreements. All adjustments align with MVP practicality and improve time-to-implement without creating technical debt.

**Timeline Impact:** ✅ All answers allow immediate implementation start. No blockers identified.

---

**Document Status:** ✅ Complete - All Questions Answered  
**Ready for Master Orchestrator:** ✅ Yes - All implementation decisions resolved

