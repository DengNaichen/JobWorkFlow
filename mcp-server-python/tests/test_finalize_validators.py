"""
Tests for finalize_validators module.

Tests guardrail validation for Resume Written status transition.
"""

import os

from utils.finalize_validators import (
    validate_tracker_exists,
    validate_resume_pdf_exists,
    validate_resume_tex_exists,
    validate_resume_written_guardrails,
)
from utils.latex_guardrails import (
    scan_tex_for_placeholders,
    PLACEHOLDER_TOKENS,
)


class TestValidateTrackerExists:
    """Tests for validate_tracker_exists function."""

    def test_valid_tracker_exists(self, tmp_path):
        """Test that validation passes for existing valid tracker."""
        # Create a valid tracker file with frontmatter
        tracker_path = tmp_path / "tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
---

## Job Description
Content here
""")

        is_valid, error = validate_tracker_exists(str(tracker_path))

        assert is_valid is True
        assert error is None

    def test_missing_tracker_fails(self, tmp_path):
        """Test that validation fails when tracker doesn't exist."""
        tracker_path = tmp_path / "nonexistent.md"

        is_valid, error = validate_tracker_exists(str(tracker_path))

        assert is_valid is False
        assert "Tracker file not found" in error

    def test_tracker_without_frontmatter_fails(self, tmp_path):
        """Test that validation fails when tracker has no frontmatter."""
        tracker_path = tmp_path / "tracker.md"
        tracker_path.write_text("Just some content without frontmatter")

        is_valid, error = validate_tracker_exists(str(tracker_path))

        assert is_valid is False
        assert "malformed" in error.lower()

    def test_tracker_without_status_field_fails(self, tmp_path):
        """Test that validation fails when tracker frontmatter lacks status."""
        tracker_path = tmp_path / "tracker.md"
        tracker_path.write_text("""---
company: Amazon
---

## Job Description
Content here
""")

        is_valid, error = validate_tracker_exists(str(tracker_path))

        assert is_valid is False
        assert "malformed" in error.lower()
        assert "status" in error.lower()

    def test_tracker_with_invalid_yaml_fails(self, tmp_path):
        """Test that validation fails when tracker has invalid YAML."""
        tracker_path = tmp_path / "tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: [invalid yaml
---

## Job Description
Content here
""")

        is_valid, error = validate_tracker_exists(str(tracker_path))

        assert is_valid is False
        assert "malformed" in error.lower()

    def test_directory_instead_of_file_fails(self, tmp_path):
        """Test that validation fails when path is a directory."""
        tracker_path = tmp_path / "tracker.md"
        tracker_path.mkdir()

        is_valid, error = validate_tracker_exists(str(tracker_path))

        assert is_valid is False
        assert "not a file" in error.lower()


class TestValidateResumePdfExists:
    """Tests for validate_resume_pdf_exists function."""

    def test_valid_pdf_exists_with_content(self, tmp_path):
        """Test that validation passes for existing non-empty PDF."""
        # Create a PDF file with content
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nSome PDF content")

        is_valid, error = validate_resume_pdf_exists(str(pdf_path))

        assert is_valid is True
        assert error is None

    def test_missing_pdf_fails(self, tmp_path):
        """Test that validation fails when PDF doesn't exist."""
        pdf_path = tmp_path / "nonexistent.pdf"

        is_valid, error = validate_resume_pdf_exists(str(pdf_path))

        assert is_valid is False
        assert error == "resume.pdf does not exist"

    def test_zero_byte_pdf_fails(self, tmp_path):
        """Test that validation fails for zero-byte PDF."""
        # Create an empty PDF file
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(b"")

        is_valid, error = validate_resume_pdf_exists(str(pdf_path))

        assert is_valid is False
        assert error == "resume.pdf is empty (0 bytes)"

    def test_directory_instead_of_file_fails(self, tmp_path):
        """Test that validation fails when path is a directory."""
        # Create a directory instead of a file
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.mkdir()

        is_valid, error = validate_resume_pdf_exists(str(pdf_path))

        assert is_valid is False
        assert error == "resume.pdf path is not a file"


class TestValidateResumeTexExists:
    """Tests for validate_resume_tex_exists function."""

    def test_valid_tex_exists(self, tmp_path):
        """Test that validation passes for existing TEX file."""
        # Create a TEX file
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("\\documentclass{article}\n\\begin{document}\nResume\n\\end{document}")

        is_valid, error = validate_resume_tex_exists(str(tex_path))

        assert is_valid is True
        assert error is None

    def test_missing_tex_fails(self, tmp_path):
        """Test that validation fails when TEX doesn't exist."""
        tex_path = tmp_path / "nonexistent.tex"

        is_valid, error = validate_resume_tex_exists(str(tex_path))

        assert is_valid is False
        assert error == "resume.tex does not exist"

    def test_directory_instead_of_file_fails(self, tmp_path):
        """Test that validation fails when path is a directory."""
        # Create a directory instead of a file
        tex_path = tmp_path / "resume.tex"
        tex_path.mkdir()

        is_valid, error = validate_resume_tex_exists(str(tex_path))

        assert is_valid is False
        assert error == "resume.tex path is not a file"

    def test_empty_tex_file_passes(self, tmp_path):
        """Test that empty TEX file passes (size check only for PDF)."""
        # Create an empty TEX file
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("")

        is_valid, error = validate_resume_tex_exists(str(tex_path))

        assert is_valid is True
        assert error is None


class TestScanTexForPlaceholders:
    """Tests for scan_tex_for_placeholders function."""

    def test_clean_tex_passes(self, tmp_path):
        """Test that TEX without placeholders passes validation."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Experience}
Worked on machine learning projects.
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is True
        assert error is None
        assert found_tokens == []

    def test_tex_with_project_ai_placeholder_fails(self, tmp_path):
        """Test that TEX with PROJECT-AI- placeholder fails."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
PROJECT-AI-DESCRIPTION-HERE
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "PROJECT-AI-" in error
        assert "PROJECT-AI-" in found_tokens

    def test_tex_with_project_be_placeholder_fails(self, tmp_path):
        """Test that TEX with PROJECT-BE- placeholder fails."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
PROJECT-BE-DESCRIPTION-HERE
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "PROJECT-BE-" in error
        assert "PROJECT-BE-" in found_tokens

    def test_tex_with_work_bullet_point_placeholder_fails(self, tmp_path):
        """Test that TEX with WORK-BULLET-POINT- placeholder fails."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Experience}
WORK-BULLET-POINT-PLACEHOLDER
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "WORK-BULLET-POINT-" in error
        assert "WORK-BULLET-POINT-" in found_tokens

    def test_tex_with_multiple_placeholders_fails(self, tmp_path):
        """Test that TEX with multiple placeholders reports all of them."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
PROJECT-AI-DESCRIPTION
PROJECT-BE-DESCRIPTION
\\section{Experience}
WORK-BULLET-POINT-PLACEHOLDER
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "PROJECT-AI-" in error
        assert "PROJECT-BE-" in error
        assert "WORK-BULLET-POINT-" in error
        assert len(found_tokens) == 3
        assert "PROJECT-AI-" in found_tokens
        assert "PROJECT-BE-" in found_tokens
        assert "WORK-BULLET-POINT-" in found_tokens

    def test_tex_with_placeholder_in_comment_still_fails(self, tmp_path):
        """Test that placeholders in comments are still detected (conservative check)."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
% TODO: Replace PROJECT-AI-DESCRIPTION
\\section{Projects}
Real project description here.
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "PROJECT-AI-" in error
        assert "PROJECT-AI-" in found_tokens

    def test_unreadable_tex_file_fails(self, tmp_path):
        """Test that unreadable TEX file returns error."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("content")

        # Make file unreadable (Unix-like systems only)
        if os.name != "nt":  # Skip on Windows
            os.chmod(tex_path, 0o000)

            is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

            assert is_valid is False
            assert "Failed to read resume.tex" in error
            assert found_tokens == []

            # Restore permissions for cleanup
            os.chmod(tex_path, 0o644)


class TestValidateResumeWrittenGuardrails:
    """Tests for validate_resume_written_guardrails function."""

    def test_all_validations_pass(self, tmp_path):
        """Test that validation passes when all checks succeed."""
        # Create valid PDF and TEX files
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nContent")

        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("\\documentclass{article}\n\\begin{document}\nResume\n\\end{document}")

        is_valid, error = validate_resume_written_guardrails(str(pdf_path), str(tex_path))

        assert is_valid is True
        assert error is None

    def test_missing_pdf_fails(self, tmp_path):
        """Test that validation fails when PDF is missing."""
        pdf_path = tmp_path / "resume.pdf"

        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("\\documentclass{article}\n\\begin{document}\nResume\n\\end{document}")

        is_valid, error = validate_resume_written_guardrails(str(pdf_path), str(tex_path))

        assert is_valid is False
        assert error == "resume.pdf does not exist"

    def test_zero_byte_pdf_fails(self, tmp_path):
        """Test that validation fails when PDF is empty."""
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(b"")

        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("\\documentclass{article}\n\\begin{document}\nResume\n\\end{document}")

        is_valid, error = validate_resume_written_guardrails(str(pdf_path), str(tex_path))

        assert is_valid is False
        assert error == "resume.pdf is empty (0 bytes)"

    def test_missing_tex_fails(self, tmp_path):
        """Test that validation fails when TEX is missing."""
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nContent")

        tex_path = tmp_path / "resume.tex"

        is_valid, error = validate_resume_written_guardrails(str(pdf_path), str(tex_path))

        assert is_valid is False
        assert error == "resume.tex does not exist"

    def test_tex_with_placeholders_fails(self, tmp_path):
        """Test that validation fails when TEX contains placeholders."""
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nContent")

        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
PROJECT-AI-PLACEHOLDER
\\end{document}
""")

        is_valid, error = validate_resume_written_guardrails(str(pdf_path), str(tex_path))

        assert is_valid is False
        assert "PROJECT-AI-" in error
        assert "placeholder tokens" in error

    def test_validation_stops_at_first_failure(self, tmp_path):
        """Test that validation returns first error encountered."""
        # Missing PDF should fail before checking TEX
        pdf_path = tmp_path / "resume.pdf"
        tex_path = tmp_path / "resume.tex"

        is_valid, error = validate_resume_written_guardrails(str(pdf_path), str(tex_path))

        assert is_valid is False
        assert error == "resume.pdf does not exist"


class TestPlaceholderTokens:
    """Tests for PLACEHOLDER_TOKENS constant."""

    def test_placeholder_tokens_defined(self):
        """Test that all required placeholder tokens are defined."""
        assert "PROJECT-AI-" in PLACEHOLDER_TOKENS
        assert "PROJECT-BE-" in PLACEHOLDER_TOKENS
        assert "WORK-BULLET-POINT-" in PLACEHOLDER_TOKENS

    def test_placeholder_tokens_count(self):
        """Test that we have at least the minimum required tokens."""
        # Requirements specify "at minimum" these three tokens
        assert len(PLACEHOLDER_TOKENS) >= 3
