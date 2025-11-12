"""
POST /inbox/ack Lambda handler for event acknowledgment.

Handles batch event acknowledgment with idempotency and error handling.
"""
import json
import os
import logging
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

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


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
    try:
        # Extract tenant_id from API key (handles auth automatically)
        try:
            tenant_id = get_tenant_id_from_event(event)
        except AuthenticationError as e:
            logger.warning(f"Authentication failed: {e}")
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
            logger.warning(f"Invalid JSON in request body: {e}")
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
            logger.warning(f"Validation error: {e}")
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
            logger.error(f"Error acknowledging events: {e}")
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
        
        logger.info(
            f"Acknowledged {len(result['acknowledged'])} events, "
            f"{len(result['failed'])} failed for tenant {tenant_id}"
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': ack_response.model_dump_json()  # Use Pydantic's JSON serialization
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in ack handler: {e}", exc_info=True)
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
