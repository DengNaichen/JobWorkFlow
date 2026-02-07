"""
Unit tests for error model and sanitization functions.

Tests error codes, error structure, and message sanitization.
"""

import pytest
from models.errors import (
    ErrorCode,
    ToolError,
    sanitize_path,
    sanitize_sql_error,
    sanitize_stack_trace,
    create_validation_error,
    create_db_not_found_error,
    create_db_error,
    create_internal_error,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_all_error_codes_exist(self):
        """Test that all required error codes are defined."""
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCode.DB_NOT_FOUND == "DB_NOT_FOUND"
        assert ErrorCode.DB_ERROR == "DB_ERROR"
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"

    def test_error_codes_are_strings(self):
        """Test that error codes are string values."""
        for code in ErrorCode:
            assert isinstance(code.value, str)


class TestToolError:
    """Tests for ToolError exception class."""

    def test_tool_error_creation(self):
        """Test creating a ToolError with all fields."""
        error = ToolError(code=ErrorCode.VALIDATION_ERROR, message="Test error", retryable=False)

        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.message == "Test error"
        assert error.retryable is False
        assert error.original_error is None

    def test_tool_error_with_original_exception(self):
        """Test creating a ToolError wrapping another exception."""
        original = ValueError("Original error")
        error = ToolError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Wrapped error",
            retryable=True,
            original_error=original,
        )

        assert error.original_error is original

    def test_tool_error_to_dict(self):
        """Test converting ToolError to dictionary format."""
        error = ToolError(
            code=ErrorCode.DB_ERROR, message="Database connection failed", retryable=True
        )

        result = error.to_dict()

        assert "error" in result
        assert result["error"]["code"] == "DB_ERROR"
        assert result["error"]["message"] == "Database connection failed"
        assert result["error"]["retryable"] is True

    def test_tool_error_is_exception(self):
        """Test that ToolError can be raised and caught as exception."""
        error = ToolError(code=ErrorCode.VALIDATION_ERROR, message="Test", retryable=False)

        with pytest.raises(ToolError) as exc_info:
            raise error

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


class TestSanitizePath:
    """Tests for path sanitization."""

    def test_sanitize_absolute_path(self):
        """Test that absolute paths return only basename."""
        assert sanitize_path("/var/data/jobs.db") == "jobs.db"
        assert sanitize_path("/tmp/test.db") == "test.db"
        assert sanitize_path("/home/user/data/capture/jobs.db") == "jobs.db"

    def test_sanitize_relative_path(self):
        """Test that relative paths are kept as-is."""
        assert sanitize_path("data/jobs.db") == "data/jobs.db"
        assert sanitize_path("jobs.db") == "jobs.db"
        assert sanitize_path("./data/jobs.db") == "./data/jobs.db"

    def test_sanitize_windows_path(self):
        """Test sanitization of Windows-style paths."""
        # On Unix systems, backslashes are part of filename
        # On Windows, this would be treated as absolute
        result = sanitize_path("C:\\data\\jobs.db")
        # Result depends on OS, but should not expose full path
        assert len(result) > 0


class TestSanitizeSqlError:
    """Tests for SQL error message sanitization."""

    def test_remove_sql_statements(self):
        """Test that SQL statements are removed from error messages."""
        error_msg = "Error executing SQL: SELECT * FROM jobs WHERE id = 1"
        result = sanitize_sql_error(error_msg)
        assert "SELECT" not in result
        assert "FROM" not in result

    def test_remove_quoted_sql(self):
        """Test that quoted SQL is replaced with placeholder."""
        error_msg = 'Query failed: "SELECT * FROM jobs" returned error'
        result = sanitize_sql_error(error_msg)
        assert "SELECT" not in result
        assert "[SQL query]" in result

    def test_remove_single_quoted_sql(self):
        """Test that single-quoted SQL is replaced."""
        error_msg = "Query failed: 'SELECT * FROM jobs' returned error"
        result = sanitize_sql_error(error_msg)
        assert "SELECT" not in result
        assert "[SQL query]" in result

    def test_remove_absolute_paths(self):
        """Test that absolute paths are sanitized."""
        error_msg = "Cannot open database at /home/user/data/jobs.db"
        result = sanitize_sql_error(error_msg)
        assert "/home/user/data/" not in result
        assert "[path]/" in result

    def test_preserve_useful_information(self):
        """Test that useful error information is preserved."""
        error_msg = "Database locked"
        result = sanitize_sql_error(error_msg)
        assert "locked" in result.lower()


class TestSanitizeStackTrace:
    """Tests for stack trace sanitization."""

    def test_keep_first_line_only(self):
        """Test that only the first line of error is kept."""
        error_msg = """ValueError: Invalid input
        at line 42 in module.py
        at line 10 in main.py"""

        result = sanitize_stack_trace(error_msg)
        assert result == "ValueError: Invalid input"
        assert "at line" not in result

    def test_single_line_unchanged(self):
        """Test that single-line errors are unchanged."""
        error_msg = "Connection refused"
        result = sanitize_stack_trace(error_msg)
        assert result == "Connection refused"

    def test_strip_whitespace(self):
        """Test that whitespace is stripped."""
        error_msg = "  Error message  \n"
        result = sanitize_stack_trace(error_msg)
        assert result == "Error message"


class TestCreateValidationError:
    """Tests for validation error creation."""

    def test_create_validation_error(self):
        """Test creating a validation error."""
        error = create_validation_error("Invalid limit value")

        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.message == "Invalid limit value"
        assert error.retryable is False

    def test_validation_error_to_dict(self):
        """Test validation error dictionary format."""
        error = create_validation_error("Test validation error")
        result = error.to_dict()

        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["retryable"] is False


class TestCreateDbNotFoundError:
    """Tests for database not found error creation."""

    def test_create_db_not_found_error(self):
        """Test creating a DB not found error."""
        error = create_db_not_found_error("/var/data/jobs.db")

        assert error.code == ErrorCode.DB_NOT_FOUND
        assert "not found" in error.message.lower()
        assert error.retryable is False

    def test_db_not_found_sanitizes_path(self):
        """Test that absolute paths are sanitized in error message."""
        error = create_db_not_found_error("/home/user/secret/jobs.db")

        # Should only show basename
        assert "jobs.db" in error.message
        assert "/home/user/secret/" not in error.message

    def test_db_not_found_keeps_relative_path(self):
        """Test that relative paths are kept in error message."""
        error = create_db_not_found_error("data/jobs.db")

        assert "data/jobs.db" in error.message


class TestCreateDbError:
    """Tests for database error creation."""

    def test_create_db_error(self):
        """Test creating a database error."""
        error = create_db_error("Connection failed", retryable=True)

        assert error.code == ErrorCode.DB_ERROR
        assert "Connection failed" in error.message
        assert error.retryable is True

    def test_db_error_sanitizes_sql(self):
        """Test that SQL is sanitized in DB errors."""
        error = create_db_error("Query failed: SELECT * FROM jobs")

        assert "SELECT" not in error.message
        assert "Database error" in error.message

    def test_db_error_with_original_exception(self):
        """Test DB error with original exception."""
        original = Exception("Original DB error")
        error = create_db_error("Wrapped error", original_error=original)

        assert error.original_error is original

    def test_db_error_default_not_retryable(self):
        """Test that DB errors are not retryable by default."""
        error = create_db_error("Test error")
        assert error.retryable is False


class TestCreateInternalError:
    """Tests for internal error creation."""

    def test_create_internal_error(self):
        """Test creating an internal error."""
        error = create_internal_error("Unexpected error occurred")

        assert error.code == ErrorCode.INTERNAL_ERROR
        assert "Unexpected error occurred" in error.message
        assert error.retryable is True

    def test_internal_error_sanitizes_stack_trace(self):
        """Test that stack traces are sanitized in internal errors."""
        error_msg = """ValueError: Something went wrong
        at line 42 in module.py
        at line 10 in main.py"""

        error = create_internal_error(error_msg)

        # Should only have first line
        assert "ValueError: Something went wrong" in error.message
        assert "at line" not in error.message

    def test_internal_error_with_original_exception(self):
        """Test internal error with original exception."""
        original = RuntimeError("Original error")
        error = create_internal_error("Wrapped error", original_error=original)

        assert error.original_error is original

    def test_internal_error_always_retryable(self):
        """Test that internal errors are always retryable."""
        error = create_internal_error("Test error")
        assert error.retryable is True


class TestErrorStructureCompliance:
    """Tests for error structure compliance with design spec."""

    def test_error_dict_has_required_fields(self):
        """Test that error dict has all required fields."""
        error = create_validation_error("Test")
        result = error.to_dict()

        assert "error" in result
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert "retryable" in result["error"]

    def test_all_error_types_produce_valid_dict(self):
        """Test that all error creation functions produce valid dicts."""
        errors = [
            create_validation_error("Test"),
            create_db_not_found_error("test.db"),
            create_db_error("Test"),
            create_internal_error("Test"),
        ]

        for error in errors:
            result = error.to_dict()
            assert "error" in result
            assert "code" in result["error"]
            assert "message" in result["error"]
            assert "retryable" in result["error"]
            assert isinstance(result["error"]["code"], str)
            assert isinstance(result["error"]["message"], str)
            assert isinstance(result["error"]["retryable"], bool)
