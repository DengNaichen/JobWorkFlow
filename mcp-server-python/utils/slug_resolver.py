"""
Slug resolution utilities for career_tailor tool.

This module provides functions to resolve deterministic application_slug
from tracker metadata, with resume_path taking precedence over fallback generation.
"""

import re
from typing import Dict, Any, Optional
from utils.artifact_paths import parse_resume_path, ArtifactPathError


def extract_slug_from_resume_path(resume_path_raw: Optional[str]) -> Optional[str]:
    """
    Extract application_slug from resume_path if available.

    The resume_path format is expected to be:
    - data/applications/<slug>/resume/resume.pdf
    - [[data/applications/<slug>/resume/resume.pdf]]

    This function parses the path and extracts the slug component.

    Args:
        resume_path_raw: Raw resume_path value from tracker frontmatter

    Returns:
        Extracted slug string, or None if resume_path is None or unparsable

    Requirements:
        - 4.1: Resolve deterministic application_slug from tracker metadata
              (resume_path first, deterministic fallback second)

    Examples:
        >>> # Wiki-link format
        >>> extract_slug_from_resume_path("[[data/applications/amazon-3629/resume/resume.pdf]]")
        'amazon-3629'

        >>> # Plain path format
        >>> extract_slug_from_resume_path("data/applications/meta-100/resume/resume.pdf")
        'meta-100'

        >>> # None input
        >>> extract_slug_from_resume_path(None)
        None

        >>> # Invalid path format
        >>> extract_slug_from_resume_path("invalid/path")
        None
    """
    if resume_path_raw is None:
        return None

    try:
        # Parse the resume_path to get the clean path
        resume_pdf_path = parse_resume_path(resume_path_raw)

        if resume_pdf_path is None:
            return None

        # Expected format: data/applications/<slug>/resume/resume.pdf
        # Use regex to extract the slug component
        pattern = r"^data/applications/([^/]+)/resume/resume\.pdf$"
        match = re.match(pattern, resume_pdf_path)

        if match:
            return match.group(1)

        # If pattern doesn't match, return None (fallback will be used)
        return None

    except (ArtifactPathError, Exception):
        # If parsing fails, return None to trigger fallback
        return None


def generate_fallback_slug(company: str, position: str, job_db_id: Optional[int]) -> str:
    """
    Generate deterministic fallback slug from tracker metadata.

    The fallback slug format is:
    - If job_db_id is available: <normalized_company>-<job_db_id>
    - If job_db_id is None: <normalized_company>-<normalized_position>

    Normalization rules:
    - Convert to lowercase
    - Replace non-alphanumeric characters with underscores
    - Collapse consecutive underscores to single underscore
    - Strip leading/trailing underscores

    Args:
        company: Company name from tracker frontmatter
        position: Position title from tracker frontmatter
        job_db_id: Optional job database ID from tracker frontmatter

    Returns:
        Deterministic fallback slug string

    Requirements:
        - 4.1: Resolve deterministic application_slug from tracker metadata
              (resume_path first, deterministic fallback second)

    Examples:
        >>> # With job_db_id
        >>> generate_fallback_slug("Amazon", "Software Engineer", 3629)
        'amazon-3629'

        >>> # Without job_db_id
        >>> generate_fallback_slug("Meta", "Senior Engineer", None)
        'meta-senior_engineer'

        >>> # Complex company name
        >>> generate_fallback_slug("General Motors", "AI Engineer", 3711)
        'general_motors-3711'

        >>> # Special characters in position
        >>> generate_fallback_slug("Google", "Backend/Full-Stack Developer", None)
        'google-backend_full_stack_developer'
    """
    # Normalize company name
    company_normalized = _normalize_text(company)

    # Generate slug based on job_db_id availability
    if job_db_id is not None:
        # Preferred format: company-id
        return f"{company_normalized}-{job_db_id}"
    else:
        # Fallback format: company-position
        position_normalized = _normalize_text(position)
        return f"{company_normalized}-{position_normalized}"


def _normalize_text(text: str) -> str:
    """
    Normalize text to a slug-safe format.

    Normalization rules:
    - Convert to lowercase
    - Replace non-alphanumeric characters with underscores
    - Collapse consecutive underscores to single underscore
    - Strip leading/trailing underscores

    Args:
        text: Input text to normalize

    Returns:
        Normalized slug-safe text

    Examples:
        >>> _normalize_text("General Motors")
        'general_motors'
        >>> _normalize_text("L'Oréal")
        'l_or_al'
        >>> _normalize_text("AT&T Inc.")
        'at_t_inc'
        >>> _normalize_text("Backend/Full-Stack Developer")
        'backend_full_stack_developer'
    """
    # Convert to lowercase
    normalized = text.lower()

    # Replace non-alphanumeric characters with underscores
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)

    # Collapse consecutive underscores
    normalized = re.sub(r"_+", "_", normalized)

    # Strip leading/trailing underscores
    normalized = normalized.strip("_")

    return normalized


def resolve_application_slug(
    tracker_data: Dict[str, Any], item_job_db_id: Optional[int] = None
) -> str:
    """
    Resolve deterministic application_slug from tracker metadata.

    Resolution logic:
    1. Try to extract slug from resume_path (if available)
    2. If extraction fails or resume_path is None, generate fallback slug
       from company/position/job_db_id

    The item_job_db_id parameter allows the caller to override the job_db_id
    from the tracker frontmatter (useful for batch processing where the item
    may provide an explicit override).

    Args:
        tracker_data: Parsed tracker data dictionary containing:
            - company: Company name (required)
            - position: Position title (required)
            - resume_path: Resume path (optional)
            - job_db_id: Job database ID (optional)
        item_job_db_id: Optional job_db_id override from batch item

    Returns:
        Deterministic application_slug string

    Raises:
        ValueError: If required fields (company, position) are missing

    Requirements:
        - 4.1: Resolve deterministic application_slug from tracker metadata
              (resume_path first, deterministic fallback second)

    Examples:
        >>> # Extract from resume_path
        >>> tracker = {
        ...     "company": "Amazon",
        ...     "position": "Software Engineer",
        ...     "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
        ...     "job_db_id": 3629
        ... }
        >>> resolve_application_slug(tracker)
        'amazon-3629'

        >>> # Fallback with job_db_id
        >>> tracker = {
        ...     "company": "Meta",
        ...     "position": "Senior Engineer",
        ...     "resume_path": None,
        ...     "job_db_id": 100
        ... }
        >>> resolve_application_slug(tracker)
        'meta-100'

        >>> # Fallback without job_db_id
        >>> tracker = {
        ...     "company": "Google",
        ...     "position": "Staff Engineer",
        ...     "resume_path": None,
        ...     "job_db_id": None
        ... }
        >>> resolve_application_slug(tracker)
        'google-staff_engineer'

        >>> # Item override for job_db_id
        >>> tracker = {
        ...     "company": "Amazon",
        ...     "position": "Engineer",
        ...     "resume_path": None,
        ...     "job_db_id": None
        ... }
        >>> resolve_application_slug(tracker, item_job_db_id=5000)
        'amazon-5000'
    """
    # Validate required fields
    company = tracker_data.get("company")
    position = tracker_data.get("position")

    if not company:
        raise ValueError("Tracker data is missing required 'company' field")
    if not position:
        raise ValueError("Tracker data is missing required 'position' field")

    # Try to extract slug from resume_path (priority 1)
    resume_path_raw = tracker_data.get("resume_path")
    slug_from_path = extract_slug_from_resume_path(resume_path_raw)

    if slug_from_path is not None:
        return slug_from_path

    # Fallback: generate slug from company/position/job_db_id (priority 2)
    # Use item_job_db_id if provided, otherwise use tracker job_db_id
    job_db_id = item_job_db_id if item_job_db_id is not None else tracker_data.get("job_db_id")

    return generate_fallback_slug(company, position, job_db_id)
