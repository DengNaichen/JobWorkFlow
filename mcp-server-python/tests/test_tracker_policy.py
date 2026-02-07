"""
Unit tests for tracker transition policy validation.

Tests transition policy rules for update_tracker_status tool.
"""

import pytest
from utils.tracker_policy import (
    validate_transition,
    check_transition_or_raise,
    TransitionResult,
    TERMINAL_STATUSES,
    CORE_TRANSITIONS,
)
from models.errors import ToolError, ErrorCode


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
        result = validate_transition("Reviewed", "Reviewed")
        assert result.allowed is True
        assert result.is_noop is True
        assert result.error_message is None
        assert result.warnings == []

    def test_noop_resume_written_to_resume_written(self):
        """Test noop when staying in Resume Written status."""
        result = validate_transition("Resume Written", "Resume Written")
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_applied_to_applied(self):
        """Test noop when staying in Applied status."""
        result = validate_transition("Applied", "Applied")
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_interview_to_interview(self):
        """Test noop when staying in Interview status."""
        result = validate_transition("Interview", "Interview")
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_offer_to_offer(self):
        """Test noop when staying in Offer status."""
        result = validate_transition("Offer", "Offer")
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_rejected_to_rejected(self):
        """Test noop when staying in Rejected status."""
        result = validate_transition("Rejected", "Rejected")
        assert result.allowed is True
        assert result.is_noop is True

    def test_noop_ghosted_to_ghosted(self):
        """Test noop when staying in Ghosted status."""
        result = validate_transition("Ghosted", "Ghosted")
        assert result.allowed is True
        assert result.is_noop is True


class TestValidateTransitionCoreForward:
    """Tests for core forward transitions."""

    def test_reviewed_to_resume_written(self):
        """Test allowed transition from Reviewed to Resume Written."""
        result = validate_transition("Reviewed", "Resume Written")
        assert result.allowed is True
        assert result.is_noop is False
        assert result.error_message is None
        assert result.warnings == []

    def test_resume_written_to_applied(self):
        """Test allowed transition from Resume Written to Applied."""
        result = validate_transition("Resume Written", "Applied")
        assert result.allowed is True
        assert result.is_noop is False
        assert result.error_message is None
        assert result.warnings == []


class TestValidateTransitionTerminalOutcomes:
    """Tests for terminal outcome transitions (Rejected, Ghosted)."""

    def test_reviewed_to_rejected(self):
        """Test allowed transition from Reviewed to Rejected."""
        result = validate_transition("Reviewed", "Rejected")
        assert result.allowed is True
        assert result.is_noop is False
        assert result.warnings == []

    def test_reviewed_to_ghosted(self):
        """Test allowed transition from Reviewed to Ghosted."""
        result = validate_transition("Reviewed", "Ghosted")
        assert result.allowed is True
        assert result.is_noop is False

    def test_resume_written_to_rejected(self):
        """Test allowed transition from Resume Written to Rejected."""
        result = validate_transition("Resume Written", "Rejected")
        assert result.allowed is True
        assert result.is_noop is False

    def test_resume_written_to_ghosted(self):
        """Test allowed transition from Resume Written to Ghosted."""
        result = validate_transition("Resume Written", "Ghosted")
        assert result.allowed is True
        assert result.is_noop is False

    def test_applied_to_rejected(self):
        """Test allowed transition from Applied to Rejected."""
        result = validate_transition("Applied", "Rejected")
        assert result.allowed is True
        assert result.is_noop is False

    def test_applied_to_ghosted(self):
        """Test allowed transition from Applied to Ghosted."""
        result = validate_transition("Applied", "Ghosted")
        assert result.allowed is True
        assert result.is_noop is False

    def test_interview_to_rejected(self):
        """Test allowed transition from Interview to Rejected."""
        result = validate_transition("Interview", "Rejected")
        assert result.allowed is True
        assert result.is_noop is False

    def test_interview_to_ghosted(self):
        """Test allowed transition from Interview to Ghosted."""
        result = validate_transition("Interview", "Ghosted")
        assert result.allowed is True
        assert result.is_noop is False

    def test_offer_to_rejected(self):
        """Test allowed transition from Offer to Rejected."""
        result = validate_transition("Offer", "Rejected")
        assert result.allowed is True
        assert result.is_noop is False

    def test_offer_to_ghosted(self):
        """Test allowed transition from Offer to Ghosted."""
        result = validate_transition("Offer", "Ghosted")
        assert result.allowed is True
        assert result.is_noop is False


class TestValidateTransitionPolicyViolations:
    """Tests for policy violations without force flag."""

    def test_applied_to_reviewed_blocked(self):
        """Test blocked backward transition from Applied to Reviewed."""
        result = validate_transition("Applied", "Reviewed")
        assert result.allowed is False
        assert result.is_noop is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message
        assert "Applied" in result.error_message
        assert "Reviewed" in result.error_message

    def test_resume_written_to_reviewed_blocked(self):
        """Test blocked backward transition from Resume Written to Reviewed."""
        result = validate_transition("Resume Written", "Reviewed")
        assert result.allowed is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message

    def test_applied_to_resume_written_blocked(self):
        """Test blocked backward transition from Applied to Resume Written."""
        result = validate_transition("Applied", "Resume Written")
        assert result.allowed is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message

    def test_reviewed_to_applied_blocked(self):
        """Test blocked skip transition from Reviewed to Applied."""
        result = validate_transition("Reviewed", "Applied")
        assert result.allowed is False
        assert result.error_message is not None
        assert "violates policy" in result.error_message

    def test_reviewed_to_interview_blocked(self):
        """Test blocked skip transition from Reviewed to Interview."""
        result = validate_transition("Reviewed", "Interview")
        assert result.allowed is False
        assert result.error_message is not None

    def test_reviewed_to_offer_blocked(self):
        """Test blocked skip transition from Reviewed to Offer."""
        result = validate_transition("Reviewed", "Offer")
        assert result.allowed is False
        assert result.error_message is not None

    def test_applied_to_interview_blocked(self):
        """Test blocked transition from Applied to Interview (not in core)."""
        result = validate_transition("Applied", "Interview")
        assert result.allowed is False
        assert result.error_message is not None

    def test_interview_to_applied_blocked(self):
        """Test blocked backward transition from Interview to Applied."""
        result = validate_transition("Interview", "Applied")
        assert result.allowed is False
        assert result.error_message is not None

    def test_error_message_includes_allowed_transitions(self):
        """Test that error message includes allowed transitions."""
        result = validate_transition("Reviewed", "Applied")
        assert result.error_message is not None
        # Should mention Resume Written as the allowed forward transition
        assert "Resume Written" in result.error_message
        # Should mention terminal outcomes
        assert "Rejected" in result.error_message or "Ghosted" in result.error_message


class TestValidateTransitionForceBypass:
    """Tests for force bypass behavior."""

    def test_force_bypass_applied_to_reviewed(self):
        """Test force bypass allows backward transition."""
        result = validate_transition("Applied", "Reviewed", force=True)
        assert result.allowed is True
        assert result.is_noop is False
        assert result.error_message is None
        assert len(result.warnings) > 0
        assert "Force bypass" in result.warnings[0]
        assert "Applied" in result.warnings[0]
        assert "Reviewed" in result.warnings[0]

    def test_force_bypass_resume_written_to_reviewed(self):
        """Test force bypass allows backward transition."""
        result = validate_transition("Resume Written", "Reviewed", force=True)
        assert result.allowed is True
        assert len(result.warnings) > 0
        assert "Force bypass" in result.warnings[0]

    def test_force_bypass_reviewed_to_applied(self):
        """Test force bypass allows skip transition."""
        result = validate_transition("Reviewed", "Applied", force=True)
        assert result.allowed is True
        assert len(result.warnings) > 0
        assert "Force bypass" in result.warnings[0]

    def test_force_bypass_reviewed_to_interview(self):
        """Test force bypass allows skip transition."""
        result = validate_transition("Reviewed", "Interview", force=True)
        assert result.allowed is True
        assert len(result.warnings) > 0

    def test_force_bypass_warning_message_clarity(self):
        """Test that force bypass warning is clear and descriptive."""
        result = validate_transition("Applied", "Reviewed", force=True)
        warning = result.warnings[0]
        assert "Force bypass" in warning
        assert "violates policy" in warning
        assert "force=true" in warning
        assert "Applied" in warning
        assert "Reviewed" in warning

    def test_force_does_not_affect_allowed_transitions(self):
        """Test that force flag doesn't add warnings to allowed transitions."""
        # Core forward transition with force should not have warnings
        result = validate_transition("Reviewed", "Resume Written", force=True)
        assert result.allowed is True
        assert result.warnings == []

        # Terminal outcome with force should not have warnings
        result = validate_transition("Reviewed", "Rejected", force=True)
        assert result.allowed is True
        assert result.warnings == []

        # Noop with force should not have warnings
        result = validate_transition("Reviewed", "Reviewed", force=True)
        assert result.allowed is True
        assert result.warnings == []


class TestCheckTransitionOrRaise:
    """Tests for check_transition_or_raise convenience function."""

    def test_allowed_transition_returns_result(self):
        """Test that allowed transition returns result without raising."""
        result = check_transition_or_raise("Reviewed", "Resume Written")
        assert result.allowed is True
        assert result.is_noop is False

    def test_noop_transition_returns_result(self):
        """Test that noop transition returns result without raising."""
        result = check_transition_or_raise("Reviewed", "Reviewed")
        assert result.allowed is True
        assert result.is_noop is True

    def test_terminal_outcome_returns_result(self):
        """Test that terminal outcome returns result without raising."""
        result = check_transition_or_raise("Reviewed", "Rejected")
        assert result.allowed is True

    def test_blocked_transition_raises_tool_error(self):
        """Test that blocked transition raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            check_transition_or_raise("Applied", "Reviewed")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "violates policy" in error.message
        assert not error.retryable

    def test_force_bypass_returns_result_with_warning(self):
        """Test that force bypass returns result without raising."""
        result = check_transition_or_raise("Applied", "Reviewed", force=True)
        assert result.allowed is True
        assert len(result.warnings) > 0

    def test_error_message_matches_validation_result(self):
        """Test that raised error message matches validation result."""
        # Get the error message from validate_transition
        validation_result = validate_transition("Applied", "Reviewed")
        expected_message = validation_result.error_message

        # Check that check_transition_or_raise raises with same message
        with pytest.raises(ToolError) as exc_info:
            check_transition_or_raise("Applied", "Reviewed")

        error = exc_info.value
        assert error.message == expected_message


class TestTransitionPolicyConstants:
    """Tests for transition policy constants."""

    def test_terminal_statuses_set(self):
        """Test that terminal statuses are correctly defined."""
        assert "Rejected" in TERMINAL_STATUSES
        assert "Ghosted" in TERMINAL_STATUSES
        assert len(TERMINAL_STATUSES) == 2

    def test_core_transitions_dict(self):
        """Test that core transitions are correctly defined."""
        assert CORE_TRANSITIONS["Reviewed"] == "Resume Written"
        assert CORE_TRANSITIONS["Resume Written"] == "Applied"
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
        result_default = validate_transition("Applied", "Reviewed")
        result_explicit = validate_transition("Applied", "Reviewed", force=False)

        assert result_default.allowed == result_explicit.allowed
        assert result_default.is_noop == result_explicit.is_noop
        assert result_default.error_message == result_explicit.error_message

    def test_multiple_violations_same_behavior(self):
        """Test that different violations have consistent behavior."""
        # All these should be blocked without force
        violations = [
            ("Applied", "Reviewed"),
            ("Resume Written", "Reviewed"),
            ("Reviewed", "Applied"),
            ("Interview", "Applied"),
        ]

        for current, target in violations:
            result = validate_transition(current, target)
            assert result.allowed is False
            assert result.error_message is not None

    def test_all_statuses_can_reach_terminal(self):
        """Test that all statuses can transition to terminal outcomes."""
        all_statuses = [
            "Reviewed",
            "Resume Written",
            "Applied",
            "Interview",
            "Offer",
            "Rejected",
            "Ghosted",
        ]

        for status in all_statuses:
            # Should be able to reach Rejected
            result = validate_transition(status, "Rejected")
            assert result.allowed is True

            # Should be able to reach Ghosted
            result = validate_transition(status, "Ghosted")
            assert result.allowed is True
