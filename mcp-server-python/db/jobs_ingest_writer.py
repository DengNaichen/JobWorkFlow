"""
Database writer layer for scrape_jobs ingestion.

Provides schema bootstrap and insert/dedupe operations for ingesting
scraped job records into the jobs database with idempotent semantics.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from models.errors import create_db_error, create_validation_error


# Default database path relative to repository root
DEFAULT_DB_PATH = "data/capture/jobs.db"

# Allowed status values for job records (Requirement 8.2)
ALLOWED_STATUSES = {"new", "shortlist", "reviewed", "reject", "resume_written", "applied"}


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


def ensure_parent_dirs(db_path: Path) -> None:
    """
    Ensure parent directories exist for the database file.

    Creates all parent directories if they don't exist.

    Args:
        db_path: Resolved database path

    Raises:
        ToolError: If directory creation fails
    """
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise create_db_error(
            f"Failed to create parent directories: {str(e)}", retryable=False, original_error=e
        ) from e


def bootstrap_schema(conn: sqlite3.Connection) -> None:
    """
    Bootstrap the jobs table and required indexes if they don't exist.

    Creates:
    - jobs table with all required columns
    - idx_jobs_status index on status column for efficient filtering

    This operation is idempotent - safe to call on existing databases.

    Args:
        conn: Database connection

    Raises:
        ToolError: If schema creation fails
    """
    try:
        # Create jobs table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                title TEXT,
                company TEXT,
                description TEXT,
                url TEXT NOT NULL UNIQUE,
                location TEXT,
                source TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                captured_at TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)

        # Create status index if it doesn't exist
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON jobs(status)
        """)

        # Commit schema changes
        conn.commit()

    except sqlite3.Error as e:
        raise create_db_error(
            f"Failed to bootstrap schema: {str(e)}", retryable=False, original_error=e
        ) from e


class JobsIngestWriter:
    """
    Context manager for ingestion write operations on the jobs database.

    Provides schema bootstrap and insert/dedupe operations with transaction
    management and guaranteed connection cleanup.

    Usage:
        with JobsIngestWriter(db_path) as writer:
            inserted, duplicates = writer.insert_cleaned_records(records, status)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize writer with database path.

        Args:
            db_path: Optional database path override
        """
        self.db_path = db_path
        self.resolved_path: Optional[Path] = None
        self.conn: Optional[sqlite3.Connection] = None
        self._in_transaction = False

    def __enter__(self):
        """
        Open connection, ensure schema, and begin transaction.

        Returns:
            self: The JobsIngestWriter instance

        Raises:
            ToolError: If database operations fail
        """
        self.resolved_path = resolve_db_path(self.db_path)

        # Ensure parent directories exist
        ensure_parent_dirs(self.resolved_path)

        try:
            # Open connection in read-write mode (creates file if needed)
            self.conn = sqlite3.connect(str(self.resolved_path))

            # Configure connection
            self.conn.row_factory = sqlite3.Row

            # Bootstrap schema (idempotent)
            bootstrap_schema(self.conn)

            # Begin transaction explicitly
            self.conn.execute("BEGIN")
            self._in_transaction = True

            return self

        except sqlite3.OperationalError as e:
            # Connection or operational errors
            raise create_db_error(str(e), retryable=True, original_error=e) from e

        except sqlite3.Error as e:
            # Other SQLite errors
            raise create_db_error(str(e), retryable=False, original_error=e) from e

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Rollback on exception, close connection always.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        Returns:
            False to propagate exceptions
        """
        try:
            # Rollback if there was an exception and we're in a transaction
            if exc_type is not None and self._in_transaction:
                self.rollback()
        finally:
            # Always close the connection
            if self.conn is not None:
                self.conn.close()
                self.conn = None

        # Don't suppress exceptions
        return False

    def insert_cleaned_records(
        self, records: list[Dict[str, Any]], status: str = "new"
    ) -> Tuple[int, int]:
        """
        Insert cleaned records with deduplication by URL.

        Uses INSERT OR IGNORE to implement idempotent insert semantics:
        - New URLs are inserted and counted as inserted_count
        - Duplicate URLs are ignored and counted as duplicate_count
        - Existing rows are never modified

        Enforces boundary behavior (Requirements 8.1, 8.2, 8.3):
        - Insert-only semantics (no UPDATE or DELETE)
        - Status validation against allowed values
        - Default status is 'new'
        - Existing rows unchanged on dedupe hits

        Args:
            records: List of cleaned job records with normalized fields
            status: Initial status for inserted rows (default: 'new')

        Returns:
            Tuple of (inserted_count, duplicate_count)

        Raises:
            ToolError: If insert operations fail or status is invalid
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        # Validate status parameter (Requirement 8.2)
        if not isinstance(status, str):
            raise create_validation_error(
                f"Invalid status type: expected string, got {type(status).__name__}"
            )

        if not status:
            raise create_validation_error("Invalid status: cannot be empty")

        if status != status.strip():
            raise create_validation_error(
                f"Invalid status: '{status}' contains leading or trailing whitespace"
            )

        if status not in ALLOWED_STATUSES:
            allowed_list = ", ".join(sorted(ALLOWED_STATUSES))
            raise create_validation_error(
                f"Invalid status value: '{status}'. Allowed values are: {allowed_list}"
            )

        if not records:
            return (0, 0)

        inserted_count = 0
        duplicate_count = 0

        try:
            for record in records:
                # Execute parameterized INSERT OR IGNORE (Requirement 8.3)
                # This ensures insert-only semantics - existing rows are never updated
                query = """
                    INSERT OR IGNORE INTO jobs (
                        url,
                        title,
                        description,
                        source,
                        job_id,
                        location,
                        company,
                        captured_at,
                        payload_json,
                        created_at,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                cursor = self.conn.execute(
                    query,
                    (
                        record["url"],
                        record.get("title", ""),
                        record.get("description", ""),
                        record.get("source", ""),
                        record.get("job_id", ""),
                        record.get("location", ""),
                        record.get("company", ""),
                        record.get("captured_at", ""),
                        record.get("payload_json", "{}"),
                        record.get("created_at", ""),
                        status,
                    ),
                )

                # Check if row was inserted (rowcount > 0) or ignored (rowcount == 0)
                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    duplicate_count += 1

            return (inserted_count, duplicate_count)

        except sqlite3.Error as e:
            raise create_db_error(str(e), retryable=False, original_error=e) from e

    def commit(self) -> None:
        """
        Commit the transaction.

        Raises:
            ToolError: If commit fails
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        if not self._in_transaction:
            return

        try:
            self.conn.commit()
            self._in_transaction = False

        except sqlite3.Error as e:
            raise create_db_error(
                f"Failed to commit transaction: {str(e)}", retryable=True, original_error=e
            ) from e

    def rollback(self) -> None:
        """
        Rollback the transaction.

        Does not raise exceptions - failures are logged but not propagated
        since rollback is often called during error handling.
        """
        if self.conn is None:
            return

        if not self._in_transaction:
            return

        try:
            self.conn.rollback()
            self._in_transaction = False
        except sqlite3.Error:
            # Suppress rollback errors - we're already in error handling
            pass
