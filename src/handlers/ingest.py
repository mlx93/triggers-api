"""
POST /events Lambda handler for event ingestion.

Handles event ingestion with idempotency, S3 fallback, and error handling.
"""
import json
import os
import secrets
import logging
from typing import Dict, Any
from botocore.exceptions import ClientError

from src.lib.auth import get_tenant_id_from_event, AuthenticationError
from src.lib.validation import get_payload_size_bytes
from src.models.schemas import (
    EventInput,
    EventOutput,
    ErrorResponse,
    ErrorCode
)
from src.lib.storage import store_event, generate_event_id

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Constants
MAX_PAYLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /events Lambda handler.
    
    Handles event ingestion with:
    - Authentication via API key
    - Request validation
    - Event ID generation if not provided
    - Size-based routing (DynamoDB <400KB, S3 ≥400KB)
    - Idempotency enforcement (409 Conflict for duplicates)
    - S3 failure fallback to DynamoDB
    
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
            event_input = EventInput(**body)
        except Exception as e:
            logger.warning(f"Validation error: {e}")
            error_response = ErrorResponse.create(
                ErrorCode.VALIDATION_ERROR,
                "Invalid event payload",
                {"detail": str(e)}
            )
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Generate event_id if not provided
        event_id = event_input.id
        if not event_id:
            event_id = generate_event_id()
        
        # Check payload size
        payload_size = get_payload_size_bytes(event_input.data)
        
        if payload_size > MAX_PAYLOAD_SIZE_BYTES:
            logger.warning(f"Payload too large: {payload_size} bytes")
            error_response = ErrorResponse.create(
                ErrorCode.VALIDATION_ERROR,
                f"Payload size exceeds maximum of {MAX_PAYLOAD_SIZE_BYTES} bytes",
                {
                    "payload_size": payload_size,
                    "max_size": MAX_PAYLOAD_SIZE_BYTES
                }
            )
            return {
                'statusCode': 413,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Prepare event data
        event_data = {
            'id': event_id,
            'event_type': event_input.event_type,
            'timestamp': event_input.timestamp,
            'data': event_input.data
        }
        
        # Store event (handles DynamoDB/S3 routing and idempotency)
        try:
            storage_result = store_event(
                tenant_id=tenant_id,
                event_data=event_data,
                payload_size=payload_size
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Duplicate event_id - idempotency conflict
                logger.info(f"Duplicate event_id: {event_id}")
                error_response = ErrorResponse.create(
                    ErrorCode.CONFLICT,
                    "Event with this ID already exists",
                    {"event_id": event_id}
                )
                return {
                    'statusCode': 409,
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps(error_response.model_dump())
                }
            else:
                # Other DynamoDB error
                logger.error(f"DynamoDB error: {e}")
                error_response = ErrorResponse.create(
                    ErrorCode.INTERNAL_ERROR,
                    "Failed to store event",
                    {"detail": str(e)}
                )
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps(error_response.model_dump())
                }
        except Exception as e:
            logger.error(f"Unexpected error storing event: {e}")
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
        
        # Build success response
        from datetime import datetime, timezone
        created_at = datetime.now(timezone.utc).isoformat()
        
        event_output = EventOutput(
            id=event_id,
            status='accepted',
            created_at=created_at
        )
        
        logger.info(f"Event ingested successfully: {event_id}, storage: {storage_result['storage_type']}")
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': event_output.model_dump_json()  # Use Pydantic's JSON serialization
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in ingest handler: {e}", exc_info=True)
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
