"""
Job schema mapping for bulk_read_new_jobs MCP tool.

Provides functions to map database rows to the stable output schema.

Note: The core mapping logic now lives in ``schemas.bulk_read_new_jobs.JobRecord``.
This module keeps the ``to_job_schema`` helper for backward compatibility and as a
convenient dict-in / dict-out shortcut.
"""

from typing import Any, Dict

from schemas.bulk_read_new_jobs import JobRecord


def to_job_schema(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a database row to the fixed job output schema.

    This function ensures:
    - Only fixed schema fields are included in output
    - Missing values are handled consistently (as None)
    - Empty strings are normalised to None
    - All values are JSON-serializable
    - Schema stability across all responses

    Delegates to ``JobRecord.model_validate`` which enforces extra='ignore'
    and empty-string-to-None normalisation via a model validator.

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
    return JobRecord.model_validate(row).model_dump()
