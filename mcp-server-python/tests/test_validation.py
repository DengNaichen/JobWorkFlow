"""
Unit tests for input validation functions.

Tests validation of limit, db_path, and cursor parameters.
"""

import pytest
from models.errors import ErrorCode, ToolError
from models.status import JobDbStatus, JobTrackerStatus
from utils.validation import (
    DEFAULT_LIMIT,
    MIN_LIMIT,
    validate_all_parameters,
    validate_batch_size,
    validate_cursor,
    validate_db_path,
    validate_job_id,
    validate_limit,
    validate_status,
    validate_unique_job_ids,
)


class TestValidateLimit:
    """Tests for limit parameter validation."""

    def test_default_limit_when_none(self):
        """Test that None returns the default limit of 50."""
        result = validate_limit(None)
        assert result == DEFAULT_LIMIT
        assert result == 50

    def test_valid_limit_in_range(self):
        """Test that valid limits within range are accepted."""
        assert validate_limit(1) == 1
        assert validate_limit(50) == 50
        assert validate_limit(100) == 100
        assert validate_limit(500) == 500
        assert validate_limit(1000) == 1000

    def test_limit_below_minimum(self):
        """Test that limit below 1 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(0)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()
        assert not error.retryable

    def test_limit_negative(self):
        """Test that negative limit raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(-1)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()

    def test_limit_above_maximum(self):
        """Test that limit above 1000 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(1001)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()
        assert not error.retryable

    def test_limit_far_above_maximum(self):
        """Test that very large limit raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(10000)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()

    def test_limit_invalid_type_string(self):
        """Test that string limit raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit("50")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_limit_invalid_type_float(self):
        """Test that float limit raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(50.5)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_limit_invalid_type_boolean_true(self):
        """Test that boolean limit raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(True)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_limit_invalid_type_boolean_false(self):
        """Test that boolean limit raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(False)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateDbPath:
    """Tests for db_path parameter validation."""

    def test_none_db_path_is_valid(self):
        """Test that None db_path is valid (means use default)."""
        result = validate_db_path(None)
        assert result is None

    def test_valid_relative_path(self):
        """Test that valid relative paths are accepted."""
        assert validate_db_path("data/capture/jobs.db") == "data/capture/jobs.db"
        assert validate_db_path("jobs.db") == "jobs.db"
        assert validate_db_path("./data/jobs.db") == "./data/jobs.db"

    def test_valid_absolute_path(self):
        """Test that valid absolute paths are accepted."""
        assert validate_db_path("/tmp/jobs.db") == "/tmp/jobs.db"
        assert validate_db_path("/var/data/jobs.db") == "/var/data/jobs.db"

    def test_empty_string_raises_error(self):
        """Test that empty string raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_db_path("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "empty" in error.message.lower()
        assert not error.retryable

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_db_path("   ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "empty" in error.message.lower()

    def test_invalid_type_integer(self):
        """Test that integer db_path raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_db_path(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_invalid_type_list(self):
        """Test that list db_path raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_db_path(["data/jobs.db"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateCursor:
    """Tests for cursor parameter validation."""

    def test_none_cursor_is_valid(self):
        """Test that None cursor is valid (means first page)."""
        result = validate_cursor(None)
        assert result is None

    def test_valid_base64_cursor(self):
        """Test that valid base64 cursors are accepted."""
        # Valid base64 strings
        assert validate_cursor("eyJpZCI6MTIzfQ==") == "eyJpZCI6MTIzfQ=="
        assert validate_cursor("YWJjZGVm") == "YWJjZGVm"
        assert validate_cursor("SGVsbG8=") == "SGVsbG8="
        assert validate_cursor("dGVzdA==") == "dGVzdA=="

    def test_empty_string_raises_error(self):
        """Test that empty string raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_cursor("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "empty" in error.message.lower()
        assert not error.retryable

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_cursor("   ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "empty" in error.message.lower()

    def test_invalid_format_with_special_chars(self):
        """Test that cursor with invalid characters raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_cursor("invalid@cursor!")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "format" in error.message.lower()

    def test_invalid_format_with_spaces(self):
        """Test that cursor with spaces raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_cursor("invalid cursor")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "format" in error.message.lower()

    def test_invalid_type_integer(self):
        """Test that integer cursor raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_cursor(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_invalid_type_dict(self):
        """Test that dict cursor raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_cursor({"id": 123})

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateAllParameters:
    """Tests for validating all parameters together."""

    def test_all_defaults(self):
        """Test validation with all default values."""
        limit, cursor, db_path = validate_all_parameters()
        assert limit == DEFAULT_LIMIT
        assert cursor is None
        assert db_path is None

    def test_all_valid_values(self):
        """Test validation with all valid custom values."""
        limit, cursor, db_path = validate_all_parameters(
            limit=100, cursor="dGVzdA==", db_path="data/jobs.db"
        )
        assert limit == 100
        assert cursor == "dGVzdA=="
        assert db_path == "data/jobs.db"

    def test_mixed_defaults_and_values(self):
        """Test validation with mix of defaults and custom values."""
        limit, cursor, db_path = validate_all_parameters(
            limit=200, cursor=None, db_path="custom.db"
        )
        assert limit == 200
        assert cursor is None
        assert db_path == "custom.db"

    def test_invalid_limit_stops_validation(self):
        """Test that invalid limit raises error immediately."""
        with pytest.raises(ToolError) as exc_info:
            validate_all_parameters(limit=0, cursor="dGVzdA==", db_path="test.db")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "limit" in error.message.lower()

    def test_invalid_cursor_with_valid_limit(self):
        """Test that invalid cursor raises error with valid limit."""
        with pytest.raises(ToolError) as exc_info:
            validate_all_parameters(limit=50, cursor="invalid!", db_path="test.db")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cursor" in error.message.lower()

    def test_invalid_db_path_with_valid_others(self):
        """Test that invalid db_path raises error with valid other params."""
        with pytest.raises(ToolError) as exc_info:
            validate_all_parameters(limit=50, cursor="dGVzdA==", db_path="")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "db_path" in error.message.lower()


class TestErrorMessageClarity:
    """Tests for error message clarity and sanitization."""

    def test_limit_error_includes_value(self):
        """Test that limit error messages include the invalid value."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(2000)

        error = exc_info.value
        assert "2000" in error.message

    def test_limit_error_includes_bounds(self):
        """Test that limit error messages include the valid bounds."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit(0)

        error = exc_info.value
        assert str(MIN_LIMIT) in error.message

    def test_type_error_includes_type_name(self):
        """Test that type errors include the actual type received."""
        with pytest.raises(ToolError) as exc_info:
            validate_limit("50")

        error = exc_info.value
        assert "str" in error.message

    def test_error_messages_are_descriptive(self):
        """Test that all error messages are descriptive and actionable."""
        # Test various error scenarios
        errors = []

        try:
            validate_limit(0)
        except ToolError as e:
            errors.append(e.message)

        try:
            validate_cursor("invalid!")
        except ToolError as e:
            errors.append(e.message)

        try:
            validate_db_path("")
        except ToolError as e:
            errors.append(e.message)

        # All error messages should be non-empty and descriptive
        for msg in errors:
            assert len(msg) > 10  # Reasonable minimum length
            assert msg[0].isupper() or msg.startswith("Invalid")  # Proper capitalization


class TestValidateStatus:
    """Tests for status parameter validation."""

    def test_valid_statuses(self):
        """Test that all valid status values are accepted."""
        for status in JobDbStatus:
            result = validate_status(status.value)
            assert result == status

    def test_invalid_status_value(self):
        """Test that invalid status values raise VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status("invalid_status")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid status value" in error.message
        assert "invalid_status" in error.message
        assert not error.retryable

    def test_status_case_sensitive(self):
        """Test that status validation is case-sensitive."""
        # Uppercase should fail
        with pytest.raises(ToolError) as exc_info:
            validate_status("NEW")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid status value" in error.message

        # Mixed case should fail
        with pytest.raises(ToolError) as exc_info:
            validate_status("New")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid status value" in error.message

    def test_status_with_leading_whitespace(self):
        """Test that status with leading whitespace raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status(" new")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()
        assert not error.retryable

    def test_status_with_trailing_whitespace(self):
        """Test that status with trailing whitespace raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status("new ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()

    def test_status_with_both_whitespace(self):
        """Test that status with leading and trailing whitespace raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status(" new ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()

    def test_status_null_value(self):
        """Test that None status raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status(None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message.lower()
        assert not error.retryable

    def test_status_empty_string(self):
        """Test that empty string status raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()
        assert not error.retryable

    def test_status_invalid_type_integer(self):
        """Test that integer status raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "int" in error.message

    def test_status_invalid_type_list(self):
        """Test that list status raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status(["new"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_status_invalid_type_dict(self):
        """Test that dict status raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_status({"status": "new"})

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_status_error_includes_allowed_values(self):
        """Test that error message includes list of allowed values."""
        with pytest.raises(ToolError) as exc_info:
            validate_status("invalid")

        error = exc_info.value
        # Check that error message includes the allowed values
        for status in JobDbStatus:
            assert status.value in error.message


class TestValidateJobId:
    """Tests for job ID parameter validation."""

    def test_valid_positive_integers(self):
        """Test that positive integers are accepted."""
        assert validate_job_id(1) == 1
        assert validate_job_id(123) == 123
        assert validate_job_id(999999) == 999999

    def test_job_id_null_value(self):
        """Test that None job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message.lower()
        assert not error.retryable

    def test_job_id_zero(self):
        """Test that zero job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(0)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "positive integer" in error.message.lower()
        assert "0" in error.message
        assert not error.retryable

    def test_job_id_negative(self):
        """Test that negative job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(-1)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "positive integer" in error.message.lower()
        assert "-1" in error.message

    def test_job_id_large_negative(self):
        """Test that large negative job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(-999)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "positive integer" in error.message.lower()

    def test_job_id_invalid_type_string(self):
        """Test that string job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id("123")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "str" in error.message

    def test_job_id_invalid_type_float(self):
        """Test that float job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(123.45)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "float" in error.message

    def test_job_id_invalid_type_boolean_true(self):
        """Test that boolean True raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(True)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_job_id_invalid_type_boolean_false(self):
        """Test that boolean False raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(False)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_job_id_invalid_type_list(self):
        """Test that list job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id([123])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_job_id_invalid_type_dict(self):
        """Test that dict job ID raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_job_id({"id": 123})

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_job_id_error_message_clarity(self):
        """Test that error messages are clear and actionable."""
        # Test with zero
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(0)

        error = exc_info.value
        assert "0" in error.message
        assert "positive" in error.message.lower()

        # Test with negative
        with pytest.raises(ToolError) as exc_info:
            validate_job_id(-5)

        error = exc_info.value
        assert "-5" in error.message
        assert "positive" in error.message.lower()


class TestValidateBatchSize:
    """Tests for batch size validation."""

    def test_empty_batch_is_valid(self):
        """Test that empty batch (0 updates) is valid."""
        # Should not raise any exception
        validate_batch_size([])

    def test_none_batch_is_valid(self):
        """Test that None batch is treated as valid (empty)."""
        # Should not raise any exception
        validate_batch_size(None)

    def test_single_update_is_valid(self):
        """Test that batch with 1 update is valid."""
        updates = [{"id": 1, "status": "new"}]
        # Should not raise any exception
        validate_batch_size(updates)

    def test_batch_size_50_is_valid(self):
        """Test that batch with 50 updates is valid."""
        updates = [{"id": i, "status": "new"} for i in range(1, 51)]
        # Should not raise any exception
        validate_batch_size(updates)

    def test_batch_size_100_is_valid(self):
        """Test that batch with exactly 100 updates is valid."""
        updates = [{"id": i, "status": "new"} for i in range(1, 101)]
        # Should not raise any exception
        validate_batch_size(updates)

    def test_batch_size_101_raises_error(self):
        """Test that batch with 101 updates raises VALIDATION_ERROR."""
        updates = [{"id": i, "status": "new"} for i in range(1, 102)]

        with pytest.raises(ToolError) as exc_info:
            validate_batch_size(updates)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Batch size too large" in error.message
        assert "101" in error.message
        assert "100" in error.message
        assert not error.retryable

    def test_batch_size_200_raises_error(self):
        """Test that batch with 200 updates raises VALIDATION_ERROR."""
        updates = [{"id": i, "status": "new"} for i in range(1, 201)]

        with pytest.raises(ToolError) as exc_info:
            validate_batch_size(updates)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Batch size too large" in error.message
        assert "200" in error.message
        assert "100" in error.message

    def test_batch_size_1000_raises_error(self):
        """Test that very large batch raises VALIDATION_ERROR."""
        updates = [{"id": i, "status": "new"} for i in range(1, 1001)]

        with pytest.raises(ToolError) as exc_info:
            validate_batch_size(updates)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Batch size too large" in error.message
        assert "1000" in error.message

    def test_error_message_clarity(self):
        """Test that error message is clear and includes relevant information."""
        updates = [{"id": i, "status": "new"} for i in range(1, 152)]

        with pytest.raises(ToolError) as exc_info:
            validate_batch_size(updates)

        error = exc_info.value
        # Should include actual size
        assert "151" in error.message
        # Should include maximum allowed
        assert "100" in error.message
        # Should be descriptive
        assert "exceeds" in error.message.lower() or "too large" in error.message.lower()


class TestValidateUniqueJobIds:
    """Tests for duplicate job ID validation."""

    def test_empty_batch_is_valid(self):
        """Test that empty batch is valid (no duplicates)."""
        # Should not raise any exception
        validate_unique_job_ids([])

    def test_none_batch_is_valid(self):
        """Test that None batch is treated as valid."""
        # Should not raise any exception
        validate_unique_job_ids(None)

    def test_single_update_is_valid(self):
        """Test that batch with single update is valid."""
        updates = [{"id": 1, "status": "new"}]
        # Should not raise any exception
        validate_unique_job_ids(updates)

    def test_all_unique_ids_is_valid(self):
        """Test that batch with all unique IDs is valid."""
        updates = [
            {"id": 1, "status": "new"},
            {"id": 2, "status": "shortlist"},
            {"id": 3, "status": "reviewed"},
        ]
        # Should not raise any exception
        validate_unique_job_ids(updates)

    def test_duplicate_id_raises_error(self):
        """Test that duplicate job ID raises VALIDATION_ERROR."""
        updates = [
            {"id": 1, "status": "new"},
            {"id": 2, "status": "shortlist"},
            {"id": 1, "status": "reviewed"},  # Duplicate ID 1
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_unique_job_ids(updates)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate job IDs" in error.message
        assert "1" in error.message
        assert not error.retryable

    def test_multiple_duplicates_raises_error(self):
        """Test that multiple duplicate IDs are all reported."""
        updates = [
            {"id": 1, "status": "new"},
            {"id": 2, "status": "shortlist"},
            {"id": 1, "status": "reviewed"},  # Duplicate ID 1
            {"id": 3, "status": "reject"},
            {"id": 2, "status": "applied"},  # Duplicate ID 2
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_unique_job_ids(updates)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate job IDs" in error.message
        # Both duplicate IDs should be mentioned
        assert "1" in error.message
        assert "2" in error.message

    def test_triple_duplicate_raises_error(self):
        """Test that ID appearing three times is reported as duplicate."""
        updates = [
            {"id": 5, "status": "new"},
            {"id": 5, "status": "shortlist"},
            {"id": 5, "status": "reviewed"},
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_unique_job_ids(updates)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate job IDs" in error.message
        assert "5" in error.message

    def test_updates_without_id_field_ignored(self):
        """Test that updates without 'id' field don't cause errors."""
        updates = [
            {"id": 1, "status": "new"},
            {"status": "shortlist"},  # Missing 'id' field
            {"id": 2, "status": "reviewed"},
        ]
        # Should not raise any exception (missing IDs are ignored for duplicate check)
        validate_unique_job_ids(updates)

    def test_non_dict_updates_ignored(self):
        """Test that non-dict updates don't cause errors."""
        updates = [
            {"id": 1, "status": "new"},
            "invalid",  # Not a dict
            {"id": 2, "status": "reviewed"},
        ]
        # Should not raise any exception (non-dict items are ignored)
        validate_unique_job_ids(updates)

    def test_large_batch_with_unique_ids(self):
        """Test that large batch with all unique IDs is valid."""
        updates = [{"id": i, "status": "new"} for i in range(1, 101)]
        # Should not raise any exception
        validate_unique_job_ids(updates)

    def test_error_message_clarity(self):
        """Test that error message is clear and lists duplicate IDs."""
        updates = [
            {"id": 10, "status": "new"},
            {"id": 20, "status": "shortlist"},
            {"id": 10, "status": "reviewed"},
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_unique_job_ids(updates)

        error = exc_info.value
        # Should include the duplicate ID
        assert "10" in error.message
        # Should be descriptive
        assert "Duplicate" in error.message or "duplicate" in error.message

    def test_duplicate_ids_mixed_types_raise_validation_error_not_type_error(self):
        """Test mixed-type duplicate IDs still raise VALIDATION_ERROR."""
        updates = [
            {"id": "abc", "status": "new"},
            {"id": "abc", "status": "shortlist"},
            {"id": 1, "status": "reviewed"},
            {"id": 1, "status": "applied"},
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_unique_job_ids(updates)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate job IDs" in error.message
        assert "abc" in error.message
        assert "1" in error.message


class TestGetCurrentUtcTimestamp:
    """Tests for UTC timestamp generation."""

    def test_timestamp_format_matches_iso8601(self):
        """Test that timestamp matches ISO 8601 format with milliseconds and Z suffix."""
        import re

        from utils.validation import get_current_utc_timestamp

        timestamp = get_current_utc_timestamp()

        # Format: YYYY-MM-DDTHH:MM:SS.mmmZ
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
        assert re.match(pattern, timestamp), (
            f"Timestamp '{timestamp}' does not match expected format"
        )

    def test_timestamp_is_utc(self):
        """Test that timestamp ends with Z indicating UTC timezone."""
        from utils.validation import get_current_utc_timestamp

        timestamp = get_current_utc_timestamp()
        assert timestamp.endswith("Z"), f"Timestamp '{timestamp}' should end with 'Z' for UTC"

    def test_timestamp_includes_milliseconds(self):
        """Test that timestamp includes millisecond precision."""
        from utils.validation import get_current_utc_timestamp

        timestamp = get_current_utc_timestamp()

        # Should have format: ...SS.mmmZ where mmm is 3 digits
        parts = timestamp.split(".")
        assert len(parts) == 2, "Timestamp should have millisecond component"

        millisecond_part = parts[1]
        assert millisecond_part.endswith("Z"), "Millisecond part should end with Z"
        assert len(millisecond_part) == 4, "Millisecond part should be 3 digits + Z"
        assert millisecond_part[:-1].isdigit(), "Millisecond part should be numeric"

    def test_timestamp_is_current(self):
        """Test that timestamp represents current time (within reasonable bounds)."""
        from datetime import datetime, timedelta, timezone

        from utils.validation import get_current_utc_timestamp

        before = datetime.now(timezone.utc)
        timestamp_str = get_current_utc_timestamp()
        after = datetime.now(timezone.utc)

        # Parse the timestamp
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Should be between before and after (with small tolerance)
        tolerance = timedelta(seconds=1)
        assert before - tolerance <= timestamp <= after + tolerance, (
            f"Timestamp {timestamp} not within expected range [{before}, {after}]"
        )

    def test_timestamp_returns_string(self):
        """Test that function returns a string."""
        from utils.validation import get_current_utc_timestamp

        timestamp = get_current_utc_timestamp()
        assert isinstance(timestamp, str), f"Expected string, got {type(timestamp).__name__}"

    def test_timestamp_example_format(self):
        """Test that timestamp matches the example format from requirements."""
        from utils.validation import get_current_utc_timestamp

        timestamp = get_current_utc_timestamp()

        # Example from requirements: 2026-02-04T03:47:36.966Z
        # Year should be 4 digits
        year = timestamp[:4]
        assert year.isdigit() and len(year) == 4, "Year should be 4 digits"

        # Should have T separator
        assert "T" in timestamp, "Should have T separator between date and time"

        # Should have exactly one dot for milliseconds
        assert timestamp.count(".") == 1, "Should have exactly one dot for milliseconds"

        # Should end with Z
        assert timestamp.endswith("Z"), "Should end with Z"

    def test_multiple_calls_produce_valid_timestamps(self):
        """Test that multiple calls all produce valid timestamps."""
        import re

        from utils.validation import get_current_utc_timestamp

        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"

        for _ in range(5):
            timestamp = get_current_utc_timestamp()
            assert re.match(pattern, timestamp), (
                f"Timestamp '{timestamp}' does not match expected format"
            )

    def test_timestamp_parseable_by_datetime(self):
        """Test that timestamp can be parsed back to datetime object."""
        from datetime import datetime

        from utils.validation import get_current_utc_timestamp

        timestamp = get_current_utc_timestamp()

        # Should be parseable by datetime.fromisoformat after replacing Z with +00:00
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            assert parsed is not None
        except ValueError as e:
            pytest.fail(f"Timestamp '{timestamp}' could not be parsed: {e}")


class TestValidateTrackerPath:
    """Tests for tracker_path parameter validation."""

    def test_valid_tracker_path(self):
        """Test that valid tracker paths are accepted."""
        from utils.validation import validate_tracker_path

        assert (
            validate_tracker_path("trackers/2026-02-05-amazon.md")
            == "trackers/2026-02-05-amazon.md"
        )
        assert validate_tracker_path("trackers/test.md") == "trackers/test.md"
        assert validate_tracker_path("path/to/tracker.md") == "path/to/tracker.md"

    def test_tracker_path_null_value(self):
        """Test that None tracker_path raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_path

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_path(None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message.lower()
        assert not error.retryable

    def test_tracker_path_empty_string(self):
        """Test that empty string tracker_path raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_path

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_path("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()
        assert not error.retryable

    def test_tracker_path_with_leading_whitespace(self):
        """Test that tracker_path with leading whitespace raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_path

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_path(" trackers/test.md")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()
        assert not error.retryable

    def test_tracker_path_with_trailing_whitespace(self):
        """Test that tracker_path with trailing whitespace raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_path

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_path("trackers/test.md ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()

    def test_tracker_path_invalid_type_integer(self):
        """Test that integer tracker_path raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_path

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_path(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "int" in error.message

    def test_tracker_path_invalid_type_list(self):
        """Test that list tracker_path raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_path

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_path(["trackers/test.md"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateTrackerStatus:
    """Tests for tracker status parameter validation."""

    def test_valid_tracker_statuses(self):
        """Test that all valid tracker status values are accepted."""
        from utils.validation import validate_tracker_status

        for status in JobTrackerStatus:
            result = validate_tracker_status(status.value)
            assert result == status

    def test_invalid_tracker_status_value(self):
        """Test that invalid tracker status values raise VALIDATION_ERROR."""
        from utils.validation import validate_tracker_status

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status("invalid_status")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid target_status value" in error.message
        assert "invalid_status" in error.message
        assert not error.retryable

    def test_tracker_status_case_sensitive(self):
        """Test that tracker status validation is case-sensitive."""
        from utils.validation import validate_tracker_status

        # Lowercase should fail
        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status("reviewed")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid target_status value" in error.message

        # All caps should fail
        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status("REVIEWED")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid target_status value" in error.message

    def test_tracker_status_with_leading_whitespace(self):
        """Test that tracker status with leading whitespace raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_status

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status(" Reviewed")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()
        assert not error.retryable

    def test_tracker_status_with_trailing_whitespace(self):
        """Test that tracker status with trailing whitespace raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_status

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status("Reviewed ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()

    def test_tracker_status_null_value(self):
        """Test that None tracker status raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_status

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status(None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message.lower()
        assert not error.retryable

    def test_tracker_status_empty_string(self):
        """Test that empty string tracker status raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_status

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()
        assert not error.retryable

    def test_tracker_status_invalid_type_integer(self):
        """Test that integer tracker status raises VALIDATION_ERROR."""
        from utils.validation import validate_tracker_status

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "int" in error.message

    def test_tracker_status_error_includes_allowed_values(self):
        """Test that error message includes list of allowed tracker status values."""
        from utils.validation import validate_tracker_status

        with pytest.raises(ToolError) as exc_info:
            validate_tracker_status("invalid")

        error = exc_info.value
        # Check that error message includes the allowed values
        for status in JobTrackerStatus:
            assert status.value in error.message


class TestValidateUpdateTrackerStatusParameters:
    """Tests for validating all update_tracker_status parameters together."""

    def test_all_required_parameters_valid(self):
        """Test validation with all required parameters."""
        from utils.validation import validate_update_tracker_status_parameters

        tracker_path, target_status, dry_run, force = validate_update_tracker_status_parameters(
            tracker_path="trackers/test.md", target_status="Reviewed"
        )
        assert tracker_path == "trackers/test.md"
        assert target_status == "Reviewed"
        assert dry_run is False  # Default
        assert force is False  # Default

    def test_all_parameters_with_optional_values(self):
        """Test validation with all parameters including optional ones."""
        from utils.validation import validate_update_tracker_status_parameters

        tracker_path, target_status, dry_run, force = validate_update_tracker_status_parameters(
            tracker_path="trackers/test.md",
            target_status="Resume Written",
            dry_run=True,
            force=True,
        )
        assert tracker_path == "trackers/test.md"
        assert target_status == "Resume Written"
        assert dry_run is True
        assert force is True

    def test_dry_run_defaults_to_false(self):
        """Test that dry_run defaults to False when not provided."""
        from utils.validation import validate_update_tracker_status_parameters

        _, _, dry_run, _ = validate_update_tracker_status_parameters(
            tracker_path="trackers/test.md", target_status="Reviewed"
        )
        assert dry_run is False

    def test_force_defaults_to_false(self):
        """Test that force defaults to False when not provided."""
        from utils.validation import validate_update_tracker_status_parameters

        _, _, _, force = validate_update_tracker_status_parameters(
            tracker_path="trackers/test.md", target_status="Reviewed"
        )
        assert force is False

    def test_unknown_property_raises_error(self):
        """Test that unknown properties raise VALIDATION_ERROR."""
        from utils.validation import validate_update_tracker_status_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_update_tracker_status_parameters(
                tracker_path="trackers/test.md", target_status="Reviewed", unknown_param="value"
            )

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Unknown input properties" in error.message
        assert "unknown_param" in error.message
        assert not error.retryable

    def test_multiple_unknown_properties_raises_error(self):
        """Test that multiple unknown properties are all reported."""
        from utils.validation import validate_update_tracker_status_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_update_tracker_status_parameters(
                tracker_path="trackers/test.md",
                target_status="Reviewed",
                unknown1="value1",
                unknown2="value2",
            )

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Unknown input properties" in error.message
        assert "unknown1" in error.message
        assert "unknown2" in error.message

    def test_invalid_tracker_path_stops_validation(self):
        """Test that invalid tracker_path raises error immediately."""
        from utils.validation import validate_update_tracker_status_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_update_tracker_status_parameters(tracker_path=None, target_status="Reviewed")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "tracker_path" in error.message.lower()

    def test_invalid_target_status_with_valid_tracker_path(self):
        """Test that invalid target_status raises error with valid tracker_path."""
        from utils.validation import validate_update_tracker_status_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_update_tracker_status_parameters(
                tracker_path="trackers/test.md", target_status="invalid"
            )

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "target_status" in error.message.lower()

    def test_invalid_dry_run_type(self):
        """Test that invalid dry_run type raises error."""
        from utils.validation import validate_update_tracker_status_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_update_tracker_status_parameters(
                tracker_path="trackers/test.md",
                target_status="Reviewed",
                dry_run="true",  # String instead of boolean
            )

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "dry_run" in error.message.lower()
        assert "type" in error.message.lower()

    def test_invalid_force_type(self):
        """Test that invalid force type raises error."""
        from utils.validation import validate_update_tracker_status_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_update_tracker_status_parameters(
                tracker_path="trackers/test.md",
                target_status="Reviewed",
                force=1,  # Integer instead of boolean
            )

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "force" in error.message.lower()
        assert "type" in error.message.lower()

    def test_all_statuses_accepted(self):
        """Test that all valid tracker statuses are accepted."""
        from utils.validation import validate_update_tracker_status_parameters

        for status in JobTrackerStatus:
            tracker_path, target_status, dry_run, force = validate_update_tracker_status_parameters(
                tracker_path="trackers/test.md", target_status=status.value
            )
            assert target_status == status


class TestValidateRunId:
    """Tests for run_id parameter validation."""

    def test_none_run_id_is_valid(self):
        """Test that None run_id is valid (means auto-generate)."""
        from utils.validation import validate_run_id

        result = validate_run_id(None)
        assert result is None

    def test_valid_run_id_string(self):
        """Test that valid run_id strings are accepted."""
        from utils.validation import validate_run_id

        assert validate_run_id("run_20260206_8f2f8f1c") == "run_20260206_8f2f8f1c"
        assert validate_run_id("batch_123") == "batch_123"
        assert validate_run_id("test-run-id") == "test-run-id"

    def test_run_id_empty_string_raises_error(self):
        """Test that empty string run_id raises VALIDATION_ERROR."""
        from utils.validation import validate_run_id

        with pytest.raises(ToolError) as exc_info:
            validate_run_id("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()
        assert not error.retryable

    def test_run_id_whitespace_only_raises_error(self):
        """Test that whitespace-only run_id raises VALIDATION_ERROR."""
        from utils.validation import validate_run_id

        with pytest.raises(ToolError) as exc_info:
            validate_run_id("   ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()

    def test_run_id_invalid_type_integer(self):
        """Test that integer run_id raises VALIDATION_ERROR."""
        from utils.validation import validate_run_id

        with pytest.raises(ToolError) as exc_info:
            validate_run_id(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "int" in error.message

    def test_run_id_invalid_type_list(self):
        """Test that list run_id raises VALIDATION_ERROR."""
        from utils.validation import validate_run_id

        with pytest.raises(ToolError) as exc_info:
            validate_run_id(["run_id"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateFinalizeItems:
    """Tests for finalize items parameter validation."""

    def test_valid_empty_items_list(self):
        """Test that empty items list is valid."""
        from utils.validation import validate_finalize_items

        result = validate_finalize_items([])
        assert result == []

    def test_valid_items_list_with_one_item(self):
        """Test that items list with one item is valid."""
        from utils.validation import validate_finalize_items

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]
        result = validate_finalize_items(items)
        assert result == items

    def test_valid_items_list_with_multiple_items(self):
        """Test that items list with multiple items is valid."""
        from utils.validation import validate_finalize_items

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"id": 2, "tracker_path": "trackers/test2.md"},
            {"id": 3, "tracker_path": "trackers/test3.md"},
        ]
        result = validate_finalize_items(items)
        assert result == items

    def test_items_list_with_100_items_is_valid(self):
        """Test that items list with exactly 100 items is valid."""
        from utils.validation import validate_finalize_items

        items = [{"id": i, "tracker_path": f"trackers/test{i}.md"} for i in range(1, 101)]
        result = validate_finalize_items(items)
        assert result == items
        assert len(result) == 100

    def test_items_list_with_101_items_raises_error(self):
        """Test that items list with 101 items raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_items

        items = [{"id": i, "tracker_path": f"trackers/test{i}.md"} for i in range(1, 102)]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_items(items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Batch size too large" in error.message
        assert "101" in error.message
        assert "100" in error.message
        assert not error.retryable

    def test_items_list_with_200_items_raises_error(self):
        """Test that items list with 200 items raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_items

        items = [{"id": i, "tracker_path": f"trackers/test{i}.md"} for i in range(1, 201)]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_items(items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Batch size too large" in error.message
        assert "200" in error.message

    def test_items_null_raises_error(self):
        """Test that None items raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_items

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_items(None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message.lower()
        assert not error.retryable

    def test_items_invalid_type_string_raises_error(self):
        """Test that string items raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_items

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_items("not a list")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "array" in error.message.lower()

    def test_items_invalid_type_dict_raises_error(self):
        """Test that dict items raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_items

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_items({"id": 1, "tracker_path": "test.md"})

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "array" in error.message.lower()

    def test_items_invalid_type_integer_raises_error(self):
        """Test that integer items raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_items

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_items(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateFinalizeDuplicateIds:
    """Tests for duplicate item ID validation in finalize batch."""

    def test_empty_items_list_is_valid(self):
        """Test that empty items list is valid (no duplicates)."""
        from utils.validation import validate_finalize_duplicate_ids

        # Should not raise any exception
        validate_finalize_duplicate_ids([])

    def test_none_items_list_is_valid(self):
        """Test that None items list is treated as valid."""
        from utils.validation import validate_finalize_duplicate_ids

        # Should not raise any exception
        validate_finalize_duplicate_ids(None)

    def test_single_item_is_valid(self):
        """Test that single item is valid."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]
        # Should not raise any exception
        validate_finalize_duplicate_ids(items)

    def test_all_unique_ids_is_valid(self):
        """Test that items with all unique IDs are valid."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"id": 2, "tracker_path": "trackers/test2.md"},
            {"id": 3, "tracker_path": "trackers/test3.md"},
        ]
        # Should not raise any exception
        validate_finalize_duplicate_ids(items)

    def test_duplicate_id_raises_error(self):
        """Test that duplicate item ID raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"id": 2, "tracker_path": "trackers/test2.md"},
            {"id": 1, "tracker_path": "trackers/test3.md"},  # Duplicate ID 1
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_duplicate_ids(items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate item IDs" in error.message
        assert "1" in error.message
        assert not error.retryable

    def test_multiple_duplicates_raises_error(self):
        """Test that multiple duplicate IDs are all reported."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"id": 2, "tracker_path": "trackers/test2.md"},
            {"id": 1, "tracker_path": "trackers/test3.md"},  # Duplicate ID 1
            {"id": 3, "tracker_path": "trackers/test4.md"},
            {"id": 2, "tracker_path": "trackers/test5.md"},  # Duplicate ID 2
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_duplicate_ids(items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate item IDs" in error.message
        # Both duplicate IDs should be mentioned
        assert "1" in error.message
        assert "2" in error.message

    def test_triple_duplicate_raises_error(self):
        """Test that ID appearing three times is reported as duplicate."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": 5, "tracker_path": "trackers/test1.md"},
            {"id": 5, "tracker_path": "trackers/test2.md"},
            {"id": 5, "tracker_path": "trackers/test3.md"},
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_duplicate_ids(items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate item IDs" in error.message
        assert "5" in error.message

    def test_mixed_type_duplicates_raise_validation_error_not_type_error(self):
        """Test mixed-type duplicate item IDs still raise VALIDATION_ERROR."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": "abc", "tracker_path": "trackers/a.md"},
            {"id": "abc", "tracker_path": "trackers/b.md"},
            {"id": 1, "tracker_path": "trackers/c.md"},
            {"id": 1, "tracker_path": "trackers/d.md"},
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_duplicate_ids(items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate item IDs" in error.message
        assert "abc" in error.message
        assert "1" in error.message

    def test_items_without_id_field_ignored(self):
        """Test that items without 'id' field don't cause errors."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"tracker_path": "trackers/test2.md"},  # Missing 'id' field
            {"id": 2, "tracker_path": "trackers/test3.md"},
        ]
        # Should not raise any exception (missing IDs are ignored for duplicate check)
        validate_finalize_duplicate_ids(items)

    def test_non_dict_items_ignored(self):
        """Test that non-dict items don't cause errors."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            "invalid",  # Not a dict
            {"id": 2, "tracker_path": "trackers/test2.md"},
        ]
        # Should not raise any exception (non-dict items are ignored)
        validate_finalize_duplicate_ids(items)

    def test_large_batch_with_unique_ids(self):
        """Test that large batch with all unique IDs is valid."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [{"id": i, "tracker_path": f"trackers/test{i}.md"} for i in range(1, 101)]
        # Should not raise any exception
        validate_finalize_duplicate_ids(items)

    def test_error_message_clarity(self):
        """Test that error message is clear and lists duplicate IDs."""
        from utils.validation import validate_finalize_duplicate_ids

        items = [
            {"id": 10, "tracker_path": "trackers/test1.md"},
            {"id": 20, "tracker_path": "trackers/test2.md"},
            {"id": 10, "tracker_path": "trackers/test3.md"},
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_duplicate_ids(items)

        error = exc_info.value
        # Should include the duplicate ID
        assert "10" in error.message
        # Should be descriptive
        assert "Duplicate" in error.message or "duplicate" in error.message


class TestValidateFinalizeResumeBatchParameters:
    """Tests for validating all finalize_resume_batch parameters together."""

    def test_all_required_parameters_valid(self):
        """Test validation with required items parameter."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]
        validated_items, run_id, db_path, dry_run = validate_finalize_resume_batch_parameters(
            items=items
        )
        assert validated_items == items
        assert run_id is None  # Default
        assert db_path is None  # Default
        assert dry_run is False  # Default

    def test_all_parameters_with_optional_values(self):
        """Test validation with all parameters including optional ones."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"id": 2, "tracker_path": "trackers/test2.md"},
        ]
        validated_items, run_id, db_path, dry_run = validate_finalize_resume_batch_parameters(
            items=items,
            run_id="run_20260206_8f2f8f1c",
            db_path="data/capture/jobs.db",
            dry_run=True,
        )
        assert validated_items == items
        assert run_id == "run_20260206_8f2f8f1c"
        assert db_path == "data/capture/jobs.db"
        assert dry_run is True

    def test_empty_items_list_is_valid(self):
        """Test that empty items list is valid."""
        from utils.validation import validate_finalize_resume_batch_parameters

        validated_items, run_id, db_path, dry_run = validate_finalize_resume_batch_parameters(
            items=[]
        )
        assert validated_items == []
        assert run_id is None
        assert db_path is None
        assert dry_run is False

    def test_run_id_defaults_to_none(self):
        """Test that run_id defaults to None when not provided."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]
        _, run_id, _, _ = validate_finalize_resume_batch_parameters(items=items)
        assert run_id is None

    def test_db_path_defaults_to_none(self):
        """Test that db_path defaults to None when not provided."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]
        _, _, db_path, _ = validate_finalize_resume_batch_parameters(items=items)
        assert db_path is None

    def test_dry_run_defaults_to_false(self):
        """Test that dry_run defaults to False when not provided."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]
        _, _, _, dry_run = validate_finalize_resume_batch_parameters(items=items)
        assert dry_run is False

    def test_items_null_raises_error(self):
        """Test that None items raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_resume_batch_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_resume_batch_parameters(items=None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "items" in error.message.lower()
        assert "cannot be null" in error.message.lower()

    def test_items_invalid_type_raises_error(self):
        """Test that invalid items type raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_resume_batch_parameters

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_resume_batch_parameters(items="not a list")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "items" in error.message.lower()
        assert "type" in error.message.lower()

    def test_items_exceeding_batch_size_raises_error(self):
        """Test that items exceeding batch size raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": i, "tracker_path": f"trackers/test{i}.md"} for i in range(1, 102)]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_resume_batch_parameters(items=items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Batch size too large" in error.message
        assert "101" in error.message
        assert "100" in error.message

    def test_duplicate_item_ids_raises_error(self):
        """Test that duplicate item IDs raise VALIDATION_ERROR."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"id": 2, "tracker_path": "trackers/test2.md"},
            {"id": 1, "tracker_path": "trackers/test3.md"},  # Duplicate
        ]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_resume_batch_parameters(items=items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Duplicate item IDs" in error.message
        assert "1" in error.message

    def test_invalid_run_id_raises_error(self):
        """Test that invalid run_id raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_resume_batch_parameters(items=items, run_id="")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "run_id" in error.message.lower()

    def test_invalid_db_path_raises_error(self):
        """Test that invalid db_path raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_resume_batch_parameters(items=items, db_path="")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "db_path" in error.message.lower()

    def test_invalid_dry_run_type_raises_error(self):
        """Test that invalid dry_run type raises VALIDATION_ERROR."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": 1, "tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_finalize_resume_batch_parameters(items=items, dry_run="true")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "dry_run" in error.message.lower()
        assert "type" in error.message.lower()

    def test_batch_size_100_is_valid(self):
        """Test that batch with exactly 100 items is valid."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [{"id": i, "tracker_path": f"trackers/test{i}.md"} for i in range(1, 101)]
        validated_items, _, _, _ = validate_finalize_resume_batch_parameters(items=items)
        assert len(validated_items) == 100

    def test_mixed_valid_parameters(self):
        """Test validation with mix of defaults and custom values."""
        from utils.validation import validate_finalize_resume_batch_parameters

        items = [
            {"id": 1, "tracker_path": "trackers/test1.md"},
            {"id": 2, "tracker_path": "trackers/test2.md"},
        ]
        validated_items, run_id, db_path, dry_run = validate_finalize_resume_batch_parameters(
            items=items, run_id="custom_run", db_path=None, dry_run=True
        )
        assert validated_items == items
        assert run_id == "custom_run"
        assert db_path is None
        assert dry_run is True


class TestValidateFinalizeItem:
    """Tests for individual finalization item validation."""

    def test_valid_item_with_required_fields_only(self):
        """Test that item with only required fields is valid."""
        from utils.validation import validate_finalize_item

        item = {"id": 1, "tracker_path": "trackers/test.md"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is True
        assert error is None

    def test_valid_item_with_optional_resume_pdf_path(self):
        """Test that item with optional resume_pdf_path is valid."""
        from utils.validation import validate_finalize_item

        item = {
            "id": 1,
            "tracker_path": "trackers/test.md",
            "resume_pdf_path": "data/applications/test/resume/resume.pdf",
        }
        is_valid, error = validate_finalize_item(item)
        assert is_valid is True
        assert error is None

    def test_item_not_dict_returns_error(self):
        """Test that non-dict item returns error."""
        from utils.validation import validate_finalize_item

        is_valid, error = validate_finalize_item("not a dict")
        assert is_valid is False
        assert error is not None
        assert "must be an object" in error

    def test_item_missing_id_returns_error(self):
        """Test that item missing 'id' field returns error."""
        from utils.validation import validate_finalize_item

        item = {"tracker_path": "trackers/test.md"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "missing required field 'id'" in error

    def test_item_missing_tracker_path_returns_error(self):
        """Test that item missing 'tracker_path' field returns error."""
        from utils.validation import validate_finalize_item

        item = {"id": 1}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "missing required field 'tracker_path'" in error

    def test_item_id_not_integer_returns_error(self):
        """Test that non-integer id returns error."""
        from utils.validation import validate_finalize_item

        item = {"id": "1", "tracker_path": "trackers/test.md"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'id' must be an integer" in error

    def test_item_id_boolean_returns_error(self):
        """Test that boolean id returns error (bool is subclass of int)."""
        from utils.validation import validate_finalize_item

        item = {"id": True, "tracker_path": "trackers/test.md"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'id' must be an integer" in error

    def test_item_id_zero_returns_error(self):
        """Test that id of 0 returns error (must be positive)."""
        from utils.validation import validate_finalize_item

        item = {"id": 0, "tracker_path": "trackers/test.md"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'id' must be a positive integer" in error

    def test_item_id_negative_returns_error(self):
        """Test that negative id returns error."""
        from utils.validation import validate_finalize_item

        item = {"id": -1, "tracker_path": "trackers/test.md"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'id' must be a positive integer" in error

    def test_item_tracker_path_not_string_returns_error(self):
        """Test that non-string tracker_path returns error."""
        from utils.validation import validate_finalize_item

        item = {"id": 1, "tracker_path": 123}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'tracker_path' must be a string" in error

    def test_item_tracker_path_empty_string_returns_error(self):
        """Test that empty tracker_path returns error."""
        from utils.validation import validate_finalize_item

        item = {"id": 1, "tracker_path": ""}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'tracker_path' cannot be empty" in error

    def test_item_tracker_path_whitespace_only_returns_error(self):
        """Test that whitespace-only tracker_path returns error."""
        from utils.validation import validate_finalize_item

        item = {"id": 1, "tracker_path": "   "}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'tracker_path' cannot be empty" in error

    def test_item_resume_pdf_path_not_string_returns_error(self):
        """Test that non-string resume_pdf_path returns error."""
        from utils.validation import validate_finalize_item

        item = {"id": 1, "tracker_path": "trackers/test.md", "resume_pdf_path": 123}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is False
        assert error is not None
        assert "'resume_pdf_path' must be a string" in error

    def test_item_with_large_id_is_valid(self):
        """Test that item with large positive id is valid."""
        from utils.validation import validate_finalize_item

        item = {"id": 999999, "tracker_path": "trackers/test.md"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is True
        assert error is None

    def test_item_with_extra_fields_is_valid(self):
        """Test that item with extra fields is valid (extra fields ignored)."""
        from utils.validation import validate_finalize_item

        item = {"id": 1, "tracker_path": "trackers/test.md", "extra_field": "ignored"}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is True
        assert error is None

    def test_item_null_returns_error(self):
        """Test that None item returns error."""
        from utils.validation import validate_finalize_item

        is_valid, error = validate_finalize_item(None)
        assert is_valid is False
        assert error is not None
        assert "must be an object" in error

    def test_item_list_returns_error(self):
        """Test that list item returns error."""
        from utils.validation import validate_finalize_item

        is_valid, error = validate_finalize_item([1, 2, 3])
        assert is_valid is False
        assert error is not None
        assert "must be an object" in error

    def test_item_with_empty_resume_pdf_path_is_valid(self):
        """Test that empty string resume_pdf_path is valid (optional field can be empty)."""
        from utils.validation import validate_finalize_item

        # Note: Empty string is technically a valid string type, though semantically
        # it may not make sense. The validation only checks type, not semantic validity.
        item = {"id": 1, "tracker_path": "trackers/test.md", "resume_pdf_path": ""}
        is_valid, error = validate_finalize_item(item)
        assert is_valid is True
        assert error is None


class TestValidateCareerTailorItems:
    """Tests for career_tailor items parameter validation."""

    def test_valid_single_item(self):
        """Test that batch with single item is valid."""
        from utils.validation import validate_career_tailor_items

        items = [{"tracker_path": "trackers/test.md"}]
        result = validate_career_tailor_items(items)
        assert result == items

    def test_valid_multiple_items(self):
        """Test that batch with multiple items is valid."""
        from utils.validation import validate_career_tailor_items

        items = [
            {"tracker_path": "trackers/test1.md"},
            {"tracker_path": "trackers/test2.md"},
            {"tracker_path": "trackers/test3.md"},
        ]
        result = validate_career_tailor_items(items)
        assert result == items

    def test_valid_100_items(self):
        """Test that batch with exactly 100 items is valid."""
        from utils.validation import validate_career_tailor_items

        items = [{"tracker_path": f"trackers/test{i}.md"} for i in range(100)]
        result = validate_career_tailor_items(items)
        assert result == items

    def test_items_null_raises_error(self):
        """Test that None items raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_items

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_items(None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message.lower()
        assert not error.retryable

    def test_items_empty_array_raises_error(self):
        """Test that empty array raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_items

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_items([])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()
        assert not error.retryable

    def test_items_exceeds_maximum_raises_error(self):
        """Test that batch with 101 items raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_items

        items = [{"tracker_path": f"trackers/test{i}.md"} for i in range(101)]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_items(items)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Batch size too large" in error.message
        assert "101" in error.message
        assert "100" in error.message
        assert not error.retryable

    def test_items_invalid_type_string(self):
        """Test that string items raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_items

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_items("not an array")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "str" in error.message

    def test_items_invalid_type_dict(self):
        """Test that dict items raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_items

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_items({"tracker_path": "test.md"})

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateCareerTailorItem:
    """Tests for individual career_tailor item validation."""

    def test_valid_item_with_tracker_path_only(self):
        """Test that item with only tracker_path is valid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md"}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is True
        assert error is None

    def test_valid_item_with_job_db_id(self):
        """Test that item with tracker_path and job_db_id is valid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "job_db_id": 123}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is True
        assert error is None

    def test_item_missing_tracker_path(self):
        """Test that item without tracker_path is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"job_db_id": 123}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "missing required field 'tracker_path'" in error.lower()

    def test_item_tracker_path_empty_string(self):
        """Test that item with empty tracker_path is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": ""}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "cannot be empty" in error.lower()

    def test_item_tracker_path_whitespace_only(self):
        """Test that item with whitespace-only tracker_path is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "   "}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "cannot be empty" in error.lower()

    def test_item_tracker_path_invalid_type(self):
        """Test that item with non-string tracker_path is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": 123}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "must be a string" in error.lower()
        assert "int" in error

    def test_item_job_db_id_positive_integer(self):
        """Test that positive job_db_id values are valid."""
        from utils.validation import validate_career_tailor_item

        for job_id in [1, 100, 9999]:
            item = {"tracker_path": "trackers/test.md", "job_db_id": job_id}
            is_valid, error = validate_career_tailor_item(item)
            assert is_valid is True
            assert error is None

    def test_item_job_db_id_zero_invalid(self):
        """Test that job_db_id of 0 is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "job_db_id": 0}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "positive integer" in error.lower()
        assert "0" in error

    def test_item_job_db_id_negative_invalid(self):
        """Test that negative job_db_id is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "job_db_id": -1}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "positive integer" in error.lower()

    def test_item_job_db_id_invalid_type_string(self):
        """Test that string job_db_id is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "job_db_id": "123"}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "must be an integer" in error.lower()
        assert "str" in error

    def test_item_job_db_id_invalid_type_float(self):
        """Test that float job_db_id is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "job_db_id": 123.45}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "must be an integer" in error.lower()
        assert "float" in error

    def test_item_job_db_id_invalid_type_boolean(self):
        """Test that boolean job_db_id is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "job_db_id": True}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "must be an integer" in error.lower()

    def test_item_with_unknown_field(self):
        """Test that item with unknown field is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "unknown_field": "value"}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "unknown fields" in error.lower()
        assert "unknown_field" in error

    def test_item_with_multiple_unknown_fields(self):
        """Test that item with multiple unknown fields is invalid."""
        from utils.validation import validate_career_tailor_item

        item = {"tracker_path": "trackers/test.md", "field1": "value1", "field2": "value2"}
        is_valid, error = validate_career_tailor_item(item)
        assert is_valid is False
        assert "unknown fields" in error.lower()
        assert "field1" in error
        assert "field2" in error

    def test_item_not_dict(self):
        """Test that non-dict item is invalid."""
        from utils.validation import validate_career_tailor_item

        is_valid, error = validate_career_tailor_item("not a dict")
        assert is_valid is False
        assert "must be an object" in error.lower()
        assert "str" in error


class TestValidateCareerTailorBatchParameters:
    """Tests for career_tailor batch parameters validation."""

    def test_valid_minimal_request(self):
        """Test validation with only required items parameter."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        result = validate_career_tailor_batch_parameters(items=items)

        assert result[0] == items  # validated_items
        assert result[1] is False  # validated_force (default)
        assert result[2] is None  # full_resume_path
        assert result[3] is None  # resume_template_path
        assert result[4] is None  # applications_dir
        assert result[5] is None  # pdflatex_cmd

    def test_valid_with_all_optional_parameters(self):
        """Test validation with all optional parameters."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        result = validate_career_tailor_batch_parameters(
            items=items,
            force=True,
            full_resume_path="data/resume.tex",
            resume_template_path="templates/resume.tex",
            applications_dir="data/apps",
            pdflatex_cmd="pdflatex",
        )

        assert result[0] == items
        assert result[1] is True
        assert result[2] == "data/resume.tex"
        assert result[3] == "templates/resume.tex"
        assert result[4] == "data/apps"
        assert result[5] == "pdflatex"

    def test_valid_force_false(self):
        """Test validation with force=False."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        result = validate_career_tailor_batch_parameters(items=items, force=False)

        assert result[1] is False

    def test_unknown_parameter_raises_error(self):
        """Test that unknown parameter raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, unknown_param="value")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Unknown input properties" in error.message
        assert "unknown_param" in error.message
        assert not error.retryable

    def test_multiple_unknown_parameters_raises_error(self):
        """Test that multiple unknown parameters are all reported."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, param1="value1", param2="value2")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Unknown input properties" in error.message
        assert "param1" in error.message
        assert "param2" in error.message

    def test_force_invalid_type_raises_error(self):
        """Test that non-boolean force raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, force="true")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "force" in error.message.lower()
        assert "type" in error.message.lower()

    def test_full_resume_path_empty_raises_error(self):
        """Test that empty full_resume_path raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, full_resume_path="")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "full_resume_path" in error.message
        assert "cannot be empty" in error.message.lower()

    def test_full_resume_path_whitespace_raises_error(self):
        """Test that whitespace-only full_resume_path raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, full_resume_path="   ")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "full_resume_path" in error.message
        assert "cannot be empty" in error.message.lower()

    def test_full_resume_path_invalid_type_raises_error(self):
        """Test that non-string full_resume_path raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, full_resume_path=123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "full_resume_path" in error.message
        assert "type" in error.message.lower()

    def test_resume_template_path_empty_raises_error(self):
        """Test that empty resume_template_path raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, resume_template_path="")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "resume_template_path" in error.message
        assert "cannot be empty" in error.message.lower()

    def test_resume_template_path_invalid_type_raises_error(self):
        """Test that non-string resume_template_path raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, resume_template_path=["path"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "resume_template_path" in error.message
        assert "type" in error.message.lower()

    def test_applications_dir_empty_raises_error(self):
        """Test that empty applications_dir raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, applications_dir="")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "applications_dir" in error.message
        assert "cannot be empty" in error.message.lower()

    def test_applications_dir_invalid_type_raises_error(self):
        """Test that non-string applications_dir raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, applications_dir=123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "applications_dir" in error.message
        assert "type" in error.message.lower()

    def test_pdflatex_cmd_empty_raises_error(self):
        """Test that empty pdflatex_cmd raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, pdflatex_cmd="")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "pdflatex_cmd" in error.message
        assert "cannot be empty" in error.message.lower()

    def test_pdflatex_cmd_invalid_type_raises_error(self):
        """Test that non-string pdflatex_cmd raises VALIDATION_ERROR."""
        from utils.validation import validate_career_tailor_batch_parameters

        items = [{"tracker_path": "trackers/test.md"}]

        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=items, pdflatex_cmd=True)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "pdflatex_cmd" in error.message
        assert "type" in error.message.lower()

    def test_items_validation_errors_propagate(self):
        """Test that items validation errors are propagated."""
        from utils.validation import validate_career_tailor_batch_parameters

        # Empty items array
        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=[])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()

        # None items
        with pytest.raises(ToolError) as exc_info:
            validate_career_tailor_batch_parameters(items=None)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message.lower()
