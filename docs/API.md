# Zapier Triggers API - Usage Guide

Complete guide to using the Zapier Triggers API for event ingestion and delivery.

## Table of Contents

- [Authentication](#authentication)
- [Endpoints](#endpoints)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)
- [Rate Limiting](#rate-limiting)
- [Monitoring](#monitoring)

## Authentication

### API Key Format

All API requests require authentication via the `X-API-Key` header. API keys are in the format:

```
ak_{32 random characters}
```

Example: `ak_abc123def456ghi789jkl012mno345pqr`

### Obtaining API Keys

API keys are obtained from your Zapier account administrator. Each API key is scoped to a single tenant, ensuring complete data isolation.

### Using API Keys

Include the API key in all requests:

```bash
curl -H "X-API-Key: ak_your_api_key_here" ...
```

### Authentication Errors

If authentication fails, you'll receive a `401 Unauthorized` response:

```json
{
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "message": "Invalid or missing API key",
    "details": {
      "detail": "X-API-Key header is required"
    }
  }
}
```

Common causes:
- Missing `X-API-Key` header
- Invalid API key format
- Inactive API key
- API key not found in database

## Endpoints

### POST /events

Ingest a new event into the system.

#### Request

```bash
POST /events
Content-Type: application/json
X-API-Key: ak_your_api_key
```

```json
{
  "id": "evt_abc123xyz789",  // Optional, auto-generated if missing
  "event_type": "user.created",
  "timestamp": "2025-11-11T15:30:45Z",
  "data": {
    "user_id": "12345",
    "email": "user@example.com"
  }
}
```

#### Request Fields

- **`id`** (optional): Event identifier. If not provided, a unique ID is generated automatically. Format: `evt_{base64url_32chars}`
- **`event_type`** (required): Event type in dot-notation format. Must match pattern: `^[a-z0-9_]+(\.[a-z0-9_]+){2,}$` (3-100 characters)
- **`timestamp`** (required): Event occurrence time in ISO 8601 format (e.g., `2025-11-11T15:30:45Z`)
- **`data`** (required): Event payload as arbitrary JSON object

#### Response (201 Created)

```json
{
  "id": "evt_abc123xyz789",
  "status": "accepted",
  "created_at": "2025-11-11T15:30:45.123Z"
}
```

#### Idempotency

If an event with the same `id` already exists, the API returns `409 Conflict`:

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Event with this ID already exists",
    "details": {
      "event_id": "evt_abc123xyz789",
      "detail": "Event with this ID was already ingested. Use a different ID or omit to auto-generate."
    }
  }
}
```

**Best Practice**: Omit the `id` field to let the API generate unique IDs automatically, or ensure your IDs are globally unique.

#### Storage Routing

- **Payloads <400KB**: Stored inline in DynamoDB
- **Payloads ≥400KB**: Stored in S3 with reference in DynamoDB
- **S3 Fallback**: If S3 write fails, payload is stored in DynamoDB (may exceed 400KB threshold)

#### Example: cURL

```bash
curl -X POST https://api.zapier.com/triggers/v1/events \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_your_api_key" \
  -d '{
    "event_type": "user.created",
    "timestamp": "2025-11-11T15:30:45Z",
    "data": {
      "user_id": "12345",
      "email": "user@example.com"
    }
  }'
```

### GET /inbox

Retrieve pending events from your inbox.

#### Request

```bash
GET /inbox?limit=25&cursor=1699712345_evt_abc123&after=2025-11-11T00:00:00Z&before=2025-11-11T23:59:59Z&event_type=user.created&status=pending
X-API-Key: ak_your_api_key
```

#### Query Parameters

- **`limit`** (optional): Number of events to return (default: 25, max: 100)
- **`cursor`** (optional): Pagination cursor from previous response (expires after 24 hours)
- **`after`** (optional): Filter events after this ISO 8601 timestamp
- **`before`** (optional): Filter events before this ISO 8601 timestamp
- **`event_type`** (optional): Filter by exact event type (dot-notation)
- **`status`** (optional): Filter by status (`pending` or `acknowledged`)

#### Response (200 OK)

```json
{
  "events": [
    {
      "id": "evt_abc123",
      "event_type": "user.created",
      "timestamp": "2025-11-11T15:30:45Z",
      "data": {
        "user_id": "12345",
        "email": "user@example.com"
      },
      "created_at": "2025-11-11T15:30:45.123Z",
      "attempt_count": 1
    }
  ],
  "pagination": {
    "next_cursor": "1699712345_evt_abc123",
    "has_more": true
  }
}
```

#### Lease Mechanism

Events retrieved from the inbox are leased for 5 minutes. During the lease period:
- The same event will not appear in subsequent queries
- If not acknowledged within 5 minutes, the event becomes available again
- The `attempt_count` is incremented each time an event is retrieved

**Best Practice**: Acknowledge events promptly after processing to prevent them from reappearing.

#### Pagination

Use the `cursor` from the response to fetch the next page:

```bash
GET /inbox?limit=25&cursor=1699712345_evt_abc123
```

**Important**: Cursors expire after 24 hours. If you use an expired cursor, you'll receive a `400 Bad Request` error.

#### Example: cURL

```bash
# First page
curl -X GET "https://api.zapier.com/triggers/v1/inbox?limit=25" \
  -H "X-API-Key: ak_your_api_key"

# Next page (using cursor from previous response)
curl -X GET "https://api.zapier.com/triggers/v1/inbox?limit=25&cursor=1699712345_evt_abc123" \
  -H "X-API-Key: ak_your_api_key"
```

### POST /inbox/ack

Acknowledge processed events to prevent them from being retrieved again.

#### Request

```bash
POST /inbox/ack
Content-Type: application/json
X-API-Key: ak_your_api_key
```

```json
{
  "event_ids": ["evt_abc123", "evt_def456", "evt_xyz789"]
}
```

#### Request Fields

- **`event_ids`** (required): Array of event IDs to acknowledge (min: 1, max: 100)

#### Response (200 OK)

```json
{
  "acknowledged": ["evt_abc123", "evt_def456"],
  "failed": [
    {
      "event_id": "evt_xyz789",
      "error": "event not found or already acknowledged"
    }
  ]
}
```

#### Idempotency

Acknowledging the same event multiple times is safe and returns success. This allows for retry logic without side effects.

#### Partial Success

If some events fail (e.g., not found or already acknowledged), they are returned in the `failed` array. Successfully acknowledged events are in `acknowledged`.

#### Example: cURL

```bash
curl -X POST https://api.zapier.com/triggers/v1/inbox/ack \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_your_api_key" \
  -d '{
    "event_ids": ["evt_abc123", "evt_def456"]
  }'
```

### GET /health

Check the health status of the API and its dependencies.

#### Request

```bash
GET /health
X-API-Key: ak_your_api_key
```

#### Response (200 OK - Healthy)

```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T15:30:45Z",
  "version": "1.0.0",
  "dependencies": {
    "dynamodb": "healthy",
    "s3": "healthy"
  }
}
```

#### Response (200 OK - Degraded)

```json
{
  "status": "degraded",
  "timestamp": "2025-11-11T15:30:45Z",
  "version": "1.0.0",
  "dependencies": {
    "dynamodb": "healthy",
    "s3": "degraded"
  }
}
```

#### Response (503 Service Unavailable - Unhealthy)

```json
{
  "status": "unhealthy",
  "timestamp": "2025-11-11T15:30:45Z",
  "version": "1.0.0",
  "dependencies": {
    "dynamodb": "unhealthy",
    "s3": "healthy"
  }
}
```

#### Status Codes

- **200**: System is healthy or degraded (operational)
- **503**: System is unhealthy (DynamoDB unavailable)

#### Status Values

- **`healthy`**: All dependencies responding within 100ms
- **`degraded`**: One dependency slow/unavailable, but core (DynamoDB) operational
- **`unhealthy`**: Core dependency (DynamoDB) unavailable

#### Example: cURL

```bash
curl -X GET https://api.zapier.com/triggers/v1/health \
  -H "X-API-Key: ak_your_api_key"
```

## Error Handling

### Error Response Format

All errors return a structured `ErrorResponse`:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "field_name",
      "issue": "Description of the issue"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request payload or query parameters |
| `AUTHENTICATION_ERROR` | 401 | Invalid or missing API key |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Duplicate event ID (idempotency violation) |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests (rate limit exceeded) |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `SERVICE_UNAVAILABLE` | 503 | Service unavailable (dependencies down) |

### Common Errors

#### 400 Bad Request - Validation Error

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid event payload",
    "details": {
      "field": "timestamp",
      "issue": "must be ISO 8601 format"
    }
  }
}
```

**Causes:**
- Missing required fields
- Invalid field formats (timestamp, event_type, event_id)
- Invalid query parameters
- Expired cursor (>24 hours old)

**Solution**: Review the error details and fix the request payload.

#### 401 Unauthorized - Authentication Error

```json
{
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "message": "Invalid or missing API key"
  }
}
```

**Causes:**
- Missing `X-API-Key` header
- Invalid API key format
- Inactive API key
- API key not found

**Solution**: Verify API key is correct and active.

#### 409 Conflict - Duplicate Event

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Event with this ID already exists"
  }
}
```

**Causes:**
- Event with the same `id` already exists

**Solution**: Use a different event ID or omit `id` to auto-generate.

#### 413 Payload Too Large

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Payload size exceeds maximum allowed size (10MB)"
  }
}
```

**Causes:**
- Request body exceeds 10MB limit

**Solution**: Reduce payload size or split into multiple events.

#### 429 Too Many Requests

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after some time."
  }
}
```

**Causes:**
- Exceeded API Gateway throttling limits (1000 req/sec)

**Solution**: Implement exponential backoff and retry logic.

### Retry Logic

For transient errors (500, 503, 429), implement exponential backoff:

```python
import time
import random

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)
```

## Best Practices

### Event ID Generation

**Recommended**: Omit the `id` field and let the API generate unique IDs automatically.

If you need to provide your own IDs:
- Use a globally unique identifier (UUID, timestamp + random, etc.)
- Format: `evt_{base64url_32chars}`
- Ensure uniqueness across all events

### Event Type Naming

Use dot-notation with clear hierarchy:

```
{namespace}.{resource}.{action}
```

Examples:
- `user.created`
- `order.completed`
- `payment.processed`
- `notification.sent`

**Guidelines:**
- Use lowercase letters, numbers, and underscores
- Minimum 3 segments (e.g., `user.created`, not `user`)
- Maximum 100 characters total
- Be consistent across your application

### Timestamp Format

Always use ISO 8601 format with timezone:

```
2025-11-11T15:30:45Z
```

**Best Practice**: Use UTC timestamps to avoid timezone issues.

### Pagination

**Recommended Pattern**:

1. Start with `limit=25` (default)
2. Use `cursor` from response for next page
3. Continue until `has_more` is `false`
4. Handle cursor expiry (24 hours)

```python
def get_all_events(client, limit=25):
    events = []
    cursor = None
    
    while True:
        response = client.get_inbox(limit=limit, cursor=cursor)
        events.extend(response['events'])
        
        if not response['pagination']['has_more']:
            break
        
        cursor = response['pagination']['next_cursor']
    
    return events
```

### Lease Management

**Best Practice**: Acknowledge events promptly after processing:

1. Retrieve events from inbox
2. Process events immediately
3. Acknowledge events before lease expires (5 minutes)
4. Handle failures gracefully (events will reappear after lease expiry)

```python
def process_events(client):
    # Retrieve events
    inbox = client.get_inbox(limit=25)
    
    # Process events
    event_ids = []
    for event in inbox['events']:
        try:
            process_event(event)
            event_ids.append(event['id'])
        except Exception as e:
            # Log error, don't acknowledge failed events
            log_error(e, event)
    
    # Acknowledge successfully processed events
    if event_ids:
        client.acknowledge(event_ids)
```

### Error Handling

**Best Practice**: Implement comprehensive error handling:

```python
def send_event_safely(client, event_data):
    try:
        response = client.send_event(**event_data)
        return response
    except ValidationError as e:
        # Fix payload and retry
        log_error("Validation error", e)
        return None
    except ConflictError as e:
        # Event already exists, skip
        log_info("Event already exists", e)
        return None
    except RateLimitError as e:
        # Implement backoff and retry
        wait_and_retry(client.send_event, event_data)
    except Exception as e:
        # Log and handle unexpected errors
        log_error("Unexpected error", e)
        raise
```

### Batch Operations

**Best Practice**: Use batch acknowledgment for efficiency:

```python
# Process events in batches
def process_batch(client, batch_size=100):
    events = get_all_events(client, limit=batch_size)
    
    # Process all events
    processed_ids = []
    for event in events:
        process_event(event)
        processed_ids.append(event['id'])
    
    # Acknowledge in batches of 100 (max)
    for i in range(0, len(processed_ids), 100):
        batch = processed_ids[i:i+100]
        client.acknowledge(batch)
```

## Rate Limiting

### Limits

- **Default**: 1000 requests/second
- **Burst**: 2000 requests

### Handling Rate Limits

When you receive a `429 Too Many Requests` response:

1. **Implement Exponential Backoff**: Wait before retrying
2. **Reduce Request Rate**: Lower concurrency or batch size
3. **Monitor Rate**: Track your request rate and stay under limits

### Example: Rate Limit Handling

```python
import time
import random

def handle_rate_limit(func, *args, **kwargs):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            
            # Exponential backoff with jitter
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)
```

## Monitoring

### CloudWatch Metrics

All handlers emit CloudWatch metrics with namespace `ZapierTriggers`:

- **EventIngested**: Event ingestion count (dimensions: TenantId, EventType)
- **InboxRetrieved**: Inbox retrieval count (dimensions: TenantId)
- **EventAcknowledged**: Acknowledgment count (dimensions: TenantId)
- **EventLatency**: Request latency (P50/P95/P99 percentiles)

### CloudWatch Alarms

Configure alarms for:
- **High Error Rate**: >10 5XX errors in 5 minutes
- **High Latency**: P95 latency >200ms in 5 minutes

See `docs/cloudwatch-alarms.md` for alarm configuration.

### CloudWatch Dashboard

Create a dashboard with widgets for:
- Event ingestion rate
- API latency (P50/P95/P99)
- Error rates (4XX/5XX)
- Event volume over time
- Per-tenant breakdowns

See `docs/cloudwatch-dashboard.md` for dashboard configuration.

### Structured Logging

All handlers emit structured JSON logs with context:
- `event_id`: Event identifier
- `tenant_id`: Tenant identifier
- `event_type`: Event type
- `payload_size`: Payload size in bytes
- `storage_type`: Storage type (dynamodb/s3)
- `latency_ms`: Request latency

Query logs using CloudWatch Logs Insights:

```
fields @timestamp, event_id, tenant_id, event_type, latency_ms
| filter event_type = "user.created"
| stats avg(latency_ms) by tenant_id
```

## Additional Resources

- [OpenAPI Specification](openapi.yaml)
- [Swagger UI](../docs/swagger-ui/index.html)
- [Python Client Example](../examples/python_client.py)
- [Load Testing Guide](../tests/load/LOAD_TESTING.md)
- [CloudWatch Alarms](cloudwatch-alarms.md)
- [CloudWatch Dashboard](cloudwatch-dashboard.md)

