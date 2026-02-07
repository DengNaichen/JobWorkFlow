"""
Property-based tests for cursor encoding/decoding.

Tests universal properties that should hold for all valid inputs.
"""

from hypothesis import given, strategies as st
from utils.cursor import encode_cursor, decode_cursor


# Strategy for generating valid ISO 8601 timestamps
@st.composite
def iso8601_timestamps(draw):
    """Generate valid ISO 8601 timestamp strings."""
    year = draw(st.integers(min_value=2000, max_value=2099))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    millisecond = draw(st.integers(min_value=0, max_value=999))

    return (
        f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}.{millisecond:03d}Z"
    )


class TestCursorRoundTripProperty:
    """Property tests for cursor round-trip consistency."""

    @given(
        captured_at=iso8601_timestamps(), record_id=st.integers(min_value=0, max_value=2**31 - 1)
    )
    def test_cursor_round_trip_consistency(self, captured_at, record_id):
        """
        **Property 1: Cursor round-trip consistency**
        **Validates: Requirements 1.5**

        For any valid (captured_at, id) pair, decode_cursor(encode_cursor(captured_at, id))
        should return the original values.

        This property ensures that:
        1. Encoding is reversible
        2. No data is lost in the encoding/decoding process
        3. The cursor format is stable and reliable
        """
        # Encode the cursor
        cursor = encode_cursor(captured_at, record_id)

        # Decode the cursor
        decoded_ts, decoded_id = decode_cursor(cursor)

        # Verify round-trip preserves values
        assert decoded_ts == captured_at, (
            f"Timestamp mismatch: expected {captured_at}, got {decoded_ts}"
        )
        assert decoded_id == record_id, f"ID mismatch: expected {record_id}, got {decoded_id}"

    @given(
        captured_at=iso8601_timestamps(), record_id=st.integers(min_value=0, max_value=2**31 - 1)
    )
    def test_cursor_encoding_is_deterministic(self, captured_at, record_id):
        """
        **Property 2: Cursor encoding is deterministic**
        **Validates: Requirements 1.5**

        For any valid (captured_at, id) pair, encoding the same values multiple times
        should always produce the same cursor string.

        This property ensures that:
        1. Cursor generation is deterministic
        2. The same pagination state always produces the same cursor
        3. Cursors can be reliably compared for equality
        """
        # Encode the same values multiple times
        cursor1 = encode_cursor(captured_at, record_id)
        cursor2 = encode_cursor(captured_at, record_id)
        cursor3 = encode_cursor(captured_at, record_id)

        # All cursors should be identical
        assert cursor1 == cursor2, "Cursor encoding is not deterministic"
        assert cursor2 == cursor3, "Cursor encoding is not deterministic"
        assert cursor1 == cursor3, "Cursor encoding is not deterministic"

    @given(
        captured_at=iso8601_timestamps(),
        id1=st.integers(min_value=0, max_value=2**31 - 1),
        id2=st.integers(min_value=0, max_value=2**31 - 1),
    )
    def test_different_ids_produce_different_cursors(self, captured_at, id1, id2):
        """
        **Property 3: Different IDs produce different cursors**
        **Validates: Requirements 1.5**

        For the same timestamp but different IDs, the cursors should be different.

        This property ensures that:
        1. The ID is properly encoded in the cursor
        2. Cursors uniquely identify pagination positions
        3. No collisions occur for different IDs
        """
        # Skip if IDs are the same
        if id1 == id2:
            return

        cursor1 = encode_cursor(captured_at, id1)
        cursor2 = encode_cursor(captured_at, id2)

        assert cursor1 != cursor2, f"Different IDs ({id1} vs {id2}) produced same cursor"

    @given(
        ts1=iso8601_timestamps(),
        ts2=iso8601_timestamps(),
        record_id=st.integers(min_value=0, max_value=2**31 - 1),
    )
    def test_different_timestamps_produce_different_cursors(self, ts1, ts2, record_id):
        """
        **Property 4: Different timestamps produce different cursors**
        **Validates: Requirements 1.5**

        For the same ID but different timestamps, the cursors should be different.

        This property ensures that:
        1. The timestamp is properly encoded in the cursor
        2. Cursors uniquely identify pagination positions
        3. No collisions occur for different timestamps
        """
        # Skip if timestamps are the same
        if ts1 == ts2:
            return

        cursor1 = encode_cursor(ts1, record_id)
        cursor2 = encode_cursor(ts2, record_id)

        assert cursor1 != cursor2, f"Different timestamps ({ts1} vs {ts2}) produced same cursor"

    @given(
        captured_at=iso8601_timestamps(), record_id=st.integers(min_value=0, max_value=2**31 - 1)
    )
    def test_cursor_is_opaque_string(self, captured_at, record_id):
        """
        **Property 5: Cursor is opaque string**
        **Validates: Requirements 1.5**

        For any valid input, the cursor should be an opaque string that doesn't
        expose the raw timestamp or ID values.

        This property ensures that:
        1. Cursors are properly encoded
        2. Internal structure is not exposed to clients
        3. Cursors are safe to use in URLs and APIs
        """
        cursor = encode_cursor(captured_at, record_id)

        # Cursor should be a string
        assert isinstance(cursor, str), "Cursor must be a string"

        # Cursor should not be empty
        assert len(cursor) > 0, "Cursor must not be empty"

        # Cursor should not contain raw timestamp components
        # (checking for year, which is always present in ISO 8601)
        year = captured_at[:4]
        assert year not in cursor, f"Cursor should not contain raw timestamp year: {year}"

        # Cursor should not contain raw ID as a substring
        # (for IDs > 9, check if the ID appears as a substring)
        if record_id > 9:
            assert str(record_id) not in cursor, f"Cursor should not contain raw ID: {record_id}"

    @given(
        captured_at=iso8601_timestamps(), record_id=st.integers(min_value=0, max_value=2**31 - 1)
    )
    def test_encoded_cursor_is_valid_base64(self, captured_at, record_id):
        """
        **Property 6: Encoded cursor is valid base64**
        **Validates: Requirements 1.5**

        For any valid input, the cursor should be a valid base64 string.

        This property ensures that:
        1. Cursors use base64 encoding
        2. Cursors are URL-safe and API-safe
        3. Cursors can be reliably transmitted
        """
        import re

        cursor = encode_cursor(captured_at, record_id)

        # Cursor should only contain base64 characters
        assert re.match(r"^[A-Za-z0-9+/=]+$", cursor), (
            f"Cursor contains invalid base64 characters: {cursor}"
        )

    @given(
        captured_at=iso8601_timestamps(), record_id=st.integers(min_value=0, max_value=2**31 - 1)
    )
    def test_cursor_decoding_never_returns_none(self, captured_at, record_id):
        """
        **Property 7: Cursor decoding never returns None for valid cursors**
        **Validates: Requirements 1.5**

        For any valid encoded cursor, decoding should never return None.
        (None is only returned when the input cursor is None)

        This property ensures that:
        1. Valid cursors always decode successfully
        2. None is reserved for "first page" semantics
        3. Decoding is reliable for all valid cursors
        """
        cursor = encode_cursor(captured_at, record_id)
        result = decode_cursor(cursor)

        assert result is not None, "Decoding a valid cursor should never return None"
        assert isinstance(result, tuple), "Decoded cursor should be a tuple"
        assert len(result) == 2, "Decoded cursor should have exactly 2 elements"
