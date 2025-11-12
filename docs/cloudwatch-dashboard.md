# CloudWatch Dashboard Configuration

**Date:** November 11, 2025  
**Status:** Documentation Complete  
**Environment:** dev/prod

---

## Overview

CloudWatch dashboard provides visual monitoring of API performance, error rates, and event volume. Dashboard widgets display key metrics from PRD_Tech_v2.md Section 12.

**Dashboard Name:** `ZapierTriggers-API-Dashboard-{env}`

**Widgets:**
1. Event ingestion rate (EventIngested count over time)
2. API latency (P50/P95/P99 percentiles)
3. Error rates (4XX/5XX counts)
4. Event volume over time
5. Per-tenant breakdown (top tenants by event volume)

---

## Widget Specifications

### Widget 1: Event Ingestion Rate

**Type:** Line Chart  
**Metric:** `EventIngested`  
**Namespace:** `ZapierTriggers`  
**Statistic:** Sum  
**Period:** 1 minute  
**Dimensions:** `Environment={env}`  
**Y-Axis:** Count  
**Title:** Event Ingestion Rate

**Query:**
```
SELECT SUM(EventIngested) FROM ZapierTriggers 
WHERE Environment = '{env}' 
GROUP BY time(1m)
```

---

### Widget 2: API Latency Percentiles

**Type:** Line Chart  
**Metric:** `EventLatency`  
**Namespace:** `ZapierTriggers`  
**Statistics:** P50, P95, P99  
**Period:** 1 minute  
**Dimensions:** `Environment={env}`  
**Y-Axis:** Milliseconds  
**Title:** API Latency (P50/P95/P99)

**Queries:**
- P50: `SELECT p50(EventLatency) FROM ZapierTriggers WHERE Environment = '{env}' GROUP BY time(1m)`
- P95: `SELECT p95(EventLatency) FROM ZapierTriggers WHERE Environment = '{env}' GROUP BY time(1m)`
- P99: `SELECT p99(EventLatency) FROM ZapierTriggers WHERE Environment = '{env}' GROUP BY time(1m)`

---

### Widget 3: Error Rates

**Type:** Bar Chart  
**Metrics:** 
- 4XX Errors: `AWS/Lambda` → `Errors` (filter by status code 4XX)
- 5XX Errors: `AWS/Lambda` → `Errors` (filter by status code 5XX)

**Statistic:** Sum  
**Period:** 5 minutes  
**Y-Axis:** Count  
**Title:** Error Rates (4XX/5XX)

**Note:** Lambda built-in metrics don't distinguish 4XX vs 5XX. Consider adding custom error metrics or using CloudWatch Logs Insights to filter by status code.

**Alternative:** Use CloudWatch Logs Insights query:
```
fields @timestamp, @message
| filter @message like /"statusCode": 4\d\d/ or @message like /"statusCode": 5\d\d/
| stats count() by bin(5m)
```

---

### Widget 4: Event Volume Over Time

**Type:** Line Chart  
**Metric:** `EventIngested`  
**Namespace:** `ZapierTriggers`  
**Statistic:** Sum  
**Period:** 1 minute  
**Dimensions:** `Environment={env}`  
**Y-Axis:** Count  
**Title:** Event Volume Over Time

**Query:**
```
SELECT SUM(EventIngested) FROM ZapierTriggers 
WHERE Environment = '{env}' 
GROUP BY time(1m)
```

---

### Widget 5: Per-Tenant Event Volume

**Type:** Pie Chart or Bar Chart  
**Metric:** `EventIngested`  
**Namespace:** `ZapierTriggers`  
**Statistic:** Sum  
**Period:** 1 hour  
**Dimensions:** `Environment={env}`, `TenantId=*`  
**Top N:** 10 tenants  
**Title:** Top 10 Tenants by Event Volume

**Query:**
```
SELECT SUM(EventIngested) FROM ZapierTriggers 
WHERE Environment = '{env}' 
GROUP BY TenantId 
ORDER BY SUM(EventIngested) DESC 
LIMIT 10
```

---

## Dashboard JSON Configuration

Full dashboard JSON can be created via AWS Console and exported, or created programmatically:

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["ZapierTriggers", "EventIngested", {"stat": "Sum", "period": 60}]
        ],
        "period": 60,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Event Ingestion Rate"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["ZapierTriggers", "EventLatency", {"stat": "p50", "period": 60, "label": "P50"}],
          ["...", {"stat": "p95", "period": 60, "label": "P95"}],
          ["...", {"stat": "p99", "period": 60, "label": "P99"}]
        ],
        "period": 60,
        "stat": "Average",
        "region": "us-east-1",
        "title": "API Latency (P50/P95/P99)"
      }
    }
  ]
}
```

---

## AWS CLI Command

Create dashboard via AWS CLI:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name "ZapierTriggers-API-Dashboard-{env}" \
  --dashboard-body file://dashboard.json
```

---

## Manual Creation via AWS Console

1. **Navigate to CloudWatch Console** → Dashboards → Create Dashboard
2. **Name Dashboard:** `ZapierTriggers-API-Dashboard-{env}`
3. **Add Widgets:**
   - Click "Add widget" → Select widget type
   - Configure metrics, statistics, periods
   - Set dimensions (Environment, TenantId, etc.)
   - Customize titles and axes
4. **Arrange Widgets:** Drag and resize widgets for optimal layout
5. **Save Dashboard**

---

## CloudWatch Logs Insights Queries

For advanced analysis, use CloudWatch Logs Insights:

### Error Rate by Status Code
```
fields @timestamp, @message
| parse @message /"statusCode": (?<status>\d+)/
| stats count() by status, bin(5m)
```

### Latency Distribution
```
fields @timestamp, @message
| parse @message /"latency_ms": (?<latency>\d+)/
| stats avg(latency), p50(latency), p95(latency), p99(latency) by bin(5m)
```

### Per-Tenant Event Volume
```
fields @timestamp, @message
| parse @message /"tenant_id": "(?<tenant>[^"]+)"/
| stats count() by tenant, bin(1h)
| sort count desc
| limit 10
```

---

## Dashboard Best Practices

1. **Organize by Functionality:** Group related metrics together
2. **Use Consistent Time Ranges:** Set default time range (e.g., 1 hour, 24 hours)
3. **Add Annotations:** Mark deployments, incidents, or significant events
4. **Set Refresh Intervals:** Auto-refresh dashboard every 1-5 minutes
5. **Create Multiple Dashboards:** Separate dashboards for dev/prod, or by team/function
6. **Share Dashboards:** Share dashboard URLs with team members for visibility

---

## References

- **PRD_Tech_v2.md Section 12:** Dashboard specifications
- **PRD_Product_Reqs_v2.md FR-10:** Metrics dashboard requirements
- **AWS CloudWatch Dashboards Documentation:** https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html

---

**Document Status:** ✅ Complete  
**Next Steps:** Create dashboard manually via AWS Console or use AWS CLI with dashboard JSON

