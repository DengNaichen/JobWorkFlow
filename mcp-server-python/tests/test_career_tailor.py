"""
Tests for career_tailor MCP tool.

This module tests the batch orchestration logic for the career_tailor tool,
including item processing, error handling, and successful_items generation.
"""

import pytest
import sqlite3
from unittest.mock import patch
from tools.career_tailor import (
    career_tailor,
    generate_run_id,
    sanitize_error_message,
    resolve_job_db_id,
    process_item_tailoring,
)
from models.errors import ToolError, ErrorCode


class TestGenerateRunId:
    """Tests for generate_run_id function."""

    def test_run_id_format(self):
        """Test that run_id has correct format."""
        run_id = generate_run_id("tailor")

        # Should have format: tailor_YYYYMMDD_<8-char-hash>
        parts = run_id.split("_")
        assert len(parts) == 3
        assert parts[0] == "tailor"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 8  # hash

    def test_run_id_uniqueness(self):
        """Test that consecutive run_ids are different."""
        run_id1 = generate_run_id("tailor")
        run_id2 = generate_run_id("tailor")

        # Should be different due to timestamp precision
        assert run_id1 != run_id2


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message function."""

    def test_sanitize_multiline_error(self):
        """Test that only first line is kept."""
        error = Exception("First line\nSecond line\nThird line")
        result = sanitize_error_message(error)

        assert result == "First line"
        assert "\n" not in result

    def test_sanitize_sql_fragment(self):
        """Test that SQL fragments are redacted."""
        error = Exception("Database error: SELECT * FROM jobs WHERE id=123")
        result = sanitize_error_message(error)

        assert "SELECT" not in result
        assert "[SQL query]" in result

    def test_sanitize_absolute_path(self):
        """Test that absolute paths are redacted."""
        error = Exception("File not found: /home/user/data/file.txt")
        result = sanitize_error_message(error)

        assert "/home/user/data/file.txt" not in result
        assert "[path]" in result

    def test_sanitize_long_message(self):
        """Test that long messages are truncated."""
        long_msg = "x" * 300
        error = Exception(long_msg)
        result = sanitize_error_message(error)

        assert len(result) <= 200
        assert result.endswith("...")


class TestResolveJobDbId:
    """Tests for resolve_job_db_id helper."""

    def test_prefers_item_job_db_id(self):
        """Item override should win over tracker value."""
        resolved = resolve_job_db_id(1001, 2002)
        assert resolved == 1001

    def test_uses_tracker_int_when_item_missing(self):
        """Tracker int should be used when item value is missing."""
        resolved = resolve_job_db_id(None, 2002)
        assert resolved == 2002

    def test_uses_tracker_numeric_string_when_item_missing(self):
        """Tracker numeric string should be parsed."""
        resolved = resolve_job_db_id(None, "2002")
        assert resolved == 2002

    def test_returns_none_for_invalid_values(self):
        """Invalid values should not resolve."""
        assert resolve_job_db_id(None, None) is None
        assert resolve_job_db_id(None, "abc") is None
        assert resolve_job_db_id(None, 0) is None
        assert resolve_job_db_id(None, False) is None


class TestProcessItemTailoring:
    """Tests for process_item_tailoring function."""

    @patch("tools.career_tailor.parse_tracker_for_career_tailor_with_error_mapping")
    @patch("tools.career_tailor.resolve_application_slug")
    @patch("tools.career_tailor.ensure_workspace_directories")
    @patch("tools.career_tailor.materialize_resume_tex")
    @patch("tools.career_tailor.regenerate_ai_context")
    @patch("tools.career_tailor.compile_resume_pdf")
    @patch("tools.career_tailor.verify_pdf_exists")
    def test_successful_item_processing(
        self,
        mock_verify_pdf,
        mock_compile_pdf,
        mock_regenerate_ai,
        mock_materialize_tex,
        mock_ensure_workspace,
        mock_resolve_slug,
        mock_parse_tracker,
    ):
        """Test successful item processing through all steps."""
        # Setup mocks
        mock_parse_tracker.return_value = {
            "company": "Amazon",
            "position": "Software Engineer",
            "job_description": "Build scalable systems",
            "job_db_id": 3629,
        }
        mock_resolve_slug.return_value = "amazon-3629"
        mock_materialize_tex.return_value = "created"
        mock_regenerate_ai.return_value = "data/applications/amazon-3629/resume/ai_context.md"
        mock_verify_pdf.return_value = (True, None)

        # Process item
        item = {"tracker_path": "trackers/2026-02-06-amazon-3629.md", "job_db_id": 3629}

        result = process_item_tailoring(
            item=item,
            force=False,
            full_resume_path="data/templates/full_resume_example.md",
            resume_template_path="data/templates/resume_skeleton_example.tex",
            applications_dir="data/applications",
            pdflatex_cmd="pdflatex",
        )

        # Verify result
        assert result["success"] is True
        assert result["tracker_path"] == "trackers/2026-02-06-amazon-3629.md"
        assert result["job_db_id"] == 3629
        assert result["application_slug"] == "amazon-3629"
        assert result["workspace_dir"] == "data/applications/amazon-3629"
        assert result["resume_tex_path"] == "data/applications/amazon-3629/resume/resume.tex"
        assert result["ai_context_path"] == "data/applications/amazon-3629/resume/ai_context.md"
        assert result["resume_pdf_path"] == "data/applications/amazon-3629/resume/resume.pdf"
        assert result["resume_tex_action"] == "created"
        assert result["action"] == "tailored"

        # Verify all steps were called
        mock_parse_tracker.assert_called_once()
        mock_resolve_slug.assert_called_once()
        mock_ensure_workspace.assert_called_once()
        mock_materialize_tex.assert_called_once()
        mock_regenerate_ai.assert_called_once()
        mock_compile_pdf.assert_called_once()
        mock_verify_pdf.assert_called_once()

    @patch("tools.career_tailor.parse_tracker_for_career_tailor_with_error_mapping")
    def test_tracker_not_found_error(self, mock_parse_tracker):
        """Test that FILE_NOT_FOUND error is properly handled."""
        # Setup mock to raise FILE_NOT_FOUND
        mock_parse_tracker.side_effect = ToolError(
            code=ErrorCode.FILE_NOT_FOUND, message="Tracker file not found: trackers/missing.md"
        )

        # Process item
        item = {"tracker_path": "trackers/missing.md"}

        result = process_item_tailoring(
            item=item,
            force=False,
            full_resume_path="data/templates/full_resume_example.md",
            resume_template_path="data/templates/resume_skeleton_example.tex",
            applications_dir="data/applications",
            pdflatex_cmd="pdflatex",
        )

        # Verify failure result
        assert result["success"] is False
        assert result["action"] == "failed"
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "Tracker file not found" in result["error"]

    @patch("tools.career_tailor.parse_tracker_for_career_tailor_with_error_mapping")
    @patch("tools.career_tailor.resolve_application_slug")
    @patch("tools.career_tailor.ensure_workspace_directories")
    @patch("tools.career_tailor.materialize_resume_tex")
    @patch("tools.career_tailor.regenerate_ai_context")
    @patch("tools.career_tailor.compile_resume_pdf")
    def test_placeholder_validation_error(
        self,
        mock_compile_pdf,
        mock_regenerate_ai,
        mock_materialize_tex,
        mock_ensure_workspace,
        mock_resolve_slug,
        mock_parse_tracker,
    ):
        """Test that placeholder validation error is properly handled."""
        # Setup mocks
        mock_parse_tracker.return_value = {
            "company": "Meta",
            "position": "Engineer",
            "job_description": "Build systems",
        }
        mock_resolve_slug.return_value = "meta-100"
        mock_materialize_tex.return_value = "preserved"
        mock_regenerate_ai.return_value = "data/applications/meta-100/resume/ai_context.md"

        # Compile fails with placeholder error
        mock_compile_pdf.side_effect = ToolError(
            code=ErrorCode.VALIDATION_ERROR,
            message="resume.tex contains placeholder tokens: PROJECT-AI-1",
        )

        # Process item
        item = {"tracker_path": "trackers/2026-02-06-meta-100.md"}

        result = process_item_tailoring(
            item=item,
            force=False,
            full_resume_path="data/templates/full_resume_example.md",
            resume_template_path="data/templates/resume_skeleton_example.tex",
            applications_dir="data/applications",
            pdflatex_cmd="pdflatex",
        )

        # Verify failure result
        assert result["success"] is False
        assert result["action"] == "failed"
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "placeholder tokens" in result["error"]

    @patch("tools.career_tailor.parse_tracker_for_career_tailor_with_error_mapping")
    @patch("tools.career_tailor.resolve_application_slug")
    @patch("tools.career_tailor.ensure_workspace_directories")
    @patch("tools.career_tailor.materialize_resume_tex")
    @patch("tools.career_tailor.regenerate_ai_context")
    @patch("tools.career_tailor.compile_resume_pdf")
    @patch("tools.career_tailor.verify_pdf_exists")
    def test_resolves_job_db_id_from_tracker_when_item_missing(
        self,
        mock_verify_pdf,
        mock_compile_pdf,
        mock_regenerate_ai,
        mock_materialize_tex,
        mock_ensure_workspace,
        mock_resolve_slug,
        mock_parse_tracker,
    ):
        """Tracker job_db_id should be used for handoff when item omits it."""
        mock_parse_tracker.return_value = {
            "company": "Amazon",
            "position": "Software Engineer",
            "job_description": "Build scalable systems",
            "job_db_id": "3629",
        }
        mock_resolve_slug.return_value = "amazon-3629"
        mock_materialize_tex.return_value = "created"
        mock_regenerate_ai.return_value = "data/applications/amazon-3629/resume/ai_context.md"
        mock_verify_pdf.return_value = (True, None)

        result = process_item_tailoring(
            item={"tracker_path": "trackers/2026-02-06-amazon-3629.md"},
            force=False,
            full_resume_path="data/templates/full_resume_example.md",
            resume_template_path="data/templates/resume_skeleton_example.tex",
            applications_dir="data/applications",
            pdflatex_cmd="pdflatex",
        )

        assert result["success"] is True
        assert result["job_db_id"] == 3629


class TestCareerTailorTool:
    """Tests for career_tailor MCP tool handler."""

    @patch("tools.career_tailor.process_item_tailoring")
    def test_successful_batch_processing(self, mock_process_item):
        """Test successful batch processing with multiple items."""
        # Setup mock to return successful results
        mock_process_item.side_effect = [
            {
                "tracker_path": "trackers/test1.md",
                "job_db_id": 1,
                "application_slug": "amazon-1",
                "workspace_dir": "data/applications/amazon-1",
                "resume_tex_path": "data/applications/amazon-1/resume/resume.tex",
                "ai_context_path": "data/applications/amazon-1/resume/ai_context.md",
                "resume_pdf_path": "data/applications/amazon-1/resume/resume.pdf",
                "resume_tex_action": "created",
                "success": True,
            },
            {
                "tracker_path": "trackers/test2.md",
                "job_db_id": 2,
                "application_slug": "meta-2",
                "workspace_dir": "data/applications/meta-2",
                "resume_tex_path": "data/applications/meta-2/resume/resume.tex",
                "ai_context_path": "data/applications/meta-2/resume/ai_context.md",
                "resume_pdf_path": "data/applications/meta-2/resume/resume.pdf",
                "resume_tex_action": "preserved",
                "success": True,
            },
        ]

        # Call tool
        args = {
            "items": [
                {"tracker_path": "trackers/test1.md", "job_db_id": 1},
                {"tracker_path": "trackers/test2.md", "job_db_id": 2},
            ]
        }

        result = career_tailor(args)

        # Verify response structure
        assert "run_id" in result
        assert result["run_id"].startswith("tailor_")
        assert result["total_count"] == 2
        assert result["success_count"] == 2
        assert result["failed_count"] == 0
        assert len(result["results"]) == 2
        assert len(result["successful_items"]) == 2

        # Verify successful_items format
        assert result["successful_items"][0] == {
            "id": 1,
            "tracker_path": "trackers/test1.md",
            "resume_pdf_path": "data/applications/amazon-1/resume/resume.pdf",
        }
        assert result["successful_items"][1] == {
            "id": 2,
            "tracker_path": "trackers/test2.md",
            "resume_pdf_path": "data/applications/meta-2/resume/resume.pdf",
        }

    @patch("tools.career_tailor.process_item_tailoring")
    def test_partial_success_batch(self, mock_process_item):
        """Test batch with one success and one failure."""
        # Setup mock to return mixed results
        mock_process_item.side_effect = [
            {
                "tracker_path": "trackers/test1.md",
                "job_db_id": 1,
                "application_slug": "amazon-1",
                "workspace_dir": "data/applications/amazon-1",
                "resume_tex_path": "data/applications/amazon-1/resume/resume.tex",
                "ai_context_path": "data/applications/amazon-1/resume/ai_context.md",
                "resume_pdf_path": "data/applications/amazon-1/resume/resume.pdf",
                "resume_tex_action": "created",
                "success": True,
            },
            {
                "tracker_path": "trackers/test2.md",
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error": "resume.tex contains placeholder tokens: PROJECT-AI-1",
            },
        ]

        # Call tool
        args = {
            "items": [
                {"tracker_path": "trackers/test1.md", "job_db_id": 1},
                {"tracker_path": "trackers/test2.md"},
            ]
        }

        result = career_tailor(args)

        # Verify counts
        assert result["total_count"] == 2
        assert result["success_count"] == 1
        assert result["failed_count"] == 1

        # Verify results order preserved
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is False

        # Verify only successful item in successful_items
        assert len(result["successful_items"]) == 1
        assert result["successful_items"][0]["id"] == 1

    @patch("tools.career_tailor.process_item_tailoring")
    def test_successful_item_without_job_db_id(self, mock_process_item):
        """Test that successful item without job_db_id is excluded from successful_items."""
        # Setup mock to return successful result without job_db_id
        mock_process_item.return_value = {
            "tracker_path": "trackers/test.md",
            "application_slug": "company-position",
            "workspace_dir": "data/applications/company-position",
            "resume_tex_path": "data/applications/company-position/resume/resume.tex",
            "ai_context_path": "data/applications/company-position/resume/ai_context.md",
            "resume_pdf_path": "data/applications/company-position/resume/resume.pdf",
            "resume_tex_action": "created",
            "success": True,
        }

        # Call tool
        args = {"items": [{"tracker_path": "trackers/test.md"}]}

        result = career_tailor(args)

        # Verify item succeeded
        assert result["success_count"] == 1
        assert result["failed_count"] == 0

        # Verify item excluded from successful_items
        assert len(result["successful_items"]) == 0

        # Verify warning added
        assert "warnings" in result
        assert len(result["warnings"]) == 1
        assert "has no job_db_id" in result["warnings"][0]
        assert "excluded from successful_items" in result["warnings"][0]

    def test_validation_error_for_empty_items(self):
        """Test that empty items array raises VALIDATION_ERROR."""
        args = {"items": []}

        with pytest.raises(ToolError) as exc_info:
            career_tailor(args)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message

    def test_validation_error_for_missing_items(self):
        """Test that missing items raises VALIDATION_ERROR."""
        args = {}

        with pytest.raises(ToolError) as exc_info:
            career_tailor(args)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be null" in error.message

    def test_validation_error_for_unknown_properties(self):
        """Test that unknown properties raise VALIDATION_ERROR."""
        args = {"items": [{"tracker_path": "trackers/test.md"}], "unknown_field": "value"}

        with pytest.raises(ToolError) as exc_info:
            career_tailor(args)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Unknown input properties" in error.message

    @patch("tools.career_tailor.compile_resume_pdf")
    @patch("tools.career_tailor.verify_pdf_exists")
    def test_boundary_no_db_or_tracker_status_mutation(
        self, mock_verify_pdf, mock_compile_pdf, tmp_path
    ):
        """career_tailor should not mutate DB status or tracker status."""
        # Setup DB state snapshot.
        db_path = tmp_path / "jobs.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, status TEXT NOT NULL)")
        conn.execute("INSERT INTO jobs (id, status) VALUES (1, 'shortlist')")
        conn.commit()
        conn.close()

        # Setup minimal tracker and templates.
        tracker_dir = tmp_path / "trackers"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        tracker_path = tracker_dir / "job.md"
        tracker_content = """---
job_db_id: 1
company: Acme
position: Backend Engineer
status: Reviewed
resume_path: '[[data/applications/acme-1/resume/resume.pdf]]'
---

## Job Description
Build scalable services.
"""
        tracker_path.write_text(tracker_content, encoding="utf-8")

        templates_dir = tmp_path / "data" / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        full_resume_path = templates_dir / "full_resume.md"
        full_resume_path.write_text("# Full Resume\n- Experience", encoding="utf-8")
        resume_template_path = templates_dir / "resume_skeleton.tex"
        resume_template_path.write_text(
            "\\documentclass{article}\\begin{document}OK\\end{document}", encoding="utf-8"
        )

        tracker_before = tracker_path.read_text(encoding="utf-8")

        # Mock compile/verify to avoid requiring real LaTeX in this boundary test.
        mock_compile_pdf.return_value = (True, None)
        mock_verify_pdf.return_value = (True, None)

        result = career_tailor(
            {
                "items": [{"tracker_path": str(tracker_path)}],
                "applications_dir": str(tmp_path / "data" / "applications"),
                "full_resume_path": str(full_resume_path),
                "resume_template_path": str(resume_template_path),
                "pdflatex_cmd": "pdflatex",
            }
        )

        assert result["success_count"] == 1
        assert result["failed_count"] == 0

        # Tracker content should be unchanged (no status mutation).
        tracker_after = tracker_path.read_text(encoding="utf-8")
        assert tracker_after == tracker_before

        # DB status should remain unchanged.
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT status FROM jobs WHERE id = 1").fetchone()
        conn.close()
        assert row[0] == "shortlist"
