# Load Testing with k6

This directory contains k6 load test scripts for the Zapier Triggers API.

## Prerequisites

Install k6:
- **macOS**: `brew install k6`
- **Linux**: See [k6 installation guide](https://grafana.com/docs/k6/latest/set-up/install-k6/)
- **Windows**: Download from [k6 releases](https://github.com/grafana/k6/releases)

## Running Load Tests

### Basic Usage

```bash
# Set environment variables
export API_URL="https://api.zapier.com/triggers/v1"
export API_KEY="ak_your_api_key_here"

# Run load test
k6 run tests/load/ingest-load.js
```

### Local Testing

For testing against `sam local`:

```bash
# Start SAM local API
sam local start-api --port 3000

# Run load test against local endpoint
k6 run --env API_URL=http://localhost:3000 --env API_KEY=ak_test123456789012345678901234567890 tests/load/ingest-load.js
```

### Custom Configuration

Override test parameters:

```bash
k6 run \
  --env API_URL=https://api-dev.zapier.com/triggers/v1 \
  --env API_KEY=ak_your_dev_key \
  --vus 50 \
  --duration 10m \
  tests/load/ingest-load.js
```

## Test Scenarios

The load test includes three scenarios:

1. **Event Ingestion (70%)**: POST /events
   - Generates random events with various event types
   - Measures ingestion latency and success rate

2. **Event Retrieval (20%)**: GET /inbox
   - Retrieves pending events
   - Measures retrieval latency and success rate

3. **Event Acknowledgment (10%)**: POST /inbox/ack
   - Acknowledges previously retrieved events
   - Measures acknowledgment latency and success rate

## Performance Targets

- **Throughput**: 1000 events/second
- **Concurrent Users**: 100
- **P95 Latency**: <100ms for ingestion
- **P99 Latency**: <200ms
- **Error Rate**: <1%

## Test Phases

1. **Ramp-up**: Gradually increase to 100 concurrent users over 2 minutes
2. **Steady-state**: Maintain 100 concurrent users for 5 minutes
3. **Ramp-down**: Gradually decrease to 0 over 1 minute

## Metrics Collected

- `http_req_duration`: HTTP request duration (P50/P95/P99)
- `http_req_failed`: Failed request rate
- `ingestion_success_rate`: Event ingestion success rate
- `retrieval_success_rate`: Event retrieval success rate
- `acknowledgment_success_rate`: Event acknowledgment success rate
- `ingestion_latency_ms`: Ingestion latency trend
- `retrieval_latency_ms`: Retrieval latency trend
- `acknowledgment_latency_ms`: Acknowledgment latency trend
- `error_count`: Total error count

## Output

k6 outputs real-time metrics during the test and a summary at the end:

```
     ✓ ingestion status is 201
     ✓ ingestion response has event ID
     ✓ retrieval status is 200
     ✓ acknowledgment status is 200

     checks.........................: 99.5% ✓ 9950    ✗ 50
     data_received..................: 2.5 MB  42 kB/s
     data_sent......................: 1.8 MB  30 kB/s
     http_req_duration..............: avg=45ms   min=12ms   med=38ms   max=250ms   p(95)=95ms   p(99)=180ms
     http_req_failed................: 0.50%  ✓ 50     ✗ 9950
     http_reqs......................: 10000  166.666667/s
     ingestion_success_rate.........: 100.00% ✓ 7000   ✗ 0
     retrieval_success_rate.........: 100.00% ✓ 2000   ✗ 0
     vus............................: 100    min=0    max=100
     vus_max........................: 100    min=100  max=100
```

## Troubleshooting

### High Error Rate

If error rate exceeds 1%:
- Check API Gateway throttling limits
- Verify API key is valid and active
- Check DynamoDB capacity (on-demand should auto-scale)
- Monitor CloudWatch metrics for bottlenecks

### High Latency

If P95 latency exceeds 100ms:
- Check Lambda cold starts (consider provisioned concurrency)
- Monitor DynamoDB read/write capacity
- Check S3 latency for large payloads
- Review CloudWatch metrics for bottlenecks

### Rate Limiting (429)

If receiving 429 responses:
- API Gateway throttling is configured (1000 req/sec, 2000 burst)
- Reduce concurrent users or increase throttling limits
- Implement exponential backoff in test script

## Continuous Integration

Add load tests to CI/CD pipeline:

```yaml
# .github/workflows/load-test.yml
name: Load Test
on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: grafana/k6-action@v0.2.0
        with:
          filename: tests/load/ingest-load.js
          cloud: true  # Use k6 Cloud for detailed results
        env:
          API_URL: ${{ secrets.API_URL }}
          API_KEY: ${{ secrets.API_KEY }}
```

