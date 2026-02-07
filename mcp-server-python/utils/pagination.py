"""
Pagination helper functions for bulk_read_new_jobs MCP tool.

Provides utilities for computing pagination metadata and building cursors.
"""

from typing import List, Dict, Any, Optional, Tuple
from utils.cursor import encode_cursor


def compute_has_more(rows: List[Dict[str, Any]], limit: int) -> bool:
    """
    Determine if there are more pages of results available.

    The query fetches limit+1 rows. If we got more than limit rows,
    there are more pages available.

    Args:
        rows: List of job records from database query
        limit: The requested page size

    Returns:
        True if more pages exist, False otherwise
    """
    return len(rows) > limit


def build_next_cursor(last_row: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Build a pagination cursor from the last row in the current page.

    Args:
        last_row: The last job record in the current page (None if empty page)

    Returns:
        Encoded cursor string, or None if last_row is None
    """
    if last_row is None:
        return None

    # Extract pagination state from the last row
    captured_at = last_row["captured_at"]
    record_id = last_row["id"]

    # Encode into opaque cursor
    return encode_cursor(captured_at, record_id)


def paginate_results(
    rows: List[Dict[str, Any]], limit: int
) -> Tuple[List[Dict[str, Any]], bool, Optional[str]]:
    """
    Apply pagination logic to query results.

    This function:
    1. Determines if more pages exist (has_more)
    2. Extracts the current page (first 'limit' rows)
    3. Builds next_cursor from the last row if has_more is True

    Args:
        rows: List of job records from database query (limit+1 rows)
        limit: The requested page size

    Returns:
        Tuple of (page, has_more, next_cursor) where:
        - page: List of job records for current page (up to 'limit' rows)
        - has_more: Boolean indicating if more pages exist
        - next_cursor: Encoded cursor for next page, or None if no more pages
    """
    # Handle empty result set
    if not rows:
        return ([], False, None)

    # Compute pagination metadata
    has_more = compute_has_more(rows, limit)

    # Extract current page (first 'limit' rows)
    page = rows[:limit]

    # Build next cursor if there are more pages
    if has_more and page:
        # Use the last row of the current page for the cursor
        next_cursor = build_next_cursor(page[-1])
    else:
        next_cursor = None

    return (page, has_more, next_cursor)
