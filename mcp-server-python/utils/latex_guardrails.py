"""
LaTeX placeholder scanner for resume quality guardrails.

This module detects unfinished placeholder content in resume.tex files.
Per current project convention, placeholder labels are identified by the
stable marker substring: ``BULLET-POINT``.
"""

from pathlib import Path
from typing import List, Tuple, Optional


# Single stable placeholder marker agreed by project convention.
PLACEHOLDER_TOKENS = [
    "BULLET-POINT",
]


def scan_tex_for_placeholders(tex_path: str) -> Tuple[bool, Optional[str], List[str]]:
    """
    Scan resume.tex for placeholder tokens that indicate incomplete content.

    This function performs a conservative check that detects placeholder tokens
    anywhere in the file, including in comments. This ensures no draft content
    accidentally makes it into finalized resumes.

    Args:
        tex_path: Path to resume.tex file

    Returns:
        Tuple of (is_valid, error_message, found_tokens)
        - (True, None, []) if no placeholders found
        - (False, error_message, found_tokens) if placeholders found

    Requirements:
        - 5.4: Scan resume.tex for placeholder tokens
        - 5.5: Block update when any guardrail check fails
        - 5.6: Placeholder tokens include BULLET-POINT

    Examples:
        >>> # Clean TEX file
        >>> scan_tex_for_placeholders("data/applications/clean/resume/resume.tex")
        (True, None, [])

        >>> # TEX with placeholders
        >>> scan_tex_for_placeholders("data/applications/draft/resume/resume.tex")
        (False, 'resume.tex contains placeholder tokens: BULLET-POINT',
         ['BULLET-POINT'])
    """
    tex_file = Path(tex_path)

    # Read the file content
    try:
        content = tex_file.read_text(encoding="utf-8")
    except (OSError, IOError) as e:
        return False, f"Failed to read resume.tex: {str(e)}", []

    # Search for placeholder marker.
    found_tokens = []
    for token in PLACEHOLDER_TOKENS:
        if token in content:
            found_tokens.append(token)

    # If any placeholders found, validation fails
    if found_tokens:
        tokens_str = ", ".join(found_tokens)
        error_msg = f"resume.tex contains placeholder tokens: {tokens_str}"
        return False, error_msg, found_tokens

    return True, None, []


def get_placeholder_tokens() -> List[str]:
    """
    Get the list of placeholder tokens that are checked.

    Returns:
        List of placeholder token strings

    Examples:
        >>> tokens = get_placeholder_tokens()
        >>> "BULLET-POINT" in tokens
        True
    """
    return PLACEHOLDER_TOKENS.copy()
