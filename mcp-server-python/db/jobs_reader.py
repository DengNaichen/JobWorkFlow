"""
Database reader layer for bulk_read_new_jobs MCP tool.

Provides read-only access to the jobs database with connection management
and deterministic query execution.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.errors import (
    create_db_error,
    create_db_not_found_error,
)
from models.status import JobDbStatus

# Default database path relative to repository root
DEFAULT_DB_PATH = "data/capture/jobs.db"


def resolve_db_path(db_path: Optional[str] = None) -> Path:
    """
    Resolve the database path with support for overrides and defaults.

    Resolution order:
    1. Provided db_path parameter
    2. JOBWORKFLOW_DB environment variable
    3. JOBWORKFLOW_ROOT/data/capture/jobs.db
    4. Default path: data/capture/jobs.db

    Args:
        db_path: Optional database path override

    Returns:
        Resolved absolute Path to the database
    """
    # Use provided path first
    if db_path is not None:
        path_str = db_path
    else:
        # Then explicit env override
        db_env = os.getenv("JOBWORKFLOW_DB")
        if db_env:
            path_str = db_env
        else:
            # Then JOBWORKFLOW_ROOT fallback
            root_env = os.getenv("JOBWORKFLOW_ROOT")
            if root_env:
                return Path(root_env) / "data" / "capture" / "jobs.db"
            # Final default
            path_str = DEFAULT_DB_PATH

    path = Path(path_str)

    # If relative, resolve from repository root
    if not path.is_absolute():
        # Find repository root (parent of mcp-server-python directory)
        current_file = Path(__file__).resolve()
        repo_root = current_file.parents[2]  # db/ -> mcp-server-python/ -> repo/
        path = repo_root / path

    return path


@contextmanager
def get_connection(db_path: Optional[str] = None):
    """
    Context manager for SQLite database connections.

    Ensures connections are always properly closed, even on errors.

    Args:
        db_path: Optional database path override

    Yields:
        sqlite3.Connection: Database connection

    Raises:
        ToolError: If database file doesn't exist or connection fails
    """
    resolved_path = resolve_db_path(db_path)

    # Check if database file exists
    if not resolved_path.exists():
        raise create_db_not_found_error(str(resolved_path))

    # Check if it's a file (not a directory)
    if not resolved_path.is_file():
        raise create_db_not_found_error(str(resolved_path))

    conn = None
    try:
        # Open connection in read-only mode for safety
        # URI mode allows read-only flag
        uri = f"file:{resolved_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)

        # Configure connection for dictionary-style row access
        conn.row_factory = sqlite3.Row

        yield conn

    except sqlite3.OperationalError as e:
        # Connection or operational errors
        error_msg = str(e)
        if "unable to open database" in error_msg.lower():
            raise create_db_not_found_error(str(resolved_path)) from e
        else:
            raise create_db_error(error_msg, retryable=True, original_error=e) from e

    except sqlite3.Error as e:
        # Other SQLite errors
        raise create_db_error(str(e), retryable=False, original_error=e) from e

    finally:
        # Always close the connection
        if conn is not None:
            conn.close()


def query_new_jobs(
    conn: sqlite3.Connection, limit: int, cursor: Optional[Tuple[str, int]] = None
) -> List[Dict[str, Any]]:
    """
    Query jobs with status='new' in deterministic order.

    Results are ordered by (captured_at DESC, id DESC) to ensure:
    - Newest jobs first
    - Deterministic ordering for pagination
    - No duplicates across pages

    Args:
        conn: Database connection
        limit: Maximum number of rows to return (will query limit+1 for has_more)
        cursor: Optional pagination cursor (captured_at, id) tuple

    Returns:
        List of job records as dictionaries

    Raises:
        ToolError: If query execution fails
    """
    try:
        # Build query based on whether we have a cursor
        if cursor is None:
            # First page - no cursor boundary
            query = """
                SELECT
                    id,
                    job_id,
                    title,
                    company,
                    description,
                    url,
                    location,
                    source,
                    status,
                    captured_at
                FROM jobs
                WHERE status = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
            """
            params = (JobDbStatus.NEW, limit + 1)
        else:
            # Subsequent page - apply cursor boundary
            cursor_ts, cursor_id = cursor
            query = """
                SELECT
                    id,
                    job_id,
                    title,
                    company,
                    description,
                    url,
                    location,
                    source,
                    status,
                    captured_at
                FROM jobs
                WHERE status = ?
                  AND (
                    captured_at < ?
                    OR (captured_at = ? AND id < ?)
                  )
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
            """
            params = (JobDbStatus.NEW, cursor_ts, cursor_ts, cursor_id, limit + 1)

        # Execute query
        cursor_obj = conn.execute(query, params)
        rows = cursor_obj.fetchall()

        # Convert Row objects to dictionaries
        results = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "job_id": row["job_id"],
                    "title": row["title"],
                    "company": row["company"],
                    "description": row["description"],
                    "url": row["url"],
                    "location": row["location"],
                    "source": row["source"],
                    "status": row["status"],
                    "captured_at": row["captured_at"],
                }
            )

        return results

    except sqlite3.Error as e:
        # Query execution error
        raise create_db_error(str(e), retryable=False, original_error=e) from e


def query_shortlist_jobs(conn: sqlite3.Connection, limit: int) -> List[Dict[str, Any]]:
    """
    Query jobs with status='shortlist' in deterministic order.

    Results are ordered by (captured_at DESC, id DESC) to ensure:
    - Newest jobs first
    - Deterministic ordering for tracker generation
    - Consistent results across repeated calls

    This function is read-only and does not modify any database records.
    Returns fixed fields required for tracker generation.

    Args:
        conn: Database connection
        limit: Maximum number of rows to return

    Returns:
        List of job records as dictionaries with fields:
        - id: Database primary key
        - job_id: External job identifier
        - title: Job title
        - company: Company name
        - description: Job description text
        - url: Original job posting URL
        - captured_at: Timestamp when job was captured
        - status: Job status (will be 'shortlist')

    Raises:
        ToolError: If query execution fails
    """
    try:
        query = """
            SELECT
                id,
                job_id,
                title,
                company,
                description,
                url,
                captured_at,
                status
            FROM jobs
            WHERE status = ?
            ORDER BY captured_at DESC, id DESC
            LIMIT ?
        """
        params = (JobDbStatus.SHORTLIST, limit)

        # Execute query
        cursor_obj = conn.execute(query, params)
        rows = cursor_obj.fetchall()

        # Convert Row objects to dictionaries
        results = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "job_id": row["job_id"],
                    "title": row["title"],
                    "company": row["company"],
                    "description": row["description"],
                    "url": row["url"],
                    "captured_at": row["captured_at"],
                    "status": row["status"],
                }
            )

        return results

    except sqlite3.Error as e:
        # Query execution error
        raise create_db_error(str(e), retryable=False, original_error=e) from e
