"""
Input validation utilities for bulk_read_new_jobs MCP tool.

Validates limit, db_path, and cursor parameters according to requirements.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple

from models.errors import create_validation_error
from models.status import JobDbStatus, JobTrackerStatus

# Constants for validation
DEFAULT_LIMIT = 50
MIN_LIMIT = 1
MAX_LIMIT = 1000

# Constants for initialize_shortlist_trackers validation
INITIALIZE_DEFAULT_LIMIT = 50
INITIALIZE_MIN_LIMIT = 1
INITIALIZE_MAX_LIMIT = 200


def validate_limit(limit: Optional[int]) -> int:
    """
    Validate the limit parameter.

    Args:
        limit: The requested batch size (None for default)

    Returns:
        Validated limit value

    Raises:
        ToolError: If limit is invalid
    """
    # Use default if not provided
    if limit is None:
        return DEFAULT_LIMIT

    # Check type (bool is a subclass of int in Python, reject explicitly)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise create_validation_error(
            f"Invalid limit type: expected integer, got {type(limit).__name__}"
        )

    # Check range
    if limit < MIN_LIMIT:
        raise create_validation_error(f"Invalid limit: {limit} is below minimum of {MIN_LIMIT}")

    if limit > MAX_LIMIT:
        raise create_validation_error(f"Invalid limit: {limit} exceeds maximum of {MAX_LIMIT}")

    return limit


def validate_db_path(db_path: Optional[str]) -> Optional[str]:
    """
    Validate the db_path parameter.

    Args:
        db_path: The database path (None for default)

    Returns:
        Validated db_path or None for default

    Raises:
        ToolError: If db_path is invalid
    """
    # None is valid (means use default)
    if db_path is None:
        return None

    # Check type
    if not isinstance(db_path, str):
        raise create_validation_error(
            f"Invalid db_path type: expected string, got {type(db_path).__name__}"
        )

    # Check not empty
    if not db_path.strip():
        raise create_validation_error("Invalid db_path: cannot be empty")

    return db_path


def validate_cursor(cursor: Optional[str]) -> Optional[str]:
    """
    Validate the cursor parameter format.

    This performs basic format validation. Full decoding is done by cursor.py.

    Args:
        cursor: The pagination cursor (None for first page)

    Returns:
        Validated cursor or None for first page

    Raises:
        ToolError: If cursor format is invalid
    """
    # None is valid (means first page)
    if cursor is None:
        return None

    # Check type
    if not isinstance(cursor, str):
        raise create_validation_error(
            f"Invalid cursor type: expected string, got {type(cursor).__name__}"
        )

    # Check not empty
    if not cursor.strip():
        raise create_validation_error("Invalid cursor: cannot be empty")

    # Basic format check - cursor should be base64-like
    # (alphanumeric, +, /, =)
    import re

    if not re.match(r"^[A-Za-z0-9+/=]+$", cursor):
        raise create_validation_error("Invalid cursor format: must be a valid base64 string")

    return cursor


def validate_all_parameters(
    limit: Optional[int] = None, cursor: Optional[str] = None, db_path: Optional[str] = None
) -> Tuple[int, Optional[str], Optional[str]]:
    """
    Validate all input parameters at once.

    Args:
        limit: The requested batch size
        cursor: The pagination cursor
        db_path: The database path

    Returns:
        Tuple of (validated_limit, validated_cursor, validated_db_path)

    Raises:
        ToolError: If any parameter is invalid
    """
    validated_limit = validate_limit(limit)
    validated_cursor = validate_cursor(cursor)
    validated_db_path = validate_db_path(db_path)

    return validated_limit, validated_cursor, validated_db_path


def validate_status(status) -> str:
    """
    Validate the status parameter for job status updates.

    Args:
        status: The status value to validate

    Returns:
        Validated status string

    Raises:
        ToolError: If status is invalid
    """
    # Check for null/None
    if status is None:
        raise create_validation_error("Invalid status: cannot be null")

    # Check type
    if not isinstance(status, str):
        raise create_validation_error(
            f"Invalid status type: expected string, got {type(status).__name__}"
        )

    # Check for empty string
    if not status:
        raise create_validation_error("Invalid status: cannot be empty")

    # Check for leading/trailing whitespace
    if status != status.strip():
        raise create_validation_error(
            f"Invalid status: '{status}' contains leading or trailing whitespace"
        )

    # Check against allowed statuses (case-sensitive)
    try:
        JobDbStatus(status)
    except ValueError:
        allowed = ", ".join(sorted(s.value for s in JobDbStatus))
        raise create_validation_error(
            f"Invalid status value: '{status}'. Allowed values are: {allowed}"
        )

    return status


def validate_job_id(job_id) -> int:
    """
    Validate the job_id parameter for job updates.

    Args:
        job_id: The job ID value to validate

    Returns:
        Validated job ID as integer

    Raises:
        ToolError: If job_id is invalid
    """
    # Check for null/None
    if job_id is None:
        raise create_validation_error("Invalid job ID: cannot be null")

    # Check type (bool is a subclass of int in Python, reject explicitly)
    if isinstance(job_id, bool) or not isinstance(job_id, int):
        raise create_validation_error(
            f"Invalid job ID type: expected integer, got {type(job_id).__name__}"
        )

    # Check for positive integer (>= 1)
    if job_id < 1:
        raise create_validation_error(f"Invalid job ID: {job_id} must be a positive integer (>= 1)")

    return job_id


def validate_batch_size(updates: list) -> None:
    """
    Validate the batch size for bulk update operations.

    Empty batches (0 updates) are valid. Batches of 1-100 updates are valid.
    Batches with more than 100 updates are rejected.

    Args:
        updates: The list of updates to validate

    Raises:
        ToolError: If batch size exceeds 100
    """
    # Empty batch is valid - return early
    if not updates or len(updates) == 0:
        return

    # Check batch size limit
    if len(updates) > 100:
        raise create_validation_error(
            f"Batch size too large: {len(updates)} updates exceeds maximum of 100"
        )


def validate_unique_job_ids(updates: list) -> None:
    """
    Validate that all job IDs in the batch are unique.

    Duplicate job IDs within one batch are not allowed and will cause
    the entire request to be rejected with a VALIDATION_ERROR.

    Args:
        updates: The list of update items to validate

    Raises:
        ToolError: If duplicate job IDs are found
    """
    # Empty batch is valid - return early
    if not updates or len(updates) == 0:
        return

    # Collect all job IDs
    job_ids = []
    for update in updates:
        # Extract job ID if present (may be missing or invalid)
        if isinstance(update, dict) and "id" in update:
            job_ids.append(update["id"])

    # Find duplicates
    seen = set()
    duplicates = set()
    for job_id in job_ids:
        if job_id in seen:
            duplicates.add(job_id)
        else:
            seen.add(job_id)

    # Raise error if duplicates found
    if duplicates:
        duplicate_list = ", ".join(sorted(str(dup_id) for dup_id in duplicates))
        raise create_validation_error(f"Duplicate job IDs found in batch: {duplicate_list}")


def get_current_utc_timestamp() -> str:
    """
    Generate a UTC timestamp in ISO 8601 format with millisecond precision.

    Returns a timestamp string in the format: YYYY-MM-DDTHH:MM:SS.mmmZ
    Example: 2026-02-04T03:47:36.966Z

    This timestamp is used for the updated_at field in job status updates.
    All jobs in a batch update should receive the same timestamp.

    Returns:
        ISO 8601 UTC timestamp string with millisecond precision and Z suffix

    Requirements: 6.1, 6.3
    """
    now = datetime.now(timezone.utc)
    # Format with millisecond precision and replace +00:00 with Z
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ============================================================================
# Validators for initialize_shortlist_trackers tool
# ============================================================================


def validate_initialize_limit(limit: Optional[int]) -> int:
    """
    Validate the limit parameter for initialize_shortlist_trackers.

    Args:
        limit: The requested number of shortlist jobs to process (None for default)

    Returns:
        Validated limit value (default: 50, range: 1-200)

    Raises:
        ToolError: If limit is invalid

    Requirements: 1.3, 1.4, 1.5
    """
    # Use default if not provided
    if limit is None:
        return INITIALIZE_DEFAULT_LIMIT

    # Check type (bool is a subclass of int in Python, reject explicitly)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise create_validation_error(
            f"Invalid limit type: expected integer, got {type(limit).__name__}"
        )

    # Check range
    if limit < INITIALIZE_MIN_LIMIT:
        raise create_validation_error(
            f"Invalid limit: {limit} is below minimum of {INITIALIZE_MIN_LIMIT}"
        )

    if limit > INITIALIZE_MAX_LIMIT:
        raise create_validation_error(
            f"Invalid limit: {limit} exceeds maximum of {INITIALIZE_MAX_LIMIT}"
        )

    return limit


def validate_trackers_dir(trackers_dir: Optional[str]) -> Optional[str]:
    """
    Validate the trackers_dir parameter for initialize_shortlist_trackers.

    Args:
        trackers_dir: The trackers directory path (None for default)

    Returns:
        Validated trackers_dir or None for default

    Raises:
        ToolError: If trackers_dir is invalid

    Requirements: 9.1
    """
    # None is valid (means use default)
    if trackers_dir is None:
        return None

    # Check type
    if not isinstance(trackers_dir, str):
        raise create_validation_error(
            f"Invalid trackers_dir type: expected string, got {type(trackers_dir).__name__}"
        )

    # Check not empty
    if not trackers_dir.strip():
        raise create_validation_error("Invalid trackers_dir: cannot be empty")

    return trackers_dir


def validate_force(force: Optional[bool]) -> bool:
    """
    Validate the force parameter for initialize_shortlist_trackers.

    Args:
        force: Whether to overwrite existing tracker files (None for default)

    Returns:
        Validated force value (default: False)

    Raises:
        ToolError: If force is invalid

    Requirements: 9.1
    """
    # Use default if not provided
    if force is None:
        return False

    # Check type
    if not isinstance(force, bool):
        raise create_validation_error(
            f"Invalid force type: expected boolean, got {type(force).__name__}"
        )

    return force


def validate_dry_run(dry_run: Optional[bool]) -> bool:
    """
    Validate the dry_run parameter for initialize_shortlist_trackers.

    Args:
        dry_run: Whether to compute outcomes without writing files (None for default)

    Returns:
        Validated dry_run value (default: False)

    Raises:
        ToolError: If dry_run is invalid

    Requirements: 9.1
    """
    # Use default if not provided
    if dry_run is None:
        return False

    # Check type
    if not isinstance(dry_run, bool):
        raise create_validation_error(
            f"Invalid dry_run type: expected boolean, got {type(dry_run).__name__}"
        )

    return dry_run


def validate_initialize_shortlist_trackers_parameters(
    limit: Optional[int] = None,
    db_path: Optional[str] = None,
    trackers_dir: Optional[str] = None,
    force: Optional[bool] = None,
    dry_run: Optional[bool] = None,
) -> Tuple[int, Optional[str], Optional[str], bool, bool]:
    """
    Validate all input parameters for initialize_shortlist_trackers at once.

    Args:
        limit: The requested number of shortlist jobs to process
        db_path: The database path
        trackers_dir: The trackers directory path
        force: Whether to overwrite existing tracker files
        dry_run: Whether to compute outcomes without writing files

    Returns:
        Tuple of (validated_limit, validated_db_path, validated_trackers_dir,
                  validated_force, validated_dry_run)

    Raises:
        ToolError: If any parameter is invalid

    Requirements: 8.1, 9.1, 9.2
    """
    validated_limit = validate_initialize_limit(limit)
    validated_db_path = validate_db_path(db_path)
    validated_trackers_dir = validate_trackers_dir(trackers_dir)
    validated_force = validate_force(force)
    validated_dry_run = validate_dry_run(dry_run)

    return (
        validated_limit,
        validated_db_path,
        validated_trackers_dir,
        validated_force,
        validated_dry_run,
    )


# ============================================================================
# Validators for update_tracker_status tool
# ============================================================================


def validate_tracker_path(tracker_path) -> str:
    """
    Validate the tracker_path parameter for update_tracker_status.

    Args:
        tracker_path: The tracker file path to validate

    Returns:
        Validated tracker_path string

    Raises:
        ToolError: If tracker_path is invalid

    Requirements: 1.1, 1.6
    """
    # Check for null/None
    if tracker_path is None:
        raise create_validation_error("Invalid tracker_path: cannot be null")

    # Check type
    if not isinstance(tracker_path, str):
        raise create_validation_error(
            f"Invalid tracker_path type: expected string, got {type(tracker_path).__name__}"
        )

    # Check for empty string
    if not tracker_path:
        raise create_validation_error("Invalid tracker_path: cannot be empty")

    # Check for leading/trailing whitespace
    if tracker_path != tracker_path.strip():
        raise create_validation_error(
            "Invalid tracker_path: contains leading or trailing whitespace"
        )

    return tracker_path


def validate_tracker_status(target_status) -> str:
    """
    Validate the target_status parameter for update_tracker_status.

    Enforces canonical tracker status vocabulary with case-sensitive matching.

    Args:
        target_status: The target status value to validate

    Returns:
        Validated target_status string

    Raises:
        ToolError: If target_status is invalid

    Requirements: 1.2, 3.1, 3.2, 3.3, 3.4
    """
    # Check for null/None
    if target_status is None:
        raise create_validation_error("Invalid target_status: cannot be null")

    # Check type
    if not isinstance(target_status, str):
        raise create_validation_error(
            f"Invalid target_status type: expected string, got {type(target_status).__name__}"
        )

    # Check for empty string
    if not target_status:
        raise create_validation_error("Invalid target_status: cannot be empty")

    # Check for leading/trailing whitespace (Requirement 3.4)
    if target_status != target_status.strip():
        raise create_validation_error(
            f"Invalid target_status: '{target_status}' contains leading or trailing whitespace"
        )

    # Check against allowed tracker statuses (case-sensitive, Requirement 3.3)
    try:
        JobTrackerStatus(target_status)
    except ValueError:
        allowed_list = ", ".join(
            f"'{s.value}'" for s in sorted(JobTrackerStatus, key=lambda s: s.value)
        )
        raise create_validation_error(
            f"Invalid target_status value: '{target_status}'. Allowed values are: {allowed_list}"
        )

    return target_status


def validate_update_tracker_status_parameters(
    tracker_path,
    target_status,
    dry_run: Optional[bool] = None,
    force: Optional[bool] = None,
    **kwargs,
) -> Tuple[str, str, bool, bool]:
    """
    Validate all input parameters for update_tracker_status at once.

    This function validates required and optional parameters, and rejects
    unknown properties to ensure a clean API surface.

    Args:
        tracker_path: The tracker file path (required)
        target_status: The target status value (required)
        dry_run: Whether to preview without writing (optional, default False)
        force: Whether to bypass transition policy (optional, default False)
        **kwargs: Captures any unknown parameters to reject them

    Returns:
        Tuple of (validated_tracker_path, validated_target_status,
                  validated_dry_run, validated_force)

    Raises:
        ToolError: If any parameter is invalid or unknown properties are present

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
    """
    # Reject unknown properties (Requirement 1.5)
    if kwargs:
        unknown_keys = ", ".join(f"'{k}'" for k in sorted(kwargs.keys()))
        raise create_validation_error(f"Unknown input properties: {unknown_keys}")

    # Validate required parameters
    validated_tracker_path = validate_tracker_path(tracker_path)
    validated_target_status = validate_tracker_status(target_status)

    # Validate optional parameters with defaults (Requirements 1.3, 1.4)
    validated_dry_run = validate_dry_run(dry_run)
    validated_force = validate_force(force)

    return validated_tracker_path, validated_target_status, validated_dry_run, validated_force


# ============================================================================
# Validators for finalize_resume_batch tool
# ============================================================================


def validate_run_id(run_id: Optional[str]) -> Optional[str]:
    """
    Validate the run_id parameter for finalize_resume_batch.

    Args:
        run_id: The batch run identifier (None for auto-generation)

    Returns:
        Validated run_id or None for auto-generation

    Raises:
        ToolError: If run_id is invalid

    Requirements: 1.5, 1.6
    """
    # None is valid (means auto-generate)
    if run_id is None:
        return None

    # Check type
    if not isinstance(run_id, str):
        raise create_validation_error(
            f"Invalid run_id type: expected string, got {type(run_id).__name__}"
        )

    # Check not empty
    if not run_id.strip():
        raise create_validation_error("Invalid run_id: cannot be empty")

    return run_id


def validate_finalize_items(items) -> list:
    """
    Validate the items parameter for finalize_resume_batch.

    Validates that items is present, is a list, and has size 0-100.
    Does not validate individual item structure (that's done per-item).

    Args:
        items: The list of finalization items

    Returns:
        Validated items list

    Raises:
        ToolError: If items is invalid or batch size exceeds 100

    Requirements: 1.1, 1.2, 1.3, 1.4
    """
    # Check for null/None (Requirement 1.1)
    if items is None:
        raise create_validation_error("Invalid items: cannot be null")

    # Check type
    if not isinstance(items, list):
        raise create_validation_error(
            f"Invalid items type: expected array, got {type(items).__name__}"
        )

    # Empty batch is valid (Requirement 1.2) - return early
    if len(items) == 0:
        return items

    # Check batch size limit (Requirement 1.3, 1.4)
    if len(items) > 100:
        raise create_validation_error(
            f"Batch size too large: {len(items)} items exceeds maximum of 100"
        )

    return items


def validate_finalize_duplicate_ids(items: list) -> None:
    """
    Validate that all item IDs in the finalize batch are unique.

    Duplicate item IDs within one batch are not allowed and will cause
    the entire request to be rejected with a VALIDATION_ERROR.

    Args:
        items: The list of finalization items to validate

    Raises:
        ToolError: If duplicate item IDs are found

    Requirements: 2.5, 11.1
    """
    # Empty batch is valid - return early
    if not items or len(items) == 0:
        return

    # Collect all item IDs
    item_ids = []
    for item in items:
        # Extract item ID if present (may be missing or invalid)
        if isinstance(item, dict) and "id" in item:
            item_ids.append(item["id"])

    # Find duplicates
    seen = set()
    duplicates = set()
    for item_id in item_ids:
        if item_id in seen:
            duplicates.add(item_id)
        else:
            seen.add(item_id)

    # Raise error if duplicates found
    if duplicates:
        duplicate_list = ", ".join(sorted(str(dup_id) for dup_id in duplicates))
        raise create_validation_error(f"Duplicate item IDs found in batch: {duplicate_list}")


def validate_finalize_item(item) -> Tuple[bool, Optional[str]]:
    """
    Validate a single finalization item's structure and required fields.

    Validates that the item has the required 'id' and 'tracker_path' fields
    with correct types and values. Optional 'resume_pdf_path' is also validated
    if present.

    Args:
        item: A single finalization item to validate

    Returns:
        Tuple of (is_valid, error_message):
        - is_valid: True if item is valid, False otherwise
        - error_message: None if valid, descriptive error string if invalid

    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    # Check if item is a dict
    if not isinstance(item, dict):
        return False, f"Item must be an object, got {type(item).__name__}"

    # Validate required 'id' field (Requirement 2.1, 2.3)
    if "id" not in item:
        return False, "Item missing required field 'id'"

    item_id = item["id"]

    # Check id type (bool is a subclass of int in Python, reject explicitly)
    if isinstance(item_id, bool) or not isinstance(item_id, int):
        return False, f"Item 'id' must be an integer, got {type(item_id).__name__}"

    # Check id is positive integer (Requirement 2.3)
    if item_id < 1:
        return False, f"Item 'id' must be a positive integer, got {item_id}"

    # Validate required 'tracker_path' field (Requirement 2.1, 2.4)
    if "tracker_path" not in item:
        return False, "Item missing required field 'tracker_path'"

    tracker_path = item["tracker_path"]

    # Check tracker_path type
    if not isinstance(tracker_path, str):
        return False, f"Item 'tracker_path' must be a string, got {type(tracker_path).__name__}"

    # Check tracker_path is not empty (Requirement 2.4)
    if not tracker_path or not tracker_path.strip():
        return False, "Item 'tracker_path' cannot be empty"

    # Validate optional 'resume_pdf_path' field if present (Requirement 2.2)
    if "resume_pdf_path" in item:
        resume_pdf_path = item["resume_pdf_path"]

        # Check resume_pdf_path type
        if not isinstance(resume_pdf_path, str):
            return (
                False,
                f"Item 'resume_pdf_path' must be a string, got {type(resume_pdf_path).__name__}",
            )

    # Item is valid
    return True, None


def validate_finalize_resume_batch_parameters(
    items,
    run_id: Optional[str] = None,
    db_path: Optional[str] = None,
    dry_run: Optional[bool] = None,
) -> Tuple[list, Optional[str], Optional[str], bool]:
    """
    Validate all input parameters for finalize_resume_batch at once.

    Validates request-level parameters including items presence, batch size,
    duplicate item IDs, and optional run_id, db_path, and dry_run parameters.

    Args:
        items: The list of finalization items (required)
        run_id: The batch run identifier (optional, auto-generated if None)
        db_path: The database path (optional, uses default if None)
        dry_run: Whether to preview without writing (optional, default False)

    Returns:
        Tuple of (validated_items, validated_run_id, validated_db_path,
                  validated_dry_run)

    Raises:
        ToolError: If any parameter is invalid or duplicate IDs are found

    Requirements: 1.1, 1.3, 1.4, 1.5, 2.5, 11.1
    """
    # Validate items presence, type, and batch size
    validated_items = validate_finalize_items(items)

    # Validate no duplicate item IDs at request level
    validate_finalize_duplicate_ids(validated_items)

    # Validate optional parameters
    validated_run_id = validate_run_id(run_id)
    validated_db_path = validate_db_path(db_path)
    validated_dry_run = validate_dry_run(dry_run)

    return validated_items, validated_run_id, validated_db_path, validated_dry_run


# ============================================================================
# Validators for scrape_jobs tool
# ============================================================================

# Constants for scrape_jobs validation
DEFAULT_SCRAPE_TERMS = ["ai engineer", "backend engineer", "machine learning"]
DEFAULT_SCRAPE_LOCATION = "Ontario, Canada"
DEFAULT_SCRAPE_SITES = ["linkedin"]
DEFAULT_RESULTS_WANTED = 20
MIN_RESULTS_WANTED = 1
MAX_RESULTS_WANTED = 200
DEFAULT_HOURS_OLD = 2
MIN_HOURS_OLD = 1
MAX_HOURS_OLD = 168
DEFAULT_REQUIRE_DESCRIPTION = True
DEFAULT_PREFLIGHT_HOST = "www.linkedin.com"
DEFAULT_RETRY_COUNT = 3
MIN_RETRY_COUNT = 1
MAX_RETRY_COUNT = 10
DEFAULT_RETRY_SLEEP_SECONDS = 30
MIN_RETRY_SLEEP_SECONDS = 0
MAX_RETRY_SLEEP_SECONDS = 300
DEFAULT_RETRY_BACKOFF = 2
MIN_RETRY_BACKOFF = 1
MAX_RETRY_BACKOFF = 10
DEFAULT_SAVE_CAPTURE_JSON = True
DEFAULT_CAPTURE_DIR = "data/capture"


def validate_scrape_terms(terms: Optional[list]) -> list:
    """
    Validate the terms parameter for scrape_jobs.

    Args:
        terms: The search terms list (None for default)

    Returns:
        Validated terms list (default: ["ai engineer", "backend engineer", "machine learning"])

    Raises:
        ToolError: If terms is invalid

    Requirements: 1.1, 1.2, 1.3
    """
    # Use default if not provided
    if terms is None:
        return DEFAULT_SCRAPE_TERMS

    # Check type
    if not isinstance(terms, list):
        raise create_validation_error(
            f"Invalid terms type: expected array, got {type(terms).__name__}"
        )

    # Check not empty
    if len(terms) == 0:
        raise create_validation_error("Invalid terms: cannot be empty array")

    # Validate each term is a string
    for i, term in enumerate(terms):
        if not isinstance(term, str):
            raise create_validation_error(
                f"Invalid terms[{i}] type: expected string, got {type(term).__name__}"
            )
        if not term.strip():
            raise create_validation_error(f"Invalid terms[{i}]: cannot be empty string")

    return terms


def validate_scrape_location(location: Optional[str]) -> str:
    """
    Validate the location parameter for scrape_jobs.

    Args:
        location: The search location (None for default)

    Returns:
        Validated location string (default: "Ontario, Canada")

    Raises:
        ToolError: If location is invalid

    Requirements: 1.1, 1.2
    """
    # Use default if not provided
    if location is None:
        return DEFAULT_SCRAPE_LOCATION

    # Check type
    if not isinstance(location, str):
        raise create_validation_error(
            f"Invalid location type: expected string, got {type(location).__name__}"
        )

    # Check not empty
    if not location.strip():
        raise create_validation_error("Invalid location: cannot be empty")

    return location


def validate_scrape_sites(sites: Optional[list]) -> list:
    """
    Validate the sites parameter for scrape_jobs.

    Args:
        sites: The source sites list (None for default)

    Returns:
        Validated sites list (default: ["linkedin"])

    Raises:
        ToolError: If sites is invalid

    Requirements: 1.1, 1.2, 3.4
    """
    # Use default if not provided
    if sites is None:
        return DEFAULT_SCRAPE_SITES

    # Check type
    if not isinstance(sites, list):
        raise create_validation_error(
            f"Invalid sites type: expected array, got {type(sites).__name__}"
        )

    # Check not empty
    if len(sites) == 0:
        raise create_validation_error("Invalid sites: cannot be empty array")

    # Validate each site is a string
    for i, site in enumerate(sites):
        if not isinstance(site, str):
            raise create_validation_error(
                f"Invalid sites[{i}] type: expected string, got {type(site).__name__}"
            )
        if not site.strip():
            raise create_validation_error(f"Invalid sites[{i}]: cannot be empty string")

    return sites


def validate_results_wanted(results_wanted: Optional[int]) -> int:
    """
    Validate the results_wanted parameter for scrape_jobs.

    Args:
        results_wanted: The requested scrape results per term (None for default)

    Returns:
        Validated results_wanted value (default: 20, range: 1-200)

    Raises:
        ToolError: If results_wanted is invalid

    Requirements: 1.1, 1.4, 12.2
    """
    # Use default if not provided
    if results_wanted is None:
        return DEFAULT_RESULTS_WANTED

    # Check type (bool is a subclass of int in Python, reject explicitly)
    if isinstance(results_wanted, bool) or not isinstance(results_wanted, int):
        raise create_validation_error(
            f"Invalid results_wanted type: expected integer, got {type(results_wanted).__name__}"
        )

    # Check range
    if results_wanted < MIN_RESULTS_WANTED:
        raise create_validation_error(
            f"Invalid results_wanted: {results_wanted} is below minimum of {MIN_RESULTS_WANTED}"
        )

    if results_wanted > MAX_RESULTS_WANTED:
        raise create_validation_error(
            f"Invalid results_wanted: {results_wanted} exceeds maximum of {MAX_RESULTS_WANTED}"
        )

    return results_wanted


def validate_hours_old(hours_old: Optional[int]) -> int:
    """
    Validate the hours_old parameter for scrape_jobs.

    Args:
        hours_old: The recency window in hours (None for default)

    Returns:
        Validated hours_old value (default: 2, range: 1-168)

    Raises:
        ToolError: If hours_old is invalid

    Requirements: 1.1, 1.4, 12.2
    """
    # Use default if not provided
    if hours_old is None:
        return DEFAULT_HOURS_OLD

    # Check type (bool is a subclass of int in Python, reject explicitly)
    if isinstance(hours_old, bool) or not isinstance(hours_old, int):
        raise create_validation_error(
            f"Invalid hours_old type: expected integer, got {type(hours_old).__name__}"
        )

    # Check range
    if hours_old < MIN_HOURS_OLD:
        raise create_validation_error(
            f"Invalid hours_old: {hours_old} is below minimum of {MIN_HOURS_OLD}"
        )

    if hours_old > MAX_HOURS_OLD:
        raise create_validation_error(
            f"Invalid hours_old: {hours_old} exceeds maximum of {MAX_HOURS_OLD}"
        )

    return hours_old


def validate_require_description(require_description: Optional[bool]) -> bool:
    """
    Validate the require_description parameter for scrape_jobs.

    Args:
        require_description: Whether to skip records without descriptions (None for default)

    Returns:
        Validated require_description value (default: True)

    Raises:
        ToolError: If require_description is invalid

    Requirements: 1.1, 5.2
    """
    # Use default if not provided
    if require_description is None:
        return DEFAULT_REQUIRE_DESCRIPTION

    # Check type
    if not isinstance(require_description, bool):
        raise create_validation_error(
            f"Invalid require_description type: expected boolean, got {type(require_description).__name__}"
        )

    return require_description


def validate_preflight_host(preflight_host: Optional[str]) -> str:
    """
    Validate the preflight_host parameter for scrape_jobs.

    Args:
        preflight_host: The DNS preflight host (None for default)

    Returns:
        Validated preflight_host string (default: "www.linkedin.com")

    Raises:
        ToolError: If preflight_host is invalid

    Requirements: 2.1, 12.2
    """
    # Use default if not provided
    if preflight_host is None:
        return DEFAULT_PREFLIGHT_HOST

    # Check type
    if not isinstance(preflight_host, str):
        raise create_validation_error(
            f"Invalid preflight_host type: expected string, got {type(preflight_host).__name__}"
        )

    # Check not empty
    if not preflight_host.strip():
        raise create_validation_error("Invalid preflight_host: cannot be empty")

    return preflight_host


def validate_retry_count(retry_count: Optional[int]) -> int:
    """
    Validate the retry_count parameter for scrape_jobs.

    Args:
        retry_count: The preflight retry count (None for default)

    Returns:
        Validated retry_count value (default: 3, range: 1-10)

    Raises:
        ToolError: If retry_count is invalid

    Requirements: 2.2, 12.2
    """
    # Use default if not provided
    if retry_count is None:
        return DEFAULT_RETRY_COUNT

    # Check type (bool is a subclass of int in Python, reject explicitly)
    if isinstance(retry_count, bool) or not isinstance(retry_count, int):
        raise create_validation_error(
            f"Invalid retry_count type: expected integer, got {type(retry_count).__name__}"
        )

    # Check range
    if retry_count < MIN_RETRY_COUNT:
        raise create_validation_error(
            f"Invalid retry_count: {retry_count} is below minimum of {MIN_RETRY_COUNT}"
        )

    if retry_count > MAX_RETRY_COUNT:
        raise create_validation_error(
            f"Invalid retry_count: {retry_count} exceeds maximum of {MAX_RETRY_COUNT}"
        )

    return retry_count


def validate_retry_sleep_seconds(retry_sleep_seconds: Optional[float]) -> float:
    """
    Validate the retry_sleep_seconds parameter for scrape_jobs.

    Args:
        retry_sleep_seconds: The base retry sleep seconds (None for default)

    Returns:
        Validated retry_sleep_seconds value (default: 30, range: 0-300)

    Raises:
        ToolError: If retry_sleep_seconds is invalid

    Requirements: 2.2, 12.2
    """
    # Use default if not provided
    if retry_sleep_seconds is None:
        return DEFAULT_RETRY_SLEEP_SECONDS

    # Check type (bool is a subclass of int in Python, reject explicitly)
    # Accept both int and float
    if isinstance(retry_sleep_seconds, bool) or not isinstance(retry_sleep_seconds, (int, float)):
        raise create_validation_error(
            f"Invalid retry_sleep_seconds type: expected number, got {type(retry_sleep_seconds).__name__}"
        )

    # Check range
    if retry_sleep_seconds < MIN_RETRY_SLEEP_SECONDS:
        raise create_validation_error(
            f"Invalid retry_sleep_seconds: {retry_sleep_seconds} is below minimum of {MIN_RETRY_SLEEP_SECONDS}"
        )

    if retry_sleep_seconds > MAX_RETRY_SLEEP_SECONDS:
        raise create_validation_error(
            f"Invalid retry_sleep_seconds: {retry_sleep_seconds} exceeds maximum of {MAX_RETRY_SLEEP_SECONDS}"
        )

    return retry_sleep_seconds


def validate_retry_backoff(retry_backoff: Optional[float]) -> float:
    """
    Validate the retry_backoff parameter for scrape_jobs.

    Args:
        retry_backoff: The retry backoff multiplier (None for default)

    Returns:
        Validated retry_backoff value (default: 2, range: 1-10)

    Raises:
        ToolError: If retry_backoff is invalid

    Requirements: 2.2, 12.2
    """
    # Use default if not provided
    if retry_backoff is None:
        return DEFAULT_RETRY_BACKOFF

    # Check type (bool is a subclass of int in Python, reject explicitly)
    # Accept both int and float
    if isinstance(retry_backoff, bool) or not isinstance(retry_backoff, (int, float)):
        raise create_validation_error(
            f"Invalid retry_backoff type: expected number, got {type(retry_backoff).__name__}"
        )

    # Check range
    if retry_backoff < MIN_RETRY_BACKOFF:
        raise create_validation_error(
            f"Invalid retry_backoff: {retry_backoff} is below minimum of {MIN_RETRY_BACKOFF}"
        )

    if retry_backoff > MAX_RETRY_BACKOFF:
        raise create_validation_error(
            f"Invalid retry_backoff: {retry_backoff} exceeds maximum of {MAX_RETRY_BACKOFF}"
        )

    return retry_backoff


def validate_save_capture_json(save_capture_json: Optional[bool]) -> bool:
    """
    Validate the save_capture_json parameter for scrape_jobs.

    Args:
        save_capture_json: Whether to persist per-term raw JSON capture files (None for default)

    Returns:
        Validated save_capture_json value (default: True)

    Raises:
        ToolError: If save_capture_json is invalid

    Requirements: 9.1, 9.2
    """
    # Use default if not provided
    if save_capture_json is None:
        return DEFAULT_SAVE_CAPTURE_JSON

    # Check type
    if not isinstance(save_capture_json, bool):
        raise create_validation_error(
            f"Invalid save_capture_json type: expected boolean, got {type(save_capture_json).__name__}"
        )

    return save_capture_json


def validate_capture_dir(capture_dir: Optional[str]) -> str:
    """
    Validate the capture_dir parameter for scrape_jobs.

    Args:
        capture_dir: The capture output directory (None for default)

    Returns:
        Validated capture_dir string (default: "data/capture")

    Raises:
        ToolError: If capture_dir is invalid

    Requirements: 9.1
    """
    # Use default if not provided
    if capture_dir is None:
        return DEFAULT_CAPTURE_DIR

    # Check type
    if not isinstance(capture_dir, str):
        raise create_validation_error(
            f"Invalid capture_dir type: expected string, got {type(capture_dir).__name__}"
        )

    # Check not empty
    if not capture_dir.strip():
        raise create_validation_error("Invalid capture_dir: cannot be empty")

    return capture_dir


def validate_scrape_status(status: Optional[str]) -> str:
    """
    Validate the status parameter for scrape_jobs.

    Args:
        status: The initial status for inserted rows (None for default)

    Returns:
        Validated status string (default: "new")

    Raises:
        ToolError: If status is invalid

    Requirements: 8.1, 8.2
    """
    # Use default if not provided
    if status is None:
        return JobDbStatus.NEW

    # Check type
    if not isinstance(status, str):
        raise create_validation_error(
            f"Invalid status type: expected string, got {type(status).__name__}"
        )

    # Check for empty string
    if not status:
        raise create_validation_error("Invalid status: cannot be empty")

    # Check for leading/trailing whitespace
    if status != status.strip():
        raise create_validation_error(
            f"Invalid status: '{status}' contains leading or trailing whitespace"
        )

    # Check against allowed statuses (case-sensitive)
    try:
        JobDbStatus(status)
    except ValueError:
        allowed = ", ".join(sorted(s.value for s in JobDbStatus))
        raise create_validation_error(
            f"Invalid status value: '{status}'. Allowed values are: {allowed}"
        )

    return status


def validate_scrape_jobs_parameters(
    terms: Optional[list] = None,
    location: Optional[str] = None,
    sites: Optional[list] = None,
    results_wanted: Optional[int] = None,
    hours_old: Optional[int] = None,
    db_path: Optional[str] = None,
    status: Optional[str] = None,
    require_description: Optional[bool] = None,
    preflight_host: Optional[str] = None,
    retry_count: Optional[int] = None,
    retry_sleep_seconds: Optional[float] = None,
    retry_backoff: Optional[float] = None,
    save_capture_json: Optional[bool] = None,
    capture_dir: Optional[str] = None,
    dry_run: Optional[bool] = None,
    **kwargs,
) -> dict:
    """
    Validate all input parameters for scrape_jobs at once.

    This function validates all required and optional parameters, and rejects
    unknown properties to ensure a clean API surface.

    Args:
        terms: Search terms (optional, default: ["ai engineer", "backend engineer", "machine learning"])
        location: Search location (optional, default: "Ontario, Canada")
        sites: Source sites list (optional, default: ["linkedin"])
        results_wanted: Requested scrape results per term (optional, default: 20, range: 1-200)
        hours_old: Recency window in hours (optional, default: 2, range: 1-168)
        db_path: SQLite path override (optional, default: data/capture/jobs.db)
        status: Initial status for inserted rows (optional, default: "new")
        require_description: Skip records without descriptions (optional, default: True)
        preflight_host: DNS preflight host (optional, default: "www.linkedin.com")
        retry_count: Preflight retry count (optional, default: 3, range: 1-10)
        retry_sleep_seconds: Base retry sleep seconds (optional, default: 30, range: 0-300)
        retry_backoff: Retry backoff multiplier (optional, default: 2, range: 1-10)
        save_capture_json: Persist per-term raw JSON capture files (optional, default: True)
        capture_dir: Capture output directory (optional, default: data/capture)
        dry_run: Compute counts only; no DB writes (optional, default: False)
        **kwargs: Captures any unknown parameters to reject them

    Returns:
        Dictionary with all validated parameters

    Raises:
        ToolError: If any parameter is invalid or unknown properties are present

    Requirements: 1.1, 1.4, 1.5, 8.2, 11.1, 12.2, 12.3
    """
    # Reject unknown properties (Requirement 1.5)
    if kwargs:
        unknown_keys = ", ".join(f"'{k}'" for k in sorted(kwargs.keys()))
        raise create_validation_error(f"Unknown input properties: {unknown_keys}")

    # Validate all parameters
    validated_terms = validate_scrape_terms(terms)
    validated_location = validate_scrape_location(location)
    validated_sites = validate_scrape_sites(sites)
    validated_results_wanted = validate_results_wanted(results_wanted)
    validated_hours_old = validate_hours_old(hours_old)
    validated_db_path = validate_db_path(db_path)
    validated_status = validate_scrape_status(status)
    validated_require_description = validate_require_description(require_description)
    validated_preflight_host = validate_preflight_host(preflight_host)
    validated_retry_count = validate_retry_count(retry_count)
    validated_retry_sleep_seconds = validate_retry_sleep_seconds(retry_sleep_seconds)
    validated_retry_backoff = validate_retry_backoff(retry_backoff)
    validated_save_capture_json = validate_save_capture_json(save_capture_json)
    validated_capture_dir = validate_capture_dir(capture_dir)
    validated_dry_run = validate_dry_run(dry_run)

    return {
        "terms": validated_terms,
        "location": validated_location,
        "sites": validated_sites,
        "results_wanted": validated_results_wanted,
        "hours_old": validated_hours_old,
        "db_path": validated_db_path,
        "status": validated_status,
        "require_description": validated_require_description,
        "preflight_host": validated_preflight_host,
        "retry_count": validated_retry_count,
        "retry_sleep_seconds": validated_retry_sleep_seconds,
        "retry_backoff": validated_retry_backoff,
        "save_capture_json": validated_save_capture_json,
        "capture_dir": validated_capture_dir,
        "dry_run": validated_dry_run,
    }


# ============================================================================
# Validators for career_tailor tool
# ============================================================================

# Constants for career_tailor validation
MIN_CAREER_TAILOR_ITEMS = 1
MAX_CAREER_TAILOR_ITEMS = 100


def validate_career_tailor_items(items) -> list:
    """
    Validate the items parameter for career_tailor.

    Validates that items is present, is a list, and has size 1-100.
    Does not validate individual item structure (that's done per-item).

    Args:
        items: The list of batch items

    Returns:
        Validated items list

    Raises:
        ToolError: If items is invalid or batch size is out of range

    Requirements: 1.1
    """
    # Check for null/None (Requirement 1.1)
    if items is None:
        raise create_validation_error("Invalid items: cannot be null")

    # Check type
    if not isinstance(items, list):
        raise create_validation_error(
            f"Invalid items type: expected array, got {type(items).__name__}"
        )

    # Check non-empty (Requirement 1.1)
    if len(items) == 0:
        raise create_validation_error("Invalid items: cannot be empty array")

    # Check batch size limit
    if len(items) > MAX_CAREER_TAILOR_ITEMS:
        raise create_validation_error(
            f"Batch size too large: {len(items)} items exceeds maximum of {MAX_CAREER_TAILOR_ITEMS}"
        )

    return items


def validate_career_tailor_item(item) -> tuple:
    """
    Validate a single career_tailor item's structure and required fields.

    Validates that the item has the required 'tracker_path' field and optional
    'job_db_id' field with correct types and values.

    Args:
        item: A single batch item to validate

    Returns:
        Tuple of (is_valid, error_message):
        - is_valid: True if item is valid, False otherwise
        - error_message: None if valid, descriptive error string if invalid

    Requirements: 1.2, 1.3
    """
    # Check if item is a dict
    if not isinstance(item, dict):
        return False, f"Item must be an object, got {type(item).__name__}"

    # Validate required 'tracker_path' field (Requirement 1.2)
    if "tracker_path" not in item:
        return False, "Item missing required field 'tracker_path'"

    tracker_path = item["tracker_path"]

    # Check tracker_path type
    if not isinstance(tracker_path, str):
        return False, f"Item 'tracker_path' must be a string, got {type(tracker_path).__name__}"

    # Check tracker_path is not empty
    if not tracker_path or not tracker_path.strip():
        return False, "Item 'tracker_path' cannot be empty"

    # Validate optional 'job_db_id' field if present (Requirement 1.3)
    if "job_db_id" in item:
        job_db_id = item["job_db_id"]

        # Check job_db_id type (bool is a subclass of int in Python, reject explicitly)
        if isinstance(job_db_id, bool) or not isinstance(job_db_id, int):
            return False, f"Item 'job_db_id' must be an integer, got {type(job_db_id).__name__}"

        # Check job_db_id is positive integer (Requirement 1.3)
        if job_db_id < 1:
            return False, f"Item 'job_db_id' must be a positive integer, got {job_db_id}"

    # Check for unknown fields in item (Requirement 1.6)
    allowed_item_fields = {"tracker_path", "job_db_id"}
    unknown_fields = set(item.keys()) - allowed_item_fields
    if unknown_fields:
        unknown_list = ", ".join(f"'{k}'" for k in sorted(unknown_fields))
        return False, f"Item contains unknown fields: {unknown_list}"

    # Item is valid
    return True, None


def validate_career_tailor_batch_parameters(
    items,
    force: Optional[bool] = None,
    full_resume_path: Optional[str] = None,
    resume_template_path: Optional[str] = None,
    applications_dir: Optional[str] = None,
    pdflatex_cmd: Optional[str] = None,
    **kwargs,
) -> tuple:
    """
    Validate all input parameters for career_tailor at once.

    Validates request-level parameters including items presence, batch size,
    and optional batch-level overrides. Rejects unknown properties.

    Args:
        items: The list of batch items (required, non-empty)
        force: Whether to overwrite existing resume.tex (optional, default False)
        full_resume_path: Override path to full resume (optional)
        resume_template_path: Override path to resume template (optional)
        applications_dir: Override applications directory (optional)
        pdflatex_cmd: Override pdflatex command (optional)
        **kwargs: Captures any unknown parameters to reject them

    Returns:
        Tuple of (validated_items, validated_force, validated_full_resume_path,
                  validated_resume_template_path, validated_applications_dir,
                  validated_pdflatex_cmd)

    Raises:
        ToolError: If any parameter is invalid or unknown properties are present

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.6
    """
    # Reject unknown properties (Requirement 1.6)
    if kwargs:
        unknown_keys = ", ".join(f"'{k}'" for k in sorted(kwargs.keys()))
        raise create_validation_error(f"Unknown input properties: {unknown_keys}")

    # Validate items presence, type, and batch size (Requirement 1.1)
    validated_items = validate_career_tailor_items(items)

    # Validate optional force parameter (Requirement 1.4)
    validated_force = validate_force(force)

    # Validate optional full_resume_path (Requirement 1.4)
    if full_resume_path is not None:
        if not isinstance(full_resume_path, str):
            raise create_validation_error(
                f"Invalid full_resume_path type: expected string, got {type(full_resume_path).__name__}"
            )
        if not full_resume_path.strip():
            raise create_validation_error("Invalid full_resume_path: cannot be empty")

    # Validate optional resume_template_path (Requirement 1.4)
    if resume_template_path is not None:
        if not isinstance(resume_template_path, str):
            raise create_validation_error(
                f"Invalid resume_template_path type: expected string, got {type(resume_template_path).__name__}"
            )
        if not resume_template_path.strip():
            raise create_validation_error("Invalid resume_template_path: cannot be empty")

    # Validate optional applications_dir (Requirement 1.4)
    if applications_dir is not None:
        if not isinstance(applications_dir, str):
            raise create_validation_error(
                f"Invalid applications_dir type: expected string, got {type(applications_dir).__name__}"
            )
        if not applications_dir.strip():
            raise create_validation_error("Invalid applications_dir: cannot be empty")

    # Validate optional pdflatex_cmd (Requirement 1.4)
    if pdflatex_cmd is not None:
        if not isinstance(pdflatex_cmd, str):
            raise create_validation_error(
                f"Invalid pdflatex_cmd type: expected string, got {type(pdflatex_cmd).__name__}"
            )
        if not pdflatex_cmd.strip():
            raise create_validation_error("Invalid pdflatex_cmd: cannot be empty")

    return (
        validated_items,
        validated_force,
        full_resume_path,
        resume_template_path,
        applications_dir,
        pdflatex_cmd,
    )
