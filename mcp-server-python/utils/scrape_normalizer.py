"""
Record normalization for scraped job data.

Maps raw source fields to cleaned schema with validation and filtering.
Handles LinkedIn job ID parsing, timestamp normalization, and field mapping.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# LinkedIn job URL pattern for extracting job IDs
JOB_URL_ID_RE = re.compile(r"/jobs/view/(\d+)")


def normalize_text(value: Any) -> str:
    """
    Normalize a value to a clean string.

    Args:
        value: Any value to normalize

    Returns:
        Stripped string, or empty string if value is None
    """
    if value is None:
        return ""
    return str(value).strip()


def parse_job_id(url: str, fallback: Any) -> str:
    """
    Parse LinkedIn job ID from URL with fallback.

    Attempts to extract numeric job ID from LinkedIn URL pattern.
    Falls back to source ID if parsing fails.

    Args:
        url: Job URL to parse
        fallback: Fallback ID value from source

    Returns:
        Extracted job ID or normalized fallback

    **Validates: Requirements 4.3**
    """
    if not url:
        return normalize_text(fallback)

    match = JOB_URL_ID_RE.search(url)
    if match:
        return match.group(1)

    return normalize_text(fallback)


def parse_captured_at(date_posted: Any) -> str:
    """
    Normalize timestamp to UTC ISO string.

    Parses date_posted field and converts to UTC ISO format.
    Falls back to current UTC timestamp if parsing fails.

    Args:
        date_posted: Date value from source (string or other)

    Returns:
        UTC ISO timestamp string

    **Validates: Requirements 4.4**
    """
    if not date_posted:
        return datetime.now(timezone.utc).isoformat()

    if isinstance(date_posted, str):
        try:
            # Handle ISO format with Z suffix
            dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            return datetime.now(timezone.utc).isoformat()

    return datetime.now(timezone.utc).isoformat()


def clean_record(record: Dict[str, Any], source_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Map raw source record to cleaned schema.

    Normalizes fields from JobSpy format to internal schema:
    - url: job_url or job_url_direct
    - title, description, company, location: direct mapping
    - source: override or site field
    - job_id: parsed from URL or fallback to source id
    - captured_at: normalized timestamp
    - id: generated UUID for internal tracking

    Args:
        record: Raw source record from JobSpy
        source_override: Optional source name override

    Returns:
        Cleaned record with normalized fields

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
    """
    # Map URL with fallback (Requirement 4.2)
    url = normalize_text(record.get("job_url") or record.get("job_url_direct"))

    # Direct field mappings (Requirement 4.1)
    title = normalize_text(record.get("title"))
    company = normalize_text(record.get("company"))
    location = normalize_text(record.get("location"))
    description = normalize_text(record.get("description"))

    # Source mapping with override support (Requirement 4.1)
    source = normalize_text(source_override or record.get("site") or "unknown")

    # Parse job ID from URL with fallback (Requirement 4.3)
    job_id = parse_job_id(url, record.get("id"))

    # Normalize timestamp (Requirement 4.4)
    captured_at = parse_captured_at(record.get("date_posted"))

    # Build cleaned record (Requirement 4.1, 4.5)
    return {
        "source": source,
        "company": company,
        "title": title,
        "location": location,
        "url": url,
        "description": description,
        "jobId": job_id,
        "capturedAt": captured_at,
        "id": str(uuid.uuid4()),
    }


def filter_records(
    records: List[Dict[str, Any]], require_description: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Filter cleaned records based on quality rules.

    Applies filtering rules:
    - Skip records with empty URL (always)
    - Skip records with empty description (if require_description=True)

    Args:
        records: List of cleaned records
        require_description: Whether to require non-empty descriptions

    Returns:
        Tuple of (filtered_records, skip_counts_dict)
        skip_counts_dict contains:
            - skipped_no_url: count of records without URL
            - skipped_no_description: count of records without description

    **Validates: Requirements 5.1, 5.2, 5.3**
    """
    filtered = []
    skip_counts = {
        "skipped_no_url": 0,
        "skipped_no_description": 0,
    }

    for record in records:
        # Always skip records without URL
        if not record.get("url"):
            skip_counts["skipped_no_url"] += 1
            continue

        # Optionally skip records without description
        if require_description and not record.get("description"):
            skip_counts["skipped_no_description"] += 1
            continue

        filtered.append(record)

    return filtered, skip_counts


def normalize_and_filter(
    raw_records: List[Dict[str, Any]],
    source_override: Optional[str] = None,
    require_description: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Normalize and filter raw source records.

    Combines cleaning and filtering in one pass:
    1. Clean each raw record to normalized schema
    2. Filter based on quality rules

    Args:
        raw_records: List of raw source records
        source_override: Optional source name override
        require_description: Whether to require non-empty descriptions

    Returns:
        Tuple of (cleaned_and_filtered_records, skip_counts_dict)

    **Validates: Requirements 5.1, 5.2, 5.3, 5.5**
    """
    # Clean all records
    cleaned = [clean_record(record, source_override) for record in raw_records]

    # Filter and collect skip counts
    filtered, skip_counts = filter_records(cleaned, require_description)

    return filtered, skip_counts


def serialize_payload(record: Dict[str, Any]) -> str:
    """
    Serialize cleaned record to JSON string for DB storage.

    Args:
        record: Cleaned record dictionary

    Returns:
        JSON string representation

    **Validates: Requirements 4.5**
    """
    return json.dumps(record, ensure_ascii=False)
