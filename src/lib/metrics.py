"""
CloudWatch metrics emission module for Zapier Triggers API.

Emits custom metrics to CloudWatch with namespace 'ZapierTriggers' and dimensions:
TenantId, EventType (when applicable), Environment.
"""
import os
from typing import Dict, Any, Optional
from aws_lambda_powertools.metrics import Metrics, MetricUnit
from aws_lambda_powertools.metrics import MetricUnit as Unit

# Initialize metrics singleton
# Namespace from PRD_Tech_v2.md Section 12
metrics = Metrics(
    namespace="ZapierTriggers",
    service="triggers-api"
)

# Get environment for dimension
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')


def _get_base_dimensions(tenant_id: Optional[str] = None) -> Dict[str, str]:
    """
    Get base dimensions for metrics.
    
    Args:
        tenant_id: Optional tenant ID to include as dimension
        
    Returns:
        Dictionary of dimension key-value pairs
    """
    dimensions = {
        "Environment": ENVIRONMENT
    }
    if tenant_id:
        dimensions["TenantId"] = tenant_id
    return dimensions


def emit_metric(
    metric_name: str,
    value: float,
    unit: str = Unit.Count.value,
    dimensions: Optional[Dict[str, str]] = None
) -> None:
    """
    Emit a custom CloudWatch metric.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: Metric unit (default: Count)
        dimensions: Optional additional dimensions
    """
    base_dims = _get_base_dimensions()
    if dimensions:
        base_dims.update(dimensions)
    
    metrics.add_metric(name=metric_name, value=value, unit=unit)
    # Note: aws-lambda-powertools automatically adds dimensions via metadata
    # We'll use add_metadata for custom dimensions
    for key, value in base_dims.items():
        metrics.add_metadata(key=key, value=value)


def emit_event_ingested(
    tenant_id: str,
    event_type: str,
    latency_ms: float,
    payload_size: int
) -> None:
    """
    Emit EventIngested metric.
    
    Metric from PRD_Tech_v2.md Section 12:
    - Count metric
    - Dimensions: TenantId, EventType, Environment
    
    Args:
        tenant_id: Tenant identifier
        event_type: Event type (e.g., "player.projection.created")
        latency_ms: Ingestion latency in milliseconds
        payload_size: Payload size in bytes
    """
    dimensions = {
        "TenantId": tenant_id,
        "EventType": event_type,
        "Environment": ENVIRONMENT
    }
    
    # Emit count metric
    metrics.add_metric(name="EventIngested", value=1, unit=Unit.Count.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="EventType", value=event_type)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)
    
    # Emit latency metric
    metrics.add_metric(name="EventLatency", value=latency_ms, unit=Unit.Milliseconds.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="EventType", value=event_type)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)
    
    # Emit payload size metric
    metrics.add_metric(name="PayloadSize", value=payload_size, unit=Unit.Bytes.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="EventType", value=event_type)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)


def emit_inbox_retrieved(
    tenant_id: str,
    event_count: int,
    latency_ms: float
) -> None:
    """
    Emit InboxRetrieved metric.
    
    Metric from PRD_Tech_v2.md Section 12:
    - Count metric
    - Dimensions: TenantId, Environment
    
    Args:
        tenant_id: Tenant identifier
        event_count: Number of events retrieved
        latency_ms: Retrieval latency in milliseconds
    """
    # Emit count metric
    metrics.add_metric(name="InboxRetrieved", value=event_count, unit=Unit.Count.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)
    
    # Emit latency metric
    metrics.add_metric(name="EventLatency", value=latency_ms, unit=Unit.Milliseconds.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)


def emit_event_acknowledged(
    tenant_id: str,
    event_count: int,
    latency_ms: float
) -> None:
    """
    Emit EventAcknowledged metric.
    
    Metric from PRD_Tech_v2.md Section 12:
    - Count metric
    - Dimensions: TenantId, Environment
    
    Args:
        tenant_id: Tenant identifier
        event_count: Number of events acknowledged
        latency_ms: Acknowledgment latency in milliseconds
    """
    # Emit count metric
    metrics.add_metric(name="EventAcknowledged", value=event_count, unit=Unit.Count.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)
    
    # Emit latency metric
    metrics.add_metric(name="EventLatency", value=latency_ms, unit=Unit.Milliseconds.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)


def emit_latency(
    tenant_id: str,
    endpoint: str,
    latency_ms: float
) -> None:
    """
    Emit latency metric for an endpoint.
    
    CloudWatch automatically calculates P50/P95/P99 percentiles.
    
    Args:
        tenant_id: Tenant identifier
        endpoint: Endpoint name (e.g., "/events", "/inbox", "/inbox/ack")
        latency_ms: Latency in milliseconds
    """
    dimensions = {
        "TenantId": tenant_id,
        "Endpoint": endpoint,
        "Environment": ENVIRONMENT
    }
    
    metrics.add_metric(name="EventLatency", value=latency_ms, unit=Unit.Milliseconds.value)
    metrics.add_metadata(key="TenantId", value=tenant_id)
    metrics.add_metadata(key="Endpoint", value=endpoint)
    metrics.add_metadata(key="Environment", value=ENVIRONMENT)

