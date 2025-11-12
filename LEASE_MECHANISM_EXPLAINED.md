# Lease Mechanism Explanation

## What You Experienced

You ran `GET /inbox` twice after posting an event, and the second time no events were returned. **This is correct behavior.**

## How the Lease Mechanism Works

### Overview
When you retrieve events from `/inbox`, they are automatically **leased** for 5 minutes. This prevents duplicate delivery while you're processing them.

### Step-by-Step Flow

1. **POST /events** - Event is created with `status: "pending"`, `in_flight_until: null`

2. **First GET /inbox** - Event is retrieved AND automatically leased:
   - Event `status` remains `"pending"`
   - Event `in_flight_until` is set to `now + 5 minutes`
   - Event `attempt_count` is incremented
   - Event is returned in the response

3. **Second GET /inbox (within 5 minutes)** - Event is NOT returned because:
   - Event `status` is still `"pending"` (good)
   - BUT `in_flight_until` is still in the future (lease is active)
   - System filters out leased events to prevent duplicate delivery

4. **After 5 minutes** - If you call GET /inbox again:
   - Lease has expired (`in_flight_until < now`)
   - Event becomes visible again
   - Event is re-leased for another 5 minutes
   - This allows for re-delivery if processing failed

5. **POST /inbox/ack** - Event is acknowledged:
   - Event `status` changes to `"acknowledged"`
   - Event `in_flight_until` is cleared
   - Event will NEVER appear in future `/inbox` calls

## Code Reference

From `src/lib/storage.py` lines 442-456:

```python
filtered_items = []
for item in items:
    in_flight_until = item.get('in_flight_until')
    if in_flight_until is None:
        # No lease - include
        filtered_items.append(item)
    else:
        # Check if lease expired
        try:
            lease_expiry = datetime.fromisoformat(in_flight_until.replace('Z', '+00:00'))
            if lease_expiry < now:
                # Lease expired - include
                filtered_items.append(item)
            # else: lease still active - exclude
        except Exception:
            # If parsing fails, include the item (safer)
            filtered_items.append(item)
```

And from lines 497-520, events are automatically leased when retrieved:

```python
# Set leases on retrieved events
lease_expiry = (now + timedelta(minutes=LEASE_DURATION_MINUTES)).isoformat()

for item in items:
    event_id = item['id']
    current_attempt_count = item.get('attempt_count', 0)
    
    try:
        get_events_table().update_item(
            Key={
                'pk': pk,
                'sk': item['sk']
            },
            UpdateExpression='SET in_flight_until = :lease, attempt_count = :count',
            ExpressionAttributeValues={
                ':lease': lease_expiry,
                ':count': current_attempt_count + 1
            }
        )
```

## Why This Design?

### Prevents Duplicate Processing
- Multiple workers can poll `/inbox` without getting the same events
- Events are "locked" for 5 minutes while being processed

### Enables Retry
- If processing fails and you don't acknowledge, the event becomes available again after 5 minutes
- `attempt_count` tracks how many times the event has been retrieved

### At-Least-Once Delivery
- Events are only removed from the inbox after explicit acknowledgment
- Ensures no events are lost due to processing failures

## Testing the Full Flow

```bash
# 1. Create an event
curl -X POST http://localhost:3000/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "event_type": "test.demo.event",
    "timestamp": "2025-11-12T00:00:00Z",
    "data": {"test": true}
  }'

# 2. Retrieve it (first time - event is leased)
curl http://localhost:3000/inbox \
  -H "X-API-Key: YOUR_API_KEY"
# Returns: 1 event with attempt_count: 1

# 3. Try to retrieve again immediately (within 5 minutes)
curl http://localhost:3000/inbox \
  -H "X-API-Key: YOUR_API_KEY"
# Returns: empty events array (event is leased)

# 4. Wait 5+ minutes, then retrieve again
sleep 301
curl http://localhost:3000/inbox \
  -H "X-API-Key: YOUR_API_KEY"
# Returns: same event with attempt_count: 2 (re-leased)

# 5. Acknowledge the event
curl -X POST http://localhost:3000/inbox/ack \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"event_ids": ["evt_YOUR_EVENT_ID"]}'

# 6. Try to retrieve one more time
curl http://localhost:3000/inbox \
  -H "X-API-Key: YOUR_API_KEY"
# Returns: empty events array (event is acknowledged, never returns)
```

## Summary

| Action | Event Status | in_flight_until | Appears in /inbox? |
|--------|-------------|-----------------|-------------------|
| POST /events | pending | null | ✅ Yes |
| GET /inbox (1st time) | pending | now + 5min | ✅ Yes (then leased) |
| GET /inbox (2nd time, <5min) | pending | future timestamp | ❌ No (leased) |
| GET /inbox (after 5min) | pending | past timestamp | ✅ Yes (lease expired) |
| POST /inbox/ack | acknowledged | null | ❌ No (forever) |

**This is the intended behavior for at-least-once delivery with duplicate prevention.**

