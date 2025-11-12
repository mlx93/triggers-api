# CloudWatch Alarms Configuration

**Date:** November 11, 2025  
**Status:** Documentation Complete  
**Environment:** dev/prod

---

## Overview

CloudWatch alarms monitor API health and performance metrics. Alarms trigger when thresholds are exceeded, enabling proactive issue detection and alerting.

**Alarm Thresholds (from PRD_Tech_v2.md Section 12):**
- **High Error Rate:** >10 5XX errors in 5-minute window
- **High Latency:** P95 latency >200ms in 5-minute window

---

## Alarm 1: High Error Rate

**Purpose:** Alert when API error rate exceeds acceptable threshold.

**Configuration:**
- **Metric:** Sum of 5XX errors across all Lambda functions
- **Namespace:** `AWS/Lambda` (built-in Lambda metrics)
- **Metric Name:** `Errors`
- **Statistic:** Sum
- **Period:** 5 minutes
- **Evaluation Periods:** 1
- **Threshold:** >10 errors
- **Comparison Operator:** GreaterThanThreshold
- **Treat Missing Data:** notBreaching

**Lambda Functions Monitored:**
- `zapier-triggers-ingest-{env}`
- `zapier-triggers-inbox-{env}`
- `zapier-triggers-ack-{env}`
- `zapier-triggers-health-{env}`

**Alarm Actions (Optional for MVP):**
- SNS topic notification (configure post-MVP)
- CloudWatch dashboard notification
- Email/Slack integration (configure post-MVP)

**AWS CLI Command:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-triggers-high-error-rate-{env} \
  --alarm-description "Alert when 5XX error count exceeds 10 in 5 minutes" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=zapier-triggers-ingest-{env} \
  --treat-missing-data notBreaching
```

**Note:** Create separate alarms for each Lambda function, or use a composite alarm to aggregate across all functions.

---

## Alarm 2: High Latency

**Purpose:** Alert when API latency exceeds acceptable threshold.

**Configuration:**
- **Metric:** P95 latency across all endpoints
- **Namespace:** `ZapierTriggers` (custom metrics)
- **Metric Name:** `EventLatency`
- **Statistic:** p95
- **Period:** 5 minutes
- **Evaluation Periods:** 1
- **Threshold:** >200ms
- **Comparison Operator:** GreaterThanThreshold
- **Treat Missing Data:** notBreaching

**Dimensions:**
- `Environment`: {env} (dev/prod)
- `TenantId`: * (all tenants)
- `Endpoint`: * (all endpoints)

**AWS CLI Command:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-triggers-high-latency-{env} \
  --alarm-description "Alert when P95 latency exceeds 200ms in 5 minutes" \
  --metric-name EventLatency \
  --namespace ZapierTriggers \
  --statistic p95 \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 200 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Environment,Value={env} \
  --treat-missing-data notBreaching
```

---

## SAM Template Integration (Optional)

Alarms can be added to `template.yaml` as CloudFormation resources:

```yaml
Resources:
  HighErrorRateAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub 'zapier-triggers-high-error-rate-${Environment}'
      AlarmDescription: Alert when 5XX error count exceeds 10 in 5 minutes
      MetricName: Errors
      Namespace: AWS/Lambda
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 10
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching
      Dimensions:
        - Name: FunctionName
          Value: !Sub 'zapier-triggers-ingest-${Environment}'

  HighLatencyAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub 'zapier-triggers-high-latency-${Environment}'
      AlarmDescription: Alert when P95 latency exceeds 200ms in 5 minutes
      MetricName: EventLatency
      Namespace: ZapierTriggers
      Statistic: p95
      Period: 300
      EvaluationPeriods: 1
      Threshold: 200
      ComparisonOperator: GreaterThanThreshold
      TreatMissingData: notBreaching
      Dimensions:
        - Name: Environment
          Value: !Ref Environment
```

---

## Manual Creation via AWS Console

1. **Navigate to CloudWatch Console** → Alarms → Create Alarm
2. **Select Metric:**
   - For Error Rate: Browse to `AWS/Lambda` → `Errors` → Select function → Sum statistic
   - For Latency: Browse to `ZapierTriggers` → `EventLatency` → P95 statistic
3. **Configure Threshold:**
   - Error Rate: >10
   - Latency: >200ms
4. **Set Period:** 5 minutes
5. **Configure Actions:** (Optional) SNS topic or dashboard notification
6. **Create Alarm**

---

## Monitoring Best Practices

1. **Review Alarms Weekly:** Check alarm history and adjust thresholds if needed
2. **Set Up Notifications:** Configure SNS topics for production environments
3. **Use Composite Alarms:** Aggregate alarms across multiple functions for simpler management
4. **Monitor Trends:** Use CloudWatch Insights to analyze alarm patterns
5. **Document Runbooks:** Create operational runbooks for alarm response procedures

---

## References

- **PRD_Tech_v2.md Section 12:** CloudWatch Alarms configuration
- **PRD_Product_Reqs_v2.md FR-5:** Health endpoint requirements
- **AWS CloudWatch Alarms Documentation:** https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html

---

**Document Status:** ✅ Complete  
**Next Steps:** Create alarms manually via AWS Console/CLI or add to SAM template

