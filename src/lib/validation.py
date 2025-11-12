"""
Validation module for Zapier Triggers API.

Handles validation of event types, timestamps, cursors, payload sizes, and IDs.
"""
import re
import json
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any
import uuid


# Event type validation: dot-notation, 3-100 chars
# Format: namespace.resource.action (minimum 3 segments)
EVENT_TYPE_PATTERN = re.compile(r'^[a-z0-9_]+(\.[a-z0-9_]+){2,}$')
EVENT_TYPE_MIN_LENGTH = 3
EVENT_TYPE_MAX_LENGTH = 100

# Event ID format: evt_{base64url_32chars}
EVENT_ID_PATTERN = re.compile(r'^evt_[A-Za-z0-9_-]{32}$')

# Tenant ID format: tenant_{uuid}
TENANT_ID_PATTERN = re.compile(r'^tenant_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)

# Payload size limits
MAX_PAYLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
S3_THRESHOLD_BYTES = 400 * 1024  # 400KB

# Cursor TTL: 24 hours
CURSOR_TTL_SECONDS = 24 * 60 * 60


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_event_type(event_type: str) -> bool:
    """
    Validate event_type format using regex.
    
    Format: namespace.resource.action (minimum 3 segments)
    Pattern: namespace.resource.action (dot-separated, min 3 segments)
    Length: 3-100 characters
    
    Args:
        event_type: Event type string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not event_type or not isinstance(event_type, str):
        return False
    
    if len(event_type) < EVENT_TYPE_MIN_LENGTH or len(event_type) > EVENT_TYPE_MAX_LENGTH:
        return False
    
    return bool(EVENT_TYPE_PATTERN.match(event_type))


def validate_timestamp(timestamp: str) -> bool:
    """
    Validate ISO 8601 timestamp format.
    
    Accepts both timezone-aware and timezone-naive formats.
    
    Args:
        timestamp: ISO 8601 timestamp string
        
    Returns:
        True if valid ISO 8601, False otherwise
    """
    if not timestamp or not isinstance(timestamp, str):
        return False
    
    try:
        # Try parsing with timezone info
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return True
    except (ValueError, AttributeError):
        try:
            # Try parsing without timezone (assumes UTC)
            datetime.fromisoformat(timestamp)
            return True
        except (ValueError, AttributeError):
            # Try RFC3339 format
            try:
                # Handle common ISO 8601 variations
                if timestamp.endswith('Z'):
                    timestamp = timestamp[:-1] + '+00:00'
                datetime.fromisoformat(timestamp)
                return True
            except (ValueError, AttributeError):
                return False


def validate_cursor(cursor: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse and validate cursor format: {unix_timestamp}_{event_id}.
    
    Validates:
    1. Format matches {timestamp}_{event_id}
    2. Timestamp is within 24 hours (TTL)
    3. Event ID format is valid
    
    Args:
        cursor: Cursor string to validate
        
    Returns:
        Tuple of (is_valid, parsed_data, error_message):
        - is_valid: True if cursor is valid and not expired
        - parsed_data: Dict with 'timestamp' and 'event_id' if valid, None otherwise
        - error_message: Error description if invalid, None otherwise
    """
    if not cursor or not isinstance(cursor, str):
        return False, None, "Cursor must be a non-empty string"
    
    # Parse cursor format: {unix_timestamp}_{event_id}
    # Use regex to handle event_ids that might contain underscores
    # Pattern: timestamp (digits) followed by underscore and event_id (evt_...)
    cursor_pattern = re.compile(r'^(\d+)_(evt_.+)$')
    match = cursor_pattern.match(cursor)
    
    if not match:
        return False, None, "Invalid cursor format: expected {timestamp}_{event_id}"
    
    timestamp_str, event_id = match.groups()
    
    # Validate timestamp component
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False, None, "Invalid cursor timestamp: must be integer"
    
    # Validate event_id format
    if not validate_event_id(event_id):
        return False, None, f"Invalid cursor event_id format: {event_id}"
    
    # Check TTL: cursor must be less than 24 hours old
    current_timestamp = int(datetime.now(timezone.utc).timestamp())
    age_seconds = current_timestamp - timestamp
    
    if age_seconds < 0:
        return False, None, "Cursor timestamp is in the future"
    
    if age_seconds > CURSOR_TTL_SECONDS:
        return False, None, "Cursor expired: must be less than 24 hours old"
    
    return True, {
        'timestamp': timestamp,
        'event_id': event_id
    }, None


def validate_payload_size(payload: Dict[str, Any]) -> bool:
    """
    Validate payload size does not exceed 10MB limit.
    
    Args:
        payload: JSON payload dictionary
        
    Returns:
        True if payload size is within limit, False otherwise
    """
    try:
        # Serialize to JSON to get accurate size
        json_str = json.dumps(payload, separators=(',', ':'))
        size_bytes = len(json_str.encode('utf-8'))
        
        return size_bytes <= MAX_PAYLOAD_SIZE_BYTES
    except (TypeError, ValueError):
        # If payload can't be serialized, consider it invalid
        return False


def get_payload_size_bytes(payload: Dict[str, Any]) -> int:
    """
    Get payload size in bytes.
    
    Args:
        payload: JSON payload dictionary
        
    Returns:
        Size in bytes, or 0 if serialization fails
    """
    try:
        json_str = json.dumps(payload, separators=(',', ':'))
        return len(json_str.encode('utf-8'))
    except (TypeError, ValueError):
        return 0


def validate_event_id(event_id: str) -> bool:
    """
    Validate event_id format: evt_{base64url_32chars}.
    
    Args:
        event_id: Event ID string to validate
        
    Returns:
        True if format is valid, False otherwise
    """
    if not event_id or not isinstance(event_id, str):
        return False
    
    return bool(EVENT_ID_PATTERN.match(event_id))


def validate_tenant_id(tenant_id: str) -> bool:
    """
    Validate tenant_id format: tenant_{uuid_v4}.
    
    Args:
        tenant_id: Tenant ID string to validate
        
    Returns:
        True if format is valid, False otherwise
    """
    if not tenant_id or not isinstance(tenant_id, str):
        return False
    
    # Check pattern matches tenant_{uuid}
    if not TENANT_ID_PATTERN.match(tenant_id):
        return False
    
    # Extract UUID part and validate it's a valid UUID v4
    uuid_part = tenant_id.replace('tenant_', '')
    try:
        uuid_obj = uuid.UUID(uuid_part)
        return uuid_obj.version == 4
    except (ValueError, AttributeError):
        return False

