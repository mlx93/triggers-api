"""
Unit tests for validation module.

Tests event_type, timestamp, cursor, payload size, event_id, and tenant_id validation.
"""
import pytest
import json
from datetime import datetime, timezone, timedelta
from src.lib.validation import (
    validate_event_type,
    validate_timestamp,
    validate_cursor,
    validate_payload_size,
    get_payload_size_bytes,
    validate_event_id,
    validate_tenant_id,
    ValidationError,
    EVENT_TYPE_MIN_LENGTH,
    EVENT_TYPE_MAX_LENGTH,
    MAX_PAYLOAD_SIZE_BYTES,
    CURSOR_TTL_SECONDS
)


class TestValidateEventType:
    """Tests for validate_event_type function."""
    
    def test_valid_event_type_three_segments(self):
        """Test valid event type with three segments."""
        assert validate_event_type("namespace.resource.action") is True
    
    def test_valid_event_type_four_segments(self):
        """Test valid event type with four segments."""
        assert validate_event_type("namespace.resource.action.status") is True
    
    def test_valid_event_type_with_underscores(self):
        """Test valid event type with underscores."""
        assert validate_event_type("namespace.resource.action_status") is True
        assert validate_event_type("name_space.resource.action") is True
    
    def test_valid_event_type_with_numbers(self):
        """Test valid event type with numbers."""
        assert validate_event_type("namespace.resource.action123") is True
        assert validate_event_type("namespace123.resource.action") is True
    
    def test_invalid_event_type_too_short(self):
        """Test that event type shorter than 3 chars fails."""
        assert validate_event_type("ab") is False
    
    def test_invalid_event_type_too_long(self):
        """Test that event type longer than 100 chars fails."""
        long_type = "a" * 101
        assert validate_event_type(long_type) is False
    
    def test_invalid_event_type_exactly_100_chars(self):
        """Test that exactly 100 chars in valid format passes."""
        # Create a valid dot-notation event type that's exactly 100 chars
        # Format: namespace.resource.action (minimum 3 segments)
        # Use: a.b.c with enough chars to total 100
        # "a" + "." + "b" + "." + "c" = 5 chars base (3 chars + 2 dots), need 95 more
        # Distribute: 32 chars in first, 32 in second, 31 in third = 95 + 5 = 100
        # Actually: 32 + 1 + 32 + 1 + 31 = 97, need 3 more = 100 total
        # So: 33 + 1 + 33 + 1 + 32 = 100
        long_type = "a" * 33 + "." + "b" * 33 + "." + "c" * 32
        assert len(long_type) == 100
        assert validate_event_type(long_type) is True
    
    def test_invalid_event_type_exactly_3_chars(self):
        """Test that exactly 3 chars passes."""
        assert validate_event_type("a.b.c") is True
    
    def test_invalid_event_type_only_two_segments(self):
        """Test that two segments fails."""
        assert validate_event_type("namespace.resource") is False
    
    def test_invalid_event_type_one_segment(self):
        """Test that one segment fails."""
        assert validate_event_type("namespace") is False
    
    def test_invalid_event_type_uppercase(self):
        """Test that uppercase fails."""
        assert validate_event_type("Namespace.Resource.Action") is False
    
    def test_invalid_event_type_special_chars(self):
        """Test that special characters fail."""
        assert validate_event_type("namespace.resource.action!") is False
        assert validate_event_type("namespace.resource@action") is False
    
    def test_invalid_event_type_empty_string(self):
        """Test that empty string fails."""
        assert validate_event_type("") is False
    
    def test_invalid_event_type_none(self):
        """Test that None fails."""
        assert validate_event_type(None) is False
    
    def test_invalid_event_type_non_string(self):
        """Test that non-string fails."""
        assert validate_event_type(123) is False


class TestValidateTimestamp:
    """Tests for validate_timestamp function."""
    
    def test_valid_iso8601_with_z(self):
        """Test valid ISO 8601 timestamp with Z suffix."""
        assert validate_timestamp("2025-11-11T15:30:45Z") is True
    
    def test_valid_iso8601_with_timezone(self):
        """Test valid ISO 8601 timestamp with timezone offset."""
        assert validate_timestamp("2025-11-11T15:30:45+00:00") is True
        assert validate_timestamp("2025-11-11T15:30:45-05:00") is True
    
    def test_valid_iso8601_with_milliseconds(self):
        """Test valid ISO 8601 timestamp with milliseconds."""
        assert validate_timestamp("2025-11-11T15:30:45.123Z") is True
    
    def test_valid_iso8601_naive(self):
        """Test valid ISO 8601 timestamp without timezone."""
        assert validate_timestamp("2025-11-11T15:30:45") is True
    
    def test_invalid_timestamp_wrong_format(self):
        """Test that wrong format fails."""
        # Python's fromisoformat is lenient with space instead of T, so test with clearly invalid formats
        assert validate_timestamp("11/11/2025 15:30:45") is False
        assert validate_timestamp("not-a-date") is False
        assert validate_timestamp("2025-13-45T15:30:45Z") is False  # Invalid date
    
    def test_invalid_timestamp_invalid_date(self):
        """Test that invalid date fails."""
        assert validate_timestamp("2025-13-45T15:30:45Z") is False
    
    def test_invalid_timestamp_empty_string(self):
        """Test that empty string fails."""
        assert validate_timestamp("") is False
    
    def test_invalid_timestamp_none(self):
        """Test that None fails."""
        assert validate_timestamp(None) is False
    
    def test_invalid_timestamp_non_string(self):
        """Test that non-string fails."""
        assert validate_timestamp(1234567890) is False


class TestValidateCursor:
    """Tests for validate_cursor function."""
    
    def test_valid_cursor(self):
        """Test valid cursor format."""
        # Create cursor with current timestamp
        timestamp = int(datetime.now(timezone.utc).timestamp())
        event_id = "evt_" + "a" * 32
        cursor = f"{timestamp}_{event_id}"
        
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is True
        assert parsed_data is not None
        assert parsed_data['timestamp'] == timestamp
        assert parsed_data['event_id'] == event_id
        assert error is None
    
    def test_cursor_expired(self):
        """Test that expired cursor (>24 hours) fails."""
        # Create cursor with timestamp 25 hours ago
        old_timestamp = int((datetime.now(timezone.utc) - timedelta(hours=25)).timestamp())
        event_id = "evt_" + "a" * 32
        cursor = f"{old_timestamp}_{event_id}"
        
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is False
        assert parsed_data is None
        assert "expired" in error.lower()
    
    def test_cursor_just_under_24_hours(self):
        """Test that cursor just under 24 hours passes."""
        # Create cursor with timestamp 23 hours ago
        timestamp = int((datetime.now(timezone.utc) - timedelta(hours=23)).timestamp())
        event_id = "evt_" + "a" * 32
        cursor = f"{timestamp}_{event_id}"
        
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is True
        assert parsed_data is not None
    
    def test_cursor_future_timestamp(self):
        """Test that cursor with future timestamp fails."""
        future_timestamp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        event_id = "evt_" + "a" * 32
        cursor = f"{future_timestamp}_{event_id}"
        
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is False
        assert parsed_data is None
        assert "future" in error.lower()
    
    def test_cursor_invalid_format_no_underscore(self):
        """Test that cursor without underscore fails."""
        cursor = "1699712345evt_abc123"
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is False
        assert parsed_data is None
        assert "format" in error.lower()
    
    def test_cursor_invalid_format_multiple_underscores(self):
        """Test that cursor with multiple underscores (but valid event_id) passes."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        event_id = "evt_" + "a" * 32
        cursor = f"{timestamp}_{event_id}"
        
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is True
    
    def test_cursor_invalid_timestamp_not_integer(self):
        """Test that cursor with non-integer timestamp fails."""
        event_id = "evt_" + "a" * 32
        cursor = f"not_a_number_{event_id}"
        
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is False
        assert parsed_data is None
        assert "timestamp" in error.lower()
    
    def test_cursor_invalid_event_id_format(self):
        """Test that cursor with invalid event_id format fails."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        invalid_event_id = "invalid_id"
        cursor = f"{timestamp}_{invalid_event_id}"
        
        is_valid, parsed_data, error = validate_cursor(cursor)
        assert is_valid is False
        assert parsed_data is None
        # Error should mention event_id format issue or invalid format
        assert error is not None
        assert ("event_id" in error.lower() or "format" in error.lower() or "invalid" in error.lower())
    
    def test_cursor_empty_string(self):
        """Test that empty cursor fails."""
        is_valid, parsed_data, error = validate_cursor("")
        assert is_valid is False
        assert parsed_data is None
    
    def test_cursor_none(self):
        """Test that None cursor fails."""
        is_valid, parsed_data, error = validate_cursor(None)
        assert is_valid is False
        assert parsed_data is None


class TestValidatePayloadSize:
    """Tests for validate_payload_size function."""
    
    def test_small_payload(self):
        """Test that small payload passes."""
        payload = {"key": "value"}
        assert validate_payload_size(payload) is True
    
    def test_large_payload_under_limit(self):
        """Test that payload just under 10MB passes."""
        # Create payload close to but under 10MB
        large_data = "x" * (MAX_PAYLOAD_SIZE_BYTES - 1000)
        payload = {"data": large_data}
        assert validate_payload_size(payload) is True
    
    def test_payload_exceeds_limit(self):
        """Test that payload over 10MB fails."""
        # Create payload over 10MB
        large_data = "x" * (MAX_PAYLOAD_SIZE_BYTES + 1000)
        payload = {"data": large_data}
        assert validate_payload_size(payload) is False
    
    def test_empty_payload(self):
        """Test that empty payload passes."""
        payload = {}
        assert validate_payload_size(payload) is True
    
    def test_nested_payload(self):
        """Test that nested payload validates correctly."""
        payload = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        assert validate_payload_size(payload) is True
    
    def test_payload_with_array(self):
        """Test that payload with array validates correctly."""
        payload = {
            "items": [{"id": i} for i in range(1000)]
        }
        assert validate_payload_size(payload) is True
    
    def test_get_payload_size_bytes(self):
        """Test get_payload_size_bytes function."""
        payload = {"key": "value"}
        size = get_payload_size_bytes(payload)
        assert isinstance(size, int)
        assert size > 0
    
    def test_get_payload_size_bytes_empty(self):
        """Test get_payload_size_bytes with empty payload."""
        payload = {}
        size = get_payload_size_bytes(payload)
        assert size == 2  # "{}" is 2 bytes


class TestValidateEventId:
    """Tests for validate_event_id function."""
    
    def test_valid_event_id(self):
        """Test valid event_id format."""
        event_id = "evt_" + "a" * 32
        assert validate_event_id(event_id) is True
    
    def test_valid_event_id_with_base64url_chars(self):
        """Test valid event_id with base64url characters."""
        # Create exactly 32 chars after "evt_" prefix
        # "aBc123XyZ789-_" is 14 chars, so 2*14 = 28, need 4 more = 32 total
        suffix = "aBc123XyZ789-_" * 2 + "aBc1"  # 28 + 4 = 32 chars
        event_id = "evt_" + suffix
        assert len(event_id) == 36  # "evt_" + 32 chars
        assert validate_event_id(event_id) is True
    
    def test_invalid_event_id_wrong_prefix(self):
        """Test that wrong prefix fails."""
        assert validate_event_id("ev_" + "a" * 32) is False
        assert validate_event_id("event_" + "a" * 32) is False
    
    def test_invalid_event_id_too_short(self):
        """Test that too short event_id fails."""
        assert validate_event_id("evt_" + "a" * 31) is False
    
    def test_invalid_event_id_too_long(self):
        """Test that too long event_id fails."""
        assert validate_event_id("evt_" + "a" * 33) is False
    
    def test_invalid_event_id_no_prefix(self):
        """Test that event_id without prefix fails."""
        assert validate_event_id("a" * 32) is False
    
    def test_invalid_event_id_empty_string(self):
        """Test that empty string fails."""
        assert validate_event_id("") is False
    
    def test_invalid_event_id_none(self):
        """Test that None fails."""
        assert validate_event_id(None) is False
    
    def test_invalid_event_id_non_string(self):
        """Test that non-string fails."""
        assert validate_event_id(12345) is False


class TestValidateTenantId:
    """Tests for validate_tenant_id function."""
    
    def test_valid_tenant_id(self):
        """Test valid tenant_id format."""
        tenant_id = "tenant_550e8400-e29b-41d4-a716-446655440000"
        assert validate_tenant_id(tenant_id) is True
    
    def test_valid_tenant_id_uppercase(self):
        """Test valid tenant_id with uppercase UUID."""
        tenant_id = "tenant_550E8400-E29B-41D4-A716-446655440000"
        assert validate_tenant_id(tenant_id) is True
    
    def test_invalid_tenant_id_wrong_prefix(self):
        """Test that wrong prefix fails."""
        assert validate_tenant_id("ten_" + "550e8400-e29b-41d4-a716-446655440000") is False
    
    def test_invalid_tenant_id_no_prefix(self):
        """Test that UUID without prefix fails."""
        assert validate_tenant_id("550e8400-e29b-41d4-a716-446655440000") is False
    
    def test_invalid_tenant_id_not_uuid_v4(self):
        """Test that non-UUID v4 fails."""
        # UUID v1
        assert validate_tenant_id("tenant_6ba7b810-9dad-11d1-80b4-00c04fd430c8") is False
    
    def test_invalid_tenant_id_malformed_uuid(self):
        """Test that malformed UUID fails."""
        assert validate_tenant_id("tenant_not-a-uuid") is False
        assert validate_tenant_id("tenant_550e8400") is False
    
    def test_invalid_tenant_id_empty_string(self):
        """Test that empty string fails."""
        assert validate_tenant_id("") is False
    
    def test_invalid_tenant_id_none(self):
        """Test that None fails."""
        assert validate_tenant_id(None) is False
    
    def test_invalid_tenant_id_non_string(self):
        """Test that non-string fails."""
        assert validate_tenant_id(12345) is False

