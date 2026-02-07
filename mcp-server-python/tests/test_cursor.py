"""
Unit tests for cursor encoding/decoding functions.

Tests cursor round-trip, edge cases, and error handling.
"""

import pytest
import base64
import json
from utils.cursor import encode_cursor, decode_cursor
from models.errors import ToolError, ErrorCode


class TestEncodeCursor:
    """Tests for cursor encoding."""

    def test_encode_basic_cursor(self):
        """Test encoding a basic cursor with timestamp and id."""
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 123)

        # Should be a non-empty string
        assert isinstance(cursor, str)
        assert len(cursor) > 0

        # Should be valid base64
        decoded = base64.b64decode(cursor)
        assert decoded is not None

    def test_encode_cursor_is_base64(self):
        """Test that encoded cursor is valid base64."""
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 456)

        # Should only contain base64 characters
        import re

        assert re.match(r"^[A-Za-z0-9+/=]+$", cursor)

    def test_encode_cursor_contains_both_fields(self):
        """Test that encoded cursor contains both captured_at and id."""
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 789)

        # Decode and parse to verify structure
        decoded = base64.b64decode(cursor)
        payload = json.loads(decoded)

        assert "captured_at" in payload
        assert "id" in payload
        assert payload["captured_at"] == "2026-02-04T03:47:36.966Z"
        assert payload["id"] == 789

    def test_encode_different_timestamps(self):
        """Test encoding cursors with different timestamps."""
        cursor1 = encode_cursor("2026-01-01T00:00:00.000Z", 1)
        cursor2 = encode_cursor("2026-12-31T23:59:59.999Z", 1)

        # Different timestamps should produce different cursors
        assert cursor1 != cursor2

    def test_encode_different_ids(self):
        """Test encoding cursors with different IDs."""
        cursor1 = encode_cursor("2026-02-04T03:47:36.966Z", 1)
        cursor2 = encode_cursor("2026-02-04T03:47:36.966Z", 2)

        # Different IDs should produce different cursors
        assert cursor1 != cursor2

    def test_encode_large_id(self):
        """Test encoding cursor with large ID."""
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 999999999)

        decoded = base64.b64decode(cursor)
        payload = json.loads(decoded)
        assert payload["id"] == 999999999

    def test_encode_cursor_is_compact(self):
        """Test that encoded cursor uses compact JSON (no spaces)."""
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 123)

        decoded = base64.b64decode(cursor)
        json_str = decoded.decode("utf-8")

        # Should not contain spaces after colons or commas
        assert ": " not in json_str
        assert ", " not in json_str


class TestDecodeCursor:
    """Tests for cursor decoding."""

    def test_decode_none_returns_none(self):
        """Test that decoding None returns None (first page)."""
        result = decode_cursor(None)
        assert result is None

    def test_decode_valid_cursor(self):
        """Test decoding a valid cursor."""
        # Create a valid cursor
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 123)

        # Decode it
        result = decode_cursor(cursor)

        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] == "2026-02-04T03:47:36.966Z"
        assert result[1] == 123

    def test_decode_cursor_round_trip(self):
        """Test that encode/decode round-trip preserves values."""
        original_ts = "2026-02-04T03:47:36.966Z"
        original_id = 456

        cursor = encode_cursor(original_ts, original_id)
        decoded_ts, decoded_id = decode_cursor(cursor)

        assert decoded_ts == original_ts
        assert decoded_id == original_id

    def test_decode_multiple_cursors(self):
        """Test decoding multiple different cursors."""
        cursors = [
            encode_cursor("2026-01-01T00:00:00.000Z", 1),
            encode_cursor("2026-02-15T12:30:45.123Z", 999),
            encode_cursor("2026-12-31T23:59:59.999Z", 123456),
        ]

        results = [decode_cursor(c) for c in cursors]

        assert results[0] == ("2026-01-01T00:00:00.000Z", 1)
        assert results[1] == ("2026-02-15T12:30:45.123Z", 999)
        assert results[2] == ("2026-12-31T23:59:59.999Z", 123456)


class TestDecodeCursorErrors:
    """Tests for cursor decoding error handling."""

    def test_decode_invalid_base64(self):
        """Test that invalid base64 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            decode_cursor("not-valid-base64!!!")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "base64" in error.message.lower()
        assert not error.retryable

    def test_decode_invalid_json(self):
        """Test that invalid JSON raises VALIDATION_ERROR."""
        # Valid base64 but invalid JSON
        invalid_json = base64.b64encode(b"not json").decode("ascii")

        with pytest.raises(ToolError) as exc_info:
            decode_cursor(invalid_json)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "json" in error.message.lower()

    def test_decode_json_array_instead_of_object(self):
        """Test that JSON array raises VALIDATION_ERROR."""
        # Valid JSON but wrong type (array instead of object)
        json_array = json.dumps([1, 2, 3])
        cursor = base64.b64encode(json_array.encode("utf-8")).decode("ascii")

        with pytest.raises(ToolError) as exc_info:
            decode_cursor(cursor)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "object" in error.message.lower()

    def test_decode_missing_captured_at_field(self):
        """Test that missing captured_at field raises VALIDATION_ERROR."""
        # Valid JSON object but missing captured_at
        payload = {"id": 123}
        json_str = json.dumps(payload)
        cursor = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

        with pytest.raises(ToolError) as exc_info:
            decode_cursor(cursor)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "captured_at" in error.message.lower()

    def test_decode_missing_id_field(self):
        """Test that missing id field raises VALIDATION_ERROR."""
        # Valid JSON object but missing id
        payload = {"captured_at": "2026-02-04T03:47:36.966Z"}
        json_str = json.dumps(payload)
        cursor = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

        with pytest.raises(ToolError) as exc_info:
            decode_cursor(cursor)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "id" in error.message.lower()

    def test_decode_captured_at_wrong_type(self):
        """Test that non-string captured_at raises VALIDATION_ERROR."""
        # captured_at is a number instead of string
        payload = {"captured_at": 123456, "id": 789}
        json_str = json.dumps(payload)
        cursor = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

        with pytest.raises(ToolError) as exc_info:
            decode_cursor(cursor)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "captured_at" in error.message.lower()
        assert "string" in error.message.lower()

    def test_decode_id_wrong_type(self):
        """Test that non-integer id raises VALIDATION_ERROR."""
        # id is a string instead of integer
        payload = {"captured_at": "2026-02-04T03:47:36.966Z", "id": "123"}
        json_str = json.dumps(payload)
        cursor = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

        with pytest.raises(ToolError) as exc_info:
            decode_cursor(cursor)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "id" in error.message.lower()
        assert "integer" in error.message.lower()

    def test_decode_empty_string(self):
        """Test that empty string raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            decode_cursor("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR

    def test_decode_invalid_utf8(self):
        """Test that invalid UTF-8 raises VALIDATION_ERROR."""
        # Create invalid UTF-8 sequence
        invalid_utf8 = base64.b64encode(b"\xff\xfe").decode("ascii")

        with pytest.raises(ToolError) as exc_info:
            decode_cursor(invalid_utf8)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "utf-8" in error.message.lower()


class TestCursorEdgeCases:
    """Tests for cursor edge cases."""

    def test_cursor_with_milliseconds(self):
        """Test cursor with millisecond precision timestamp."""
        ts = "2026-02-04T03:47:36.123Z"
        cursor = encode_cursor(ts, 100)
        decoded_ts, decoded_id = decode_cursor(cursor)

        assert decoded_ts == ts
        assert decoded_id == 100

    def test_cursor_with_microseconds(self):
        """Test cursor with microsecond precision timestamp."""
        ts = "2026-02-04T03:47:36.123456Z"
        cursor = encode_cursor(ts, 200)
        decoded_ts, decoded_id = decode_cursor(cursor)

        assert decoded_ts == ts
        assert decoded_id == 200

    def test_cursor_with_zero_id(self):
        """Test cursor with ID of 0."""
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 0)
        decoded_ts, decoded_id = decode_cursor(cursor)

        assert decoded_id == 0

    def test_cursor_with_special_timestamp_format(self):
        """Test cursor with various timestamp formats."""
        # Different valid ISO 8601 formats
        timestamps = [
            "2026-02-04T03:47:36Z",
            "2026-02-04T03:47:36.0Z",
            "2026-02-04T03:47:36.000000Z",
            "2026-12-31T23:59:59.999Z",
        ]

        for ts in timestamps:
            cursor = encode_cursor(ts, 123)
            decoded_ts, decoded_id = decode_cursor(cursor)
            assert decoded_ts == ts
            assert decoded_id == 123

    def test_cursor_opacity(self):
        """Test that cursor is opaque (not human-readable)."""
        cursor = encode_cursor("2026-02-04T03:47:36.966Z", 123)

        # Cursor should not contain the raw timestamp or ID
        assert "2026-02-04" not in cursor
        assert "123" not in cursor

    def test_different_cursors_for_different_inputs(self):
        """Test that different inputs always produce different cursors."""
        cursors = set()

        # Generate many cursors with different inputs
        for i in range(100):
            ts = f"2026-02-04T03:47:{i:02d}.000Z"
            cursor = encode_cursor(ts, i)
            cursors.add(cursor)

        # All cursors should be unique
        assert len(cursors) == 100


class TestCursorErrorMessages:
    """Tests for cursor error message clarity."""

    def test_error_messages_are_descriptive(self):
        """Test that all cursor error messages are descriptive."""
        test_cases = [
            ("invalid!!!", "base64"),
            (base64.b64encode(b"not json").decode("ascii"), "json"),
            (base64.b64encode(b"[]").decode("ascii"), "object"),
        ]

        for cursor, expected_keyword in test_cases:
            try:
                decode_cursor(cursor)
                assert False, f"Expected error for cursor: {cursor}"
            except ToolError as e:
                assert expected_keyword in e.message.lower()
                assert len(e.message) > 10  # Reasonable minimum length

    def test_error_includes_validation_code(self):
        """Test that all cursor errors use VALIDATION_ERROR code."""
        invalid_cursors = [
            "invalid!!!",
            base64.b64encode(b"not json").decode("ascii"),
            base64.b64encode(b"[]").decode("ascii"),
            base64.b64encode(b'{"id": 123}').decode("ascii"),
        ]

        for cursor in invalid_cursors:
            try:
                decode_cursor(cursor)
                assert False, f"Expected error for cursor: {cursor}"
            except ToolError as e:
                assert e.code == ErrorCode.VALIDATION_ERROR
                assert not e.retryable
