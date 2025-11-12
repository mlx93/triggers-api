# Zapier Triggers API - Demo Video Script (Final)

**Duration:** 5 minutes | **Format:** Screen recording with voiceover | **Audience:** Developers, PMs, Technical Decision Makers

---

## Pre-Demo Setup

- [ ] API Base: `https://xiz2bca1sg.execute-api.us-east-1.amazonaws.com/`
- [ ] Swagger UI: `http://triggers-api-docs-mlx.s3-website-us-east-1.amazonaws.com`
- [ ] **API Keys:**
  - **Key A:** `ak_demo20241112tenantA1234567890123` (Tenant: `tenant_demo_video_key_a_2024_11_12`)
  - **Key B:** `ak_demo20241112tenantB1234567890123` (Tenant: `tenant_demo_video_key_b_2024_11_12`)
- [ ] Authorize with API Key A in Swagger UI before starting (click "Authorize" button at top)
- [ ] Payloads ready: small event, large event (>400KB), event with explicit `id`
- [ ] CloudWatch dashboard open

---

## Script

### Scene 1: Hook & Root Endpoint (0:00 - 0:50)

**[Screen: Browser → API root endpoint]**

> "Hi everyone. Zapier integrations today use polling - checking every few minutes. This means delays and wasted resources. What if ANY system could push events to Zapier in real-time? That's the Triggers API."

**[Navigate to: https://xiz2bca1sg.execute-api.us-east-1.amazonaws.com/]**

> "Let's start with the root endpoint. No authentication needed - just hit the API base URL."

**[Show JSON response with API info, endpoints, documentation links]**

> "See? Developer-friendly from the start. It shows the API version, five available endpoints, authentication requirements, and links to documentation. This is pull-based, not push-based - Zapier controls when to fetch events, not the sender. No webhook endpoints to secure, no rate limiting from senders."

**Key Points:** Pull-based model | Five endpoints | Developer-friendly

---

### Scene 2: Swagger UI Overview (0:50 - 1:20)

**[Screen: Swagger UI]**

> "We've built comprehensive interactive documentation. Each endpoint includes detailed schemas, examples, and you can test everything directly here."

**[Scroll through endpoints: /, /health, /events, /inbox, /inbox/ack]**

> "Five endpoints: root, health check, event ingestion, event retrieval, and acknowledgment. Let's see them in action."

**[Click to expand POST /events]**

> "Event ingestion accepts JSON with event type, timestamp, and your data. The API handles payloads up to 10 megabytes automatically - small events in DynamoDB, large ones in S3. You don't think about it."

**Key Points:** Interactive docs | Automatic storage optimization

---

### Scene 3: Sending Events + Idempotency (1:20 - 2:45)

**[Screen: Swagger UI POST /events]**

> "Let's send our first event."

**[Click "Authorize" at top, enter API key: `ak_demo20241112tenantA1234567890123`]**

**[Click "Try it out", paste payload]**
```json
{
  "event_type": "player.projection.created",
  "timestamp": "2025-11-11T15:30:45Z",
  "data": {"player_id": 12345, "player_name": "Mike Trout", "projection_value": 42}
}
```

**[Click "Execute"]**

> "201 Created in under 100 milliseconds. The event is stored durably. Now here's what makes this unique - idempotency."

**[Send same event with explicit `id`]**

```json
{
  "id": "evt_test_12345",
  "event_type": "player.projection.created",
  "timestamp": "2025-11-11T15:30:45Z",
  "data": {"player_id": 12345, "player_name": "Mike Trout", "projection_value": 42}
}
```

**[Click "Execute", show 201 Created]**

**[Send exact same event again]**

> "Send twice? No problem."

**[Show 409 Conflict response]**

> "409 Conflict - the existing event is returned. Prevents duplicates automatically. No manual deduplication needed."

**Key Points:** Sub-100ms latency | Idempotency built-in | Automatic duplicate prevention

---

### Scene 4: Retrieving Events + Multi-Tenant (2:45 - 3:45)

**[Screen: Swagger UI GET /inbox]**

> "Now let's retrieve events. This is pull-based - Zapier controls when to fetch, not the sender."

**[Click "Try it out", click "Execute"]**

**[Show response with events, highlight `attempt_count: 1`]**

> "Notice the attempt count is 1. This event has a 20-second lease. If my app crashes before acknowledging, this event automatically becomes available again after the lease expires. No lost events."

> "Let me send another event before demonstrating multi-tenant isolation."

**[Switch to POST /events, click "Try it out", paste payload]**
```json
{
  "event_type": "player.projection.updated",
  "timestamp": "2025-11-11T15:31:00Z",
  "data": {"player_id": 12345, "projection_value": 43}
}
```

**[Click "Execute", show 201 Created]**

> "Now let's demonstrate multi-tenant isolation. I'll switch to a different API key."

**[Click "Authorize" at top, enter different API key (Key B), close dialog]**

**[Click "Try it out", click "Execute"]**

**[Show empty inbox: `{"events": [], "pagination": {...}}`]**

> "Empty inbox. Complete isolation - your data is YOUR data."

**[Click "Authorize" at top, switch back to API Key A, close dialog]**

**[Switch back to GET /inbox, click "Try it out", click "Execute"]**

**[Show response with the second event (projection.updated)]**

> "Switch back to the original key, and we see the second event we just sent. The first event is still under lease from our earlier retrieval, but this new event appears immediately. Each API key is completely separate."

**Key Points:** Pull-based model | Lease mechanism (automatic retry) | Complete multi-tenant isolation

---

### Scene 5: Acknowledging Events (3:45 - 4:15)

**[Screen: Swagger UI POST /inbox/ack]**

> "After processing events, acknowledge them so they don't get delivered again."

**[Click "Try it out", paste: `{"event_ids": ["evt_abc123xyz789"]}`]**

**[Click "Execute", show response: `{"acknowledged": [...], "failed": []}`]**

> "Perfect. The API supports batch acknowledgment up to 100 events. Processed? Acknowledge it. Crashed? Event comes back automatically after the lease expires."

**Key Points:** Batch acknowledgment | Complete flow demonstrated

---

### Scene 6: Closing (4:15 - 5:00)

**[Screen: Swagger UI homepage]**

> "To summarize: the Zapier Triggers API provides reliable, real-time event ingestion with sub-100 millisecond latency. Pull-based delivery means Zapier controls timing. Idempotency prevents duplicates. Multi-tenant isolation ensures your data is secure. And the 20-second lease mechanism guarantees no lost events - if your app crashes, events automatically become available again."

> "Get your API key and start building. Documentation is at triggers-api-docs-mlx.s3-website-us-east-1.amazonaws.com. Thanks for watching!"

**Key Points:** Unique features emphasized | Clear call to action | Documentation link

---

## Post-Demo Notes

**Key Metrics:** <100ms P95 latency | 99.9% uptime target | 1000+ events/second per tenant

**Common Questions:**
- **Q: Why pull-based instead of webhooks?** A: Zapier controls timing, no webhook endpoints to secure, Zapier can batch process efficiently.
- **Q: What if my app crashes?** A: 20-second lease mechanism ensures events automatically become available again.
- **Q: Is my data secure?** A: Complete multi-tenant isolation - each API key is completely separate.
- **Q: How do I handle duplicates?** A: Idempotency built-in - send same event_id twice, get existing event back (409 Conflict).

**Recording Tips:** Practice 3+ times | Have payloads ready to paste | Zoom in on important details | Use cursor highlights | Show actual API responses

---

**Status:** ✅ Ready for Production | **Length:** 5:00 | **Difficulty:** Moderate
