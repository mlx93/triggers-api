"""
POST /inbox/ack Lambda handler for event acknowledgment.

Handles batch event acknowledgment with idempotency and error handling.
"""
import json
import os
import time
from typing import Dict, Any

from src.lib.auth import get_tenant_id_from_event, AuthenticationError
from src.models.schemas import (
    AckRequest,
    AckResponse,
    AckFailure,
    ErrorResponse,
    ErrorCode
)
from src.lib.storage import acknowledge_events
from src.lib.logging import get_logger
from src.lib.metrics import emit_event_acknowledged, metrics

logger = get_logger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /inbox/ack Lambda handler.
    
    Handles batch event acknowledgment with:
    - Authentication via API key
    - Request validation (max 100 event_ids)
    - Batch updates to acknowledged status
    - Lease clearing
    - Idempotency (safe to acknowledge twice)
    - Tenant isolation validation
    
    Args:
        event: Lambda event dictionary
        context: Lambda context
        
    Returns:
        Lambda response dictionary with statusCode, body, headers
    """
    start_time = time.time()
    
    try:
        # Extract tenant_id from API key (handles auth automatically)
        try:
            tenant_id = get_tenant_id_from_event(event)
        except AuthenticationError as e:
            logger.warning("Authentication failed", extra={"error": str(e)})
            error_response = ErrorResponse.create(
                ErrorCode.AUTHENTICATION_ERROR,
                "Invalid or missing API key",
                {"detail": str(e)}
            )
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Parse request body
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in request body", extra={"error": str(e)})
            error_response = ErrorResponse.create(
                ErrorCode.VALIDATION_ERROR,
                "Invalid JSON in request body",
                {"detail": str(e)}
            )
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Validate request schema using Pydantic
        try:
            ack_request = AckRequest(**body)
        except Exception as e:
            logger.warning("Validation error", extra={"error": str(e), "tenant_id": tenant_id})
            error_response = ErrorResponse.create(
                ErrorCode.VALIDATION_ERROR,
                "Invalid acknowledgment request",
                {"detail": str(e)}
            )
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Acknowledge events
        try:
            result = acknowledge_events(
                tenant_id=tenant_id,
                event_ids=ack_request.event_ids
            )
        except Exception as e:
            logger.error(
                "Error acknowledging events",
                extra={
                    "tenant_id": tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )
            error_response = ErrorResponse.create(
                ErrorCode.INTERNAL_ERROR,
                "Failed to acknowledge events",
                {"detail": str(e)}
            )
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Convert failures to AckFailure models
        failures = [
            AckFailure(event_id=f['event_id'], error=f['error'])
            for f in result['failed']
        ]
        
        # Build response
        ack_response = AckResponse(
            acknowledged=result['acknowledged'],
            failed=failures
        )
        
        # Emit metrics
        try:
            emit_event_acknowledged(
                tenant_id=tenant_id,
                event_count=len(result['acknowledged']),
                latency_ms=latency_ms
            )
            metrics.flush_metrics()
        except Exception as e:
            # Don't fail request if metrics fail
            logger.warning("Failed to emit metrics", extra={"error": str(e)})
        
        # Structured logging with context
        logger.info(
            "Events acknowledged",
            extra={
                "tenant_id": tenant_id,
                "acknowledged_count": len(result['acknowledged']),
                "failed_count": len(result['failed']),
                "latency_ms": latency_ms
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': ack_response.model_dump_json()  # Use Pydantic's JSON serialization
        }
        
    except Exception as e:
        logger.error(
            "Unexpected error in ack handler",
            extra={"error": str(e)},
            exc_info=True
        )
        error_response = ErrorResponse.create(
            ErrorCode.INTERNAL_ERROR,
            "Internal server error",
            {"detail": str(e)}
        )
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps(error_response.model_dump())
        }
