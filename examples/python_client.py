"""
Zapier Triggers API Python Client Library

A simple, production-ready client for interacting with the Zapier Triggers API.

Example Usage:
    from python_client import ZapierTriggersClient
    
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
"""
import json
import time
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    raise ImportError(
        "The 'requests' library is required. Install it with: pip install requests"
    )


class ZapierTriggersError(Exception):
    """Base exception for Zapier Triggers API errors."""
    pass


class ValidationError(ZapierTriggersError):
    """Raised when request validation fails (400)."""
    pass


class AuthenticationError(ZapierTriggersError):
    """Raised when authentication fails (401)."""
    pass


class NotFoundError(ZapierTriggersError):
    """Raised when resource is not found (404)."""
    pass


class ConflictError(ZapierTriggersError):
    """Raised when duplicate event ID is detected (409)."""
    pass


class RateLimitError(ZapierTriggersError):
    """Raised when rate limit is exceeded (429)."""
    pass


class InternalError(ZapierTriggersError):
    """Raised when internal server error occurs (500)."""
    pass


class ServiceUnavailableError(ZapierTriggersError):
    """Raised when service is unavailable (503)."""
    pass


class ZapierTriggersClient:
    """
    Client for interacting with the Zapier Triggers API.
    
    Args:
        api_key: API key for authentication (format: ak_{32chars})
        base_url: Base URL for the API (default: https://api.zapier.com/triggers/v1)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retries for transient errors (default: 3)
        retry_backoff: Enable exponential backoff for retries (default: True)
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.zapier.com/triggers/v1",
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff: bool = True
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        })
    
    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API with error handling and retries.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., '/events')
            params: Query parameters (for GET requests)
            data: Request body data (for POST requests)
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            Various ZapierTriggersError subclasses based on HTTP status code
        """
        url = f"{self.base_url}{path}"
        
        for attempt in range(self.max_retries + 1):
            try:
                if method == 'GET':
                    response = self.session.get(url, params=params, timeout=self.timeout)
                elif method == 'POST':
                    response = self.session.post(
                        url,
                        json=data,
                        timeout=self.timeout
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Handle successful responses
                if response.status_code in (200, 201):
                    return response.json()
                
                # Handle error responses
                error_data = response.json() if response.content else {}
                error_code = error_data.get('error', {}).get('code', '')
                error_message = error_data.get('error', {}).get('message', '')
                
                # Map status codes to exceptions
                if response.status_code == 400:
                    raise ValidationError(f"{error_message} (400)")
                elif response.status_code == 401:
                    raise AuthenticationError(f"{error_message} (401)")
                elif response.status_code == 404:
                    raise NotFoundError(f"{error_message} (404)")
                elif response.status_code == 409:
                    raise ConflictError(f"{error_message} (409)")
                elif response.status_code == 413:
                    raise ValidationError(f"Payload too large: {error_message} (413)")
                elif response.status_code == 422:
                    raise ValidationError(f"Semantic validation error: {error_message} (422)")
                elif response.status_code == 429:
                    # Rate limit - retry with backoff
                    if attempt < self.max_retries and self.retry_backoff:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(wait_time)
                        continue
                    raise RateLimitError(f"{error_message} (429)")
                elif response.status_code == 500:
                    # Internal error - retry with backoff
                    if attempt < self.max_retries and self.retry_backoff:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(wait_time)
                        continue
                    raise InternalError(f"{error_message} (500)")
                elif response.status_code == 503:
                    # Service unavailable - retry with backoff
                    if attempt < self.max_retries and self.retry_backoff:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(wait_time)
                        continue
                    raise ServiceUnavailableError(f"{error_message} (503)")
                else:
                    raise ZapierTriggersError(
                        f"Unexpected status code {response.status_code}: {error_message}"
                    )
            
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
                raise ZapierTriggersError("Request timeout")
            
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(wait_time)
                    continue
                raise ZapierTriggersError(f"Request failed: {str(e)}")
        
        # Should never reach here, but just in case
        raise ZapierTriggersError("Max retries exceeded")
    
    def send_event(
        self,
        event_type: str,
        timestamp: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an event to the API.
        
        Args:
            event_type: Event type in dot-notation (e.g., 'user.created')
            timestamp: Event occurrence time in ISO 8601 format
            data: Event payload as dictionary
            event_id: Optional event identifier (auto-generated if not provided)
            
        Returns:
            Response dictionary with 'id', 'status', and 'created_at'
            
        Raises:
            ValidationError: If request validation fails
            ConflictError: If event ID already exists
            AuthenticationError: If API key is invalid
            RateLimitError: If rate limit is exceeded
            InternalError: If internal server error occurs
            
        Example:
            >>> response = client.send_event(
            ...     event_type="user.created",
            ...     timestamp="2025-11-11T15:30:45Z",
            ...     data={"user_id": "12345", "email": "user@example.com"}
            ... )
            >>> print(response['id'])
            'evt_abc123xyz789'
        """
        payload = {
            'event_type': event_type,
            'timestamp': timestamp,
            'data': data
        }
        
        if event_id:
            payload['id'] = event_id
        
        return self._make_request('POST', '/events', data=payload)
    
    def get_inbox(
        self,
        limit: int = 25,
        cursor: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve pending events from inbox.
        
        Args:
            limit: Number of events to return (default: 25, max: 100)
            cursor: Pagination cursor from previous response
            after: Filter events after this ISO 8601 timestamp
            before: Filter events before this ISO 8601 timestamp
            event_type: Filter by exact event type
            status: Filter by status ('pending' or 'acknowledged')
            
        Returns:
            Response dictionary with 'events' array and 'pagination' info
            
        Raises:
            ValidationError: If query parameters are invalid
            AuthenticationError: If API key is invalid
            
        Example:
            >>> inbox = client.get_inbox(limit=25)
            >>> for event in inbox['events']:
            ...     print(f"Event: {event['id']} - {event['event_type']}")
        """
        params = {'limit': limit}
        
        if cursor:
            params['cursor'] = cursor
        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if event_type:
            params['event_type'] = event_type
        if status:
            params['status'] = status
        
        return self._make_request('GET', '/inbox', params=params)
    
    def acknowledge(self, event_ids: List[str]) -> Dict[str, Any]:
        """
        Acknowledge processed events.
        
        Args:
            event_ids: List of event IDs to acknowledge (max: 100)
            
        Returns:
            Response dictionary with 'acknowledged' and 'failed' arrays
            
        Raises:
            ValidationError: If request validation fails
            AuthenticationError: If API key is invalid
            
        Example:
            >>> result = client.acknowledge(["evt_abc123", "evt_def456"])
            >>> print(f"Acknowledged: {len(result['acknowledged'])} events")
            >>> print(f"Failed: {len(result['failed'])} events")
        """
        if not event_ids:
            raise ValidationError("event_ids cannot be empty")
        
        if len(event_ids) > 100:
            raise ValidationError("event_ids cannot exceed 100 items")
        
        payload = {'event_ids': event_ids}
        return self._make_request('POST', '/inbox/ack', data=payload)
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check system health status.
        
        Returns:
            Response dictionary with 'status', 'timestamp', 'version', and 'dependencies'
            
        Raises:
            ServiceUnavailableError: If service is unhealthy
            
        Example:
            >>> health = client.health_check()
            >>> print(f"Status: {health['status']}")
            >>> print(f"DynamoDB: {health['dependencies']['dynamodb']}")
            >>> print(f"S3: {health['dependencies']['s3']}")
        """
        return self._make_request('GET', '/health')
    
    def get_all_events(
        self,
        limit: int = 25,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all events from inbox (handles pagination automatically).
        
        Args:
            limit: Number of events per page (default: 25, max: 100)
            filters: Optional filters (after, before, event_type, status)
            
        Returns:
            List of all events
            
        Example:
            >>> events = client.get_all_events(limit=25)
            >>> print(f"Total events: {len(events)}")
        """
        all_events = []
        cursor = None
        filters = filters or {}
        
        while True:
            inbox = self.get_inbox(
                limit=limit,
                cursor=cursor,
                **filters
            )
            
            all_events.extend(inbox['events'])
            
            if not inbox['pagination']['has_more']:
                break
            
            cursor = inbox['pagination']['next_cursor']
        
        return all_events


# Example usage
if __name__ == '__main__':
    # Initialize client
    client = ZapierTriggersClient(
        api_key="ak_test123456789012345678901234567890",
        base_url="http://localhost:3000"  # For local testing
    )
    
    # Example 1: Send an event
    print("Sending event...")
    try:
        response = client.send_event(
            event_type="user.created",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "user_id": "12345",
                "email": "user@example.com",
                "name": "John Doe"
            }
        )
        print(f"Event sent! ID: {response['id']}")
    except Exception as e:
        print(f"Error sending event: {e}")
    
    # Example 2: Retrieve inbox
    print("\nRetrieving inbox...")
    try:
        inbox = client.get_inbox(limit=25)
        print(f"Found {len(inbox['events'])} events")
        for event in inbox['events']:
            print(f"  - {event['id']}: {event['event_type']}")
    except Exception as e:
        print(f"Error retrieving inbox: {e}")
    
    # Example 3: Acknowledge events
    print("\nAcknowledging events...")
    try:
        inbox = client.get_inbox(limit=25)
        event_ids = [e['id'] for e in inbox['events']]
        
        if event_ids:
            result = client.acknowledge(event_ids)
            print(f"Acknowledged: {len(result['acknowledged'])} events")
            if result['failed']:
                print(f"Failed: {len(result['failed'])} events")
        else:
            print("No events to acknowledge")
    except Exception as e:
        print(f"Error acknowledging events: {e}")
    
    # Example 4: Health check
    print("\nChecking health...")
    try:
        health = client.health_check()
        print(f"Status: {health['status']}")
        print(f"DynamoDB: {health['dependencies']['dynamodb']}")
        print(f"S3: {health['dependencies']['s3']}")
    except Exception as e:
        print(f"Error checking health: {e}")

