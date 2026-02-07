"""
Main MCP tool handler for update_tracker_status.

Orchestrates validation, parsing, transition checks, guardrails, and write flow
to provide a safe tracker status update tool with Resume Written guardrails.
"""

from typing import Dict, Any, Optional, List

from pydantic import ValidationError

from schemas.update_tracker_status import UpdateTrackerStatusRequest, UpdateTrackerStatusResponse
from utils.pydantic_error_mapper import map_pydantic_validation_error
from utils.validation import validate_update_tracker_status_parameters
from utils.tracker_parser import parse_tracker_with_error_mapping
from utils.tracker_policy import validate_transition
from utils.artifact_paths import resolve_artifact_paths, ArtifactPathError
from utils.finalize_validators import validate_resume_written_guardrails
from utils.tracker_sync import update_tracker_status as write_tracker_status
from models.errors import ToolError, create_validation_error, create_internal_error


def _build_response(
    tracker_path: str,
    previous_status: str,
    target_status: str,
    action: str,
    success: bool,
    dry_run: bool,
    error_message: Optional[str] = None,
    guardrail_check_passed: Optional[bool] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build structured success/blocked response payload."""
    return UpdateTrackerStatusResponse(
        tracker_path=tracker_path,
        previous_status=previous_status,
        target_status=target_status,
        action=action,
        success=success,
        dry_run=dry_run,
        error=error_message,
        guardrail_check_passed=guardrail_check_passed,
        warnings=warnings or [],
    ).model_dump(exclude_none=True)


def build_success_response(
    tracker_path: str,
    previous_status: str,
    target_status: str,
    action: str,
    dry_run: bool,
    guardrail_check_passed: Optional[bool] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a success response for tracker status update."""
    return _build_response(
        tracker_path=tracker_path,
        previous_status=previous_status,
        target_status=target_status,
        action=action,
        success=True,
        dry_run=dry_run,
        guardrail_check_passed=guardrail_check_passed,
        warnings=warnings,
    )


def build_blocked_response(
    tracker_path: str,
    previous_status: str,
    target_status: str,
    dry_run: bool,
    error_message: str,
    guardrail_check_passed: Optional[bool] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a blocked response for policy/guardrail failures."""
    return _build_response(
        tracker_path=tracker_path,
        previous_status=previous_status,
        target_status=target_status,
        action="blocked",
        success=False,
        dry_run=dry_run,
        error_message=error_message,
        guardrail_check_passed=guardrail_check_passed,
        warnings=warnings,
    )


def update_tracker_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update tracker frontmatter status with transition policy and guardrails.

    This is the main entry point for the MCP tool. It orchestrates all components:
    1. Validates input parameters (tracker_path, target_status, dry_run, force)
    2. Parses tracker file and extracts current status
    3. Checks if target equals current (noop case)
    4. Validates transition policy (with optional force bypass)
    5. If target_status='Resume Written', performs artifact guardrails
    6. If dry_run=true, returns predicted action without writing
    7. If write mode and checks pass, updates tracker status atomically
    8. Returns structured response with action and validation outcomes

    Args:
        args: Dictionary containing parameters:
            - tracker_path (str): Path to tracker markdown file
            - target_status (str): Target status value (must be in allowed set)
            - dry_run (bool, optional): Preview mode without file write (default: False)
            - force (bool, optional): Bypass transition policy with warning (default: False)

    Returns:
        Dictionary with structure (success case):
        {
            "tracker_path": str,
            "previous_status": str,
            "target_status": str,
            "action": str,              # "updated", "noop", "would_update"
            "success": true,
            "dry_run": bool,
            "guardrail_check_passed": bool,  # Present if guardrails were evaluated
            "warnings": []              # List of warning messages
        }

        Dictionary with structure (blocked case):
        {
            "tracker_path": str,
            "previous_status": str,
            "target_status": str,
            "action": "blocked",
            "success": false,
            "dry_run": bool,
            "error": str,               # Reason for blocking
            "guardrail_check_passed": bool,  # Present if guardrails were evaluated
            "warnings": []
        }

        On system error, returns:
        {
            "error": {
                "code": str,            # VALIDATION_ERROR, FILE_NOT_FOUND, INTERNAL_ERROR
                "message": str,         # Human-readable error message
                "retryable": bool       # Whether operation can be retried
            }
        }

    Requirements:
        - 1.1-1.6: Tool input interface
        - 2.1-2.5: Tracker file parsing and validation
        - 3.1-3.4: Allowed tracker status set
        - 4.1-4.5: Transition policy
        - 5.1-5.6: Resume Written guardrails
        - 6.1-6.5: Artifact path resolution
        - 7.1-7.5: File write semantics
        - 8.1-8.4: Dry-run behavior
        - 9.1-9.5: Structured response format
        - 10.1-10.6: Error handling
    """
    try:
        request = UpdateTrackerStatusRequest.model_validate(args)
        extra_fields = request.model_extra or {}

        # Step 1: Validate input parameters (Requirements 1.1-1.6)
        # This will raise ToolError with VALIDATION_ERROR if invalid
        tracker_path, target_status, dry_run, force = validate_update_tracker_status_parameters(
            tracker_path=request.tracker_path,
            target_status=request.target_status,
            dry_run=request.dry_run,
            force=request.force,
            **extra_fields,
        )

        # Step 2: Parse tracker file and extract current status (Requirements 2.1-2.5)
        # This will raise ToolError with FILE_NOT_FOUND or VALIDATION_ERROR if invalid
        tracker_data = parse_tracker_with_error_mapping(tracker_path)
        current_status = tracker_data["status"]

        # Step 3: Check for noop case (Requirement 4.1)
        if target_status == current_status:
            return build_success_response(
                tracker_path=tracker_path,
                previous_status=current_status,
                target_status=target_status,
                action="noop",
                dry_run=dry_run,
            )

        # Step 4: Validate transition policy (Requirements 4.2-4.5)
        transition_result = validate_transition(current_status, target_status, force)

        if not transition_result.allowed:
            # Transition policy violation without force - return blocked response
            # (Requirement 10.3: Policy failures as structured blocked response)
            return build_blocked_response(
                tracker_path=tracker_path,
                previous_status=current_status,
                target_status=target_status,
                dry_run=dry_run,
                error_message=transition_result.error_message,
            )

        # Collect warnings from transition (e.g., force bypass)
        warnings = transition_result.warnings.copy()

        # Step 5: If target_status='Resume Written', perform artifact guardrails
        guardrail_check_passed = None
        if target_status == "Resume Written":
            # Step 5a: Resolve artifact paths (Requirements 6.1-6.5)
            resume_path_raw = tracker_data["frontmatter"].get("resume_path")

            try:
                pdf_path, tex_path = resolve_artifact_paths(resume_path_raw)
            except ArtifactPathError as e:
                # Missing or unparsable resume_path - return top-level VALIDATION_ERROR
                # (Requirement 6.4)
                raise create_validation_error(
                    f"Cannot resolve artifact paths for Resume Written check: {str(e)}"
                ) from e

            # Step 5b: Validate Resume Written guardrails (Requirements 5.1-5.6)
            guardrail_valid, guardrail_error = validate_resume_written_guardrails(
                pdf_path, tex_path
            )
            guardrail_check_passed = guardrail_valid

            if not guardrail_valid:
                # Guardrail check failed - return blocked response
                # (Requirement 10.3: Guardrail failures as structured blocked response)
                return build_blocked_response(
                    tracker_path=tracker_path,
                    previous_status=current_status,
                    target_status=target_status,
                    dry_run=dry_run,
                    error_message=guardrail_error,
                    guardrail_check_passed=False,
                    warnings=warnings,
                )

        # Step 6: If dry_run=true, return predicted action without writing (Requirements 8.1-8.4)
        if dry_run:
            return build_success_response(
                tracker_path=tracker_path,
                previous_status=current_status,
                target_status=target_status,
                action="would_update",
                dry_run=True,
                guardrail_check_passed=guardrail_check_passed,
                warnings=warnings,
            )

        # Step 7: Write mode - update tracker status atomically (Requirements 7.1-7.5)
        write_tracker_status(tracker_path, target_status)

        # Step 8: Return success response
        return build_success_response(
            tracker_path=tracker_path,
            previous_status=current_status,
            target_status=target_status,
            action="updated",
            dry_run=False,
            guardrail_check_passed=guardrail_check_passed,
            warnings=warnings,
        )

    except ValidationError as e:
        return map_pydantic_validation_error(e).to_dict()

    except ToolError as e:
        # Known tool errors with structured error information (Requirements 10.1-10.6)
        # These are already sanitized and formatted correctly
        # Top-level errors: VALIDATION_ERROR, FILE_NOT_FOUND, INTERNAL_ERROR
        return e.to_dict()

    except Exception as e:
        # Unexpected errors - wrap in INTERNAL_ERROR (Requirement 10.4)
        # Sanitize to avoid exposing sensitive system details (Requirement 10.6)
        internal_error = create_internal_error(message=str(e), original_error=e)
        return internal_error.to_dict()
