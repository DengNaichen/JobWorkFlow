"""
Capture writer for persisting per-term scrape results to JSON files.

This module provides functionality to write cleaned job records to JSON
capture files with deterministic filename strategies.

Requirements: 9.1, 9.3, 9.5
"""

from __future__ import annotations

import json
import re
from typing import Any

from utils.path_resolution import resolve_repo_relative_path


def slugify(text: str) -> str:
    """
    Convert text to a filesystem-safe slug.

    Args:
        text: Input text to slugify

    Returns:
        Slugified text with only lowercase alphanumeric and underscores

    Examples:
        >>> slugify("AI Engineer")
        'ai_engineer'
        >>> slugify("Backend/Full-Stack Developer")
        'backend_full_stack_developer'
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "query"


def build_capture_filename(
    term: str,
    location: str,
    hours_old: int,
    sites: list[str],
) -> str:
    """
    Build deterministic capture filename for a scrape term.

    Filename format: jobspy_{site}_{term_slug}_{location_slug}_{hours}h.json

    Args:
        term: Search term
        location: Search location
        hours_old: Recency window in hours
        sites: List of source sites (uses first site for filename)

    Returns:
        Deterministic filename string

    Requirements: 9.1, 9.3

    Examples:
        >>> build_capture_filename("ai engineer", "Ontario, Canada", 2, ["linkedin"])
        'jobspy_linkedin_ai_engineer_ontario_canada_2h.json'
    """
    term_slug = slugify(term)
    location_slug = slugify(location)
    site = sites[0] if sites else "unknown"

    return f"jobspy_{site}_{term_slug}_{location_slug}_{hours_old}h.json"


def write_capture_file(
    records: list[dict[str, Any]],
    term: str,
    location: str,
    hours_old: int,
    sites: list[str],
    capture_dir: str,
) -> str:
    """
    Write cleaned records to a JSON capture file.

    Args:
        records: List of cleaned job records to write
        term: Search term (used for filename)
        location: Search location (used for filename)
        hours_old: Recency window in hours (used for filename)
        sites: List of source sites (used for filename)
        capture_dir: Directory to write capture file (relative or absolute)

    Returns:
        Relative path to the written capture file (from repo root)

    Raises:
        OSError: If file write fails

    Requirements: 9.1, 9.3, 9.5

    Examples:
        >>> records = [{"url": "https://example.com/job1", "title": "Engineer"}]
        >>> path = write_capture_file(records, "ai engineer", "Ontario, Canada", 2, ["linkedin"], "data/capture")
        >>> path
        'data/capture/jobspy_linkedin_ai_engineer_ontario_canada_2h.json'
    """
    # Resolve capture directory path
    capture_path = resolve_repo_relative_path(capture_dir)

    # Ensure directory exists
    capture_path.mkdir(parents=True, exist_ok=True)

    # Build filename
    filename = build_capture_filename(term, location, hours_old, sites)

    # Full file path
    file_path = capture_path / filename

    # Write JSON with pretty formatting
    file_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    # Return relative path from repo root
    from utils.path_resolution import get_repo_root

    repo_root = get_repo_root()

    try:
        relative_path = file_path.relative_to(repo_root)
        return str(relative_path)
    except ValueError:
        # If file is outside repo root, return as-is
        return str(file_path)
