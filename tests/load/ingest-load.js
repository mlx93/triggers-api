/**
 * k6 load test script for Zapier Triggers API.
 * 
 * Performance Targets:
 * - Throughput: 1000 events/sec
 * - Concurrent Users: 100
 * - P95 Latency: <100ms for ingestion
 * 
 * Test Scenarios:
 * - Ingestion load test (POST /events)
 * - Retrieval load test (GET /inbox)
 * - Acknowledgment load test (POST /inbox/ack)
 * 
 * Usage:
 *   k6 run --env API_URL=https://api.zapier.com/triggers/v1 --env API_KEY=ak_... ingest-load.js
 * 
 * For local testing:
 *   k6 run --env API_URL=http://localhost:3000 --env API_KEY=ak_... ingest-load.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const ingestionRate = new Rate('ingestion_success_rate');
const retrievalRate = new Rate('retrieval_success_rate');
const ackRate = new Rate('acknowledgment_success_rate');
const ingestionLatency = new Trend('ingestion_latency_ms');
const retrievalLatency = new Trend('retrieval_latency_ms');
const ackLatency = new Trend('acknowledgment_latency_ms');
const errorRate = new Counter('error_count');

// Configuration
const API_URL = __ENV.API_URL || 'http://localhost:3000';
const API_KEY = __ENV.API_KEY || 'ak_test123456789012345678901234567890';
const BASE_URL = API_URL;

// Test data generation
function generateEventId() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  const randomPart = Array.from({ length: 32 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  return `evt_${randomPart}`;
}

function generateEventType() {
  const types = [
    'user.created',
    'user.updated',
    'order.completed',
    'order.cancelled',
    'payment.processed',
    'notification.sent'
  ];
  return types[Math.floor(Math.random() * types.length)];
}

function generateEventPayload() {
  return {
    event_type: generateEventType(),
    timestamp: new Date().toISOString(),
    data: {
      id: Math.floor(Math.random() * 1000000),
      timestamp: Date.now(),
      metadata: {
        source: 'load_test',
        iteration: __VU,
        request: __ITER
      }
    }
  };
}

// Common headers
const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY
};

// Test options
export const options = {
  stages: [
    // Ramp-up phase: gradually increase to 100 concurrent users over 2 minutes
    { duration: '2m', target: 100 },
    // Steady-state phase: maintain 100 concurrent users for 5 minutes
    { duration: '5m', target: 100 },
    // Ramp-down phase: gradually decrease to 0 over 1 minute
    { duration: '1m', target: 0 }
  ],
  thresholds: {
    // Performance thresholds
    'http_req_duration': ['p(95)<100', 'p(99)<200'], // P95 < 100ms, P99 < 200ms
    'http_req_failed': ['rate<0.01'], // Error rate < 1%
    'ingestion_success_rate': ['rate>0.99'], // 99% success rate
    'retrieval_success_rate': ['rate>0.99'],
    'acknowledgment_success_rate': ['rate>0.99']
  }
};

// Test scenarios
export default function () {
  // Scenario 1: Event Ingestion (70% of requests)
  if (Math.random() < 0.7) {
    const payload = generateEventPayload();
    const startTime = Date.now();
    
    const response = http.post(
      `${BASE_URL}/events`,
      JSON.stringify(payload),
      { headers: headers }
    );
    
    const latency = Date.now() - startTime;
    ingestionLatency.add(latency);
    
    const success = check(response, {
      'ingestion status is 201': (r) => r.status === 201,
      'ingestion response has event ID': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.id && body.id.startsWith('evt_');
        } catch (e) {
          return false;
        }
      }
    });
    
    ingestionRate.add(success);
    if (!success) {
      errorRate.add(1);
    }
    
    // Store event ID for acknowledgment scenario
    if (success && response.status === 201) {
      try {
        const body = JSON.parse(response.body);
        __VU.eventIds = __VU.eventIds || [];
        __VU.eventIds.push(body.id);
      } catch (e) {
        // Ignore parse errors
      }
    }
  }
  
  // Scenario 2: Event Retrieval (20% of requests)
  else if (Math.random() < 0.9) { // 20% of total = 0.2 / 0.3 remaining = 0.67
    const startTime = Date.now();
    
    const response = http.get(
      `${BASE_URL}/inbox?limit=25`,
      { headers: headers }
    );
    
    const latency = Date.now() - startTime;
    retrievalLatency.add(latency);
    
    const success = check(response, {
      'retrieval status is 200': (r) => r.status === 200,
      'retrieval response has events array': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body.events);
        } catch (e) {
          return false;
        }
      }
    });
    
    retrievalRate.add(success);
    if (!success) {
      errorRate.add(1);
    }
    
    // Store event IDs from retrieval for acknowledgment
    if (success && response.status === 200) {
      try {
        const body = JSON.parse(response.body);
        if (body.events && body.events.length > 0) {
          __VU.eventIds = __VU.eventIds || [];
          body.events.forEach(event => {
            if (event.id && !__VU.eventIds.includes(event.id)) {
              __VU.eventIds.push(event.id);
            }
          });
        }
      } catch (e) {
        // Ignore parse errors
      }
    }
  }
  
  // Scenario 3: Event Acknowledgment (10% of requests)
  else {
    // Only acknowledge if we have event IDs
    if (__VU.eventIds && __VU.eventIds.length > 0) {
      // Take up to 10 event IDs for acknowledgment
      const eventIdsToAck = __VU.eventIds.splice(0, Math.min(10, __VU.eventIds.length));
      
      const startTime = Date.now();
      
      const response = http.post(
        `${BASE_URL}/inbox/ack`,
        JSON.stringify({ event_ids: eventIdsToAck }),
        { headers: headers }
      );
      
      const latency = Date.now() - startTime;
      ackLatency.add(latency);
      
      const success = check(response, {
        'acknowledgment status is 200': (r) => r.status === 200,
        'acknowledgment response has acknowledged array': (r) => {
          try {
            const body = JSON.parse(r.body);
            return Array.isArray(body.acknowledged);
          } catch (e) {
            return false;
          }
        }
      });
      
      ackRate.add(success);
      if (!success) {
        errorRate.add(1);
      }
    }
  }
  
  // Small sleep to avoid overwhelming the server
  sleep(0.1);
}

// Setup function (runs once before all VUs)
export function setup() {
  console.log(`Starting load test against ${BASE_URL}`);
  console.log(`API Key: ${API_KEY.substring(0, 10)}...`);
  
  // Health check
  const healthResponse = http.get(`${BASE_URL}/health`, { headers: headers });
  if (healthResponse.status !== 200) {
    console.warn(`Warning: Health check returned status ${healthResponse.status}`);
  }
  
  return {
    apiUrl: BASE_URL,
    apiKey: API_KEY
  };
}

// Teardown function (runs once after all VUs)
export function teardown(data) {
  console.log('Load test completed');
}

