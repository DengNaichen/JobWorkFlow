"""
Guardrail validators for Resume Written status transition.

This module provides validation functions to ensure resume artifacts meet
quality requirements before allowing tracker status to be set to "Resume Written".
"""

from pathlib import Path
from typing import Optional, Tuple
import re

from utils.latex_guardrails import scan_tex_for_placeholders
from utils.tracker_parser import parse_tracker_file, TrackerParseError
from models.errors import sanitize_path


class GuardrailError(Exception):
    """Exception raised when guardrail validation fails."""


def _sanitize_paths_in_message(message: str) -> str:
    """
    Redact absolute paths in validator error messages.

    Keeps relative paths readable while stripping sensitive host paths.
    """
    sanitized_tokens = []
    for token in message.split():
        stripped = token.strip(".,;:()[]{}\"'")
        is_abs_posix = stripped.startswith("/")
        is_abs_windows = bool(re.match(r"^[A-Za-z]:\\", stripped))

        if is_abs_posix or is_abs_windows:
            sanitized_tokens.append(token.replace(stripped, sanitize_path(stripped)))
        else:
            sanitized_tokens.append(token)

    return " ".join(sanitized_tokens)


def validate_tracker_exists(tracker_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that tracker file exists and is readable.
    
    Args:
        tracker_path: Path to tracker markdown file
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if validation passes
        - (False, error_message) if validation fails
        
    Requirements:
        - 3.1: Verify tracker_path file exists and is readable
        
    Examples:
        >>> # Valid tracker
        >>> validate_tracker_exists("trackers/2026-02-05-amazon.md")
        (True, None)
        
        >>> # Missing tracker
        >>> validate_tracker_exists("trackers/nonexistent.md")
        (False, 'Tracker file not found: trackers/nonexistent.md')
        
        >>> # Malformed tracker
        >>> validate_tracker_exists("trackers/malformed.md")
        (False, 'Tracker file is malformed: ...')
    """
    try:
        # Use parse_tracker_file which validates existence, readability, and format
        parse_tracker_file(tracker_path)
        return True, None
    except FileNotFoundError as e:
        return False, _sanitize_paths_in_message(str(e))
    except TrackerParseError as e:
        return False, f"Tracker file is malformed: {_sanitize_paths_in_message(str(e))}"
    except Exception as e:
        return False, _sanitize_paths_in_message(f"Failed to validate tracker: {str(e)}")


def validate_resume_pdf_exists(pdf_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that resume.pdf exists and has non-zero size.
    
    Args:
        pdf_path: Path to resume.pdf file
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if validation passes
        - (False, error_message) if validation fails
        
    Requirements:
        - 5.1: Verify resume.pdf exists
        - 5.2: Verify resume.pdf size is greater than zero
        
    Examples:
        >>> # Valid PDF
        >>> validate_resume_pdf_exists("data/applications/test/resume/resume.pdf")
        (True, None)
        
        >>> # Missing PDF
        >>> validate_resume_pdf_exists("data/applications/missing/resume/resume.pdf")
        (False, 'resume.pdf does not exist')
        
        >>> # Zero-byte PDF
        >>> validate_resume_pdf_exists("data/applications/empty/resume/resume.pdf")
        (False, 'resume.pdf is empty (0 bytes)')
    """
    pdf_file = Path(pdf_path)
    
    # Check if file exists
    if not pdf_file.exists():
        return False, "resume.pdf does not exist"
    
    # Check if it's a file (not a directory)
    if not pdf_file.is_file():
        return False, "resume.pdf path is not a file"
    
    # Check if file has non-zero size
    file_size = pdf_file.stat().st_size
    if file_size == 0:
        return False, "resume.pdf is empty (0 bytes)"
    
    return True, None


def validate_resume_tex_exists(tex_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that resume.tex exists.
    
    Args:
        tex_path: Path to resume.tex file
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if validation passes
        - (False, error_message) if validation fails
        
    Requirements:
        - 5.3: Verify companion resume.tex exists
        
    Examples:
        >>> # Valid TEX
        >>> validate_resume_tex_exists("data/applications/test/resume/resume.tex")
        (True, None)
        
        >>> # Missing TEX
        >>> validate_resume_tex_exists("data/applications/missing/resume/resume.tex")
        (False, 'resume.tex does not exist')
    """
    tex_file = Path(tex_path)
    
    # Check if file exists
    if not tex_file.exists():
        return False, "resume.tex does not exist"
    
    # Check if it's a file (not a directory)
    if not tex_file.is_file():
        return False, "resume.tex path is not a file"
    
    return True, None


def validate_resume_written_guardrails(pdf_path: str, tex_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate all Resume Written guardrails.
    
    This is the main entry point for Resume Written validation. It checks:
    1. resume.pdf exists and has non-zero size
    2. resume.tex exists
    3. resume.tex does not contain placeholder tokens
    
    Args:
        pdf_path: Path to resume.pdf file
        tex_path: Path to resume.tex file
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if all validations pass
        - (False, error_message) if any validation fails
        
    Requirements:
        - 5.1: Verify resume.pdf exists
        - 5.2: Verify resume.pdf size is greater than zero
        - 5.3: Verify companion resume.tex exists
        - 5.4: Scan resume.tex for placeholder tokens
        - 5.5: Block update when any guardrail check fails
        
    Examples:
        >>> # All validations pass
        >>> validate_resume_written_guardrails(
        ...     "data/applications/test/resume/resume.pdf",
        ...     "data/applications/test/resume/resume.tex"
        ... )
        (True, None)
        
        >>> # PDF missing
        >>> validate_resume_written_guardrails(
        ...     "data/applications/missing/resume/resume.pdf",
        ...     "data/applications/missing/resume/resume.tex"
        ... )
        (False, 'resume.pdf does not exist')
        
        >>> # Placeholders present
        >>> validate_resume_written_guardrails(
        ...     "data/applications/draft/resume/resume.pdf",
        ...     "data/applications/draft/resume/resume.tex"
        ... )
        (False, 'resume.tex contains placeholder tokens: PROJECT-AI-')
    """
    # Validate PDF exists and has non-zero size
    pdf_valid, pdf_error = validate_resume_pdf_exists(pdf_path)
    if not pdf_valid:
        return False, pdf_error
    
    # Validate TEX exists
    tex_valid, tex_error = validate_resume_tex_exists(tex_path)
    if not tex_valid:
        return False, tex_error
    
    # Scan TEX for placeholders
    placeholder_valid, placeholder_error, _ = scan_tex_for_placeholders(tex_path)
    if not placeholder_valid:
        return False, placeholder_error
    
    # All validations passed
    return True, None
