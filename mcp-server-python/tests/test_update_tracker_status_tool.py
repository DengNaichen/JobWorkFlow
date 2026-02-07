"""
Integration tests for update_tracker_status tool.

Tests verify the complete tool workflow including validation, parsing,
transition checks, guardrails, dry-run, and atomic file operations.
"""

from pathlib import Path
import pytest
from tools.update_tracker_status import update_tracker_status


class TestUpdateTrackerStatusTool:
    """Integration tests for the update_tracker_status tool."""

    @pytest.fixture
    def test_tracker(self, tmp_path):
        """Create a test tracker file with Reviewed status."""
        # Create resume artifacts first
        resume_dir = tmp_path / "data" / "applications" / "test-app" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create resume.pdf with non-zero size
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nTest PDF content")

        # Create resume.tex without placeholders
        tex_path = resume_dir / "resume.tex"
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Experience}
Real content here
\end{document}
"""
        tex_path.write_text(tex_content)

        # Create tracker with absolute path to resume
        tracker_path = tmp_path / "test-tracker.md"
        content = f"""---
status: Reviewed
company: Amazon
job_id: "4368663835"
title: Software Engineer
resume_path: "{str(pdf_path)}"
---

## Job Description

Build scalable systems...
"""
        tracker_path.write_text(content)
        return str(tracker_path)

    @pytest.fixture
    def test_tracker_with_resume_written(self, tmp_path):
        """Create a test tracker file with Resume Written status."""
        # Create resume artifacts first
        resume_dir = tmp_path / "data" / "applications" / "test-app" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create resume.pdf with non-zero size
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nTest PDF content")

        # Create resume.tex without placeholders
        tex_path = resume_dir / "resume.tex"
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Experience}
Real content here
\end{document}
"""
        tex_path.write_text(tex_content)

        # Create tracker with absolute path to resume
        tracker_path = tmp_path / "test-tracker-written.md"
        content = f"""---
status: Resume Written
company: Meta
job_id: "4368669999"
title: Senior Engineer
resume_path: "{str(pdf_path)}"
---

## Job Description

Work on social platforms...
"""
        tracker_path.write_text(content)
        return str(tracker_path)

    @pytest.fixture
    def test_resume_with_placeholders(self, tmp_path):
        """Create test resume artifacts with placeholders in TEX."""
        resume_dir = tmp_path / "data" / "applications" / "draft-app" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create resume.pdf
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nTest PDF content")

        # Create resume.tex WITH placeholders
        tex_path = resume_dir / "resume.tex"
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Projects}
PROJECT-AI-placeholder
\section{Work}
WORK-BULLET-POINT-placeholder
\end{document}
"""
        tex_path.write_text(tex_content)

        return str(pdf_path)  # Return PDF path for use in tracker

    # ========================================================================
    # Test: Input Validation
    # ========================================================================

    def test_missing_tracker_path(self):
        """Test that missing tracker_path returns VALIDATION_ERROR."""
        result = update_tracker_status({"target_status": "Resume Written"})

        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "tracker_path" in result["error"]["message"]

    def test_missing_target_status(self, test_tracker):
        """Test that missing target_status returns VALIDATION_ERROR."""
        result = update_tracker_status({"tracker_path": test_tracker})

        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "target_status" in result["error"]["message"]

    def test_invalid_target_status(self, test_tracker):
        """Test that invalid target_status returns VALIDATION_ERROR."""
        result = update_tracker_status(
            {"tracker_path": test_tracker, "target_status": "InvalidStatus"}
        )

        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "Invalid target_status" in result["error"]["message"]

    def test_unknown_parameter(self, test_tracker):
        """Test that unknown parameters return VALIDATION_ERROR."""
        result = update_tracker_status(
            {
                "tracker_path": test_tracker,
                "target_status": "Resume Written",
                "unknown_param": "value",
            }
        )

        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "Unknown input properties" in result["error"]["message"]

    # ========================================================================
    # Test: File Not Found
    # ========================================================================

    def test_tracker_not_found(self):
        """Test that missing tracker file returns FILE_NOT_FOUND."""
        result = update_tracker_status(
            {"tracker_path": "nonexistent/tracker.md", "target_status": "Resume Written"}
        )

        assert "error" in result
        assert result["error"]["code"] == "FILE_NOT_FOUND"

    # ========================================================================
    # Test: Noop Case
    # ========================================================================

    def test_noop_same_status(self, test_tracker):
        """Test that setting status to current value returns noop."""
        result = update_tracker_status({"tracker_path": test_tracker, "target_status": "Reviewed"})

        assert result["success"] is True
        assert result["action"] == "noop"
        assert result["previous_status"] == "Reviewed"
        assert result["target_status"] == "Reviewed"
        assert result["dry_run"] is False

    # ========================================================================
    # Test: Successful Transitions
    # ========================================================================

    def test_successful_forward_transition(self, test_tracker):
        """Test successful forward transition from Reviewed to Resume Written."""
        result = update_tracker_status(
            {"tracker_path": test_tracker, "target_status": "Resume Written"}
        )

        assert result["success"] is True
        assert result["action"] == "updated"
        assert result["previous_status"] == "Reviewed"
        assert result["target_status"] == "Resume Written"
        assert result["guardrail_check_passed"] is True
        assert result["warnings"] == []

        # Verify file was actually updated
        tracker_path = Path(test_tracker)
        content = tracker_path.read_text()
        assert "status: Resume Written" in content
        # Verify body is preserved
        assert "## Job Description" in content
        assert "Build scalable systems..." in content

    def test_successful_transition_to_terminal_status(self, test_tracker):
        """Test successful transition to terminal status (Rejected)."""
        result = update_tracker_status({"tracker_path": test_tracker, "target_status": "Rejected"})

        assert result["success"] is True
        assert result["action"] == "updated"
        assert result["previous_status"] == "Reviewed"
        assert result["target_status"] == "Rejected"

        # Verify file was updated
        tracker_path = Path(test_tracker)
        content = tracker_path.read_text()
        assert "status: Rejected" in content

    def test_transition_resume_written_to_applied(self, test_tracker_with_resume_written):
        """Test successful transition from Resume Written to Applied."""
        result = update_tracker_status(
            {"tracker_path": test_tracker_with_resume_written, "target_status": "Applied"}
        )

        assert result["success"] is True
        assert result["action"] == "updated"
        assert result["previous_status"] == "Resume Written"
        assert result["target_status"] == "Applied"

    # ========================================================================
    # Test: Blocked Transitions (Policy Violations)
    # ========================================================================

    def test_blocked_backward_transition(self, test_tracker_with_resume_written):
        """Test that backward transition is blocked without force."""
        result = update_tracker_status(
            {"tracker_path": test_tracker_with_resume_written, "target_status": "Reviewed"}
        )

        assert result["success"] is False
        assert result["action"] == "blocked"
        assert "violates policy" in result["error"]

        # Verify file was NOT updated
        tracker_path = Path(test_tracker_with_resume_written)
        content = tracker_path.read_text()
        assert "status: Resume Written" in content  # Still original status

    def test_force_bypass_policy_violation(self, test_tracker_with_resume_written):
        """Test that force=true allows policy violation with warning."""
        result = update_tracker_status(
            {
                "tracker_path": test_tracker_with_resume_written,
                "target_status": "Reviewed",
                "force": True,
            }
        )

        assert result["success"] is True
        assert result["action"] == "updated"
        assert len(result["warnings"]) > 0
        assert "Force bypass" in result["warnings"][0]

        # Verify file WAS updated
        tracker_path = Path(test_tracker_with_resume_written)
        content = tracker_path.read_text()
        assert "status: Reviewed" in content

    # ========================================================================
    # Test: Resume Written Guardrails
    # ========================================================================

    def test_resume_written_blocked_missing_pdf(self, tmp_path):
        """Test that Resume Written is blocked when PDF is missing."""
        # Create tracker without resume artifacts
        tracker_path = tmp_path / "test-tracker-no-pdf.md"
        content = """---
status: Reviewed
company: TestCo
resume_path: "[[data/applications/missing/resume/resume.pdf]]"
---

## Job Description
"""
        tracker_path.write_text(content)

        result = update_tracker_status(
            {"tracker_path": str(tracker_path), "target_status": "Resume Written"}
        )

        assert result["success"] is False
        assert result["action"] == "blocked"
        assert result["guardrail_check_passed"] is False
        assert "resume.pdf" in result["error"]

    def test_resume_written_blocked_placeholder_in_tex(
        self, tmp_path, test_resume_with_placeholders
    ):
        """Test that Resume Written is blocked when TEX contains placeholders."""
        # Create tracker pointing to resume with placeholders
        tracker_path = tmp_path / "test-tracker-placeholder.md"
        content = f"""---
status: Reviewed
company: TestCo
resume_path: "{test_resume_with_placeholders}"
---

## Job Description
"""
        tracker_path.write_text(content)

        result = update_tracker_status(
            {"tracker_path": str(tracker_path), "target_status": "Resume Written"}
        )

        assert result["success"] is False
        assert result["action"] == "blocked"
        assert result["guardrail_check_passed"] is False
        assert "placeholder" in result["error"].lower()

    def test_resume_written_missing_resume_path(self, tmp_path):
        """Test that Resume Written is blocked when resume_path is missing."""
        # Create tracker without resume_path field
        tracker_path = tmp_path / "test-tracker-no-path.md"
        content = """---
status: Reviewed
company: TestCo
---

## Job Description
"""
        tracker_path.write_text(content)

        result = update_tracker_status(
            {"tracker_path": str(tracker_path), "target_status": "Resume Written"}
        )

        assert "error" in result
        # Should be top-level VALIDATION_ERROR for missing resume_path
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "artifact paths" in result["error"]["message"]

    # ========================================================================
    # Test: Dry-Run Mode
    # ========================================================================

    def test_dry_run_successful_transition(self, test_tracker):
        """Test dry-run mode returns predicted action without writing."""
        result = update_tracker_status(
            {"tracker_path": test_tracker, "target_status": "Resume Written", "dry_run": True}
        )

        assert result["success"] is True
        assert result["action"] == "would_update"
        assert result["dry_run"] is True
        assert result["guardrail_check_passed"] is True

        # Verify file was NOT updated
        tracker_path = Path(test_tracker)
        content = tracker_path.read_text()
        assert "status: Reviewed" in content  # Still original status

    def test_dry_run_blocked_transition(self, test_tracker_with_resume_written):
        """Test dry-run mode shows blocked transition without writing."""
        result = update_tracker_status(
            {
                "tracker_path": test_tracker_with_resume_written,
                "target_status": "Reviewed",
                "dry_run": True,
            }
        )

        assert result["success"] is False
        assert result["action"] == "blocked"
        assert result["dry_run"] is True
        assert "violates policy" in result["error"]

        # Verify file was NOT updated
        tracker_path = Path(test_tracker_with_resume_written)
        content = tracker_path.read_text()
        assert "status: Resume Written" in content

    def test_dry_run_guardrail_failure(self, tmp_path):
        """Test dry-run mode shows guardrail failure without writing."""
        # Create tracker without resume artifacts
        tracker_path = tmp_path / "test-tracker-dry.md"
        content = """---
status: Reviewed
company: TestCo
resume_path: "[[data/applications/missing/resume/resume.pdf]]"
---

## Job Description
"""
        tracker_path.write_text(content)

        result = update_tracker_status(
            {"tracker_path": str(tracker_path), "target_status": "Resume Written", "dry_run": True}
        )

        assert result["success"] is False
        assert result["action"] == "blocked"
        assert result["dry_run"] is True
        assert result["guardrail_check_passed"] is False

    # ========================================================================
    # Test: Content Preservation
    # ========================================================================

    def test_content_preservation(self, test_tracker):
        """Test that non-status frontmatter and body are preserved."""
        # Read original content
        tracker_path = Path(test_tracker)

        # Update status
        result = update_tracker_status(
            {"tracker_path": test_tracker, "target_status": "Resume Written"}
        )

        assert result["success"] is True

        # Read updated content
        updated_content = tracker_path.read_text()

        # Verify status changed
        assert "status: Resume Written" in updated_content
        assert "status: Reviewed" not in updated_content

        # Verify other frontmatter fields preserved
        assert "company: Amazon" in updated_content
        assert "job_id:" in updated_content and "4368663835" in updated_content
        assert "title: Software Engineer" in updated_content
        assert "resume_path:" in updated_content

        # Verify body preserved
        assert "## Job Description" in updated_content
        assert "Build scalable systems..." in updated_content

    # ========================================================================
    # Test: Response Structure
    # ========================================================================

    def test_response_structure_success(self, test_tracker):
        """Test that success response has all required fields."""
        result = update_tracker_status(
            {"tracker_path": test_tracker, "target_status": "Resume Written"}
        )

        # Required fields
        assert "tracker_path" in result
        assert "previous_status" in result
        assert "target_status" in result
        assert "action" in result
        assert "success" in result
        assert "dry_run" in result
        assert "warnings" in result

        # Guardrail field present when evaluated
        assert "guardrail_check_passed" in result

    def test_response_structure_blocked(self, test_tracker_with_resume_written):
        """Test that blocked response has all required fields."""
        result = update_tracker_status(
            {"tracker_path": test_tracker_with_resume_written, "target_status": "Reviewed"}
        )

        # Required fields
        assert "tracker_path" in result
        assert "previous_status" in result
        assert "target_status" in result
        assert "action" in result
        assert result["action"] == "blocked"
        assert "success" in result
        assert result["success"] is False
        assert "dry_run" in result
        assert "error" in result
        assert "warnings" in result

    def test_response_structure_top_level_error(self):
        """Test that top-level error has correct structure."""
        result = update_tracker_status(
            {"tracker_path": "nonexistent.md", "target_status": "Resume Written"}
        )

        assert "error" in result
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert "retryable" in result["error"]
