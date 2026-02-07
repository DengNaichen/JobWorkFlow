"""
MCP tool handler for finalize_resume_batch.

This tool performs the final write-back step after resume compile succeeds.
It commits durable completion state by updating DB status/audit fields and
synchronizing tracker frontmatter status in one operational step.

This tool is commit-focused:
- Database status remains the SSOT.
- Tracker status is a synchronized projection for Obsidian workflow.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import hashlib
import re

from pydantic import ValidationError

from db.jobs_writer import JobsWriter
from schemas.finalize_resume_batch import FinalizeResumeBatchRequest, FinalizeResumeBatchResponse
from utils.validation import (
    validate_finalize_resume_batch_parameters,
    validate_finalize_item,
    get_current_utc_timestamp,
)
from utils.tracker_parser import resolve_resume_pdf_path_from_tracker
from utils.artifact_paths import resolve_resume_tex_path
from utils.finalize_validators import validate_tracker_exists, validate_resume_written_guardrails
from utils.tracker_sync import update_tracker_status
from models.errors import ToolError, create_internal_error
from utils.pydantic_error_mapper import map_pydantic_validation_error


def generate_run_id() -> str:
    """
    Generate a deterministic batch run identifier.

    Format: run_YYYYMMDD_<8-char-hash>

    The hash is based on the current timestamp with microsecond precision
    to ensure uniqueness across multiple calls in the same second.

    Returns:
        Run ID string in format: run_20260206_8f2f8f1c

    Requirements:
        - 1.6: Generate deterministic batch run identifier when run_id is omitted

    Examples:
        >>> run_id = generate_run_id()
        >>> run_id.startswith("run_")
        True
        >>> len(run_id.split("_")[2])
        8
    """
    now = datetime.now(timezone.utc)

    # Date component: YYYYMMDD
    date_str = now.strftime("%Y%m%d")

    # Hash component: first 8 chars of hash of full timestamp
    timestamp_str = now.isoformat()
    hash_obj = hashlib.sha256(timestamp_str.encode("utf-8"))
    hash_str = hash_obj.hexdigest()[:8]

    return f"run_{date_str}_{hash_str}"


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error message for safe reporting.

    Removes stack traces, SQL fragments, and sensitive absolute paths
    while keeping actionable summary for retry.

    Args:
        error: Exception to sanitize

    Returns:
        Sanitized error message string

    Requirements:
        - 11.6: Error messages are sanitized (no stack traces, no SQL fragments, no sensitive absolute paths)
    """
    error_str = str(error)

    # Keep only summary line (drop stack-trace details).
    error_str = error_str.splitlines()[0].strip()

    # Redact SQL fragments.
    error_str = re.sub(
        r"\b(SELECT|INSERT|UPDATE|DELETE)\b.*", "[SQL query]", error_str, flags=re.IGNORECASE
    )

    # Redact absolute POSIX/Windows path tokens.
    redacted_tokens: List[str] = []
    for token in error_str.split():
        stripped = token.strip(".,;:()[]{}\"'")
        if stripped.startswith("/") or re.match(r"^[A-Za-z]:\\", stripped):
            redacted_tokens.append(token.replace(stripped, "[path]"))
        else:
            redacted_tokens.append(token)
    error_str = " ".join(redacted_tokens)

    # Truncate very long messages.
    if len(error_str) > 200:
        error_str = error_str[:197] + "..."

    return error_str


def validate_item_preconditions(item: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate all preconditions for a single finalization item.

    This function performs:
    1. Item structure validation (id, tracker_path)
    2. Tracker existence validation
    3. Resume PDF path resolution
    4. Artifact validation (PDF, TEX, placeholders)

    Args:
        item: Finalization item dictionary

    Returns:
        Tuple of (is_valid, error_message, resume_pdf_path):
        - is_valid: True if all validations pass, False otherwise
        - error_message: None if valid, descriptive error string if invalid
        - resume_pdf_path: Resolved PDF path if valid, None if invalid

    Requirements:
        - 2.1: Each item requires id and tracker_path
        - 2.3: When item id is not a positive integer, report item failure
        - 2.4: When item tracker_path is missing/empty, report item failure
        - 3.1: Verify tracker_path file exists and is readable
        - 3.2: Verify resume.pdf exists and has non-zero file size
        - 3.3: Verify companion resume.tex exists
        - 3.4: Scan resume.tex for known placeholder tokens before commit
        - 3.5: When placeholder tokens are present, mark item as failed
        - 3.6: Resolve resume_pdf_path from tracker frontmatter when item override is not provided
    """
    # Validate item structure
    item_valid, item_error = validate_finalize_item(item)
    if not item_valid:
        return False, item_error, None

    # Extract fields
    tracker_path = item["tracker_path"]
    item_resume_pdf_path = item.get("resume_pdf_path")

    # Validate tracker exists
    tracker_valid, tracker_error = validate_tracker_exists(tracker_path)
    if not tracker_valid:
        return False, tracker_error, None

    # Resolve resume_pdf_path
    try:
        resume_pdf_path = resolve_resume_pdf_path_from_tracker(tracker_path, item_resume_pdf_path)
    except Exception as e:
        return False, f"Failed to resolve resume_pdf_path: {sanitize_error_message(e)}", None

    # Derive resume.tex path
    try:
        resume_tex_path = resolve_resume_tex_path(resume_pdf_path)
    except Exception as e:
        return False, f"Failed to resolve resume.tex path: {sanitize_error_message(e)}", None

    # Validate artifacts (PDF, TEX, placeholders)
    artifacts_valid, artifacts_error = validate_resume_written_guardrails(
        resume_pdf_path, resume_tex_path
    )
    if not artifacts_valid:
        return False, artifacts_error, None

    # All validations passed
    return True, None, resume_pdf_path


def process_item_finalize(
    item: Dict[str, Any], resume_pdf_path: str, run_id: str, writer: JobsWriter, dry_run: bool
) -> Dict[str, Any]:
    """
    Process finalization for a single item.

    This function executes the finalization sequence:
    1. Update DB to resume_written status with audit fields
    2. Update tracker frontmatter status to "Resume Written"
    3. On tracker sync failure, apply compensation fallback to reviewed

    Args:
        item: Finalization item dictionary
        resume_pdf_path: Validated resume PDF path
        run_id: Batch run identifier
        writer: JobsWriter instance for DB operations
        dry_run: Whether to preview without writing

    Returns:
        Result dictionary with id, tracker_path, resume_pdf_path, action, success, error

    Requirements:
        - 5.1: On successful item finalization, set DB status='resume_written'
        - 5.2: Set resume_pdf_path to the validated PDF path
        - 5.3: Set resume_written_at to current UTC timestamp
        - 5.4: Set run_id to batch run id for the invocation
        - 5.5: Increment attempt_count by 1 for each finalization attempt
        - 5.6: Clear last_error on successful finalization
        - 6.1: On successful item finalization, update tracker frontmatter status to Resume Written
        - 6.4: When tracker write succeeds, mark item as finalized
        - 6.5: When tracker write fails, enter failure compensation flow
        - 7.1: When any finalize write step fails, set DB status='reviewed'
        - 7.2: Write last_error with sanitized failure reason
        - 7.3: Fallback update includes updated_at timestamp
        - 9.1: When dry_run=true, run all item validations and planning steps
        - 9.2: When dry_run=true, do not mutate DB rows
        - 9.3: When dry_run=true, do not write tracker files
    """
    job_id = item["id"]
    tracker_path = item["tracker_path"]
    timestamp = get_current_utc_timestamp()

    # Dry-run mode: return predicted action without writes
    if dry_run:
        return {
            "id": job_id,
            "tracker_path": tracker_path,
            "resume_pdf_path": resume_pdf_path,
            "action": "would_finalize",
            "success": True,
        }

    # Execute finalization sequence with compensation fallback
    try:
        # Step 1: Update DB to resume_written status
        writer.finalize_resume_written(
            job_id=job_id, resume_pdf_path=resume_pdf_path, run_id=run_id, timestamp=timestamp
        )
        writer.commit()

        # Step 2: Update tracker frontmatter status
        try:
            update_tracker_status(tracker_path, "Resume Written")

            # Success: both DB and tracker updated
            return {
                "id": job_id,
                "tracker_path": tracker_path,
                "resume_pdf_path": resume_pdf_path,
                "action": "finalized",
                "success": True,
            }

        except Exception as tracker_error:
            # Tracker sync failed after DB success - apply compensation fallback
            fallback_timestamp = get_current_utc_timestamp()
            sanitized_error = sanitize_error_message(tracker_error)

            try:
                writer.fallback_to_reviewed(
                    job_id=job_id,
                    last_error=f"Tracker sync failed: {sanitized_error}",
                    timestamp=fallback_timestamp,
                )
                writer.commit()
            except Exception as fallback_error:
                # Fallback also failed - report both errors
                sanitized_fallback = sanitize_error_message(fallback_error)
                return {
                    "id": job_id,
                    "tracker_path": tracker_path,
                    "resume_pdf_path": resume_pdf_path,
                    "action": "failed",
                    "success": False,
                    "error": f"Tracker sync failed: {sanitized_error}; Fallback also failed: {sanitized_fallback}",
                }

            # Fallback succeeded - item failed but DB is in consistent state
            return {
                "id": job_id,
                "tracker_path": tracker_path,
                "resume_pdf_path": resume_pdf_path,
                "action": "failed",
                "success": False,
                "error": f"Tracker sync failed: {sanitized_error}",
            }

    except Exception as db_error:
        # DB finalization failed - no compensation needed (transaction rolled back)
        sanitized_error = sanitize_error_message(db_error)
        return {
            "id": job_id,
            "tracker_path": tracker_path,
            "resume_pdf_path": resume_pdf_path,
            "action": "failed",
            "success": False,
            "error": f"DB finalization failed: {sanitized_error}",
        }


def finalize_resume_batch(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool handler for finalize_resume_batch.

    This tool performs the final write-back step after resume compile succeeds.
    It commits durable completion state by updating DB status/audit fields and
    synchronizing tracker frontmatter status in one operational step.

    Args:
        args: Tool arguments containing:
            - items: List of finalization items (required)
            - run_id: Batch run identifier (optional, auto-generated if None)
            - db_path: Database path (optional, uses default if None)
            - dry_run: Preview mode without writes (optional, default False)

    Returns:
        Dictionary containing:
            - run_id: Batch run identifier
            - finalized_count: Number of successfully finalized items
            - failed_count: Number of failed items
            - dry_run: Whether this was a dry-run
            - warnings: List of non-fatal warnings (optional)
            - results: List of per-item results in input order

    Raises:
        ToolError: For request-level validation failures, DB errors, or internal errors

    Requirements:
        - 1.1: Accept items as an array of finalization entries
        - 1.2: When items is empty, return success with zero finalized items
        - 1.3: Support batches from 1 to 100 items
        - 1.4: When batch size exceeds 100, return VALIDATION_ERROR
        - 1.5: Support optional run_id, db_path, and dry_run parameters
        - 1.6: When run_id is omitted, generate one deterministic batch run identifier
        - 2.6: Preserve result order matching input order
        - 4.1: Connect to data/capture/jobs.db by default
        - 4.2: Support db_path override
        - 4.3: When DB file is missing, return DB_NOT_FOUND
        - 4.4: Preflight required columns before processing
        - 4.5: When required columns are missing, fail with schema/migration-required error
        - 7.4: Continue processing remaining items after one item fails
        - 7.5: Fallback behavior is applied per-item (not all-or-nothing)
        - 9.1: When dry_run=true, run all item validations and planning steps
        - 9.2: When dry_run=true, do not mutate DB rows
        - 9.3: When dry_run=true, do not write tracker files
        - 9.5: Dry-run response ordering matches input ordering
        - 10.1: Return run_id, finalized_count, failed_count, dry_run, results
        - 10.3: Keep results ordered exactly as input
        - 10.4: All response values are JSON-serializable
        - 11.1: Request-level validation failures return top-level VALIDATION_ERROR
        - 11.2: Missing DB returns top-level DB_NOT_FOUND
        - 11.3: DB operation failures return top-level DB_ERROR
        - 11.4: Unexpected runtime failures return top-level INTERNAL_ERROR
        - 11.6: Per-item precondition/finalization failures are represented in results
    """
    try:
        request = FinalizeResumeBatchRequest.model_validate(args)

        # Validate request-level parameters
        items, run_id_param, db_path, dry_run = validate_finalize_resume_batch_parameters(
            items=request.items,
            run_id=request.run_id,
            db_path=request.db_path,
            dry_run=request.dry_run,
        )

        # Generate run_id if not provided
        run_id = run_id_param if run_id_param is not None else generate_run_id()

        # Handle empty batch
        if len(items) == 0:
            return FinalizeResumeBatchResponse(
                run_id=run_id,
                finalized_count=0,
                failed_count=0,
                dry_run=dry_run,
                results=[],
            ).model_dump(exclude_none=True)

        # Open DB connection and preflight schema
        with JobsWriter(db_path) as writer:
            # Preflight required columns
            writer.ensure_finalize_columns()

            # Process each item in input order
            results: List[Dict[str, Any]] = []

            for item in items:
                # Validate item preconditions
                preconditions_valid, preconditions_error, resume_pdf_path = (
                    validate_item_preconditions(item)
                )

                if not preconditions_valid:
                    # Item failed precondition validation
                    results.append(
                        {
                            "id": item.get("id"),
                            "tracker_path": item.get("tracker_path"),
                            "resume_pdf_path": None,
                            "action": "failed",
                            "success": False,
                            "error": preconditions_error,
                        }
                    )
                    continue

                # Process item finalization
                result = process_item_finalize(
                    item=item,
                    resume_pdf_path=resume_pdf_path,
                    run_id=run_id,
                    writer=writer,
                    dry_run=dry_run,
                )
                results.append(result)

            # Aggregate counts
            finalized_count = sum(1 for r in results if r["success"])
            failed_count = sum(1 for r in results if not r["success"])

            return FinalizeResumeBatchResponse(
                run_id=run_id,
                finalized_count=finalized_count,
                failed_count=failed_count,
                dry_run=dry_run,
                results=results,
            ).model_dump(exclude_none=True)

    except ValidationError as e:
        raise map_pydantic_validation_error(e) from e

    except ToolError:
        # ToolError already has proper error code - re-raise
        raise

    except Exception as e:
        # Unexpected error - wrap as INTERNAL_ERROR
        raise create_internal_error(
            f"Unexpected error in finalize_resume_batch: {sanitize_error_message(e)}"
        ) from e
