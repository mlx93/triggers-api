# Python Client Example

This directory contains a Python client library for interacting with the Zapier Triggers API.

## Installation

Install the required dependency:

```bash
pip install requests
```

## Usage

### Basic Usage

```python
from python_client import ZapierTriggersClient

# Initialize client
client = ZapierTriggersClient(
    api_key="ak_your_api_key_here",
    base_url="https://api.zapier.com/triggers/v1"
)

# Send an event
response = client.send_event(
    event_type="user.created",
    timestamp="2025-11-11T15:30:45Z",
    data={"user_id": "12345", "email": "user@example.com"}
)
print(f"Event ID: {response['id']}")

# Retrieve inbox
inbox = client.get_inbox(limit=25)
for event in inbox['events']:
    print(f"Event: {event['id']} - {event['event_type']}")

# Acknowledge events
event_ids = [e['id'] for e in inbox['events']]
result = client.acknowledge(event_ids)
print(f"Acknowledged: {len(result['acknowledged'])} events")
```

### Error Handling

The client raises specific exceptions for different error conditions:

```python
from python_client import (
    ZapierTriggersClient,
    ValidationError,
    AuthenticationError,
    ConflictError,
    RateLimitError
)

client = ZapierTriggersClient(api_key="ak_your_api_key")

try:
    response = client.send_event(
        event_type="user.created",
        timestamp="2025-11-11T15:30:45Z",
        data={"user_id": "12345"}
    )
except ValidationError as e:
    print(f"Validation error: {e}")
except AuthenticationError as e:
    print(f"Authentication error: {e}")
except ConflictError as e:
    print(f"Duplicate event: {e}")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
```

### Retry Logic

The client automatically retries transient errors (500, 503, 429) with exponential backoff:

```python
client = ZapierTriggersClient(
    api_key="ak_your_api_key",
    max_retries=5,  # Default: 3
    retry_backoff=True  # Default: True
)
```

### Pagination

Retrieve all events automatically:

```python
# Get all events (handles pagination)
all_events = client.get_all_events(limit=25)
print(f"Total events: {len(all_events)}")

# With filters
filtered_events = client.get_all_events(
    limit=25,
    filters={
        'event_type': 'user.created',
        'after': '2025-11-11T00:00:00Z'
    }
)
```

### Complete Example

See `python_client.py` for a complete example with all endpoints.

## Running the Example

```bash
# Set your API key
export API_KEY="ak_your_api_key_here"

# Run the example
python python_client.py
```

For local testing:

```bash
# Start SAM local API
sam local start-api --port 3000

# Run example against local endpoint
python python_client.py
# (Update base_url in code to http://localhost:3000)
```

## API Reference

### ZapierTriggersClient

#### `__init__(api_key, base_url, timeout, max_retries, retry_backoff)`

Initialize the client.

- **api_key** (str): API key for authentication
- **base_url** (str): Base URL for the API (default: https://api.zapier.com/triggers/v1)
- **timeout** (int): Request timeout in seconds (default: 30)
- **max_retries** (int): Maximum retries for transient errors (default: 3)
- **retry_backoff** (bool): Enable exponential backoff (default: True)

#### `send_event(event_type, timestamp, data, event_id=None)`

Send an event to the API.

- **event_type** (str): Event type in dot-notation
- **timestamp** (str): Event occurrence time (ISO 8601)
- **data** (dict): Event payload
- **event_id** (str, optional): Event identifier (auto-generated if not provided)

Returns: Response dictionary with 'id', 'status', 'created_at'

#### `get_inbox(limit=25, cursor=None, after=None, before=None, event_type=None, status=None)`

Retrieve pending events from inbox.

- **limit** (int): Number of events to return (default: 25, max: 100)
- **cursor** (str, optional): Pagination cursor
- **after** (str, optional): Filter events after timestamp
- **before** (str, optional): Filter events before timestamp
- **event_type** (str, optional): Filter by event type
- **status** (str, optional): Filter by status ('pending' or 'acknowledged')

Returns: Response dictionary with 'events' array and 'pagination' info

#### `acknowledge(event_ids)`

Acknowledge processed events.

- **event_ids** (list): List of event IDs to acknowledge (max: 100)

Returns: Response dictionary with 'acknowledged' and 'failed' arrays

#### `health_check()`

Check system health status.

Returns: Response dictionary with 'status', 'timestamp', 'version', 'dependencies'

#### `get_all_events(limit=25, filters=None)`

Retrieve all events from inbox (handles pagination automatically).

- **limit** (int): Number of events per page (default: 25)
- **filters** (dict, optional): Filters (after, before, event_type, status)

Returns: List of all events

## Exception Classes

- **ZapierTriggersError**: Base exception
- **ValidationError**: Request validation failed (400)
- **AuthenticationError**: Authentication failed (401)
- **NotFoundError**: Resource not found (404)
- **ConflictError**: Duplicate event ID (409)
- **RateLimitError**: Rate limit exceeded (429)
- **InternalError**: Internal server error (500)
- **ServiceUnavailableError**: Service unavailable (503)

