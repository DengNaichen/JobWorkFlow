"""
Artifact path resolution utilities for update_tracker_status tool.

This module provides functions to parse and resolve artifact paths from
tracker frontmatter, supporting both wiki-link and plain path formats.
"""

from pathlib import Path
from typing import Optional, Tuple
import re


class ArtifactPathError(Exception):
    """Exception raised when artifact path resolution fails."""

    pass


def parse_resume_path(resume_path_raw: Optional[str]) -> Optional[str]:
    """
    Parse resume_path from tracker frontmatter and extract the actual path.

    Supports two formats:
    - Wiki-link format: [[data/applications/slug/resume/resume.pdf]]
    - Plain path format: data/applications/slug/resume/resume.pdf

    Args:
        resume_path_raw: Raw resume_path value from tracker frontmatter

    Returns:
        Parsed path string without wiki-link brackets, or None if input is None

    Raises:
        ArtifactPathError: If resume_path format is invalid or unparsable

    Requirements:
        - 6.1: Resolve resume.pdf path from tracker frontmatter resume_path
        - 6.2: Support wiki-link path format ([[...]]) and plain path format
        - 6.4: Return VALIDATION_ERROR when resume_path is missing or unparsable
        - 6.5: Path resolution is deterministic for identical tracker content

    Examples:
        >>> # Wiki-link format
        >>> parse_resume_path("[[data/applications/amazon-352/resume/resume.pdf]]")
        'data/applications/amazon-352/resume/resume.pdf'

        >>> # Plain path format
        >>> parse_resume_path("data/applications/amazon-352/resume/resume.pdf")
        'data/applications/amazon-352/resume/resume.pdf'

        >>> # None input
        >>> parse_resume_path(None)
        None

        >>> # Empty string
        >>> parse_resume_path("")
        Traceback (most recent call last):
        ...
        ArtifactPathError: resume_path is empty
    """
    if resume_path_raw is None:
        return None

    if not isinstance(resume_path_raw, str):
        raise ArtifactPathError(
            f"resume_path must be a string, got {type(resume_path_raw).__name__}"
        )

    # Strip whitespace
    resume_path_raw = resume_path_raw.strip()

    if not resume_path_raw:
        raise ArtifactPathError("resume_path is empty")

    # Check for wiki-link format: [[path]]
    wiki_link_pattern = r"^\[\[(.*?)\]\]$"
    match = re.match(wiki_link_pattern, resume_path_raw)

    if match:
        # Extract path from wiki-link brackets
        path = match.group(1).strip()
        if not path:
            raise ArtifactPathError("resume_path wiki-link contains empty path")
        return path

    # Plain path format - return as-is
    return resume_path_raw


def resolve_resume_tex_path(resume_pdf_path: str) -> str:
    """
    Resolve companion resume.tex path from resume.pdf path.

    The resume.tex file is expected to be in the same directory as resume.pdf,
    with the filename 'resume.tex'.

    Args:
        resume_pdf_path: Path to resume.pdf (without wiki-link brackets)

    Returns:
        Path to companion resume.tex file

    Requirements:
        - 6.3: Derive resume.tex from resolved resume workspace directory
        - 6.5: Path resolution is deterministic for identical tracker content

    Examples:
        >>> resolve_resume_tex_path("data/applications/amazon-352/resume/resume.pdf")
        'data/applications/amazon-352/resume/resume.tex'

        >>> resolve_resume_tex_path("data/applications/meta-100/resume/resume.pdf")
        'data/applications/meta-100/resume/resume.tex'
    """
    if not resume_pdf_path:
        raise ArtifactPathError("resume_pdf_path cannot be empty")

    # Get the directory containing resume.pdf
    pdf_path = Path(resume_pdf_path)
    resume_dir = pdf_path.parent

    # Construct path to resume.tex in the same directory
    tex_path = resume_dir / "resume.tex"

    return str(tex_path)


def resolve_artifact_paths(resume_path_raw: Optional[str]) -> Tuple[str, str]:
    """
    Resolve both resume.pdf and resume.tex paths from tracker frontmatter.

    This is a convenience function that combines parse_resume_path and
    resolve_resume_tex_path to get both artifact paths in one call.

    Args:
        resume_path_raw: Raw resume_path value from tracker frontmatter

    Returns:
        Tuple of (resume_pdf_path, resume_tex_path)

    Raises:
        ArtifactPathError: If resume_path is None, empty, or unparsable

    Requirements:
        - 6.1: Resolve resume.pdf path from tracker frontmatter resume_path
        - 6.2: Support wiki-link path format ([[...]]) and plain path format
        - 6.3: Derive resume.tex from resolved resume workspace directory
        - 6.4: Return VALIDATION_ERROR when resume_path is missing or unparsable
        - 6.5: Path resolution is deterministic for identical tracker content

    Examples:
        >>> # Wiki-link format
        >>> pdf, tex = resolve_artifact_paths("[[data/applications/amazon-352/resume/resume.pdf]]")
        >>> pdf
        'data/applications/amazon-352/resume/resume.pdf'
        >>> tex
        'data/applications/amazon-352/resume/resume.tex'

        >>> # Plain path format
        >>> pdf, tex = resolve_artifact_paths("data/applications/meta-100/resume/resume.pdf")
        >>> pdf
        'data/applications/meta-100/resume/resume.pdf'
        >>> tex
        'data/applications/meta-100/resume/resume.tex'

        >>> # Missing resume_path
        >>> resolve_artifact_paths(None)
        Traceback (most recent call last):
        ...
        ArtifactPathError: resume_path is required for artifact resolution
    """
    if resume_path_raw is None:
        raise ArtifactPathError("resume_path is required for artifact resolution")

    # Parse the resume.pdf path
    resume_pdf_path = parse_resume_path(resume_path_raw)

    if resume_pdf_path is None:
        raise ArtifactPathError("resume_path is required for artifact resolution")

    # Resolve the companion resume.tex path
    resume_tex_path = resolve_resume_tex_path(resume_pdf_path)

    return resume_pdf_path, resume_tex_path
