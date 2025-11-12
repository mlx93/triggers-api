"""
GET /inbox Lambda handler for event retrieval.

Handles event retrieval with filters, pagination, cursor validation, and lease mechanism.
"""
import json
import os
import logging
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

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


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
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Convert query params to InboxQueryParams model
        try:
            inbox_params = InboxQueryParams(**query_params)
        except Exception as e:
            logger.warning(f"Invalid query parameters: {e}")
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
                logger.warning(f"Invalid cursor: {e}")
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
            logger.error(f"Error querying events: {e}")
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
        
        # Build response
        inbox_response = InboxResponse(
            events=inbox_events,
            pagination=pagination
        )
        
        logger.info(f"Retrieved {len(inbox_events)} events for tenant {tenant_id}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': inbox_response.model_dump_json()  # Use Pydantic's JSON serialization
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in inbox handler: {e}", exc_info=True)
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
