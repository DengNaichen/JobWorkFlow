"""
MCP tool handler for career_tailor.

This tool performs batch full-run tailoring: for each tracker item, initialize
workspace artifacts, generate ai_context.md, and compile resume.tex into resume.pdf.

This tool is artifact-focused:
- No DB status writes
- No tracker status writes
- No internal compensation/fallback writes
- Returns successful_items for downstream finalize_resume_batch
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import hashlib
import re

from pydantic import ValidationError

from schemas.career_tailor import CareerTailorRequest, CareerTailorResponse
from utils.pydantic_error_mapper import map_pydantic_validation_error
from utils.validation import validate_career_tailor_batch_parameters
from utils.tracker_parser import parse_tracker_for_career_tailor_with_error_mapping
from utils.slug_resolver import resolve_application_slug
from utils.file_ops import ensure_workspace_directories, materialize_resume_tex
from utils.ai_context_renderer import regenerate_ai_context
from utils.latex_compiler import compile_resume_pdf, verify_pdf_exists
from models.errors import ToolError, ErrorCode, create_internal_error


# Default paths
DEFAULT_FULL_RESUME_PATH = "data/templates/full_resume_example.md"
DEFAULT_RESUME_TEMPLATE_PATH = "data/templates/resume_skeleton_example.tex"
DEFAULT_APPLICATIONS_DIR = "data/applications"
DEFAULT_PDFLATEX_CMD = "pdflatex"


def generate_run_id(prefix: str = "tailor") -> str:
    """
    Generate a deterministic batch run identifier.

    Format: <prefix>_YYYYMMDD_<8-char-hash>

    The hash is based on the current timestamp with microsecond precision
    to ensure uniqueness across multiple calls in the same second.

    Args:
        prefix: Prefix for the run ID (default: "tailor")

    Returns:
        Run ID string in format: tailor_20260207_8f2f8f1c

    Examples:
        >>> run_id = generate_run_id("tailor")
        >>> run_id.startswith("tailor_")
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

    return f"{prefix}_{date_str}_{hash_str}"


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
        - 8.6: Error messages are sanitized (no stack traces, no sensitive absolute paths, no secrets)
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


def resolve_job_db_id(item_job_db_id: Any, tracker_job_db_id: Any) -> Optional[int]:
    """
    Resolve job_db_id for finalize handoff.

    Priority:
    1. explicit item-level job_db_id (already validated)
    2. tracker frontmatter job_db_id (int or numeric string)

    Returns None when no positive integer ID can be resolved.
    """
    if (
        isinstance(item_job_db_id, int)
        and not isinstance(item_job_db_id, bool)
        and item_job_db_id > 0
    ):
        return item_job_db_id

    if (
        isinstance(tracker_job_db_id, int)
        and not isinstance(tracker_job_db_id, bool)
        and tracker_job_db_id > 0
    ):
        return tracker_job_db_id

    if isinstance(tracker_job_db_id, str):
        stripped = tracker_job_db_id.strip()
        if stripped.isdigit():
            parsed = int(stripped)
            if parsed > 0:
                return parsed

    return None


def process_item_tailoring(
    item: Dict[str, Any],
    force: bool,
    full_resume_path: str,
    resume_template_path: str,
    applications_dir: str,
    pdflatex_cmd: str,
) -> Dict[str, Any]:
    """
    Process tailoring for a single item.

    This function executes the full tailoring sequence:
    1. Parse tracker
    2. Resolve slug
    3. Create workspace
    4. Materialize resume.tex
    5. Regenerate ai_context.md
    6. Compile PDF
    7. Verify PDF

    Args:
        item: Batch item dictionary with tracker_path and optional job_db_id
        force: Whether to overwrite existing resume.tex
        full_resume_path: Path to full resume markdown file
        resume_template_path: Path to resume template file
        applications_dir: Base directory for applications
        pdflatex_cmd: Command to run pdflatex

    Returns:
        Result dictionary with tracker_path, job_db_id, application_slug,
        workspace_dir, resume_tex_path, ai_context_path, resume_pdf_path,
        resume_tex_action, success, error_code, error

    Requirements:
        - 2.2: When one item fails, record item failure and continue next item
        - 3.1: Load tracker markdown from tracker_path
        - 3.2: When tracker file is missing/unreadable, fail with FILE_NOT_FOUND
        - 3.3: Extract frontmatter fields needed for workspace resolution
        - 3.4: Require ## Job Description heading
        - 3.5: When ## Job Description is missing, fail with VALIDATION_ERROR
        - 3.6: Extract job description content for ai_context.md
        - 4.1: Resolve deterministic application_slug from tracker metadata
        - 4.2: Ensure directories exist (resume/, cover/, cv/)
        - 4.3: Initialize resume/resume.tex from template when missing
        - 4.4: When force=true, overwrite existing resume.tex from template
        - 4.5: Regenerate resume/ai_context.md on each successful item run
        - 4.6: Generated files SHALL be written atomically
        - 5.1: Run LaTeX compile (pdflatex) on resume.tex
        - 5.2: Before compile, scan placeholders in resume.tex
        - 5.3: When placeholders exist, fail with VALIDATION_ERROR and skip compile
        - 5.4: When compile succeeds, verify resume.pdf exists and has non-zero size
        - 5.5: When compile/toolchain fails, fail with COMPILE_ERROR
        - 8.2: Missing source files map to FILE_NOT_FOUND or TEMPLATE_NOT_FOUND
        - 8.3: Compile failures map to COMPILE_ERROR
        - 8.4: Unexpected runtime failures map to INTERNAL_ERROR
    """
    tracker_path = item["tracker_path"]
    item_job_db_id = item.get("job_db_id")

    try:
        # Step 1: Parse tracker (Requirements 3.1-3.6)
        tracker_data = parse_tracker_for_career_tailor_with_error_mapping(tracker_path)

        # Resolve job_db_id from item override first, then tracker metadata.
        resolved_job_db_id = resolve_job_db_id(item_job_db_id, tracker_data.get("job_db_id"))

        # Step 2: Resolve deterministic slug (Requirement 4.1)
        application_slug = resolve_application_slug(tracker_data, resolved_job_db_id)

        # Step 3: Ensure workspace directories (Requirement 4.2)
        workspace_dir = f"{applications_dir}/{application_slug}"
        ensure_workspace_directories(application_slug, applications_dir)

        # Step 4: Materialize resume.tex (Requirements 4.3, 4.4, 4.6)
        resume_tex_path = f"{workspace_dir}/resume/resume.tex"
        try:
            resume_tex_action = materialize_resume_tex(
                template_path=resume_template_path, target_path=resume_tex_path, force=force
            )
        except FileNotFoundError as e:
            # Template not found
            raise ToolError(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                message=f"Resume template not found: {resume_template_path}",
            ) from e

        # Step 5: Regenerate ai_context.md (Requirements 4.5, 4.6)
        ai_context_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=workspace_dir,
            full_resume_path=full_resume_path,
        )

        # Step 6: Compile PDF (Requirements 5.1-5.5)
        resume_pdf_path = f"{workspace_dir}/resume/resume.pdf"
        compile_resume_pdf(tex_path=resume_tex_path, pdflatex_cmd=pdflatex_cmd)

        # Step 7: Verify PDF exists and has non-zero size (Requirement 5.4)
        pdf_valid, pdf_error = verify_pdf_exists(resume_pdf_path)
        if not pdf_valid:
            raise ToolError(code=ErrorCode.COMPILE_ERROR, message=pdf_error)

        # Success: return result with all paths
        result = {
            "tracker_path": tracker_path,
            "application_slug": application_slug,
            "workspace_dir": workspace_dir,
            "resume_tex_path": resume_tex_path,
            "ai_context_path": ai_context_path,
            "resume_pdf_path": resume_pdf_path,
            "resume_tex_action": resume_tex_action,
            "action": "tailored",
            "success": True,
        }

        # Include job_db_id if available
        if resolved_job_db_id is not None:
            result["job_db_id"] = resolved_job_db_id

        return result

    except ToolError as e:
        # ToolError already has proper error code - return failure result
        result = {
            "tracker_path": tracker_path,
            "action": "failed",
            "success": False,
            "error_code": e.code.value,
            "error": sanitize_error_message(e),
        }

        # Include job_db_id if available
        if item_job_db_id is not None:
            result["job_db_id"] = item_job_db_id

        return result

    except Exception as e:
        # Unexpected error - map to INTERNAL_ERROR
        sanitized_error = sanitize_error_message(e)
        result = {
            "tracker_path": tracker_path,
            "action": "failed",
            "success": False,
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "error": f"Internal error: {sanitized_error}",
        }

        # Include job_db_id if available
        if item_job_db_id is not None:
            result["job_db_id"] = item_job_db_id

        return result


def career_tailor(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool handler for career_tailor.

    This tool performs batch full-run tailoring: for each tracker item, initialize
    workspace artifacts, generate ai_context.md, and compile resume.tex into resume.pdf.

    Args:
        args: Tool arguments containing:
            - items: List of batch items (required, non-empty)
            - force: Whether to overwrite existing resume.tex (optional, default False)
            - full_resume_path: Override path to full resume (optional)
            - resume_template_path: Override path to resume template (optional)
            - applications_dir: Override applications directory (optional)
            - pdflatex_cmd: Override pdflatex command (optional)

    Returns:
        Dictionary containing:
            - run_id: Batch run identifier
            - total_count: Total number of items processed
            - success_count: Number of successfully tailored items
            - failed_count: Number of failed items
            - results: List of per-item results in input order
            - successful_items: List of items ready for finalize_resume_batch
            - warnings: List of non-fatal warnings (optional)

    Raises:
        ToolError: For request-level validation failures or internal errors

    Requirements:
        - 1.1: Require items as a non-empty array
        - 1.2: Each item requires tracker_path
        - 1.3: Each item may include optional job_db_id override
        - 1.4: Support optional batch-level overrides
        - 1.5: Execution is always full-run (no mode flags)
        - 1.6: When request fields are invalid or unknown, return VALIDATION_ERROR
        - 2.1: Process items in input order
        - 2.2: When one item fails, record item failure and continue next item
        - 2.3: Preserve input order in results
        - 2.4: Return top-level counts (success_count, failed_count, total_count)
        - 2.5: Do not abort the whole batch due to one item-level failure
        - 6.1: Do not read or write job status in jobs.db
        - 6.2: Do not call finalize_resume_batch
        - 6.3: Do not update tracker frontmatter status
        - 6.4: Only write workspace artifacts
        - 6.5: Do not implement compensation/fallback writes for failed items
        - 7.1: Return successful_items for downstream finalize_resume_batch
        - 7.2: Each successful item includes tracker_path and resume_pdf_path
        - 7.3: When item job_db_id is available/resolved, include id
        - 7.4: When job_db_id is missing, item is still successful for tailoring,
               but excluded from successful_items and reported in warnings
        - 7.5: Return machine-consumable per-item fields
        - 8.1: Request-level failures return top-level VALIDATION_ERROR
        - 8.5: Top-level error object includes retryable
    """
    try:
        request = CareerTailorRequest.model_validate(args)

        # Validate request-level parameters (Requirements 1.1-1.6)
        # Extract known parameters and pass rest as kwargs to catch unknown fields
        known_params = {
            "items",
            "force",
            "full_resume_path",
            "resume_template_path",
            "applications_dir",
            "pdflatex_cmd",
        }
        unknown_params = {k: v for k, v in args.items() if k not in known_params}

        (items, force, full_resume_path, resume_template_path, applications_dir, pdflatex_cmd) = (
            validate_career_tailor_batch_parameters(
                items=request.items,
                force=request.force,
                full_resume_path=request.full_resume_path,
                resume_template_path=request.resume_template_path,
                applications_dir=request.applications_dir,
                pdflatex_cmd=request.pdflatex_cmd,
                **unknown_params,
            )
        )

        # Apply defaults for optional parameters
        full_resume_path = full_resume_path or DEFAULT_FULL_RESUME_PATH
        resume_template_path = resume_template_path or DEFAULT_RESUME_TEMPLATE_PATH
        applications_dir = applications_dir or DEFAULT_APPLICATIONS_DIR
        pdflatex_cmd = pdflatex_cmd or DEFAULT_PDFLATEX_CMD

        # Generate run_id
        run_id = generate_run_id("tailor")

        # Process each item in input order (Requirements 2.1, 2.2, 2.3, 2.5)
        results: List[Dict[str, Any]] = []
        warnings: List[str] = []

        for item in items:
            result = process_item_tailoring(
                item=item,
                force=force,
                full_resume_path=full_resume_path,
                resume_template_path=resume_template_path,
                applications_dir=applications_dir,
                pdflatex_cmd=pdflatex_cmd,
            )
            results.append(result)

        # Aggregate counts (Requirement 2.4)
        total_count = len(results)
        success_count = sum(1 for r in results if r["success"])
        failed_count = sum(1 for r in results if not r["success"])

        # Build successful_items handoff payload (Requirements 7.1-7.4)
        successful_items: List[Dict[str, Any]] = []

        for result in results:
            if result["success"]:
                # Check if job_db_id is available
                if "job_db_id" in result:
                    # Include in successful_items for downstream finalize
                    successful_items.append(
                        {
                            "id": result["job_db_id"],
                            "tracker_path": result["tracker_path"],
                            "resume_pdf_path": result["resume_pdf_path"],
                        }
                    )
                else:
                    # Successful tailoring but no job_db_id - add warning
                    warnings.append(
                        f"Item {result['tracker_path']} succeeded but has no job_db_id; "
                        f"excluded from successful_items"
                    )

        # Build response
        return CareerTailorResponse(
            run_id=run_id,
            total_count=total_count,
            success_count=success_count,
            failed_count=failed_count,
            results=results,
            successful_items=successful_items,
            warnings=warnings or None,
        ).model_dump(exclude_none=True)

    except ValidationError as e:
        raise map_pydantic_validation_error(e) from e

    except ToolError:
        # ToolError already has proper error code - re-raise
        raise

    except Exception as e:
        # Unexpected error - wrap as INTERNAL_ERROR
        raise create_internal_error(
            f"Unexpected error in career_tailor: {sanitize_error_message(e)}"
        ) from e
