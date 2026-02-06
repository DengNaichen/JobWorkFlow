"""
Main MCP tool handler for bulk_read_new_jobs.

Integrates validation, cursor decoding, database reading, pagination,
and schema mapping to provide a complete read-only batch retrieval tool
for jobs with status='new'.
"""

from typing import Dict, Any

from utils.validation import validate_all_parameters
from utils.cursor import decode_cursor
from db.jobs_reader import get_connection, query_new_jobs
from utils.pagination import paginate_results
from models.job import to_job_schema
from models.errors import ToolError, create_internal_error


def bulk_read_new_jobs(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve jobs with status='new' in configurable batches with cursor-based pagination.
    
    This is the main entry point for the MCP tool. It orchestrates all components:
    1. Validates input parameters (limit, cursor, db_path)
    2. Decodes pagination cursor if provided
    3. Queries database for new jobs with deterministic ordering
    4. Applies pagination logic to compute has_more and next_cursor
    5. Maps database rows to stable output schema
    6. Returns structured response with jobs and pagination metadata
    
    Args:
        args: Dictionary containing optional parameters:
            - limit (int): Batch size (1-1000, default 50)
            - cursor (str): Opaque pagination cursor for next page
            - db_path (str): Database path override (default: data/capture/jobs.db)
    
    Returns:
        Dictionary with structure:
        {
            "jobs": [...],           # List of job records
            "count": int,            # Number of jobs in this page
            "has_more": bool,        # Whether more pages exist
            "next_cursor": str|None  # Cursor for next page, or None if terminal page
        }
        
        On error, returns:
        {
            "error": {
                "code": str,         # Error code (VALIDATION_ERROR, DB_NOT_FOUND, etc.)
                "message": str,      # Human-readable error message
                "retryable": bool    # Whether operation can be retried
            }
        }
    
    Requirements:
        - 1.1: Return up to batch size jobs with status='new'
        - 1.2: Default batch size of 50
        - 6.1-6.6: MCP tool interface compliance
        - 7.1-7.7: Cursor-based pagination support
    """
    try:
        # Step 1: Extract and validate all input parameters
        limit = args.get("limit")
        cursor_str = args.get("cursor")
        db_path = args.get("db_path")
        
        # Validate parameters (raises ToolError on invalid input)
        validated_limit, validated_cursor, validated_db_path = validate_all_parameters(
            limit=limit,
            cursor=cursor_str,
            db_path=db_path
        )
        
        # Step 2: Decode cursor if provided
        # Returns None for first page, or (captured_at, id) tuple for subsequent pages
        cursor_state = decode_cursor(validated_cursor)
        
        # Step 3: Query database for new jobs
        # Uses context manager to ensure connection is always closed
        with get_connection(validated_db_path) as conn:
            # Query limit+1 rows to determine if more pages exist
            rows = query_new_jobs(
                conn=conn,
                limit=validated_limit,
                cursor=cursor_state
            )
        
        # Step 4: Apply pagination logic
        # Returns (page, has_more, next_cursor)
        page, has_more, next_cursor = paginate_results(rows, validated_limit)
        
        # Step 5: Map database rows to stable output schema
        # Ensures only fixed fields are included, no arbitrary columns
        jobs = [to_job_schema(row) for row in page]
        
        # Step 6: Build and return response
        return {
            "jobs": jobs,
            "count": len(jobs),
            "has_more": has_more,
            "next_cursor": next_cursor
        }
    
    except ToolError as e:
        # Known tool errors with structured error information
        # These are already sanitized and formatted correctly
        return e.to_dict()
    
    except Exception as e:
        # Unexpected errors - wrap in INTERNAL_ERROR
        # Sanitize to avoid exposing sensitive system details
        internal_error = create_internal_error(
            message=str(e),
            original_error=e
        )
        return internal_error.to_dict()
