"""
Tracker planning utilities for deterministic slug and filename generation.

This module provides functions to compute deterministic application slugs,
tracker filenames, and paths for the initialize_shortlist_trackers tool.
"""

import re
from pathlib import Path
from typing import Dict, Any


def normalize_company_name(company: str) -> str:
    """
    Normalize company name to a slug-safe format.

    Normalization rules:
    - Convert to lowercase
    - Replace non-alphanumeric characters with underscores
    - Collapse consecutive underscores to single underscore
    - Strip leading/trailing underscores

    Args:
        company: Raw company name

    Returns:
        Normalized company slug component

    Examples:
        >>> normalize_company_name("General Motors")
        'general_motors'
        >>> normalize_company_name("L'Oréal")
        'l_or_al'
        >>> normalize_company_name("AT&T Inc.")
        'at_t_inc'
    """
    # Convert to lowercase
    normalized = company.lower()

    # Replace non-alphanumeric characters with underscores
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)

    # Collapse consecutive underscores
    normalized = re.sub(r"_+", "_", normalized)

    # Strip leading/trailing underscores
    normalized = normalized.strip("_")

    return normalized


def generate_application_slug(company: str, job_db_id: int) -> str:
    """
    Generate deterministic application slug for workspace directory naming.

    The slug format is: <normalized_company>-<job_db_id>
    This ensures uniqueness even when multiple jobs exist for the same company.

    Args:
        company: Company name from job record
        job_db_id: Database primary key (id field)

    Returns:
        Deterministic application slug

    Examples:
        >>> generate_application_slug("General Motors", 3711)
        'general_motors-3711'
        >>> generate_application_slug("Amazon", 3629)
        'amazon-3629'
    """
    company_slug = normalize_company_name(company)
    return f"{company_slug}-{job_db_id}"


def generate_tracker_filename(company: str, job_db_id: int, captured_at: str) -> str:
    """
    Generate deterministic tracker filename.

    The filename format is: <captured_date>-<normalized_company>-<job_db_id>.md

    Args:
        company: Company name from job record
        job_db_id: Database primary key (id field)
        captured_at: ISO timestamp string from database (e.g., "2026-02-04T15:30:00")

    Returns:
        Deterministic tracker filename with .md extension

    Examples:
        >>> generate_tracker_filename("Amazon", 3629, "2026-02-04T15:30:00")
        '2026-02-04-amazon-3629.md'
        >>> generate_tracker_filename("General Motors", 3711, "2026-02-04T10:00:00")
        '2026-02-04-general_motors-3711.md'
    """
    # Extract date from captured_at timestamp
    # Handle both ISO format with T separator and space separator
    if "T" in captured_at:
        date_str = captured_at.split("T")[0]
    else:
        date_str = captured_at.split(" ")[0]

    # Normalize company name
    company_slug = normalize_company_name(company)

    # Build filename
    return f"{date_str}-{company_slug}-{job_db_id}.md"


def compute_tracker_path(
    company: str, job_db_id: int, captured_at: str, trackers_dir: str = "trackers"
) -> Path:
    """
    Compute full tracker file path from trackers directory and job data.

    Args:
        company: Company name from job record
        job_db_id: Database primary key (id field)
        captured_at: ISO timestamp string from database
        trackers_dir: Base directory for tracker files (default: "trackers")

    Returns:
        Path object for the tracker file

    Examples:
        >>> compute_tracker_path("Amazon", 3629, "2026-02-04T15:30:00")
        Path('trackers/2026-02-04-amazon-3629.md')
        >>> compute_tracker_path("Meta", 3630, "2026-02-04T16:00:00", "custom/trackers")
        Path('custom/trackers/2026-02-04-meta-3630.md')
    """
    filename = generate_tracker_filename(company, job_db_id, captured_at)
    return Path(trackers_dir) / filename


def compute_resume_path(application_slug: str) -> str:
    """
    Compute wiki-link path for resume PDF.

    Args:
        application_slug: Application workspace slug

    Returns:
        Wiki-link formatted path string for resume

    Examples:
        >>> compute_resume_path("amazon-3629")
        '[[data/applications/amazon-3629/resume/resume.pdf]]'
    """
    return f"[[data/applications/{application_slug}/resume/resume.pdf]]"


def compute_cover_letter_path(application_slug: str) -> str:
    """
    Compute wiki-link path for cover letter PDF.

    Args:
        application_slug: Application workspace slug

    Returns:
        Wiki-link formatted path string for cover letter

    Examples:
        >>> compute_cover_letter_path("amazon-3629")
        '[[data/applications/amazon-3629/cover/cover-letter.pdf]]'
    """
    return f"[[data/applications/{application_slug}/cover/cover-letter.pdf]]"


def compute_workspace_directories(
    application_slug: str, base_dir: str = "data/applications"
) -> Dict[str, Path]:
    """
    Compute required workspace directories for a job application.

    Args:
        application_slug: Application workspace slug
        base_dir: Base directory for applications (default: "data/applications")

    Returns:
        Dictionary with directory paths:
        - workspace_root: Root directory for this application
        - resume_dir: Directory for resume files
        - cover_dir: Directory for cover letter files

    Examples:
        >>> dirs = compute_workspace_directories("amazon-3629")
        >>> dirs["resume_dir"]
        Path('data/applications/amazon-3629/resume')
        >>> dirs["cover_dir"]
        Path('data/applications/amazon-3629/cover')
    """
    workspace_root = Path(base_dir) / application_slug
    resume_dir = workspace_root / "resume"
    cover_dir = workspace_root / "cover"

    return {"workspace_root": workspace_root, "resume_dir": resume_dir, "cover_dir": cover_dir}


def plan_tracker(job: Dict[str, Any], trackers_dir: str = "trackers") -> Dict[str, Any]:
    """
    Plan all tracker-related paths and metadata for a job.

    This is a convenience function that computes all planning outputs
    needed for tracker initialization in a single call.

    Args:
        job: Job record dictionary with keys: id, company, captured_at
        trackers_dir: Base directory for tracker files (default: "trackers")

    Returns:
        Dictionary with planning results:
        - application_slug: Workspace directory slug
        - tracker_filename: Tracker markdown filename
        - tracker_path: Full path to tracker file
        - exists: Boolean indicating if tracker file already exists
        - resume_path: Wiki-link path for resume PDF
        - cover_letter_path: Wiki-link path for cover letter PDF
        - workspace_dirs: Dictionary of workspace directory paths

    Examples:
        >>> job = {"id": 3629, "company": "Amazon", "captured_at": "2026-02-04T15:30:00"}
        >>> plan = plan_tracker(job)
        >>> plan["application_slug"]
        'amazon-3629'
        >>> plan["tracker_filename"]
        '2026-02-04-amazon-3629.md'
        >>> plan["resume_path"]
        '[[data/applications/amazon-3629/resume/resume.pdf]]'
    """
    job_db_id = job["id"]
    company = job["company"]
    captured_at = job["captured_at"]

    # Generate all planning components
    application_slug = generate_application_slug(company, job_db_id)
    tracker_filename = generate_tracker_filename(company, job_db_id, captured_at)
    tracker_path = compute_tracker_path(company, job_db_id, captured_at, trackers_dir)

    # Compute workspace paths
    resume_path = compute_resume_path(application_slug)
    cover_letter_path = compute_cover_letter_path(application_slug)
    workspace_dirs = compute_workspace_directories(application_slug)

    # Check if tracker file already exists
    exists = tracker_path.exists()

    return {
        "application_slug": application_slug,
        "tracker_filename": tracker_filename,
        "tracker_path": tracker_path,
        "exists": exists,
        "resume_path": resume_path,
        "cover_letter_path": cover_letter_path,
        "workspace_dirs": workspace_dirs,
    }
