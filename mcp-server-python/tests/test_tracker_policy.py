"""
Unit tests for tracker transition policy validation.

Tests transition policy rules for update_tracker_status tool.
"""

import pytest
from models.errors import ErrorCode, ToolError
from models.status import JobTrackerStatus
from utils.tracker_policy import (
    CORE_TRANSITIONS,
    TERMINAL_STATUSES,
    TransitionResult,
    check_transition_or_raise,
    validate_transition,
)


class TestTransitionResult:
    """Tests for TransitionResult class."""

    def test_allowed_transition_result(self):
        """Test creating an allowed transition result."""
        result = TransitionResult(allowed=True, is_noop=False)
        assert result.allowed is True
        assert result.is_noop is False
        assert result.error_message is None
        assert result.warnings == []

    def test_noop_transition_result(self):
        """Test creating a noop transition result."""
        result = TransitionResult(allowed=True, is_noop=True)
        assert result.allowed is True
        assert result.is_noop is True
        assert result.error_message is None
        assert result.warnings == []

    def test_blocked_transition_result(self):
        """Test creating a blocked transition result with error message."""
        result = TransitionResult(allowed=False, error_message="Transition not allowed")
        assert result.allowed is False
        assert result.is_noop is False
        assert result.error_message == "Transition not allowed"
        assert result.warnings == []

    def test_transition_result_with_warnings(self):
        """Test creating a transition result with warnings."""
        warnings = ["Force bypass applied"]
        result = TransitionResult(allowed=True, is_noop=False, warnings=warnings)
        assert result.allowed is True
        assert result.warnings == warnings

    def test_to_dict_allowed(self):
        """Test converting allowed result to dictionary."""
        result = TransitionResult(allowed=True, is_noop=False)
        data = result.to_dict()
        assert data["allowed"] is True
        assert data["is_noop"] is False
        assert "error_message" not in data
        assert "warnings" not in data

    def test_to_dict_with_error(self):
        """Test converting blocked result to dictionary."""
        result = TransitionResult(allowed=False, error_message="Not allowed")
        data = result.to_dict()
        assert data["allowed"] is False
        assert data["error_message"] == "Not allowed"

    def test_to_dict_with_warnings(self):
        """Test converting result with warnings to dictionary."""
        result = TransitionResult(allowed=True, warnings=["Warning message"])
        data = result.to_dict()
        assert data["warnings"] == ["Warning message"]


class TestValidateTransitionNoop:
    """Tests for noop transitions (target == current)."""

    def test_noop_reviewed_to_reviewed(self):
        """Test noop when staying in Reviewed status."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.REVIEWED)
        assert result.allowed is True
        assert result.is_noop is True
        assert result.error_message is None
        assert result.warnings == []

    def test_noop_resume_written_to_resume_written(self):
        """Test noop when staying in Resume Written status."""
        result = validate_transition(
            JobTrackerStatus.RESUME_WRITTEN, JobTrackerStatus.RESUME_WRITTEN
        )
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_applied_to_applied(self):
        """Test noop when staying in Applied status."""
        result = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.APPLIED)
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_interview_to_interview(self):
        """Test noop when staying in Interview status."""
        result = validate_transition(JobTrackerStatus.INTERVIEW, JobTrackerStatus.INTERVIEW)
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_offer_to_offer(self):
        """Test noop when staying in Offer status."""
        result = validate_transition(JobTrackerStatus.OFFER, JobTrackerStatus.OFFER)
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_rejected_to_rejected(self):
        """Test noop when staying in Rejected status."""
        result = validate_transition(JobTrackerStatus.REJECTED, JobTrackerStatus.REJECTED)
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_ghosted_to_ghosted(self):
        """Test noop when staying in Ghosted status."""
        result = validate_transition(JobTrackerStatus.GHOSTED, JobTrackerStatus.GHOSTED)
        assert result.allowed is True
        assert result.is_noop is True


class TestValidateTransitionCoreForward:
    """Tests for core forward transitions."""

    def test_reviewed_to_resume_written(self):
        """Test allowed transition from Reviewed to Resume Written."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.RESUME_WRITTEN)
        assert result.allowed is True
        assert result.is_noop is False
        assert result.error_message is None
        assert result.warnings == []

    def test_resume_written_to_applied(self):
        """Test allowed transition from Resume Written to Applied."""
        result = validate_transition(JobTrackerStatus.RESUME_WRITTEN, JobTrackerStatus.APPLIED)
        assert result.allowed is True
        assert result.is_noop is False
        assert result.error_message is None
        assert result.warnings == []


class TestValidateTransitionTerminalOutcomes:
    """Tests for terminal outcome transitions (Rejected, Ghosted)."""

    def test_reviewed_to_rejected(self):
        """Test allowed transition from Reviewed to Rejected."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.REJECTED)
        assert result.allowed is True
        assert result.is_noop is False
        assert result.warnings == []

    def test_reviewed_to_ghosted(self):
        """Test allowed transition from Reviewed to Ghosted."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.GHOSTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_resume_written_to_rejected(self):
        """Test allowed transition from Resume Written to Rejected."""
        result = validate_transition(JobTrackerStatus.RESUME_WRITTEN, JobTrackerStatus.REJECTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_resume_written_to_ghosted(self):
        """Test allowed transition from Resume Written to Ghosted."""
        result = validate_transition(JobTrackerStatus.RESUME_WRITTEN, JobTrackerStatus.GHOSTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_applied_to_rejected(self):
        """Test allowed transition from Applied to Rejected."""
        result = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.REJECTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_applied_to_ghosted(self):
        """Test allowed transition from Applied to Ghosted."""
        result = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.GHOSTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_interview_to_rejected(self):
        """Test allowed transition from Interview to Rejected."""
        result = validate_transition(JobTrackerStatus.INTERVIEW, JobTrackerStatus.REJECTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_interview_to_ghosted(self):
        """Test allowed transition from Interview to Ghosted."""
        result = validate_transition(JobTrackerStatus.INTERVIEW, JobTrackerStatus.GHOSTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_offer_to_rejected(self):
        """Test allowed transition from Offer to Rejected."""
        result = validate_transition(JobTrackerStatus.OFFER, JobTrackerStatus.REJECTED)
        assert result.allowed is True
        assert result.is_noop is False

    def test_offer_to_ghosted(self):
        """Test allowed transition from Offer to Ghosted."""
        result = validate_transition(JobTrackerStatus.OFFER, JobTrackerStatus.GHOSTED)
        assert result.allowed is True
        assert result.is_noop is False


class TestValidateTransitionPolicyViolations:
    """Tests for policy violations without force flag."""

    def test_applied_to_reviewed_blocked(self):
        """Test blocked backward transition from Applied to Reviewed."""
        result = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED)
        assert result.allowed is False
        assert result.is_noop is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message
        assert "Applied" in result.error_message
        assert "Reviewed" in result.error_message

    def test_resume_written_to_reviewed_blocked(self):
        """Test blocked backward transition from Resume Written to Reviewed."""
        result = validate_transition(JobTrackerStatus.RESUME_WRITTEN, JobTrackerStatus.REVIEWED)
        assert result.allowed is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message

    def test_applied_to_resume_written_blocked(self):
        """Test blocked backward transition from Applied to Resume Written."""
        result = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.RESUME_WRITTEN)
        assert result.allowed is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message

    def test_reviewed_to_applied_blocked(self):
        """Test blocked skip transition from Reviewed to Applied."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.APPLIED)
        assert result.allowed is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message

    def test_reviewed_to_interview_blocked(self):
        """Test blocked skip transition from Reviewed to Interview."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.INTERVIEW)
        assert result.allowed is False
        assert result.error_message is not None

    def test_reviewed_to_offer_blocked(self):
        """Test blocked skip transition from Reviewed to Offer."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.OFFER)
        assert result.allowed is False
        assert result.error_message is not None

    def test_applied_to_interview_blocked(self):
        """Test blocked transition from Applied to Interview (not in core)."""
        result = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.INTERVIEW)
        assert result.allowed is False
        assert result.error_message is not None

    def test_interview_to_applied_blocked(self):
        """Test blocked backward transition from Interview to Applied."""
        result = validate_transition(JobTrackerStatus.INTERVIEW, JobTrackerStatus.APPLIED)
        assert result.allowed is False
        assert result.error_message is not None

    def test_error_message_includes_allowed_transitions(self):
        """Test that error message includes allowed transitions."""
        result = validate_transition(JobTrackerStatus.REVIEWED, JobTrackerStatus.APPLIED)
        assert result.error_message is not None
        # Should mention Resume Written as the allowed forward transition
        assert JobTrackerStatus.RESUME_WRITTEN.value in result.error_message
        # Should mention terminal outcomes
        assert (
            JobTrackerStatus.REJECTED.value in result.error_message
            or JobTrackerStatus.GHOSTED.value in result.error_message
        )


class TestValidateTransitionForceBypass:
    """Tests for force bypass behavior."""

    def test_force_bypass_applied_to_reviewed(self):
        """Test force bypass allows backward transition."""
        result = validate_transition(
            JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED, force=True
        )
        assert result.allowed is True
        assert result.is_noop is False
        assert result.error_message is None
        assert len(result.warnings) > 0
        assert "Force bypass" in result.warnings[0]
        assert "Applied" in result.warnings[0]
        assert "Reviewed" in result.warnings[0]

    def test_force_bypass_resume_written_to_reviewed(self):
        """Test force bypass allows backward transition."""
        result = validate_transition(
            JobTrackerStatus.RESUME_WRITTEN, JobTrackerStatus.REVIEWED, force=True
        )
        assert result.allowed is True
        assert len(result.warnings) > 0
        assert "Force bypass" in result.warnings[0]

    def test_force_bypass_reviewed_to_applied(self):
        """Test force bypass allows skip transition."""
        result = validate_transition(
            JobTrackerStatus.REVIEWED, JobTrackerStatus.APPLIED, force=True
        )
        assert result.allowed is True
        assert len(result.warnings) > 0
        assert "Force bypass" in result.warnings[0]

    def test_force_bypass_reviewed_to_interview(self):
        """Test force bypass allows skip transition."""
        result = validate_transition(
            JobTrackerStatus.REVIEWED, JobTrackerStatus.INTERVIEW, force=True
        )
        assert result.allowed is True
        assert len(result.warnings) > 0

    def test_force_bypass_warning_message_clarity(self):
        """Test that force bypass warning is clear and descriptive."""
        result = validate_transition(
            JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED, force=True
        )
        warning = result.warnings[0]
        assert "Force bypass" in warning
        assert "violates policy" in warning
        assert "force=true" in warning
        assert "Applied" in warning
        assert "Reviewed" in warning

    def test_force_does_not_affect_allowed_transitions(self):
        """Test that force flag doesn't add warnings to allowed transitions."""
        # Core forward transition with force should not have warnings
        result = validate_transition(
            JobTrackerStatus.REVIEWED, JobTrackerStatus.RESUME_WRITTEN, force=True
        )
        assert result.allowed is True
        assert result.warnings == []

        # Terminal outcome with force should not have warnings
        result = validate_transition(
            JobTrackerStatus.REVIEWED, JobTrackerStatus.REJECTED, force=True
        )
        assert result.allowed is True
        assert result.warnings == []

        # Noop with force should not have warnings
        result = validate_transition(
            JobTrackerStatus.REVIEWED, JobTrackerStatus.REVIEWED, force=True
        )
        assert result.allowed is True
        assert result.warnings == []


class TestCheckTransitionOrRaise:
    """Tests for check_transition_or_raise convenience function."""

    def test_allowed_transition_returns_result(self):
        """Test that allowed transition returns result without raising."""
        result = check_transition_or_raise(
            JobTrackerStatus.REVIEWED, JobTrackerStatus.RESUME_WRITTEN
        )
        assert result.allowed is True
        assert result.is_noop is False

    def test_noop_transition_returns_result(self):
        """Test that noop transition returns result without raising."""
        result = check_transition_or_raise(JobTrackerStatus.REVIEWED, JobTrackerStatus.REVIEWED)
        assert result.allowed is True
        assert result.is_noop is True

    def test_terminal_outcome_returns_result(self):
        """Test that terminal outcome returns result without raising."""
        result = check_transition_or_raise(JobTrackerStatus.REVIEWED, JobTrackerStatus.REJECTED)
        assert result.allowed is True

    def test_blocked_transition_raises_tool_error(self):
        """Test that blocked transition raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            check_transition_or_raise(JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "violates policy" in error.message
        assert not error.retryable

    def test_force_bypass_returns_result_with_warning(self):
        """Test that force bypass returns result without raising."""
        result = check_transition_or_raise(
            JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED, force=True
        )
        assert result.allowed is True
        assert len(result.warnings) > 0

    def test_error_message_matches_validation_result(self):
        """Test that raised error message matches validation result."""
        # Get the error message from validate_transition
        validation_result = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED)
        expected_message = validation_result.error_message

        # Check that check_transition_or_raise raises with same message
        with pytest.raises(ToolError) as exc_info:
            check_transition_or_raise(JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED)

        error = exc_info.value
        assert error.message == expected_message


class TestTransitionPolicyConstants:
    """Tests for transition policy constants."""

    def test_terminal_statuses_set(self):
        """Test that terminal statuses are correctly defined."""
        assert JobTrackerStatus.REJECTED in TERMINAL_STATUSES
        assert JobTrackerStatus.GHOSTED in TERMINAL_STATUSES
        assert len(TERMINAL_STATUSES) == 2

    def test_core_transitions_dict(self):
        """Test that core transitions are correctly defined."""
        assert CORE_TRANSITIONS[JobTrackerStatus.REVIEWED] == JobTrackerStatus.RESUME_WRITTEN
        assert CORE_TRANSITIONS[JobTrackerStatus.RESUME_WRITTEN] == JobTrackerStatus.APPLIED
        assert len(CORE_TRANSITIONS) == 2

    def test_core_transitions_keys_are_strings(self):
        """Test that core transition keys are strings."""
        for key in CORE_TRANSITIONS.keys():
            assert isinstance(key, str)

    def test_core_transitions_values_are_strings(self):
        """Test that core transition values are strings."""
        for value in CORE_TRANSITIONS.values():
            assert isinstance(value, str)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_force_false_explicit(self):
        """Test that force=False behaves same as default."""
        result_default = validate_transition(JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED)
        result_explicit = validate_transition(
            JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED, force=False
        )

        assert result_default.allowed == result_explicit.allowed
        assert result_default.is_noop == result_explicit.is_noop
        assert result_default.error_message == result_explicit.error_message

    def test_multiple_violations_same_behavior(self):
        """Test that different violations have consistent behavior."""
        # All these should be blocked without force
        violations = [
            (JobTrackerStatus.APPLIED, JobTrackerStatus.REVIEWED),
            (JobTrackerStatus.RESUME_WRITTEN, JobTrackerStatus.REVIEWED),
            (JobTrackerStatus.REVIEWED, JobTrackerStatus.APPLIED),
            (JobTrackerStatus.INTERVIEW, JobTrackerStatus.APPLIED),
        ]

        for current, target in violations:
            result = validate_transition(current, target)
            assert result.allowed is False
            assert result.error_message is not None

    def test_all_statuses_can_reach_terminal(self):
        """Test that all statuses can transition to terminal outcomes."""
        for status in JobTrackerStatus:
            # Should be able to reach Rejected
            result = validate_transition(status, JobTrackerStatus.REJECTED)
            assert result.allowed is True

            # Should be able to reach Ghosted
            result = validate_transition(status, JobTrackerStatus.GHOSTED)
            assert result.allowed is True
