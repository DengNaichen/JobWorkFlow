"""
LaTeX compiler utilities for resume PDF generation.

This module provides utilities to compile LaTeX files into PDFs using pdflatex,
with pre-compile validation including placeholder scanning.
"""

import subprocess
from pathlib import Path
from typing import Optional, Tuple

from models.errors import ToolError, ErrorCode
from utils.latex_guardrails import scan_tex_for_placeholders


def compile_resume_pdf(
    tex_path: str,
    pdflatex_cmd: str = "pdflatex",
    timeout: int = 30
) -> Tuple[bool, Optional[str]]:
    """
    Compile resume.tex to resume.pdf with pre-compile placeholder validation.
    
    This function performs the full compile gate:
    1. Scan for placeholder tokens (Requirement 5.2)
    2. If placeholders found, fail with VALIDATION_ERROR (Requirement 5.3)
    3. Run pdflatex to generate PDF (Requirement 5.1)
    4. Verify PDF exists and has non-zero size (Requirement 5.4)
    
    Args:
        tex_path: Path to resume.tex file
        pdflatex_cmd: Command to run pdflatex (default: "pdflatex")
        timeout: Maximum seconds to wait for compilation (default: 30)
        
    Returns:
        Tuple of (success, error_message)
        - (True, None) if compilation succeeded
        - (False, error_message) if compilation failed
        
    Raises:
        ToolError: With VALIDATION_ERROR code if placeholders found
        ToolError: With COMPILE_ERROR code if compilation fails
        
    Requirements:
        - 5.1: Run LaTeX compile (pdflatex) on resume.tex
        - 5.2: Before compile, scan placeholders in resume.tex
        - 5.3: When placeholders exist, fail with VALIDATION_ERROR and skip compile
        - 5.4: When compile succeeds, verify resume.pdf exists and has non-zero size
        - 5.5: When compile/toolchain fails, fail with COMPILE_ERROR
        
    Examples:
        >>> # Clean TEX file compiles successfully
        >>> compile_resume_pdf("data/applications/test/resume/resume.tex")
        (True, None)
        
        >>> # TEX with placeholders fails before compile
        >>> compile_resume_pdf("data/applications/draft/resume/resume.tex")
        ToolError: VALIDATION_ERROR - resume.tex contains placeholder tokens: PROJECT-AI-
    """
    tex_file = Path(tex_path)
    
    # Validate tex file exists
    if not tex_file.exists():
        raise ToolError(
            code=ErrorCode.FILE_NOT_FOUND,
            message=f"resume.tex not found: {tex_path}"
        )
    
    # Requirement 5.2 & 5.3: Scan for placeholders before compile
    is_valid, error_msg, found_tokens = scan_tex_for_placeholders(tex_path)
    if not is_valid:
        # Fail with VALIDATION_ERROR and skip compile
        raise ToolError(
            code=ErrorCode.VALIDATION_ERROR,
            message=error_msg
        )
    
    # Requirement 5.1: Run pdflatex to compile PDF
    pdf_path = tex_file.parent / "resume.pdf"
    working_dir = tex_file.parent
    
    try:
        # Run pdflatex with minimal output
        result = subprocess.run(
            [pdflatex_cmd, "-interaction=nonstopmode", "-halt-on-error", tex_file.name],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # Check if compilation succeeded
        if result.returncode != 0:
            # Extract relevant error from output
            error_lines = []
            for line in result.stdout.split('\n'):
                if line.startswith('!') or 'error' in line.lower():
                    error_lines.append(line)
            
            error_summary = '\n'.join(error_lines[:5]) if error_lines else result.stdout[:500]
            
            raise ToolError(
                code=ErrorCode.COMPILE_ERROR,
                message=f"pdflatex compilation failed: {error_summary}"
            )
            
    except subprocess.TimeoutExpired:
        raise ToolError(
            code=ErrorCode.COMPILE_ERROR,
            message=f"pdflatex compilation timed out after {timeout} seconds"
        )
    except FileNotFoundError:
        raise ToolError(
            code=ErrorCode.COMPILE_ERROR,
            message=f"pdflatex command not found: {pdflatex_cmd}"
        )
    except Exception as e:
        raise ToolError(
            code=ErrorCode.COMPILE_ERROR,
            message=f"pdflatex execution failed: {str(e)}"
        )
    
    # Requirement 5.4: Verify PDF exists and has non-zero size
    if not pdf_path.exists():
        raise ToolError(
            code=ErrorCode.COMPILE_ERROR,
            message="pdflatex completed but resume.pdf was not created"
        )
    
    pdf_size = pdf_path.stat().st_size
    if pdf_size == 0:
        raise ToolError(
            code=ErrorCode.COMPILE_ERROR,
            message="pdflatex created resume.pdf but file is empty (0 bytes)"
        )
    
    return True, None


def verify_pdf_exists(pdf_path: str) -> Tuple[bool, Optional[str]]:
    """
    Verify that a PDF file exists and has non-zero size.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Tuple of (exists_and_valid, error_message)
        - (True, None) if PDF exists and has non-zero size
        - (False, error_message) if PDF missing or empty
        
    Examples:
        >>> verify_pdf_exists("data/applications/test/resume/resume.pdf")
        (True, None)
        
        >>> verify_pdf_exists("data/applications/missing/resume/resume.pdf")
        (False, "resume.pdf not found: ...")
    """
    pdf_file = Path(pdf_path)
    
    if not pdf_file.exists():
        return False, f"resume.pdf not found: {pdf_path}"
    
    pdf_size = pdf_file.stat().st_size
    if pdf_size == 0:
        return False, f"resume.pdf is empty (0 bytes): {pdf_path}"
    
    return True, None
