"""
GET /inbox Lambda handler for event retrieval.

Handles event retrieval with filters, pagination, cursor validation, and lease mechanism.
"""
import json
import os
import time
from typing import Dict, Any
from urllib.parse import parse_qs

from src.lib.auth import get_tenant_id_from_event, AuthenticationError
from src.models.schemas import (
    InboxQueryParams,
    InboxResponse,
    InboxEvent,
    PaginationInfo,
    ErrorResponse,
    ErrorCode
)
from src.lib.storage import query_events
from src.lib.logging import get_logger
from src.lib.metrics import emit_inbox_retrieved, metrics

logger = get_logger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /inbox Lambda handler.
    
    Handles event retrieval with:
    - Authentication via API key
    - Query parameter parsing and validation
    - Cursor validation (24-hour TTL)
    - DynamoDB query with filters
    - Lease mechanism (5-minute in_flight_until)
    - S3 payload retrieval
    - Pagination cursor generation
    
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
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Convert query params to InboxQueryParams model
        try:
            inbox_params = InboxQueryParams(**query_params)
        except Exception as e:
            logger.warning("Invalid query parameters", extra={"error": str(e), "tenant_id": tenant_id})
            error_response = ErrorResponse.create(
                ErrorCode.VALIDATION_ERROR,
                "Invalid query parameters",
                {"detail": str(e)}
            )
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Validate cursor if provided
        if inbox_params.cursor:
            try:
                from src.lib.storage import parse_cursor
                parse_cursor(inbox_params.cursor)  # Will raise ValueError if invalid
            except ValueError as e:
                logger.warning("Invalid cursor", extra={"error": str(e), "tenant_id": tenant_id, "cursor": inbox_params.cursor})
                error_response = ErrorResponse.create(
                    ErrorCode.VALIDATION_ERROR,
                    f"Invalid cursor: {str(e)}",
                    {"cursor": inbox_params.cursor}
                )
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps(error_response.model_dump())
                }
        
        # Build filters dictionary
        filters = {}
        if inbox_params.event_type:
            filters['event_type'] = inbox_params.event_type
        if inbox_params.after:
            filters['after'] = inbox_params.after
        if inbox_params.before:
            filters['before'] = inbox_params.before
        if inbox_params.status:
            filters['status'] = inbox_params.status
        
        # Query events from storage
        try:
            events, next_cursor = query_events(
                tenant_id=tenant_id,
                filters=filters if filters else None,
                cursor=inbox_params.cursor,
                limit=inbox_params.limit
            )
        except Exception as e:
            logger.error(
                "Error querying events",
                extra={
                    "tenant_id": tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )
            error_response = ErrorResponse.create(
                ErrorCode.INTERNAL_ERROR,
                "Failed to retrieve events",
                {"detail": str(e)}
            )
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps(error_response.model_dump())
            }
        
        # Convert DynamoDB items to InboxEvent models
        # Convert Decimal to int for attempt_count
        from decimal import Decimal
        inbox_events = []
        for item in events:
            try:
                # Skip events where data is None (S3 fetch failed)
                if item.get('data') is None:
                    logger.warning(f"Skipping event {item.get('id')}: S3 data fetch failed")
                    continue
                
                attempt_count = item.get('attempt_count', 0)
                if isinstance(attempt_count, Decimal):
                    attempt_count = int(attempt_count)
                
                inbox_event = InboxEvent(
                    id=item['id'],
                    event_type=item['event_type'],
                    timestamp=item['timestamp'],
                    data=item.get('data', {}),
                    created_at=item['created_at'],
                    attempt_count=attempt_count
                )
                inbox_events.append(inbox_event)
            except Exception as e:
                logger.warning(f"Failed to convert event {item.get('id')}: {e}")
                # Skip invalid events
                continue
        
        # Build pagination info
        pagination = PaginationInfo(
            next_cursor=next_cursor,
            has_more=next_cursor is not None
        )
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Build response
        inbox_response = InboxResponse(
            events=inbox_events,
            pagination=pagination
        )
        
        # Emit metrics
        try:
            emit_inbox_retrieved(
                tenant_id=tenant_id,
                event_count=len(inbox_events),
                latency_ms=latency_ms
            )
            metrics.flush_metrics()
        except Exception as e:
            # Don't fail request if metrics fail
            logger.warning("Failed to emit metrics", extra={"error": str(e)})
        
        # Structured logging with context
        logger.info(
            "Retrieved events",
            extra={
                "tenant_id": tenant_id,
                "event_count": len(inbox_events),
                "latency_ms": latency_ms,
                "has_more": pagination.has_more
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': inbox_response.model_dump_json()  # Use Pydantic's JSON serialization
        }
        
    except Exception as e:
        logger.error(
            "Unexpected error in inbox handler",
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
