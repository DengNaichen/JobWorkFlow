"""
Database writer layer for bulk_update_job_status MCP tool.

Provides write-only access to the jobs database with transaction management
and atomic batch update semantics.
"""

import os
import sqlite3
from pathlib import Path
from typing import List, Optional

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


class JobsWriter:
    """
    Context manager for write operations on the jobs database.

    Provides transaction management with automatic rollback on exceptions
    and guaranteed connection cleanup.

    Usage:
        with JobsWriter(db_path) as writer:
            writer.ensure_updated_at_column()
            missing = writer.validate_jobs_exist([1, 2, 3])
            if not missing:
                writer.update_job_status(1, "shortlist", timestamp)
                writer.commit()
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
        Open connection and begin transaction.

        Returns:
            self: The JobsWriter instance

        Raises:
            ToolError: If database file doesn't exist or connection fails
        """
        self.resolved_path = resolve_db_path(self.db_path)

        # Check if database file exists
        if not self.resolved_path.exists():
            raise create_db_not_found_error(str(self.resolved_path))

        # Check if it's a file (not a directory)
        if not self.resolved_path.is_file():
            raise create_db_not_found_error(str(self.resolved_path))

        try:
            # Open connection in read-write mode
            self.conn = sqlite3.connect(str(self.resolved_path))

            # Configure connection
            self.conn.row_factory = sqlite3.Row

            # Begin transaction explicitly
            self.conn.execute("BEGIN")
            self._in_transaction = True

            return self

        except sqlite3.OperationalError as e:
            # Connection or operational errors
            error_msg = str(e)
            if "unable to open database" in error_msg.lower():
                raise create_db_not_found_error(str(self.resolved_path)) from e
            else:
                raise create_db_error(error_msg, retryable=True, original_error=e) from e

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

    def ensure_updated_at_column(self) -> None:
        """
        Verify that the jobs table has an updated_at column.

        This is a schema preflight check that must pass before any updates
        are executed.

        Raises:
            ToolError: If the updated_at column is missing
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        try:
            # Query table schema
            cursor = self.conn.execute("PRAGMA table_info(jobs)")
            columns = cursor.fetchall()

            # Check if updated_at column exists
            column_names = [col["name"] for col in columns]
            if "updated_at" not in column_names:
                raise create_db_error(
                    "Schema error: jobs table is missing required 'updated_at' column. Database migration required.",
                    retryable=False,
                )

        except sqlite3.Error as e:
            raise create_db_error(str(e), retryable=False, original_error=e) from e

    def ensure_finalize_columns(self) -> None:
        """
        Verify that the jobs table has all required columns for finalization.

        This is a schema preflight check that must pass before any finalize
        operations are executed. Validates presence of:
        - status
        - updated_at
        - resume_pdf_path
        - resume_written_at
        - run_id
        - attempt_count
        - last_error

        Raises:
            ToolError: If any required column is missing
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        required_columns = [
            "status",
            "updated_at",
            "resume_pdf_path",
            "resume_written_at",
            "run_id",
            "attempt_count",
            "last_error",
        ]

        try:
            # Query table schema
            cursor = self.conn.execute("PRAGMA table_info(jobs)")
            columns = cursor.fetchall()

            # Check if all required columns exist
            column_names = [col["name"] for col in columns]
            missing_columns = [col for col in required_columns if col not in column_names]

            if missing_columns:
                missing_str = ", ".join(f"'{col}'" for col in missing_columns)
                raise create_db_error(
                    f"Schema error: jobs table is missing required columns: {missing_str}. Database migration required.",
                    retryable=False,
                )

        except sqlite3.Error as e:
            raise create_db_error(str(e), retryable=False, original_error=e) from e

    def validate_jobs_exist(self, job_ids: List[int]) -> List[int]:
        """
        Check which job IDs exist in the database.

        Args:
            job_ids: List of job IDs to validate

        Returns:
            List of missing job IDs (empty if all exist)

        Raises:
            ToolError: If query execution fails
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        if not job_ids:
            return []

        try:
            # Build parameterized query with correct number of placeholders
            placeholders = ",".join("?" * len(job_ids))
            query = f"SELECT id FROM jobs WHERE id IN ({placeholders})"

            # Execute query
            cursor = self.conn.execute(query, job_ids)
            rows = cursor.fetchall()

            # Extract existing IDs
            existing_ids = {row["id"] for row in rows}

            # Find missing IDs
            missing_ids = [job_id for job_id in job_ids if job_id not in existing_ids]

            return missing_ids

        except sqlite3.Error as e:
            raise create_db_error(str(e), retryable=False, original_error=e) from e

    def update_job_status(self, job_id: int, status: str, timestamp: str) -> None:
        """
        Execute UPDATE for a single job.

        Updates both the status and updated_at fields.

        Args:
            job_id: The job ID to update
            status: The new status value
            timestamp: The ISO 8601 UTC timestamp

        Raises:
            ToolError: If UPDATE execution fails
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        try:
            # Execute parameterized UPDATE
            query = """
                UPDATE jobs
                SET status = ?,
                    updated_at = ?
                WHERE id = ?
            """
            self.conn.execute(query, (status, timestamp, job_id))

        except sqlite3.Error as e:
            raise create_db_error(str(e), retryable=False, original_error=e) from e

    def finalize_resume_written(
        self, job_id: int, resume_pdf_path: str, run_id: str, timestamp: str
    ) -> None:
        """
        Execute finalization UPDATE for a successful resume write.

        Updates the job to 'resume_written' status with all completion
        audit fields. Increments attempt_count and clears last_error.

        This method implements the success path for finalization:
        - Sets status to 'resume_written'
        - Records the validated resume PDF path
        - Records the completion timestamp
        - Associates with the batch run_id
        - Increments attempt counter
        - Clears any previous error state

        Args:
            job_id: The job ID to finalize
            resume_pdf_path: Path to the validated resume PDF artifact
            run_id: Batch run identifier for this finalization
            timestamp: ISO 8601 UTC timestamp for resume_written_at and updated_at

        Raises:
            ToolError: If UPDATE execution fails
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        try:
            # Execute parameterized UPDATE with all finalization fields
            query = """
                UPDATE jobs
                SET status = ?,
                    resume_pdf_path = ?,
                    resume_written_at = ?,
                    run_id = ?,
                    attempt_count = COALESCE(attempt_count, 0) + 1,
                    last_error = NULL,
                    updated_at = ?
                WHERE id = ?
            """
            cursor = self.conn.execute(
                query,
                (JobDbStatus.RESUME_WRITTEN, resume_pdf_path, timestamp, run_id, timestamp, job_id),
            )

            # Missing target job is a per-item finalization failure.
            if cursor.rowcount == 0:
                raise create_db_error(f"No job found with id {job_id}", retryable=False)

        except sqlite3.Error as e:
            raise create_db_error(str(e), retryable=False, original_error=e) from e

    def fallback_to_reviewed(self, job_id: int, last_error: str, timestamp: str) -> None:
        """
        Execute fallback UPDATE to 'reviewed' status after finalization failure.

        This method implements the compensation path when finalization fails
        (e.g., tracker sync failure after DB success). It returns the job to
        a retryable 'reviewed' state with error context.

        Updates performed:
        - Sets status to 'reviewed' (retryable state)
        - Records the sanitized error message in last_error
        - Updates the timestamp
        - Preserves attempt_count from the already-recorded finalize attempt

        This ensures failed finalization never leaves jobs in an ambiguous
        'resume_written' state when the full commit sequence didn't complete.

        Args:
            job_id: The job ID to update
            last_error: Sanitized error message describing the failure
            timestamp: ISO 8601 UTC timestamp for updated_at

        Raises:
            ToolError: If UPDATE execution fails
        """
        if self.conn is None:
            raise create_db_error("Connection not established", retryable=False)

        try:
            # Execute parameterized UPDATE for fallback compensation
            query = """
                UPDATE jobs
                SET status = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE id = ?
            """
            cursor = self.conn.execute(query, (JobDbStatus.REVIEWED, last_error, timestamp, job_id))

            if cursor.rowcount == 0:
                raise create_db_error(
                    f"No job found with id {job_id} during fallback", retryable=False
                )

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
            # Keep writer reusable for multi-step flows (e.g. finalize then fallback)
            # by immediately starting a new transaction after each successful commit.
            self.conn.execute("BEGIN")
            self._in_transaction = True

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
