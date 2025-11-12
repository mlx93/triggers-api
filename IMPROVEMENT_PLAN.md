# Improvement Plan: Explicit Retry Logic & Latency Testing

**Date:** November 11, 2025  
**Status:** Planning Document  
**Purpose:** Ideas and recommendations for implementing explicit retry logic and < 100ms latency testing

---

## Table of Contents

1. [Explicit Retry Logic Improvements](#explicit-retry-logic-improvements)
2. [Latency Testing & Monitoring](#latency-testing--monitoring)
3. [Implementation Priority](#implementation-priority)
4. [Success Metrics](#success-metrics)

---

## Explicit Retry Logic Improvements

### 1. Server-Side Retry Mechanisms

#### 1.1 Retry-After Header in Error Responses
**Idea:** Add `Retry-After` header to error responses to guide client retry behavior.

**Implementation Approach:**
- Add `Retry-After` header to 429 (Rate Limit) responses
- Add `Retry-After` header to 503 (Service Unavailable) responses
- Calculate retry delay based on:
  - Rate limit: Time until rate limit window resets
  - Service unavailable: Estimated recovery time (e.g., 5 seconds)
  - Lease expiry: Time until event becomes available again (for /inbox)

**Code Changes:**
- Modify `ErrorResponse` schema to include optional `retry_after` field
- Update error handlers in `ingest.py`, `inbox.py`, `ack.py` to set header
- Add helper function `calculate_retry_after()` in `src/lib/errors.py`

**Example Response:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please retry after some time.",
    "details": {
      "retry_after_seconds": 60
    }
  }
}
```
Headers: `Retry-After: 60`

**Benefits:**
- Clients can implement intelligent retry logic
- Reduces unnecessary retry attempts
- Improves API efficiency

---

#### 1.2 Exponential Backoff Guidance in API Documentation
**Idea:** Document recommended retry strategies with exponential backoff examples.

**Implementation Approach:**
- Add "Retry Strategies" section to `docs/API.md`
- Provide code examples in Python, JavaScript, Go
- Include recommended backoff formula: `delay = min(base_delay * (2^attempt), max_delay)`
- Document retryable vs non-retryable errors

**Recommended Backoff Strategy:**
```
Initial delay: 1 second
Max delay: 60 seconds
Max attempts: 5
Backoff multiplier: 2
Jitter: ±20% random variation
```

**Retryable Errors:**
- 429 (Rate Limit Exceeded)
- 500 (Internal Server Error)
- 503 (Service Unavailable)
- 502 (Bad Gateway)
- 504 (Gateway Timeout)

**Non-Retryable Errors:**
- 400 (Bad Request)
- 401 (Unauthorized)
- 403 (Forbidden)
- 404 (Not Found)
- 409 (Conflict - idempotency)

**Documentation Structure:**
```markdown
## Retry Strategies

### Exponential Backoff
[Code examples for Python, JavaScript, Go]

### Retry-After Header
[How to use Retry-After header]

### Idempotency
[How to handle 409 Conflict errors]
```

---

#### 1.3 Client SDK with Built-in Retry Logic
**Idea:** Enhance `examples/python_client.py` with automatic retry logic.

**Implementation Approach:**
- Add `RetryConfig` class with configurable retry parameters
- Implement `retry_with_backoff()` decorator/context manager
- Add automatic retry for retryable errors
- Respect `Retry-After` header when present
- Add retry metrics (attempt count, total retry time)

**SDK Features:**
```python
from zapier_triggers import TriggersClient, RetryConfig

client = TriggersClient(
    api_key="ak_...",
    retry_config=RetryConfig(
        max_attempts=5,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True
    )
)

# Automatic retry on retryable errors
response = client.send_event(
    event_type="user.created",
    timestamp="2025-11-11T15:30:45Z",
    data={"user_id": "123"}
)
```

**Benefits:**
- Reduces client implementation complexity
- Standardizes retry behavior across clients
- Improves reliability

---

#### 1.4 Dead Letter Queue (DLQ) for Failed Events
**Idea:** Add SQS Dead Letter Queue for events that fail after maximum retries.

**Implementation Approach:**
- Create SQS queue for failed events
- Add Lambda function to process DLQ messages
- Store failed events in separate DynamoDB table with metadata:
  - Original event data
  - Failure reason
  - Retry attempt count
  - Timestamp
- Add `/events/failed` endpoint to retrieve failed events
- Add CloudWatch alarm for DLQ depth

**Use Cases:**
- Events that fail validation after multiple retries
- Events that fail storage after maximum attempts
- Events that exceed retry limit

**Benefits:**
- Prevents event loss
- Enables manual review and reprocessing
- Provides audit trail

**Priority:** P2 (Nice-to-have)

---

#### 1.5 Retry Policy Configuration via API
**Idea:** Allow tenants to configure retry policies per event type.

**Implementation Approach:**
- Add `retry_policy` field to event ingestion:
  ```json
  {
    "event_type": "user.created",
    "timestamp": "2025-11-11T15:30:45Z",
    "data": {...},
    "retry_policy": {
      "max_attempts": 3,
      "backoff_strategy": "exponential"
    }
  }
  ```
- Store retry policy in DynamoDB event item
- Use policy when event is retrieved from inbox
- Track retry attempts against policy

**Benefits:**
- Tenant-specific retry behavior
- Fine-grained control per event type
- Better resource utilization

**Priority:** P2 (Nice-to-have)

---

### 2. Client-Side Retry Enhancements

#### 2.1 Retry Metrics in Response Headers
**Idea:** Include retry-related metadata in response headers.

**Headers to Add:**
- `X-Retry-Available`: Boolean indicating if retry is recommended
- `X-Retry-After`: Seconds until retry is recommended (same as Retry-After)
- `X-Attempt-Count`: Current attempt count (for /inbox events)
- `X-Lease-Expires`: ISO 8601 timestamp when lease expires

**Implementation:**
- Add headers in `inbox.py` for retrieved events
- Add headers in error responses
- Document headers in OpenAPI spec

**Benefits:**
- Clients can make informed retry decisions
- Better observability

---

#### 2.2 Retry Best Practices Documentation
**Idea:** Create comprehensive retry guide with examples.

**Documentation Sections:**
1. **When to Retry**: Retryable vs non-retryable errors
2. **Retry Strategies**: Exponential backoff, linear backoff, fixed delay
3. **Idempotency**: How to handle duplicate events (409 Conflict)
4. **Rate Limiting**: How to handle 429 responses
5. **Lease Management**: How to handle lease expiry
6. **Code Examples**: Python, JavaScript, Go, curl

**Location:** `docs/RETRY_GUIDE.md`

---

## Latency Testing & Monitoring

### 1. Automated Latency Testing

#### 1.1 Continuous Load Testing with k6
**Idea:** Enhance existing k6 load tests to validate < 100ms latency target.

**Current State:**
- Load tests exist in `tests/load/ingest-load.js`
- Target: P95 < 100ms, P99 < 200ms
- No automated validation of targets

**Improvements:**

**A. Add Latency Assertions:**
```javascript
// In k6 test script
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const ingestionLatency = new Trend('ingestion_latency_ms');

export default function () {
  const start = Date.now();
  const response = http.post(`${API_URL}/events`, ...);
  const latency = Date.now() - start;
  
  ingestionLatency.add(latency);
  
  // Assert P95 < 100ms
  check(response, {
    'latency P95 < 100ms': () => {
      const p95 = ingestionLatency.values['p(95)'];
      return p95 < 100;
    }
  });
}
```

**B. Add CI/CD Integration:**
- Run load tests on every deployment
- Fail build if P95 latency > 100ms
- Generate latency report as artifact

**C. Add Latency Regression Detection:**
- Compare current test results with baseline
- Alert if latency increases > 20% from baseline
- Store baseline in S3 or DynamoDB

**Implementation:**
- Update `tests/load/ingest-load.js` with assertions
- Add GitHub Actions workflow for automated testing
- Add baseline comparison logic

---

#### 1.2 Synthetic Monitoring with AWS Synthetics
**Idea:** Create Canary scripts to continuously monitor latency from multiple regions.

**Implementation Approach:**
- Create AWS Synthetics Canary script
- Monitor `/events` endpoint from multiple AWS regions
- Measure latency: DNS lookup, connection, TLS handshake, request/response
- Alert if P95 latency > 100ms
- Run every 5 minutes

**Canary Script Structure:**
```javascript
// canary-scripts/latency-monitor.js
const synthetics = require('Synthetics');
const log = require('SyntheticsLogger');

const apiEndpoint = process.env.API_ENDPOINT;
const apiKey = process.env.API_KEY;

exports.handler = async () => {
  const startTime = Date.now();
  
  const response = await synthetics.executeHttpStep('ingest_event', {
    requestOptions: {
      hostname: apiEndpoint,
      method: 'POST',
      path: '/events',
      headers: {
        'X-API-Key': apiKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        event_type: 'synthetic.monitor.test',
        timestamp: new Date().toISOString(),
        data: { test: true }
      })
    }
  });
  
  const latency = Date.now() - startTime;
  
  // Assert latency < 100ms
  if (latency > 100) {
    throw new Error(`Latency ${latency}ms exceeds 100ms target`);
  }
  
  return response;
};
```

**Benefits:**
- Continuous monitoring from production-like environment
- Multi-region perspective
- Early detection of latency issues

---

#### 1.3 Performance Benchmark Suite
**Idea:** Create dedicated performance test suite with latency assertions.

**Test Scenarios:**
1. **Cold Start Latency**: First request after idle period
2. **Warm Latency**: Subsequent requests (cached Lambda)
3. **Concurrent Load**: 100 concurrent requests
4. **Large Payload**: Events with 400KB+ payloads (S3 routing)
5. **Small Payload**: Events < 400KB (DynamoDB routing)

**Implementation:**
- Create `tests/performance/test_latency.py`
- Use `pytest-benchmark` for latency measurements
- Assert P50, P95, P99 percentiles
- Generate performance report

**Example Test:**
```python
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

def test_ingestion_latency_p95(benchmark, api_client):
    """Test that P95 latency is < 100ms for event ingestion."""
    def ingest_event():
        start = time.time()
        response = api_client.post('/events', json={
            'event_type': 'test.latency',
            'timestamp': '2025-11-11T15:30:45Z',
            'data': {'test': True}
        })
        latency = (time.time() - start) * 1000
        assert response.status_code == 201
        return latency
    
    latencies = benchmark.pedantic(
        ingest_event,
        iterations=100,
        rounds=10
    )
    
    p95 = np.percentile(latencies, 95)
    assert p95 < 100, f"P95 latency {p95}ms exceeds 100ms target"
```

---

### 2. CloudWatch Monitoring & Alarms

#### 2.1 Enhanced Latency Alarms
**Idea:** Add CloudWatch alarms specifically for < 100ms latency target.

**Current State:**
- Alarm exists for P95 > 200ms (from `docs/cloudwatch-alarms.md`)
- No alarm for < 100ms target

**New Alarms to Add:**

**A. P95 Latency > 100ms Alarm:**
```yaml
# In template.yaml
LatencyP95Alarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub 'zapier-triggers-latency-p95-${Environment}'
    AlarmDescription: Alert when P95 latency exceeds 100ms target
    MetricName: EventLatency
    Namespace: ZapierTriggers
    Statistic: p95
    Period: 300  # 5 minutes
    EvaluationPeriods: 1
    Threshold: 100
    ComparisonOperator: GreaterThanThreshold
    TreatMissingData: notBreaching
    Dimensions:
      - Name: Environment
        Value: !Ref Environment
      - Name: Endpoint
        Value: /events
    AlarmActions:
      - !Ref LatencyAlarmSNS  # SNS topic for notifications
```

**B. P99 Latency > 200ms Alarm:**
- Similar to above, but P99 threshold = 200ms

**C. Average Latency > 50ms Alarm:**
- Early warning indicator
- Threshold: 50ms (half of target)

**D. Latency Spike Detection:**
- Alert if latency increases > 50% from baseline
- Use CloudWatch Anomaly Detection

---

#### 2.2 Latency Dashboard Widgets
**Idea:** Enhance CloudWatch dashboard with latency-focused widgets.

**New Widgets:**

**A. Latency Target Compliance:**
- Gauge widget showing % of requests < 100ms
- Green: > 95%, Yellow: 90-95%, Red: < 90%

**B. Latency Distribution:**
- Histogram showing latency distribution
- Bins: 0-50ms, 50-100ms, 100-200ms, 200-500ms, > 500ms

**C. Latency Trend:**
- Line chart showing P50, P95, P99 over time
- Overlay with 100ms target line

**D. Latency by Endpoint:**
- Bar chart comparing latency across endpoints
- /events, /inbox, /inbox/ack

**E. Cold Start Impact:**
- Metric: Latency difference between cold and warm starts
- Track Lambda cold start frequency

**Implementation:**
- Update `docs/cloudwatch-dashboard.md` with new widgets
- Create CloudWatch dashboard JSON
- Add to SAM template or create via AWS CLI

---

#### 2.3 Real-Time Latency Monitoring
**Idea:** Add real-time latency monitoring with CloudWatch Logs Insights.

**CloudWatch Logs Insights Queries:**

**A. P95 Latency Query:**
```
fields @timestamp, latency_ms
| filter @message like /Event ingested successfully/
| parse @message /latency_ms":(\d+)/ as latency_ms
| stats p95(latency_ms) as p95_latency by bin(1m)
| filter p95_latency > 100
```

**B. Latency by Event Type:**
```
fields @timestamp, latency_ms, event_type
| filter @message like /Event ingested successfully/
| parse @message /latency_ms":(\d+).*event_type":"([^"]+)"/ as latency_ms, event_type
| stats avg(latency_ms) as avg_latency, p95(latency_ms) as p95_latency by event_type
```

**C. Slow Requests (> 100ms):**
```
fields @timestamp, latency_ms, event_id, tenant_id
| filter @message like /Event ingested successfully/
| parse @message /latency_ms":(\d+).*event_id":"([^"]+).*tenant_id":"([^"]+)/ as latency_ms, event_id, tenant_id
| filter latency_ms > 100
| sort latency_ms desc
| limit 100
```

**Benefits:**
- Real-time analysis of latency issues
- Identify slow event types or tenants
- Debug latency spikes

---

### 3. Load Testing Infrastructure

#### 3.1 Automated Load Test Pipeline
**Idea:** Integrate load testing into CI/CD pipeline.

**GitHub Actions Workflow:**
```yaml
# .github/workflows/performance-test.yml
name: Performance Tests
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install k6
        run: |
          sudo gpg -k
          sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6
      
      - name: Run Load Tests
        run: |
          k6 run --out json=results.json tests/load/ingest-load.js
        env:
          API_URL: ${{ secrets.API_URL }}
          API_KEY: ${{ secrets.API_KEY }}
      
      - name: Validate Latency Targets
        run: |
          python scripts/validate_latency.py results.json
      
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: results.json
      
      - name: Comment PR with Results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const results = require('./results.json');
            const p95 = results.metrics.http_req_duration.values.p95;
            const status = p95 < 100 ? '✅' : '❌';
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Performance Test Results\n\n${status} P95 Latency: ${p95}ms (target: < 100ms)`
            });
```

**Validation Script:**
```python
# scripts/validate_latency.py
import json
import sys

def validate_latency(results_file):
    with open(results_file) as f:
        results = json.load(f)
    
    metrics = results['metrics']
    p95 = metrics['http_req_duration']['values']['p95']
    p99 = metrics['http_req_duration']['values']['p99']
    
    print(f"P95 Latency: {p95}ms (target: < 100ms)")
    print(f"P99 Latency: {p99}ms (target: < 200ms)")
    
    if p95 > 100:
        print("❌ P95 latency exceeds 100ms target")
        sys.exit(1)
    
    if p99 > 200:
        print("❌ P99 latency exceeds 200ms target")
        sys.exit(1)
    
    print("✅ All latency targets met")

if __name__ == '__main__':
    validate_latency(sys.argv[1])
```

---

#### 3.2 Baseline Performance Tracking
**Idea:** Track performance baselines and detect regressions.

**Implementation:**
- Store baseline metrics in DynamoDB or S3
- Compare current test results with baseline
- Alert if latency increases > 20% from baseline
- Update baseline after successful deployments

**Baseline Schema:**
```json
{
  "baseline_id": "2025-11-11-v1.0.0",
  "p50_latency_ms": 35,
  "p95_latency_ms": 75,
  "p99_latency_ms": 120,
  "avg_latency_ms": 40,
  "timestamp": "2025-11-11T15:30:45Z",
  "git_commit": "abc123",
  "environment": "prod"
}
```

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 weeks)
1. ✅ Add `Retry-After` header to error responses
2. ✅ Add latency assertions to k6 load tests
3. ✅ Add P95 > 100ms CloudWatch alarm
4. ✅ Create retry best practices documentation

### Phase 2: Enhanced Monitoring (2-3 weeks)
5. ✅ Enhance CloudWatch dashboard with latency widgets
6. ✅ Add CloudWatch Logs Insights queries
7. ✅ Create performance benchmark suite
8. ✅ Add CI/CD integration for load tests

### Phase 3: Advanced Features (3-4 weeks)
9. ✅ Enhance Python client SDK with retry logic
10. ✅ Add AWS Synthetics Canary monitoring
11. ✅ Implement baseline performance tracking
12. ✅ Add retry metrics in response headers

### Phase 4: Optional Enhancements (Future)
13. ⚠️ Dead Letter Queue for failed events
14. ⚠️ Retry policy configuration via API
15. ⚠️ Multi-region latency monitoring

---

## Success Metrics

### Retry Logic Success Metrics
- **Retry-After Header Adoption**: % of clients using Retry-After header
- **Retry Success Rate**: % of retried requests that succeed
- **Average Retry Attempts**: Mean number of retries per failed request
- **Client SDK Usage**: % of clients using SDK with built-in retry

### Latency Testing Success Metrics
- **P95 Latency Compliance**: % of time P95 < 100ms (target: > 95%)
- **P99 Latency Compliance**: % of time P99 < 200ms (target: > 95%)
- **Latency Alert Response Time**: Time to resolve latency alerts (target: < 15 minutes)
- **Test Coverage**: % of endpoints with latency tests (target: 100%)
- **Baseline Regression Detection**: % of regressions caught before production (target: > 80%)

### Monitoring Success Metrics
- **Alarm Accuracy**: % of alarms that indicate real issues (target: > 90%)
- **False Positive Rate**: % of alarms that are false positives (target: < 10%)
- **Dashboard Usage**: Frequency of dashboard views by team
- **Latency Visibility**: Time to identify latency issues (target: < 5 minutes)

---

## Next Steps

1. **Review and Prioritize**: Review this plan with team, prioritize features
2. **Create Issues**: Create GitHub issues for each prioritized feature
3. **Design Review**: Conduct design review for high-priority features
4. **Implementation**: Begin with Phase 1 quick wins
5. **Measure**: Track success metrics after each phase

---

## Appendix: Example Code Snippets

### Retry-After Header Implementation
```python
# src/lib/errors.py
from datetime import datetime, timedelta, timezone

def calculate_retry_after(error_code: str, context: dict = None) -> int:
    """Calculate Retry-After value in seconds."""
    if error_code == "RATE_LIMIT_EXCEEDED":
        # Return time until rate limit window resets
        return context.get('rate_limit_reset_seconds', 60)
    elif error_code == "SERVICE_UNAVAILABLE":
        # Return estimated recovery time
        return 5
    elif error_code == "LEASE_ACTIVE":
        # Return time until lease expires
        lease_expiry = context.get('lease_expiry')
        if lease_expiry:
            now = datetime.now(timezone.utc)
            expiry = datetime.fromisoformat(lease_expiry.replace('Z', '+00:00'))
            return max(0, int((expiry - now).total_seconds()))
    return 60  # Default
```

### Latency Validation Script
```python
# scripts/validate_latency.py
import json
import sys
import numpy as np

def validate_latency(results_file, p95_target=100, p99_target=200):
    """Validate latency targets from k6 results."""
    with open(results_file) as f:
        results = json.load(f)
    
    metrics = results.get('metrics', {})
    http_req_duration = metrics.get('http_req_duration', {})
    values = http_req_duration.get('values', {})
    
    p95 = values.get('p95', 0)
    p99 = values.get('p99', 0)
    p50 = values.get('p50', 0)
    avg = values.get('avg', 0)
    
    print(f"Latency Metrics:")
    print(f"  Average: {avg:.2f}ms")
    print(f"  P50: {p50:.2f}ms")
    print(f"  P95: {p95:.2f}ms (target: < {p95_target}ms)")
    print(f"  P99: {p99:.2f}ms (target: < {p99_target}ms)")
    
    failed = False
    if p95 > p95_target:
        print(f"❌ P95 latency {p95:.2f}ms exceeds target {p95_target}ms")
        failed = True
    
    if p99 > p99_target:
        print(f"❌ P99 latency {p99:.2f}ms exceeds target {p99_target}ms")
        failed = True
    
    if not failed:
        print("✅ All latency targets met")
    
    return 0 if not failed else 1

if __name__ == '__main__':
    sys.exit(validate_latency(sys.argv[1]))
```

---

**End of Planning Document**

