"""
Transition policy validation for update_tracker_status tool.

This module enforces tracker status transition rules:
- Noop when target equals current status
- Core forward transitions (Reviewed -> Resume Written, Resume Written -> Applied)
- Terminal outcomes (Rejected, Ghosted) allowed from any status
- Force bypass with warning for policy violations
"""

from typing import Dict, Any, Optional, List
from models.errors import create_validation_error


# Terminal statuses that can be reached from any current status
TERMINAL_STATUSES = {"Rejected", "Ghosted"}

# Core forward transitions: current_status -> allowed_next_status
CORE_TRANSITIONS = {"Reviewed": "Resume Written", "Resume Written": "Applied"}


class TransitionResult:
    """Result of a transition policy check."""

    def __init__(
        self,
        allowed: bool,
        is_noop: bool = False,
        error_message: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ):
        """
        Initialize a transition result.

        Args:
            allowed: Whether the transition is allowed
            is_noop: Whether this is a no-op (target == current)
            error_message: Error message if transition is blocked
            warnings: List of warning messages (e.g., for force bypass)
        """
        self.allowed = allowed
        self.is_noop = is_noop
        self.error_message = error_message
        self.warnings = warnings or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        result = {"allowed": self.allowed, "is_noop": self.is_noop}
        if self.error_message:
            result["error_message"] = self.error_message
        if self.warnings:
            result["warnings"] = self.warnings
        return result


def validate_transition(
    current_status: str, target_status: str, force: bool = False
) -> TransitionResult:
    """
    Validate a tracker status transition according to policy rules.

    Policy rules:
    1. If target_status == current_status, return success with is_noop=True
    2. Core forward transitions are always allowed:
       - Reviewed -> Resume Written
       - Resume Written -> Applied
    3. Terminal outcomes (Rejected, Ghosted) are allowed from any status
    4. Other transitions are policy violations:
       - If force=False, block the transition
       - If force=True, allow with warning

    Args:
        current_status: The current tracker status
        target_status: The desired target status
        force: Whether to bypass policy violations with warning

    Returns:
        TransitionResult indicating whether transition is allowed,
        with optional error message or warnings

    Requirements:
        - 4.1: When target_status equals current status, return success with action noop
        - 4.2: Apply transition checks for non-terminal progression statuses
        - 4.3: Allow terminal outcomes (Rejected, Ghosted) from any current status
        - 4.4: When transition violates policy and force=false, return VALIDATION_ERROR
        - 4.5: When force=true, allow policy-violating transition with warning

    Examples:
        >>> # Noop case
        >>> result = validate_transition("Reviewed", "Reviewed")
        >>> result.allowed
        True
        >>> result.is_noop
        True

        >>> # Core forward transition
        >>> result = validate_transition("Reviewed", "Resume Written")
        >>> result.allowed
        True
        >>> result.is_noop
        False

        >>> # Terminal outcome from any status
        >>> result = validate_transition("Reviewed", "Rejected")
        >>> result.allowed
        True

        >>> # Policy violation without force
        >>> result = validate_transition("Applied", "Reviewed")
        >>> result.allowed
        False
        >>> result.error_message is not None
        True

        >>> # Policy violation with force
        >>> result = validate_transition("Applied", "Reviewed", force=True)
        >>> result.allowed
        True
        >>> len(result.warnings) > 0
        True
    """
    # Rule 1: Noop when target == current (Requirement 4.1)
    if target_status == current_status:
        return TransitionResult(allowed=True, is_noop=True)

    # Rule 2: Core forward transitions (Requirement 4.2)
    if current_status in CORE_TRANSITIONS:
        if CORE_TRANSITIONS[current_status] == target_status:
            return TransitionResult(allowed=True, is_noop=False)

    # Rule 3: Terminal outcomes allowed from any status (Requirement 4.3)
    if target_status in TERMINAL_STATUSES:
        return TransitionResult(allowed=True, is_noop=False)

    # Rule 4: Policy violation handling (Requirements 4.4, 4.5)
    error_msg = (
        f"Transition from '{current_status}' to '{target_status}' "
        f"violates policy. Allowed transitions from '{current_status}': "
    )

    # Build list of allowed transitions for this status
    allowed_transitions = []
    if current_status in CORE_TRANSITIONS:
        allowed_transitions.append(CORE_TRANSITIONS[current_status])
    allowed_transitions.extend(TERMINAL_STATUSES)

    error_msg += ", ".join(f"'{s}'" for s in sorted(allowed_transitions))

    if force:
        # Allow with warning (Requirement 4.5)
        warning = (
            f"Force bypass: Transition from '{current_status}' to '{target_status}' "
            f"violates policy but was allowed due to force=true"
        )
        return TransitionResult(allowed=True, is_noop=False, warnings=[warning])
    else:
        # Block transition (Requirement 4.4)
        return TransitionResult(allowed=False, error_message=error_msg)


def check_transition_or_raise(
    current_status: str, target_status: str, force: bool = False
) -> TransitionResult:
    """
    Validate transition and raise ToolError if blocked.

    This is a convenience wrapper around validate_transition that raises
    a ToolError with VALIDATION_ERROR code when the transition is not allowed.

    Args:
        current_status: The current tracker status
        target_status: The desired target status
        force: Whether to bypass policy violations with warning

    Returns:
        TransitionResult if transition is allowed (including noop and force bypass)

    Raises:
        ToolError: With VALIDATION_ERROR code if transition is blocked

    Requirements:
        - 4.4: When transition violates policy and force=false, return VALIDATION_ERROR
        - 10.1: Request-level input validation failures return VALIDATION_ERROR

    Examples:
        >>> # Allowed transition
        >>> result = check_transition_or_raise("Reviewed", "Resume Written")
        >>> result.allowed
        True

        >>> # Blocked transition
        >>> try:
        ...     check_transition_or_raise("Applied", "Reviewed")
        ... except Exception as e:
        ...     print(e.code)
        VALIDATION_ERROR
    """
    result = validate_transition(current_status, target_status, force)

    if not result.allowed:
        raise create_validation_error(result.error_message)

    return result
