"""
Integration tests against deployed API (not mocked).

Tests the deployed API endpoints to verify they work correctly.
"""
import os
import json
import pytest
import requests
from datetime import datetime, timezone

# Configuration from environment or defaults
API_URL = os.environ.get('API_URL', 'https://xiz2bca1sg.execute-api.us-east-1.amazonaws.com')
API_KEY = os.environ.get('API_KEY', 'ak_test1234567890123456789012345678')
TENANT_ID = os.environ.get('TENANT_ID', 'tenant_550e8400-e29b-41d4-a716-446655440000')

HEADERS = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
}


class TestDeployedAPI:
    """Test suite for deployed API."""
    
    def test_health_endpoint(self):
        """Test GET /health endpoint."""
        response = requests.get(f'{API_URL}/health', headers=HEADERS, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'status' in data
        assert 'dependencies' in data
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']
        print(f"✓ Health check: {data['status']}")
    
    def test_ingest_event(self):
        """Test POST /events endpoint."""
        event_data = {
            'event_type': 'test.resource.action',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {'message': 'integration test'}
        }
        response = requests.post(
            f'{API_URL}/events',
            headers=HEADERS,
            json=event_data,
            timeout=10
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'id' in data
        assert 'status' in data
        assert data['status'] == 'accepted'
        print(f"✓ Event ingested: {data['id']}")
        return data['id']
    
    def test_retrieve_inbox(self):
        """Test GET /inbox endpoint."""
        response = requests.get(
            f'{API_URL}/inbox?limit=10',
            headers=HEADERS,
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'events' in data
        assert 'pagination' in data
        assert isinstance(data['events'], list)
        print(f"✓ Retrieved {len(data['events'])} events from inbox")
        return data['events']
    
    def test_acknowledge_event(self):
        """Test POST /inbox/ack endpoint."""
        # First, ingest an event
        event_id = self.test_ingest_event()
        
        # Wait a moment for event to be available
        import time
        time.sleep(2)
        
        # Retrieve it from inbox
        events = self.test_retrieve_inbox()
        event_ids = [e['id'] for e in events if e.get('id')]
        
        if not event_ids:
            pytest.skip("No events in inbox to acknowledge")
        
        # Acknowledge the first event
        ack_data = {'event_ids': [event_ids[0]]}
        response = requests.post(
            f'{API_URL}/inbox/ack',
            headers=HEADERS,
            json=ack_data,
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'acknowledged' in data
        assert event_ids[0] in data['acknowledged']
        print(f"✓ Acknowledged event: {event_ids[0]}")
    
    def test_end_to_end_flow(self):
        """Test complete flow: ingest → retrieve → ack."""
        # Ingest
        event_id = self.test_ingest_event()
        
        # Wait for event to be available
        import time
        time.sleep(2)
        
        # Retrieve
        events = self.test_retrieve_inbox()
        assert any(e['id'] == event_id for e in events), f"Event {event_id} not found in inbox"
        
        # Acknowledge
        ack_data = {'event_ids': [event_id]}
        response = requests.post(
            f'{API_URL}/inbox/ack',
            headers=HEADERS,
            json=ack_data,
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert event_id in data['acknowledged']
        
        # Verify it's no longer in inbox
        time.sleep(1)
        events_after = self.test_retrieve_inbox()
        assert not any(e['id'] == event_id for e in events_after), f"Event {event_id} still in inbox after ack"
        print(f"✓ End-to-end flow completed successfully")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

