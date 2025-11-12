"""
Pydantic schema models for Zapier Triggers API.

All models match PRD_Product_Reqs_v2.md Section 6 schemas exactly.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from ..lib.validation import (
    validate_event_type,
    validate_timestamp,
    validate_event_id,
    ValidationError
)


# Error codes from PRD_Product_Reqs_v2.md FR-7
class ErrorCode:
    """Error code constants."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


# ============================================================================
# POST /events Schemas
# ============================================================================

class EventInput(BaseModel):
    """
    POST /events request schema.
    
    Schema from PRD_Product_Reqs_v2.md FR-1:
    - id: optional, generated if missing
    - event_type: required, dot-notation
    - timestamp: required, ISO 8601
    - data: required, arbitrary JSON
    """
    id: Optional[str] = Field(
        default=None,
        description="Event identifier (optional, generated if missing)"
    )
    event_type: str = Field(
        ...,
        description="Event type in dot-notation format (e.g., resource.action.status)"
    )
    timestamp: str = Field(
        ...,
        description="Event occurrence time in ISO 8601 format"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Event payload as arbitrary JSON object"
    )
    
    @field_validator('id')
    @classmethod
    def validate_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate event_id format if provided."""
        if v is not None and not validate_event_id(v):
            raise ValueError("Invalid event_id format: must be evt_{base64url_32chars}")
        return v
    
    @field_validator('event_type')
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event_type format."""
        if not validate_event_type(v):
            raise ValueError(
                "Invalid event_type format: must be dot-notation "
                "(namespace.resource.action) with 3-100 characters"
            )
        return v
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate ISO 8601 timestamp."""
        if not validate_timestamp(v):
            raise ValueError("Invalid timestamp format: must be ISO 8601")
        return v
    
    @field_validator('data')
    @classmethod
    def validate_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data is a dictionary."""
        if not isinstance(v, dict):
            raise ValueError("data must be a JSON object")
        return v


class EventOutput(BaseModel):
    """
    POST /events response schema (success).
    
    Schema from PRD_Product_Reqs_v2.md FR-1:
    - id: event identifier
    - status: "accepted"
    - created_at: ISO 8601 timestamp
    """
    id: str = Field(..., description="Event identifier")
    status: Literal["accepted"] = Field(
        default="accepted",
        description="Event status"
    )
    created_at: str = Field(..., description="Event creation time in ISO 8601 format")


# ============================================================================
# GET /inbox Schemas
# ============================================================================

class InboxQueryParams(BaseModel):
    """
    GET /inbox query parameters.
    
    Schema from PRD_Product_Reqs_v2.md FR-3:
    - limit: default 25, max 100
    - cursor: optional pagination cursor
    - after: optional ISO 8601 timestamp filter
    - before: optional ISO 8601 timestamp filter
    - event_type: optional event type filter
    - status: optional status filter (pending/acknowledged)
    """
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Number of events to return (default 25, max 100)"
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Pagination cursor from previous response"
    )
    after: Optional[str] = Field(
        default=None,
        description="Filter events after this ISO 8601 timestamp"
    )
    before: Optional[str] = Field(
        default=None,
        description="Filter events before this ISO 8601 timestamp"
    )
    event_type: Optional[str] = Field(
        default=None,
        description="Filter by exact event type"
    )
    status: Optional[Literal["pending", "acknowledged"]] = Field(
        default=None,
        description="Filter by event status"
    )
    
    @field_validator('after', 'before')
    @classmethod
    def validate_timestamp_filter(cls, v: Optional[str]) -> Optional[str]:
        """Validate ISO 8601 timestamp filters."""
        if v is not None and not validate_timestamp(v):
            raise ValueError("Invalid timestamp format: must be ISO 8601")
        return v
    
    @field_validator('event_type')
    @classmethod
    def validate_event_type_filter(cls, v: Optional[str]) -> Optional[str]:
        """Validate event_type filter format if provided."""
        if v is not None and not validate_event_type(v):
            raise ValueError(
                "Invalid event_type format: must be dot-notation "
                "(namespace.resource.action) with 3-100 characters"
            )
        return v


class InboxEvent(BaseModel):
    """
    Individual event in inbox response.
    
    Schema from PRD_Product_Reqs_v2.md FR-3:
    - id: event identifier
    - event_type: event type
    - timestamp: event occurrence time
    - data: event payload
    - created_at: system ingestion time
    - attempt_count: number of retrieval attempts
    """
    id: str = Field(..., description="Event identifier")
    event_type: str = Field(..., description="Event type in dot-notation")
    timestamp: str = Field(..., description="Event occurrence time (ISO 8601)")
    data: Dict[str, Any] = Field(..., description="Event payload")
    created_at: str = Field(..., description="System ingestion time (ISO 8601)")
    attempt_count: int = Field(..., ge=0, description="Number of retrieval attempts")


class PaginationInfo(BaseModel):
    """Pagination metadata."""
    next_cursor: Optional[str] = Field(
        default=None,
        description="Cursor for next page of results"
    )
    has_more: bool = Field(..., description="Whether more events are available")


class InboxResponse(BaseModel):
    """
    GET /inbox response schema.
    
    Schema from PRD_Product_Reqs_v2.md FR-3:
    - events: array of InboxEvent
    - pagination: pagination metadata (next_cursor, has_more)
    """
    events: List[InboxEvent] = Field(..., description="List of events")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


# ============================================================================
# POST /inbox/ack Schemas
# ============================================================================

class AckRequest(BaseModel):
    """
    POST /inbox/ack request schema.
    
    Schema from PRD_Product_Reqs_v2.md FR-4:
    - event_ids: array of event IDs to acknowledge (max 100 items, min 1)
    """
    event_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Array of event IDs to acknowledge"
    )
    
    @field_validator('event_ids')
    @classmethod
    def validate_event_ids(cls, v: List[str]) -> List[str]:
        """Validate all event IDs have correct format."""
        for event_id in v:
            if not validate_event_id(event_id):
                raise ValueError(f"Invalid event_id format: {event_id}")
        return v


class AckFailure(BaseModel):
    """
    Failed acknowledgment item.
    
    Schema from PRD_Product_Reqs_v2.md FR-4:
    - event_id: event identifier that failed
    - error: error message
    """
    event_id: str = Field(..., description="Event identifier that failed")
    error: str = Field(..., description="Error message describing the failure")


class AckResponse(BaseModel):
    """
    POST /inbox/ack response schema.
    
    Schema from PRD_Product_Reqs_v2.md FR-4:
    - acknowledged: array of successfully acknowledged event IDs
    - failed: array of AckFailure items
    """
    acknowledged: List[str] = Field(
        ...,
        description="Array of successfully acknowledged event IDs"
    )
    failed: List[AckFailure] = Field(
        ...,
        description="Array of failed acknowledgments"
    )


# ============================================================================
# GET /health Schemas
# ============================================================================

class HealthDependencies(BaseModel):
    """Health check dependencies status."""
    dynamodb: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="DynamoDB connectivity status"
    )
    s3: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="S3 connectivity status"
    )


class HealthResponse(BaseModel):
    """
    GET /health response schema.
    
    Schema from PRD_Product_Reqs_v2.md FR-5:
    - status: overall system status (healthy/degraded/unhealthy)
    - timestamp: current time in ISO 8601
    - version: API version
    - dependencies: dependency statuses
    """
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Overall system health status"
    )
    timestamp: str = Field(..., description="Current time in ISO 8601 format")
    version: str = Field(default="1.0.0", description="API version")
    dependencies: HealthDependencies = Field(..., description="Dependency statuses")


# ============================================================================
# Error Response Schema
# ============================================================================

class ErrorDetails(BaseModel):
    """Error details for field-specific errors."""
    field: Optional[str] = Field(default=None, description="Field name with error")
    issue: Optional[str] = Field(default=None, description="Description of the issue")
    # Allow additional details as a dict
    additional: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")


class ErrorResponse(BaseModel):
    """
    Structured error response schema.
    
    Schema from PRD_Product_Reqs_v2.md FR-7:
    - error.code: error code
    - error.message: human-readable error message
    - error.details: optional field-specific error details
    """
    error: Dict[str, Any] = Field(..., description="Error information")
    
    @classmethod
    def create(
        cls,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> "ErrorResponse":
        """
        Create an ErrorResponse with structured format.
        
        Args:
            code: Error code (e.g., VALIDATION_ERROR)
            message: Human-readable error message
            details: Optional error details dictionary
            
        Returns:
            ErrorResponse instance
        """
        error_dict = {
            "code": code,
            "message": message
        }
        if details:
            error_dict["details"] = details
        
        return cls(error=error_dict)
    
    @property
    def code(self) -> str:
        """Get error code."""
        return self.error.get("code", "")
    
    @property
    def message(self) -> str:
        """Get error message."""
        return self.error.get("message", "")
    
    @property
    def details(self) -> Optional[Dict[str, Any]]:
        """Get error details."""
        return self.error.get("details")

