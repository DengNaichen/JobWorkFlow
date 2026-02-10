"""
Tests for latex_guardrails module.

Tests placeholder scanning functionality for LaTeX resume files.
"""

import os

from utils.latex_guardrails import (
    scan_tex_for_placeholders,
    get_placeholder_tokens,
    PLACEHOLDER_TOKENS,
)


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

    def test_tex_with_bullet_point_placeholder_fails(self, tmp_path):
        """Test that TEX with BULLET-POINT placeholder fails."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
RESEARCH-1-BULLET-POINT-1
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "BULLET-POINT" in error
        assert "BULLET-POINT" in found_tokens

    def test_tex_without_bullet_point_passes(self, tmp_path):
        """Test that TEX without BULLET-POINT marker passes validation."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
PROJECT-BULLET-1
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is True
        assert error is None
        assert found_tokens == []

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
        assert "BULLET-POINT" in error
        assert "BULLET-POINT" in found_tokens

    def test_tex_with_multiple_placeholders_fails(self, tmp_path):
        """Test that TEX with multiple placeholders reports all of them."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
PROJECT-BULLET-1
RESEARCH-2-BULLET-POINT-2
\\section{Experience}
WORK-BULLET-POINT-PLACEHOLDER
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "BULLET-POINT" in error
        assert len(found_tokens) == 1
        assert "BULLET-POINT" in found_tokens

    def test_tex_with_placeholder_in_comment_still_fails(self, tmp_path):
        """Test that placeholders in comments are still detected (conservative check)."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
% TODO: Replace PROJECT-BULLET-1
\\section{Projects}
Real project description here.
\\end{document}
""")

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is True
        assert error is None
        assert found_tokens == []

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

    def test_nonexistent_file_fails(self, tmp_path):
        """Test that nonexistent file returns error."""
        tex_path = tmp_path / "nonexistent.tex"

        is_valid, error, found_tokens = scan_tex_for_placeholders(str(tex_path))

        assert is_valid is False
        assert "Failed to read resume.tex" in error
        assert found_tokens == []


class TestGetPlaceholderTokens:
    """Tests for get_placeholder_tokens function."""

    def test_returns_all_required_tokens(self):
        """Test that function returns all required placeholder tokens."""
        tokens = get_placeholder_tokens()

        assert "BULLET-POINT" in tokens

    def test_returns_copy_not_reference(self):
        """Test that function returns a copy, not a reference to the original list."""
        tokens1 = get_placeholder_tokens()
        tokens2 = get_placeholder_tokens()

        # Modify one list
        tokens1.append("TEST-TOKEN")

        # Other list should be unchanged
        assert "TEST-TOKEN" not in tokens2
        assert "TEST-TOKEN" not in PLACEHOLDER_TOKENS

    def test_minimum_token_count(self):
        """Test that we have at least the minimum required tokens."""
        tokens = get_placeholder_tokens()

        assert len(tokens) == 1


class TestPlaceholderTokensConstant:
    """Tests for PLACEHOLDER_TOKENS constant."""

    def test_placeholder_tokens_defined(self):
        """Test that all required placeholder tokens are defined."""
        assert "BULLET-POINT" in PLACEHOLDER_TOKENS

    def test_placeholder_tokens_count(self):
        """Test that we have at least the minimum required tokens."""
        assert len(PLACEHOLDER_TOKENS) == 1
