# Zapier Triggers API - Demo Video Script

**Duration:** 5 minutes  
**Presenter:** Developer/Product Manager  
**Format:** Screen recording with voiceover  
**Audience:** Zapier team, developers, stakeholders

---

## Pre-Demo Setup Checklist

**Required:**
- [ ] API deployed to AWS (dev or prod environment)
- [ ] Swagger UI accessible at https://api.zapier.com/triggers/v1/docs
- [ ] API key generated and ready
- [ ] Sample event payloads prepared (small and large)
- [ ] Terminal/curl ready for CLI examples
- [ ] CloudWatch dashboard open in browser tab
- [ ] Screen recording software tested (QuickTime/OBS)
- [ ] Microphone tested for clear audio

**Browser Tabs (in order):**
1. Swagger UI (main demo interface)
2. AWS CloudWatch Dashboard
3. Terminal/command line
4. DynamoDB console (optional, for showing data)

---

## Script

### Scene 1: Introduction (0:00 - 0:45)

**[Screen: Title slide or Swagger UI homepage]**

**Narration:**
> "Hi everyone, I'm excited to show you the Zapier Triggers API - a new unified system that enables real-time, event-driven automation on the Zapier platform."

**[Click through Swagger UI interface]**

> "This API solves a critical problem: today, Zapier integrations rely on polling-based triggers, which introduces latency and complexity. The Triggers API provides a simple REST interface for any system to send events into Zapier in real time."

**[Highlight the three main endpoints: POST /events, GET /inbox, POST /inbox/ack]**

> "The API has three core endpoints: one for sending events, one for retrieving them, and one for acknowledging processed events. Let's see it in action."

**Key Points to Emphasize:**
- Real-time event processing
- Simple REST API
- Three core operations

---

### Scene 2: Swagger UI Overview (0:45 - 1:15)

**[Screen: Swagger UI with all endpoints visible]**

**Narration:**
> "We've built comprehensive API documentation using OpenAPI 3.1 and Swagger UI. This gives developers an interactive way to explore and test the API."

**[Scroll through the documentation]**

> "Each endpoint includes detailed schema definitions, example requests and responses, and you can test everything directly from this interface."

**[Click to expand POST /events endpoint]**

> "Let's start with event ingestion. This endpoint accepts JSON payloads with a few required fields: an event type, a timestamp in ISO 8601 format, and your event data."

**[Show the schema in Swagger UI]**

> "Notice the schema is flexible - you can send any JSON in the data field, and the API handles payloads up to 10 megabytes. For smaller events, we store everything in DynamoDB. For larger payloads, we automatically store the body in S3 and keep a reference in the database."

**Key Points to Emphasize:**
- Interactive documentation
- Clear schema definitions
- Automatic large payload handling

---

### Scene 3: Sending Events (1:15 - 2:30)

**[Screen: Swagger UI POST /events endpoint]**

**Narration:**
> "Let's send our first event. I'll click 'Try it out' here in Swagger."

**[Click "Try it out" button]**

**[Paste prepared event payload]**

**Example Payload:**
```json
{
  "event_type": "player.projection.created",
  "timestamp": "2025-11-11T15:30:45Z",
  "data": {
    "player_id": "12345",
    "player_name": "Mike Trout",
    "projection_value": 42.5,
    "season": "2025",
    "confidence": 0.87
  }
}
```

**[Enter API key in authorization field]**

> "I'm authenticating with my API key - notice it's passed in the X-API-Key header. Security is built-in."

**[Click "Execute"]**

> "And... we get a 201 response in under 100 milliseconds. The API returns the event ID and creation timestamp."

**[Show the response]**

```json
{
  "id": "evt_abc123xyz789",
  "status": "accepted",
  "created_at": "2025-11-11T15:30:45.123Z"
}
```

> "That event is now durably stored and ready to be processed. Let's send a larger event to demonstrate the automatic S3 fallback."

**[Paste a larger payload, ~500KB]**

**[Click "Execute" again]**

> "Same fast response, but behind the scenes, this payload was automatically stored in S3 because it exceeded our 400 kilobyte threshold. The API handles this transparently - developers don't need to think about it."

**Key Points to Emphasize:**
- Sub-100ms latency
- Automatic storage optimization
- Transparent for developers

---

### Scene 4: Retrieving Events from Inbox (2:30 - 3:30)

**[Screen: Switch to GET /inbox endpoint in Swagger UI]**

**Narration:**
> "Now let's retrieve those events. The inbox endpoint returns all pending events for the authenticated tenant."

**[Click "Try it out"]**

**[Set parameters: limit=25, event_type filter]**

> "We support cursor-based pagination and filtering. I can filter by event type, timestamp range, or status. Let me retrieve player projection events."

**[Enter API key, click "Execute"]**

**[Show response]**

```json
{
  "events": [
    {
      "id": "evt_abc123xyz789",
      "event_type": "player.projection.created",
      "timestamp": "2025-11-11T15:30:45Z",
      "data": {
        "player_id": "12345",
        "player_name": "Mike Trout",
        "projection_value": 42.5
      },
      "created_at": "2025-11-11T15:30:45.123Z",
      "attempt_count": 1
    }
  ],
  "pagination": {
    "next_cursor": "1699712345_evt_abc123",
    "has_more": false
  }
}
```

> "Notice the attempt count is 1 - this tracks how many times an event has been retrieved. Behind the scenes, we also set a 5-minute lease on these events."

**[Highlight attempt_count field]**

> "If my application crashes before acknowledging, these events will automatically become available again after the lease expires. This ensures at-least-once delivery without losing events."

**Key Points to Emphasize:**
- Flexible filtering and pagination
- Automatic lease mechanism
- Delivery guarantees

---

### Scene 5: Acknowledging Events (3:30 - 4:00)

**[Screen: Switch to POST /inbox/ack endpoint]**

**Narration:**
> "After processing events, we acknowledge them so they don't get delivered again. This endpoint accepts a batch of event IDs."

**[Click "Try it out"]**

**[Enter payload with event IDs]**

```json
{
  "event_ids": ["evt_abc123xyz789", "evt_def456xyz"]
}
```

**[Click "Execute"]**

**[Show response]**

```json
{
  "acknowledged": ["evt_abc123xyz789", "evt_def456xyz"],
  "failed": []
}
```

> "Perfect - both events were acknowledged. The API supports batch acknowledgment up to 100 events, making it efficient for high-throughput scenarios."

**[Optional: Show a failed acknowledgment example]**

> "If we try to acknowledge an invalid event ID, the API tells us exactly which ones succeeded and which failed. This makes error handling straightforward."

**Key Points to Emphasize:**
- Batch acknowledgment support
- Clear success/failure feedback
- Idempotent operations

---

### Scene 6: Monitoring & Observability (4:00 - 4:35)

**[Screen: Switch to CloudWatch Dashboard browser tab]**

**Narration:**
> "Let's look at monitoring. We've built a comprehensive CloudWatch dashboard that tracks everything."

**[Show dashboard with multiple graphs]**

> "Here you can see event ingestion rate, API latency broken down by percentiles - P50, P95, and P99 - and error rates. Everything is tracking well under our 100-millisecond target."

**[Point to specific metrics]**

> "This graph shows the distribution of event types we're processing. And here we track storage patterns - how many events went to DynamoDB versus S3."

**[Show logs in CloudWatch Logs Insights]**

> "All operations are logged with structured JSON, making it easy to debug issues or analyze patterns. We can query logs by tenant, event type, or any other dimension."

**[Optional: Show a log query example]**

**Key Points to Emphasize:**
- Real-time metrics
- Sub-100ms P95 latency
- Comprehensive logging

---

### Scene 7: Developer Experience & Closing (4:35 - 5:00)

**[Screen: Return to Swagger UI or show Python client code]**

**Narration:**
> "We've designed this API with developer experience as a top priority. Beyond the interactive documentation, we provide a Python client library and curl examples to get started quickly."

**[Optional: Show quick Python example]**

```python
from triggers_client import TriggersClient

client = TriggersClient(api_key="ak_your_key")

# Send an event
response = client.send_event(
    event_type="player.projection.created",
    data={"player_id": "12345", "value": 42.5}
)

# Retrieve events
inbox = client.get_inbox(limit=25)

# Acknowledge
client.acknowledge([event["id"] for event in inbox["events"]])
```

> "This is a complete integration in just a few lines of code."

**[Return to Swagger UI homepage]**

> "To summarize: the Zapier Triggers API provides reliable, real-time event ingestion with sub-100 millisecond latency, flexible delivery semantics with automatic retry, and a developer-friendly interface that makes integration straightforward."

**[Show key metrics/numbers if available]**

> "We're hitting our goals: 99.9% reliability, 50% latency reduction compared to polling, and developers can integrate in under 30 minutes."

**[Final screen: Thank you slide or contact information]**

> "Thanks for watching! If you have questions or want to start testing, check out the documentation at api.zapier.com/triggers. I'm excited to see what you build with this."

---

## Post-Demo Notes

### Key Metrics to Highlight
- **Latency:** <100ms P95 for all operations
- **Reliability:** 99.9% uptime
- **Developer Time:** <30 minutes from API key to first event
- **Throughput:** 1000+ events/second per tenant

### Common Questions to Prepare For
1. **Q: How does this compare to webhooks?**
   - A: This is pull-based by design for MVP simplicity. Push webhooks can be added in v2 if needed.

2. **Q: What happens if my system crashes mid-processing?**
   - A: The 5-minute lease mechanism ensures events automatically become available again. You won't lose events.

3. **Q: Can I filter by custom fields in the data payload?**
   - A: Not in MVP - filtering is on top-level fields (event_type, timestamp, status). Custom queries can be added based on demand.

4. **Q: What's the cost?**
   - A: Fully serverless, so you pay only for what you use. DynamoDB on-demand + Lambda + S3 costs are minimal for typical workloads.

5. **Q: How do I get an API key?**
   - A: Currently manual provisioning via admin script. Self-service portal planned for v2.

### Demo Tips
- **Practice timing:** Run through at least 3 times to stay within 5 minutes
- **Prepare payloads:** Have them in a text file ready to paste
- **Check lighting/audio:** Professional presentation matters
- **Zoom in on important details:** Make sure schema examples are readable
- **Use cursor highlights:** Tools like Mousepose can highlight your clicks
- **Have a backup plan:** If API is slow/down, have pre-recorded responses ready

### Recording Checklist
- [ ] Close unnecessary browser tabs
- [ ] Disable notifications (Do Not Disturb mode)
- [ ] Clear browser history/autocomplete for clean demo
- [ ] Test API key works before recording
- [ ] Check screen resolution (1080p minimum)
- [ ] Record test clip to verify audio levels
- [ ] Have water nearby for voiceover

---

**Script Status:** Ready for Production  
**Estimated Video Length:** 4:45 - 5:00  
**Difficulty:** Moderate - requires API to be deployed and functional  
**Audience Level:** Technical (developers and product managers)
