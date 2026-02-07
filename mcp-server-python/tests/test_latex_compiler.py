"""
Tests for utils/latex_compiler.py

Tests the LaTeX compilation functionality including:
- Placeholder scanning before compile
- PDF compilation with pdflatex
- PDF verification
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from utils.latex_compiler import compile_resume_pdf, verify_pdf_exists
from models.errors import ToolError, ErrorCode


class TestCompileResumePdf:
    """Tests for compile_resume_pdf function."""
    
    def test_missing_tex_file_raises_file_not_found(self, tmp_path):
        """Test that missing resume.tex raises FILE_NOT_FOUND error."""
        tex_path = tmp_path / "resume.tex"
        
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.FILE_NOT_FOUND
        assert "resume.tex not found" in error.message
    
    def test_tex_with_placeholders_raises_validation_error(self, tmp_path):
        """Test that resume.tex with placeholders fails with VALIDATION_ERROR before compile."""
        # Create resume.tex with placeholder
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Projects}
PROJECT-AI-DESCRIPTION-HERE
\\end{document}
""")
        
        # Should raise VALIDATION_ERROR and skip compile
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "placeholder tokens" in error.message
        assert "PROJECT-AI-" in error.message
        
        # Verify PDF was NOT created (compile was skipped)
        pdf_path = tmp_path / "resume.pdf"
        assert not pdf_path.exists()
    
    def test_tex_with_multiple_placeholders_raises_validation_error(self, tmp_path):
        """Test that resume.tex with multiple placeholders reports all of them."""
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
        
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "placeholder tokens" in error.message
        # Should mention at least one placeholder
        assert any(token in error.message for token in ["PROJECT-AI-", "PROJECT-BE-", "WORK-BULLET-POINT-"])
    
    @patch('subprocess.run')
    def test_successful_compilation(self, mock_run, tmp_path):
        """Test successful PDF compilation with clean resume.tex."""
        # Create clean resume.tex
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Experience}
Worked on machine learning projects.
\\end{document}
""")
        
        # Mock successful pdflatex execution
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        # Create the PDF file that pdflatex would create
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_text("fake pdf content")
        
        # Should succeed
        success, error = compile_resume_pdf(str(tex_path))
        
        assert success is True
        assert error is None
        
        # Verify pdflatex was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0][0] == "pdflatex"
        assert "-interaction=nonstopmode" in call_args[0][0]
        assert "-halt-on-error" in call_args[0][0]
        assert call_args[1]['cwd'] == tmp_path
    
    @patch('subprocess.run')
    def test_compilation_failure_raises_compile_error(self, mock_run, tmp_path):
        """Test that pdflatex compilation failure raises COMPILE_ERROR."""
        # Create clean resume.tex (no placeholders)
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
\\section{Experience}
Valid content.
\\end{document}
""")
        
        # Mock failed pdflatex execution
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="! LaTeX Error: Missing \\begin{document}.",
            stderr=""
        )
        
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.COMPILE_ERROR
        assert "pdflatex compilation failed" in error.message
    
    @patch('subprocess.run')
    def test_compilation_timeout_raises_compile_error(self, mock_run, tmp_path):
        """Test that pdflatex timeout raises COMPILE_ERROR."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
Valid content.
\\end{document}
""")
        
        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired("pdflatex", 30)
        
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path), timeout=30)
        
        error = exc_info.value
        assert error.code == ErrorCode.COMPILE_ERROR
        assert "timed out" in error.message
    
    @patch('subprocess.run')
    def test_pdflatex_command_not_found_raises_compile_error(self, mock_run, tmp_path):
        """Test that missing pdflatex command raises COMPILE_ERROR."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
Valid content.
\\end{document}
""")
        
        # Mock command not found
        mock_run.side_effect = FileNotFoundError("pdflatex not found")
        
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.COMPILE_ERROR
        assert "pdflatex command not found" in error.message
    
    @patch('subprocess.run')
    def test_pdf_not_created_raises_compile_error(self, mock_run, tmp_path):
        """Test that missing PDF after successful pdflatex raises COMPILE_ERROR."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
Valid content.
\\end{document}
""")
        
        # Mock successful pdflatex but don't create PDF
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.COMPILE_ERROR
        assert "resume.pdf was not created" in error.message
    
    @patch('subprocess.run')
    def test_empty_pdf_raises_compile_error(self, mock_run, tmp_path):
        """Test that empty PDF (0 bytes) raises COMPILE_ERROR."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
Valid content.
\\end{document}
""")
        
        # Mock successful pdflatex
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        # Create empty PDF
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_text("")
        
        with pytest.raises(ToolError) as exc_info:
            compile_resume_pdf(str(tex_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.COMPILE_ERROR
        assert "empty (0 bytes)" in error.message
    
    @patch('subprocess.run')
    def test_custom_pdflatex_command(self, mock_run, tmp_path):
        """Test that custom pdflatex command is used."""
        tex_path = tmp_path / "resume.tex"
        tex_path.write_text("""
\\documentclass{article}
\\begin{document}
Valid content.
\\end{document}
""")
        
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_text("fake pdf")
        
        compile_resume_pdf(str(tex_path), pdflatex_cmd="custom-pdflatex")
        
        # Verify custom command was used
        call_args = mock_run.call_args
        assert call_args[0][0][0] == "custom-pdflatex"


class TestVerifyPdfExists:
    """Tests for verify_pdf_exists function."""
    
    def test_existing_valid_pdf_returns_true(self, tmp_path):
        """Test that existing non-empty PDF returns True."""
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_text("fake pdf content")
        
        exists, error = verify_pdf_exists(str(pdf_path))
        
        assert exists is True
        assert error is None
    
    def test_missing_pdf_returns_false(self, tmp_path):
        """Test that missing PDF returns False with error message."""
        pdf_path = tmp_path / "resume.pdf"
        
        exists, error = verify_pdf_exists(str(pdf_path))
        
        assert exists is False
        assert "resume.pdf not found" in error
    
    def test_empty_pdf_returns_false(self, tmp_path):
        """Test that empty PDF (0 bytes) returns False with error message."""
        pdf_path = tmp_path / "resume.pdf"
        pdf_path.write_text("")
        
        exists, error = verify_pdf_exists(str(pdf_path))
        
        assert exists is False
        assert "empty (0 bytes)" in error
