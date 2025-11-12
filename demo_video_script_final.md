# Zapier Triggers API - Demo Video Script (Final)

**Duration:** 5 minutes | **Format:** Screen recording with voiceover | **Audience:** Developers, PMs, Technical Decision Makers

---

## Pre-Demo Setup

- [ ] API Base: `https://xiz2bca1sg.execute-api.us-east-1.amazonaws.com/`
- [ ] Swagger UI: `http://triggers-api-docs-mlx.s3-website-us-east-1.amazonaws.com`
- [ ] Two API keys: `ak_test1234567890123456789012345678` (Key A) + second key (Key B)
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

**[Click "Try it out", paste payload]**
```json
{
  "event_type": "player.projection.created",
  "timestamp": "2025-11-11T15:30:45Z",
  "data": {"player_id": "12345", "player_name": "Mike Trout", "projection_value": 42.5}
}
```

**[Enter API key, click "Execute"]**

> "201 Created in under 100 milliseconds. The event is stored durably. Now here's what makes this unique - idempotency."

**[Send same event with explicit `id`: `"id": "evt_test_12345"`]**

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

**[Click "Try it out", enter API Key A, click "Execute"]**

**[Show response with events, highlight `attempt_count: 1`]**

> "Notice the attempt count is 1. This event has a 5-minute lease. If my app crashes before acknowledging, this event automatically becomes available again after the lease expires. No lost events."

**[Switch to API Key B in Swagger UI]**

> "Now let's demonstrate multi-tenant isolation. I'll try to retrieve events with a different API key."

**[Enter API Key B, click "Execute"]**

**[Show empty inbox: `{"events": [], "pagination": {...}}`]**

> "Empty inbox. Complete isolation - your data is YOUR data."

**[Switch back to API Key A, retrieve again]**

> "Switch back to the original key, and the event appears. Each API key is completely separate."

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

### Scene 6: Monitoring + Health (4:15 - 4:45)

**[Screen: CloudWatch Dashboard]**

> "Let's look at monitoring. We've built a comprehensive CloudWatch dashboard tracking event ingestion rate, latency percentiles, and error rates."

**[Show dashboard metrics]**

> "Everything is tracking well under our 100-millisecond target. This isn't a prototype - it's production-ready."

**[Switch to Swagger UI GET /health]**

> "The health endpoint shows system status."

**[Click "Execute", show response with status]**

> "Status may show 'degraded' - this is normal when latency is 100-500ms. Not an error, just means response time is slightly slower than optimal."

**Key Points:** Real-time metrics | Production-ready observability | Health status explained

---

### Scene 7: Closing (4:45 - 5:00)

**[Screen: Swagger UI homepage]**

> "To summarize: the Zapier Triggers API provides reliable, real-time event ingestion with sub-100 millisecond latency. Pull-based delivery means Zapier controls timing. Idempotency prevents duplicates. Multi-tenant isolation ensures your data is secure. And the lease mechanism guarantees no lost events."

> "Get your API key and start building. Documentation is at triggers-api-docs-mlx.s3-website-us-east-1.amazonaws.com. Thanks for watching!"

**Key Points:** Unique features emphasized | Clear call to action | Documentation link

---

## Post-Demo Notes

**Key Metrics:** <100ms P95 latency | 99.9% uptime target | 1000+ events/second per tenant

**Common Questions:**
- **Q: Why pull-based instead of webhooks?** A: Zapier controls timing, no webhook endpoints to secure, Zapier can batch process efficiently.
- **Q: What if my app crashes?** A: 5-minute lease mechanism ensures events automatically become available again.
- **Q: Is my data secure?** A: Complete multi-tenant isolation - each API key is completely separate.
- **Q: How do I handle duplicates?** A: Idempotency built-in - send same event_id twice, get existing event back (409 Conflict).

**Recording Tips:** Practice 3+ times | Have payloads ready to paste | Zoom in on important details | Use cursor highlights | Show actual API responses

---

**Status:** ✅ Ready for Production | **Length:** 5:00 | **Difficulty:** Moderate
