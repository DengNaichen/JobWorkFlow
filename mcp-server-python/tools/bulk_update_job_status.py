"""
Main MCP tool handler for bulk_update_job_status.

Integrates validation, database writing, transaction management, and error handling
to provide a complete write-only batch status update tool for job records.
"""

from typing import Dict, Any, List, Optional

from utils.validation import (
    validate_batch_size,
    validate_unique_job_ids,
    validate_job_id,
    validate_status,
    get_current_utc_timestamp,
)
from db.jobs_writer import JobsWriter
from models.errors import ToolError, create_validation_error, create_internal_error


def validate_request_shape(args: Dict[str, Any]) -> None:
    """
    Validate the top-level request structure.

    Ensures that the 'updates' parameter is present and is a list.

    Args:
        args: The request arguments dictionary

    Raises:
        ToolError: If request structure is invalid
    """
    # Check that 'updates' key exists
    if "updates" not in args:
        raise create_validation_error("Missing required parameter: 'updates'")

    # Check that 'updates' is a list
    updates = args["updates"]
    if not isinstance(updates, list):
        raise create_validation_error(
            f"Invalid updates type: expected list, got {type(updates).__name__}"
        )


def validate_update_item(update: Any, index: int) -> Optional[str]:
    """
    Validate a single update item structure and values.

    Returns None if valid, or an error message if invalid.

    Args:
        update: The update item to validate
        index: The index of this item in the batch (for error messages)

    Returns:
        None if valid, error message string if invalid
    """
    # Check that update is a dict
    if not isinstance(update, dict):
        return f"Update item at index {index} is not an object"

    # Check that 'id' key exists
    if "id" not in update:
        return "Missing required field: 'id'"

    # Check that 'status' key exists
    if "status" not in update:
        return "Missing required field: 'status'"

    # Validate job ID
    try:
        validate_job_id(update["id"])
    except ToolError as e:
        return e.message

    # Validate status
    try:
        validate_status(update["status"])
    except ToolError as e:
        return e.message

    return None


def collect_item_failures(updates: List[Dict[str, Any]], writer: JobsWriter) -> Dict[Any, str]:
    """
    Collect all per-item validation and existence failures.

    This performs semantic validation on each update item and checks
    that all referenced job IDs exist in the database.

    Args:
        updates: List of update items to validate
        writer: JobsWriter instance for database queries

    Returns:
        Dictionary mapping job_id (or item identifier) to error message for failed items.
        Empty dict if all items are valid.
    """
    failures = {}
    valid_job_ids = []

    # Validate each update item
    for index, update in enumerate(updates):
        error = validate_update_item(update, index)
        if error:
            # Use the job ID if available, otherwise use index-based key
            job_id = update.get("id", f"item_{index}")
            failures[job_id] = error
        else:
            # Collect valid job IDs for existence check
            valid_job_ids.append(update["id"])

    # If there are validation failures, don't check existence
    if failures:
        return failures

    # Check job existence for all valid items
    missing_ids = writer.validate_jobs_exist(valid_job_ids)

    # Add existence failures
    for job_id in missing_ids:
        failures[job_id] = f"Job ID {job_id} does not exist"

    return failures


def build_success_response(updates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a success response for a batch update.

    Args:
        updates: List of update items that were successfully processed

    Returns:
        Success response dictionary with updated_count, failed_count, and results
    """
    results = []
    for update in updates:
        results.append({"id": update["id"], "success": True})

    return {"updated_count": len(updates), "failed_count": 0, "results": results}


def build_failure_response(
    updates: List[Dict[str, Any]], failures: Dict[Any, str]
) -> Dict[str, Any]:
    """
    Build a failure response for a batch update with per-item errors.

    Args:
        updates: List of update items that were attempted
        failures: Dictionary mapping job_id (or item identifier) to error message

    Returns:
        Failure response dictionary with updated_count=0, failed_count, and results
    """
    results = []
    for index, update in enumerate(updates):
        job_id = update.get("id", f"item_{index}")

        # Check if this item has a failure (by job_id or by item_index key)
        error_msg = failures.get(job_id) or failures.get(f"item_{index}")

        if error_msg:
            results.append({"id": job_id, "success": False, "error": error_msg})
        else:
            # This shouldn't happen, but handle gracefully
            results.append({"id": job_id, "success": False, "error": "Unknown error"})

    return {"updated_count": 0, "failed_count": len(failures), "results": results}


def bulk_update_job_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update multiple job statuses in a single atomic transaction.

    This is the main entry point for the MCP tool. It orchestrates all components:
    1. Validates request structure and batch size
    2. Validates for duplicate job IDs
    3. Opens database connection and begins transaction
    4. Performs schema preflight check (updated_at column must exist)
    5. Validates per-item semantic rules and job existence
    6. If any validation fails: rollback and return detailed failure results
    7. If all valid: execute all updates with same timestamp and commit
    8. Returns structured response with success/failure details per job

    Args:
        args: Dictionary containing parameters:
            - updates (list): Array of update items, each with:
                - id (int): Job ID to update (positive integer)
                - status (str): Target status value (must be in allowed set)
            - db_path (str, optional): Database path override

    Returns:
        Dictionary with structure (success case):
        {
            "updated_count": int,    # Number of jobs successfully updated
            "failed_count": 0,       # Number of failed updates
            "results": [             # Per-job results
                {
                    "id": int,
                    "success": true
                },
                ...
            ]
        }

        Dictionary with structure (validation failure case):
        {
            "updated_count": 0,
            "failed_count": int,
            "results": [
                {
                    "id": int,
                    "success": false,
                    "error": str
                },
                ...
            ]
        }

        On system error, returns:
        {
            "error": {
                "code": str,         # Error code (VALIDATION_ERROR, DB_NOT_FOUND, etc.)
                "message": str,      # Human-readable error message
                "retryable": bool    # Whether operation can be retried
            }
        }

    Requirements:
        - 1.1-1.4: Batch status updates with size validation
        - 2.1-2.5: Status validation
        - 3.1-3.6: Job existence and ID validation
        - 4.1-4.5: Atomic transaction semantics
        - 5.1-5.5: Idempotent updates
        - 6.1-6.5: Timestamp tracking
        - 7.1-7.7: Database operations
        - 8.1-8.5: Structured response format
        - 9.1-9.7: Error handling
        - 10.1-10.6: MCP tool interface
        - 11.1-11.5: Write-only operations
    """
    try:
        # Step 1: Validate request structure
        validate_request_shape(args)

        # Step 2: Extract parameters
        updates = args["updates"]
        db_path = args.get("db_path")

        # Step 3: Validate batch size
        validate_batch_size(updates)

        # Step 4: Handle empty batch (valid case)
        if not updates or len(updates) == 0:
            return {"updated_count": 0, "failed_count": 0, "results": []}

        # Step 5: Validate unique job IDs
        validate_unique_job_ids(updates)

        # Step 6: Execute updates in transaction
        with JobsWriter(db_path) as writer:
            # Step 6a: Schema preflight check
            writer.ensure_updated_at_column()

            # Step 6b: Collect per-item validation and existence failures
            failures = collect_item_failures(updates, writer)

            # Step 6c: If any failures, rollback and return failure response
            if failures:
                writer.rollback()
                return build_failure_response(updates, failures)

            # Step 6d: Generate single timestamp for entire batch
            timestamp = get_current_utc_timestamp()

            # Step 6e: Execute all updates
            for update in updates:
                writer.update_job_status(
                    job_id=update["id"], status=update["status"], timestamp=timestamp
                )

            # Step 6f: Commit transaction
            writer.commit()

            # Step 7: Return success response
            return build_success_response(updates)

    except ToolError as e:
        # Known tool errors with structured error information
        # These are already sanitized and formatted correctly
        return e.to_dict()

    except Exception as e:
        # Unexpected errors - wrap in INTERNAL_ERROR
        # Sanitize to avoid exposing sensitive system details
        internal_error = create_internal_error(message=str(e), original_error=e)
        return internal_error.to_dict()
