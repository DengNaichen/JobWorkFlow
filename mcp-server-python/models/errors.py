"""
Error model for bulk_read_new_jobs MCP tool.

Provides structured error codes and sanitized error messages.
"""

from enum import Enum
from typing import Optional
import re


class ErrorCode(str, Enum):
    """Structured error codes for the MCP tool."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    DB_NOT_FOUND = "DB_NOT_FOUND"
    DB_ERROR = "DB_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ToolError(Exception):
    """Base exception for tool errors with structured error information."""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        retryable: bool = False,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize a tool error.
        
        Args:
            code: The error code
            message: Human-readable error message
            retryable: Whether the operation can be retried
            original_error: The original exception if this wraps another error
        """
        self.code = code
        self.message = message
        self.retryable = retryable
        self.original_error = original_error
        super().__init__(message)
    
    def to_dict(self) -> dict:
        """Convert error to dictionary format for MCP response."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "retryable": self.retryable
            }
        }


def sanitize_path(path: str) -> str:
    """
    Sanitize file paths to avoid exposing sensitive system details.
    
    Returns only the basename for absolute paths, keeps relative paths.
    
    Args:
        path: The file path to sanitize
        
    Returns:
        Sanitized path string
    """
    import os
    # If it's an absolute path, return only the basename
    if os.path.isabs(path):
        return os.path.basename(path)
    return path


def sanitize_sql_error(error_msg: str) -> str:
    """
    Sanitize SQL error messages to remove sensitive details.
    
    Removes SQL fragments and keeps only actionable information.
    
    Args:
        error_msg: The original error message
        
    Returns:
        Sanitized error message
    """
    # Remove SQL statements (anything between quotes or after "SQL:")
    sanitized = re.sub(r'SQL:.*', '', error_msg, flags=re.IGNORECASE)
    sanitized = re.sub(r'"[^"]*SELECT[^"]*"', '[SQL query]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"'[^']*SELECT[^']*'", '[SQL query]', sanitized, flags=re.IGNORECASE)
    
    # Remove unquoted SQL statements (SELECT, INSERT, UPDATE, DELETE followed by anything)
    sanitized = re.sub(r'\b(SELECT|INSERT|UPDATE|DELETE)\b.*', '[SQL query]', sanitized, flags=re.IGNORECASE)
    
    # Remove absolute paths
    sanitized = re.sub(r'/[^\s]+/', '[path]/', sanitized)
    
    return sanitized.strip()


def sanitize_stack_trace(error_msg: str) -> str:
    """
    Remove stack traces from error messages.
    
    Args:
        error_msg: The original error message
        
    Returns:
        Error message without stack trace
    """
    # Take only the first line (usually the most relevant)
    lines = error_msg.split('\n')
    if lines:
        return lines[0].strip()
    return error_msg


def create_validation_error(message: str) -> ToolError:
    """
    Create a validation error.
    
    Args:
        message: Description of the validation failure
        
    Returns:
        ToolError with VALIDATION_ERROR code
    """
    return ToolError(
        code=ErrorCode.VALIDATION_ERROR,
        message=message,
        retryable=False
    )


def create_db_not_found_error(db_path: str) -> ToolError:
    """
    Create a database not found error.
    
    Args:
        db_path: The database path that was not found
        
    Returns:
        ToolError with DB_NOT_FOUND code
    """
    sanitized_path = sanitize_path(db_path)
    return ToolError(
        code=ErrorCode.DB_NOT_FOUND,
        message=f"Database not found: {sanitized_path}",
        retryable=False
    )


def create_file_not_found_error(file_path: str, file_type: str = "File") -> ToolError:
    """
    Create a file not found error.
    
    Args:
        file_path: The file path that was not found
        file_type: Type of file (e.g., "Tracker file", "Resume file")
        
    Returns:
        ToolError with FILE_NOT_FOUND code
    """
    sanitized_path = sanitize_path(file_path)
    return ToolError(
        code=ErrorCode.FILE_NOT_FOUND,
        message=f"{file_type} not found: {sanitized_path}",
        retryable=False
    )


def create_db_error(message: str, retryable: bool = False, original_error: Optional[Exception] = None) -> ToolError:
    """
    Create a database error.
    
    Args:
        message: Description of the database error
        retryable: Whether the operation can be retried
        original_error: The original exception
        
    Returns:
        ToolError with DB_ERROR code
    """
    sanitized_message = sanitize_sql_error(message)
    sanitized_message = sanitize_stack_trace(sanitized_message)
    
    return ToolError(
        code=ErrorCode.DB_ERROR,
        message=f"Database error: {sanitized_message}",
        retryable=retryable,
        original_error=original_error
    )


def create_internal_error(message: str, original_error: Optional[Exception] = None) -> ToolError:
    """
    Create an internal error for unexpected exceptions.
    
    Args:
        message: Description of the internal error
        original_error: The original exception
        
    Returns:
        ToolError with INTERNAL_ERROR code
    """
    sanitized_message = sanitize_stack_trace(message)
    
    return ToolError(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"Internal error: {sanitized_message}",
        retryable=True,
        original_error=original_error
    )
