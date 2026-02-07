"""
Job schema mapping for bulk_read_new_jobs MCP tool.

Provides functions to map database rows to the stable output schema
with consistent handling of missing values and JSON serialization.
"""

from typing import Dict, Any, Optional


def to_job_schema(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a database row to the fixed job output schema.

    This function ensures:
    - Only fixed schema fields are included in output
    - Missing values are handled consistently (as None)
    - All values are JSON-serializable
    - Schema stability across all responses

    Fixed schema fields:
    - id: integer
    - job_id: string
    - title: string
    - company: string
    - description: string
    - url: string
    - location: string
    - source: string
    - status: string
    - captured_at: string (ISO 8601 timestamp)

    Args:
        row: Database row as dictionary

    Returns:
        Dictionary with fixed schema fields, JSON-serializable

    Requirements:
        - 3.1: Include all fixed fields
        - 3.2: Do not include arbitrary additional columns
        - 3.3: Handle missing values consistently
        - 3.4: Ensure JSON serializability
        - 3.5: Maintain stable schema contract
    """
    # Map to fixed schema with explicit field selection
    # This ensures no arbitrary database columns leak into the output
    return {
        "id": _get_field(row, "id", None),
        "job_id": _get_field(row, "job_id", None),
        "title": _get_field(row, "title", None),
        "company": _get_field(row, "company", None),
        "description": _get_field(row, "description", None),
        "url": _get_field(row, "url", None),
        "location": _get_field(row, "location", None),
        "source": _get_field(row, "source", None),
        "status": _get_field(row, "status", None),
        "captured_at": _get_field(row, "captured_at", None),
    }


def _get_field(row: Dict[str, Any], field: str, default: Optional[Any] = None) -> Any:
    """
    Safely extract a field from a row with consistent default handling.

    Args:
        row: Database row dictionary
        field: Field name to extract
        default: Default value if field is missing or None

    Returns:
        Field value or default
    """
    value = row.get(field, default)
    # Return None for empty strings to maintain consistency
    # This ensures missing values are represented uniformly
    if value == "":
        return None
    return value
