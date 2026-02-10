"""
Integration tests for finalize_validators with artifact_paths.

Tests the complete flow of resolving artifact paths and validating guardrails.
"""

from utils.artifact_paths import resolve_artifact_paths
from utils.finalize_validators import validate_resume_written_guardrails


class TestFinalizeValidatorsIntegration:
    """Integration tests for finalize validators with artifact path resolution."""

    def test_complete_flow_with_wiki_link_format(self, tmp_path):
        """Test complete flow from wiki-link path to guardrail validation."""
        # Setup: Create application directory structure
        app_dir = tmp_path / "data" / "applications" / "amazon-352" / "resume"
        app_dir.mkdir(parents=True)

        # Create valid artifacts
        pdf_path = app_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nValid PDF content")

        tex_path = app_dir / "resume.tex"
        tex_path.write_text(
            "\\documentclass{article}\n\\begin{document}\nClean resume\n\\end{document}"
        )

        # Simulate tracker frontmatter with wiki-link format
        resume_path_raw = f"[[{app_dir / 'resume.pdf'}]]"

        # Resolve paths
        resolved_pdf, resolved_tex = resolve_artifact_paths(resume_path_raw)

        # Validate guardrails
        is_valid, error = validate_resume_written_guardrails(resolved_pdf, resolved_tex)

        assert is_valid is True
        assert error is None

    def test_complete_flow_with_plain_path_format(self, tmp_path):
        """Test complete flow from plain path to guardrail validation."""
        # Setup: Create application directory structure
        app_dir = tmp_path / "data" / "applications" / "meta-100" / "resume"
        app_dir.mkdir(parents=True)

        # Create valid artifacts
        pdf_path = app_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nValid PDF content")

        tex_path = app_dir / "resume.tex"
        tex_path.write_text(
            "\\documentclass{article}\n\\begin{document}\nClean resume\n\\end{document}"
        )

        # Simulate tracker frontmatter with plain path format
        resume_path_raw = str(app_dir / "resume.pdf")

        # Resolve paths
        resolved_pdf, resolved_tex = resolve_artifact_paths(resume_path_raw)

        # Validate guardrails
        is_valid, error = validate_resume_written_guardrails(resolved_pdf, resolved_tex)

        assert is_valid is True
        assert error is None

    def test_complete_flow_fails_with_missing_pdf(self, tmp_path):
        """Test that complete flow fails when PDF is missing."""
        # Setup: Create application directory structure
        app_dir = tmp_path / "data" / "applications" / "google-200" / "resume"
        app_dir.mkdir(parents=True)

        # Create only TEX file (PDF missing)
        tex_path = app_dir / "resume.tex"
        tex_path.write_text(
            "\\documentclass{article}\n\\begin{document}\nClean resume\n\\end{document}"
        )

        # Simulate tracker frontmatter
        resume_path_raw = str(app_dir / "resume.pdf")

        # Resolve paths
        resolved_pdf, resolved_tex = resolve_artifact_paths(resume_path_raw)

        # Validate guardrails - should fail
        is_valid, error = validate_resume_written_guardrails(resolved_pdf, resolved_tex)

        assert is_valid is False
        assert error == "resume.pdf does not exist"

    def test_complete_flow_fails_with_placeholders(self, tmp_path):
        """Test that complete flow fails when TEX contains placeholders."""
        # Setup: Create application directory structure
        app_dir = tmp_path / "data" / "applications" / "apple-300" / "resume"
        app_dir.mkdir(parents=True)

        # Create PDF
        pdf_path = app_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nValid PDF content")

        # Create TEX with placeholder
        tex_path = app_dir / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
PROJECT-BULLET-POINT-1
\\end{document}
""")

        # Simulate tracker frontmatter
        resume_path_raw = str(app_dir / "resume.pdf")

        # Resolve paths
        resolved_pdf, resolved_tex = resolve_artifact_paths(resume_path_raw)

        # Validate guardrails - should fail
        is_valid, error = validate_resume_written_guardrails(resolved_pdf, resolved_tex)

        assert is_valid is False
        assert "BULLET-POINT" in error
        assert "placeholder tokens" in error

    def test_complete_flow_fails_with_zero_byte_pdf(self, tmp_path):
        """Test that complete flow fails when PDF is empty."""
        # Setup: Create application directory structure
        app_dir = tmp_path / "data" / "applications" / "netflix-400" / "resume"
        app_dir.mkdir(parents=True)

        # Create empty PDF
        pdf_path = app_dir / "resume.pdf"
        pdf_path.write_bytes(b"")

        # Create valid TEX
        tex_path = app_dir / "resume.tex"
        tex_path.write_text(
            "\\documentclass{article}\n\\begin{document}\nClean resume\n\\end{document}"
        )

        # Simulate tracker frontmatter
        resume_path_raw = str(app_dir / "resume.pdf")

        # Resolve paths
        resolved_pdf, resolved_tex = resolve_artifact_paths(resume_path_raw)

        # Validate guardrails - should fail
        is_valid, error = validate_resume_written_guardrails(resolved_pdf, resolved_tex)

        assert is_valid is False
        assert error == "resume.pdf is empty (0 bytes)"
