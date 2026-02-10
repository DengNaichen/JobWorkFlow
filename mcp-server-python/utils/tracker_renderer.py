"""
Tracker markdown renderer for initialize_shortlist_trackers tool.

This module provides functions to render stable tracker markdown files
with required frontmatter fields and section structure.
"""

from typing import Any, Dict

import yaml
from models.status import JobTrackerStatus


def render_tracker_markdown(job: Dict[str, Any], plan: Dict[str, Any]) -> str:
    """
    Render complete tracker markdown content with frontmatter and sections.

    The tracker includes:
    - YAML frontmatter with required stable fields
    - ## Job Description section with description text or fallback
    - ## Notes section (empty)

    Initial tracker status is set to "Reviewed" for newly initialized trackers.

    Args:
        job: Job record dictionary with fields from database:
            - id: Database primary key
            - job_id: External job identifier
            - title: Job title
            - company: Company name
            - description: Job description text (may be None)
            - url: Original job posting URL
            - captured_at: Timestamp when job was captured
        plan: Planning dictionary from tracker_planner.plan_tracker():
            - resume_path: Wiki-link path for resume PDF
            - cover_letter_path: Wiki-link path for cover letter PDF
            - application_slug: Workspace directory slug

    Returns:
        Complete markdown content as string

    Requirements:
        - 2.3: Include required frontmatter fields
        - 2.4: Include ## Job Description section
        - 2.5: Include ## Notes section
        - 2.6: Set initial status to "Reviewed"
        - 10.1: Use exact "## Job Description" heading
        - 10.2: Stable frontmatter field names
        - 10.5: Obsidian Dataview compatible YAML

    Examples:
        >>> job = {
        ...     "id": 3629,
        ...     "job_id": "4368663835",
        ...     "title": "Software Engineer",
        ...     "company": "Amazon",
        ...     "description": "Build scalable systems...",
        ...     "url": "https://example.com/job/123",
        ...     "captured_at": "2026-02-04T15:30:00"
        ... }
        >>> plan = {
        ...     "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
        ...     "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
        ...     "application_slug": "amazon-3629"
        ... }
        >>> content = render_tracker_markdown(job, plan)
        >>> "## Job Description" in content
        True
        >>> "status: Reviewed" in content
        True
    """
    # Extract application date from captured_at timestamp
    application_date = _extract_date(job["captured_at"])

    # Build frontmatter dictionary with required stable fields
    frontmatter = {
        "job_db_id": job["id"],
        "job_id": job["job_id"],
        "company": job["company"],
        "position": job["title"],
        "status": JobTrackerStatus.REVIEWED.value,  # Initial tracker status
        "application_date": application_date,
        "reference_link": job["url"],
        "resume_path": plan["resume_path"],
        "cover_letter_path": plan["cover_letter_path"],
        # Compatibility fields for current tracker ecosystem
        "next_action": ["Wait for feedback"],
        "salary": 0,
        "website": "",
    }

    # Render YAML frontmatter
    yaml_content = yaml.dump(
        frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False
    )

    # Build job description section content
    description_content = _render_job_description(job.get("description"))

    # Assemble complete markdown document
    markdown_parts = [
        "---",
        yaml_content.rstrip(),
        "---",
        "",
        "## Job Description",
        "",
        description_content,
        "",
        "## Notes",
        "",
    ]

    return "\n".join(markdown_parts)


def _extract_date(captured_at: str) -> str:
    """
    Extract ISO date (YYYY-MM-DD) from timestamp string.

    Handles both ISO format with T separator and space separator.

    Args:
        captured_at: Timestamp string (e.g., "2026-02-04T15:30:00" or "2026-02-04 15:30:00")

    Returns:
        ISO date string in YYYY-MM-DD format

    Requirements:
        - 10.4: Use ISO date format YYYY-MM-DD

    Examples:
        >>> _extract_date("2026-02-04T15:30:00")
        '2026-02-04'
        >>> _extract_date("2026-02-04 15:30:00")
        '2026-02-04'
    """
    # Handle both T and space separators
    if "T" in captured_at:
        return captured_at.split("T")[0]
    else:
        return captured_at.split(" ")[0]


def _render_job_description(description: Any) -> str:
    """
    Render job description content with fallback for missing descriptions.

    Args:
        description: Job description text (may be None or empty string)

    Returns:
        Description text or fallback message

    Requirements:
        - 2.4: Insert description text or fallback when missing

    Examples:
        >>> _render_job_description("Build scalable systems")
        'Build scalable systems'
        >>> _render_job_description(None)
        'No description available.'
        >>> _render_job_description("")
        'No description available.'
    """
    if description is None or description == "":
        return "No description available."
    return description
