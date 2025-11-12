/**
 * Quick k6 test to verify API connectivity (10 seconds, 5 VUs)
 */
import http from 'k6/http';
import { check } from 'k6';

const API_URL = __ENV.API_URL || 'http://localhost:3000';
const API_KEY = __ENV.API_KEY || 'ak_test123456789012345678901234567890';

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY
};

export const options = {
  vus: 5,
  duration: '10s',
};

export default function () {
  // Test health endpoint first
  const healthResponse = http.get(`${API_URL}/health`, { headers: headers });
  check(healthResponse, {
    'health status is 200': (r) => r.status === 200,
  });

  // Test event ingestion
  const payload = {
    event_type: 'test.quick.load',
    timestamp: new Date().toISOString(),
    data: { test: true, iteration: __VU }
  };

  const response = http.post(
    `${API_URL}/events`,
    JSON.stringify(payload),
    { headers: headers }
  );

  check(response, {
    'ingestion status is 201': (r) => r.status === 201,
    'response has event ID': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.id && body.id.startsWith('evt_');
      } catch (e) {
        return false;
      }
    }
  });
}

