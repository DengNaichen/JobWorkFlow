"""
Unit tests for JobsWriter class.

Tests transaction management, connection handling, and write operations.
"""

import os
import sqlite3
import tempfile

import pytest
from db.jobs_writer import JobsWriter, resolve_db_path
from models.errors import ErrorCode, ToolError
from models.status import JobDbStatus


@pytest.fixture
def temp_db():
    """Create a temporary database with jobs table for testing."""
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create database with schema
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            description TEXT,
            source TEXT,
            job_id TEXT,
            location TEXT,
            company TEXT,
            captured_at TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            updated_at TEXT
        )
    """)

    # Insert test data
    conn.execute("""
        INSERT INTO jobs (url, title, company, status, payload_json, created_at, captured_at)
        VALUES
            ('http://example.com/job1', 'Job 1', 'Company A', 'new', '{}', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
            ('http://example.com/job2', 'Job 2', 'Company B', 'shortlist', '{}', '2024-01-02T00:00:00Z', '2024-01-02T00:00:00Z'),
            ('http://example.com/job3', 'Job 3', 'Company C', 'new', '{}', '2024-01-03T00:00:00Z', '2024-01-03T00:00:00Z')
    """)
    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except Exception:
        pass


@pytest.fixture
def temp_db_no_updated_at():
    """Create a temporary database without updated_at column for testing."""
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create database with schema missing updated_at
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except Exception:
        pass


@pytest.fixture
def temp_db_missing_finalize_columns():
    """Create a temporary database missing finalize columns for testing."""
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create database with schema missing finalize columns
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except Exception:
        pass


@pytest.fixture
def temp_db_with_finalize_columns():
    """Create a temporary database with all finalize columns for testing."""
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create database with complete schema including finalize columns
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            description TEXT,
            source TEXT,
            job_id TEXT,
            location TEXT,
            company TEXT,
            captured_at TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            updated_at TEXT,
            resume_pdf_path TEXT,
            resume_written_at TEXT,
            run_id TEXT,
            attempt_count INTEGER DEFAULT 0,
            last_error TEXT
        )
    """)

    # Insert test data
    conn.execute("""
        INSERT INTO jobs (url, title, company, status, payload_json, created_at, captured_at)
        VALUES
            ('http://example.com/job1', 'Job 1', 'Company A', 'new', '{}', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z'),
            ('http://example.com/job2', 'Job 2', 'Company B', 'shortlist', '{}', '2024-01-02T00:00:00Z', '2024-01-02T00:00:00Z'),
            ('http://example.com/job3', 'Job 3', 'Company C', 'new', '{}', '2024-01-03T00:00:00Z', '2024-01-03T00:00:00Z')
    """)
    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except Exception:
        pass


def test_connection_with_valid_database(temp_db):
    """Test opening connection with valid database path."""
    with JobsWriter(temp_db) as writer:
        assert writer.conn is not None
        assert writer._in_transaction is True


def test_connection_with_nonexistent_database():
    """Test connection fails with DB_NOT_FOUND when database doesn't exist."""
    with pytest.raises(ToolError) as exc_info:
        with JobsWriter("/nonexistent/path/to/db.db"):
            pass

    assert exc_info.value.code == ErrorCode.DB_NOT_FOUND
    assert "not found" in exc_info.value.message.lower()


def test_connection_cleanup_on_success(temp_db):
    """Test connection is properly closed after successful operations."""
    writer = JobsWriter(temp_db)
    with writer:
        conn = writer.conn
        assert conn is not None

    # Connection should be closed after exiting context
    assert writer.conn is None
    # Verify connection is actually closed
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_connection_cleanup_on_exception(temp_db):
    """Test connection is properly closed even when exception occurs."""
    writer = JobsWriter(temp_db)

    try:
        with writer:
            conn = writer.conn
            assert conn is not None
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Connection should be closed after exception
    assert writer.conn is None
    # Verify connection is actually closed
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_ensure_updated_at_column_exists(temp_db):
    """Test schema preflight passes when updated_at column exists."""
    with JobsWriter(temp_db) as writer:
        # Should not raise
        writer.ensure_updated_at_column()


def test_ensure_updated_at_column_missing(temp_db_no_updated_at):
    """Test schema preflight fails when updated_at column is missing."""
    with pytest.raises(ToolError) as exc_info:
        with JobsWriter(temp_db_no_updated_at) as writer:
            writer.ensure_updated_at_column()

    assert exc_info.value.code == ErrorCode.DB_ERROR
    assert "updated_at" in exc_info.value.message.lower()
    assert "schema" in exc_info.value.message.lower()


def test_validate_jobs_exist_all_exist(temp_db):
    """Test job existence validation when all jobs exist."""
    with JobsWriter(temp_db) as writer:
        missing = writer.validate_jobs_exist([1, 2, 3])
        assert missing == []


def test_validate_jobs_exist_some_missing(temp_db):
    """Test job existence validation when some jobs are missing."""
    with JobsWriter(temp_db) as writer:
        missing = writer.validate_jobs_exist([1, 2, 999, 1000])
        assert set(missing) == {999, 1000}


def test_validate_jobs_exist_all_missing(temp_db):
    """Test job existence validation when all jobs are missing."""
    with JobsWriter(temp_db) as writer:
        missing = writer.validate_jobs_exist([999, 1000, 1001])
        assert set(missing) == {999, 1000, 1001}


def test_validate_jobs_exist_empty_list(temp_db):
    """Test job existence validation with empty list."""
    with JobsWriter(temp_db) as writer:
        missing = writer.validate_jobs_exist([])
        assert missing == []


def test_update_job_status(temp_db):
    """Test updating a job status."""
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db) as writer:
        writer.update_job_status(1, "shortlist", timestamp)
        writer.commit()

    # Verify update was applied
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT status, updated_at FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["status"] == "shortlist"
    assert row["updated_at"] == timestamp


def test_update_multiple_jobs(temp_db):
    """Test updating multiple jobs in one transaction."""
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db) as writer:
        writer.update_job_status(1, JobDbStatus.SHORTLIST, timestamp)
        writer.update_job_status(3, JobDbStatus.REVIEWED, timestamp)
        writer.commit()

    # Verify updates were applied
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT id, status, updated_at FROM jobs WHERE id IN (1, 3) ORDER BY id")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0]["id"] == 1
    assert rows[0]["status"] == JobDbStatus.SHORTLIST
    assert rows[0]["updated_at"] == timestamp
    assert rows[1]["id"] == 3
    assert rows[1]["status"] == JobDbStatus.REVIEWED
    assert rows[1]["updated_at"] == timestamp


def test_transaction_commit(temp_db):
    """Test explicit transaction commit."""
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db) as writer:
        writer.update_job_status(1, "shortlist", timestamp)
        writer.commit()

    # Verify update was committed
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row[0] == "shortlist"


def test_transaction_rollback_on_exception(temp_db):
    """Test transaction is rolled back when exception occurs."""
    timestamp = "2024-01-15T12:00:00.000Z"

    try:
        with JobsWriter(temp_db) as writer:
            writer.update_job_status(1, "shortlist", timestamp)
            # Raise exception before commit
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Verify update was NOT committed
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    # Should still be 'new' (original value)
    assert row[0] == "new"


def test_transaction_explicit_rollback(temp_db):
    """Test explicit transaction rollback."""
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db) as writer:
        writer.update_job_status(1, "shortlist", timestamp)
        writer.rollback()

    # Verify update was NOT committed
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    # Should still be 'new' (original value)
    assert row[0] == "new"


def test_idempotent_update(temp_db):
    """Test updating a job to its current status (idempotent operation)."""
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db) as writer:
        # Job 1 already has status 'new', update it to 'new' again
        writer.update_job_status(1, "new", timestamp)
        writer.commit()

    # Verify update was applied (timestamp should be updated)
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT status, updated_at FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["status"] == "new"
    assert row["updated_at"] == timestamp


def test_sql_injection_prevention_in_status(temp_db):
    """Test that SQL injection attempts in status are treated as literal values."""
    timestamp = "2024-01-15T12:00:00.000Z"
    malicious_status = "'; DROP TABLE jobs; --"

    with JobsWriter(temp_db) as writer:
        # This should not execute SQL injection
        writer.update_job_status(1, malicious_status, timestamp)
        writer.commit()

    # Verify the malicious string was stored as literal data
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row[0] == malicious_status

    # Verify table still exists
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("SELECT COUNT(*) FROM jobs")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 3  # All rows still exist


def test_sql_injection_prevention_in_job_id(temp_db):
    """Test that parameterized queries prevent SQL injection in job IDs."""
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db) as writer:
        # Job ID is an integer, so this tests the parameterization
        writer.update_job_status(1, "shortlist", timestamp)
        writer.commit()

    # Verify only the intended row was updated
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'shortlist'")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 2  # Job 1 (updated) + Job 2 (already shortlist)


def test_resolve_db_path_with_explicit_path():
    """Test database path resolution with explicit path."""
    explicit_path = "/tmp/test.db"
    resolved = resolve_db_path(explicit_path)
    assert str(resolved) == explicit_path


def test_resolve_db_path_with_relative_path():
    """Test database path resolution with relative path."""
    relative_path = "data/capture/jobs.db"
    resolved = resolve_db_path(relative_path)
    # Should be converted to absolute path
    assert resolved.is_absolute()
    assert resolved.name == "jobs.db"


def test_resolve_db_path_with_env_override(monkeypatch):
    """Test database path resolution with environment variable override."""
    test_path = "/custom/path/jobs.db"
    monkeypatch.setenv("JOBWORKFLOW_DB", test_path)

    resolved = resolve_db_path()
    assert str(resolved) == test_path


def test_resolve_db_path_default():
    """Test database path resolution with default path."""
    resolved = resolve_db_path()
    # Should resolve to absolute path ending with data/capture/jobs.db
    assert resolved.is_absolute()
    assert resolved.name == "jobs.db"
    assert "data" in str(resolved)
    assert "capture" in str(resolved)


def test_schema_preflight_prevents_updates_when_column_missing(temp_db_no_updated_at):
    """
    Integration test: Verify schema preflight prevents updates when updated_at is missing.

    This test demonstrates the complete workflow where:
    1. Connection is established
    2. Schema preflight is run
    3. If schema check fails, no updates are executed
    4. Transaction is rolled back

    This validates Requirements 6.4 and 4.1.
    """
    timestamp = "2024-01-15T12:00:00.000Z"

    # Attempt to update with missing updated_at column
    with pytest.raises(ToolError) as exc_info:
        with JobsWriter(temp_db_no_updated_at) as writer:
            # Schema preflight should fail before any updates
            writer.ensure_updated_at_column()

            # These lines should never execute
            writer.update_job_status(1, "shortlist", timestamp)
            writer.commit()

    # Verify error details
    assert exc_info.value.code == ErrorCode.DB_ERROR
    assert "updated_at" in exc_info.value.message.lower()
    assert "schema" in exc_info.value.message.lower()
    assert exc_info.value.retryable is False


def test_schema_preflight_allows_updates_when_column_exists(temp_db):
    """
    Integration test: Verify schema preflight allows updates when updated_at exists.

    This test demonstrates the complete workflow where:
    1. Connection is established
    2. Schema preflight passes
    3. Updates are executed successfully
    4. Transaction is committed

    This validates Requirements 6.4 and 4.1.
    """
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db) as writer:
        # Schema preflight should pass
        writer.ensure_updated_at_column()

        # Verify jobs exist
        missing = writer.validate_jobs_exist([1, 2])
        assert missing == []

        # Execute updates
        writer.update_job_status(1, JobDbStatus.SHORTLIST, timestamp)
        writer.update_job_status(2, JobDbStatus.REVIEWED, timestamp)

        # Commit transaction
        writer.commit()

    # Verify updates were applied
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT id, status, updated_at FROM jobs WHERE id IN (1, 2) ORDER BY id")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0]["id"] == 1
    assert rows[0]["status"] == JobDbStatus.SHORTLIST
    assert rows[0]["updated_at"] == timestamp
    assert rows[1]["id"] == 2
    assert rows[1]["status"] == JobDbStatus.REVIEWED
    assert rows[1]["updated_at"] == timestamp


def test_ensure_finalize_columns_all_present(temp_db_with_finalize_columns):
    """Test schema preflight passes when all finalize columns exist."""
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        # Should not raise
        writer.ensure_finalize_columns()


def test_ensure_finalize_columns_missing_all(temp_db_no_updated_at):
    """Test schema preflight fails when all finalize columns are missing."""
    with pytest.raises(ToolError) as exc_info:
        with JobsWriter(temp_db_no_updated_at) as writer:
            writer.ensure_finalize_columns()

    assert exc_info.value.code == ErrorCode.DB_ERROR
    assert "schema" in exc_info.value.message.lower()
    # Should mention multiple missing columns
    assert "updated_at" in exc_info.value.message.lower()
    assert "resume_pdf_path" in exc_info.value.message.lower()
    assert exc_info.value.retryable is False


def test_ensure_finalize_columns_missing_some(temp_db_missing_finalize_columns):
    """Test schema preflight fails when some finalize columns are missing."""
    with pytest.raises(ToolError) as exc_info:
        with JobsWriter(temp_db_missing_finalize_columns) as writer:
            writer.ensure_finalize_columns()

    assert exc_info.value.code == ErrorCode.DB_ERROR
    assert "schema" in exc_info.value.message.lower()
    # Should mention the missing columns (but not updated_at which exists)
    assert "resume_pdf_path" in exc_info.value.message.lower()
    assert "resume_written_at" in exc_info.value.message.lower()
    assert "run_id" in exc_info.value.message.lower()
    assert "attempt_count" in exc_info.value.message.lower()
    assert "last_error" in exc_info.value.message.lower()
    assert exc_info.value.retryable is False


def test_ensure_finalize_columns_prevents_operations(temp_db_missing_finalize_columns):
    """
    Integration test: Verify finalize schema preflight prevents operations when columns missing.

    This test demonstrates the complete workflow where:
    1. Connection is established
    2. Schema preflight is run
    3. If schema check fails, no finalize operations are executed
    4. Transaction is rolled back

    This validates Requirements 4.4 and 4.5.
    """
    with pytest.raises(ToolError) as exc_info:
        with JobsWriter(temp_db_missing_finalize_columns) as writer:
            # Schema preflight should fail before any operations
            writer.ensure_finalize_columns()

            # These lines should never execute
            writer.update_job_status(1, "resume_written", "2024-01-15T12:00:00.000Z")
            writer.commit()

    # Verify error details
    assert exc_info.value.code == ErrorCode.DB_ERROR
    assert "schema" in exc_info.value.message.lower()
    assert "resume_pdf_path" in exc_info.value.message.lower()
    assert exc_info.value.retryable is False


def test_finalize_resume_written_success(temp_db_with_finalize_columns):
    """Test successful finalization with all audit fields updated."""
    timestamp = "2024-01-15T12:00:00.000Z"
    resume_pdf_path = "data/applications/test-job/resume/resume.pdf"
    run_id = "run_20240115_abc123"

    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.finalize_resume_written(
            job_id=1, resume_pdf_path=resume_pdf_path, run_id=run_id, timestamp=timestamp
        )
        writer.commit()

    # Verify all fields were updated correctly
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT status, resume_pdf_path, resume_written_at, run_id,
               attempt_count, last_error, updated_at
        FROM jobs WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()

    assert row["status"] == "resume_written"
    assert row["resume_pdf_path"] == resume_pdf_path
    assert row["resume_written_at"] == timestamp
    assert row["run_id"] == run_id
    assert row["attempt_count"] == 1  # Incremented from 0
    assert row["last_error"] is None  # Cleared
    assert row["updated_at"] == timestamp


def test_finalize_resume_written_increments_attempt_count(temp_db_with_finalize_columns):
    """Test that attempt_count is incremented on each finalization."""
    timestamp1 = "2024-01-15T12:00:00.000Z"
    timestamp2 = "2024-01-15T13:00:00.000Z"
    resume_pdf_path = "data/applications/test-job/resume/resume.pdf"
    run_id1 = "run_20240115_abc123"
    run_id2 = "run_20240115_def456"

    # First finalization
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.finalize_resume_written(
            job_id=1, resume_pdf_path=resume_pdf_path, run_id=run_id1, timestamp=timestamp1
        )
        writer.commit()

    # Second finalization (retry scenario)
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.finalize_resume_written(
            job_id=1, resume_pdf_path=resume_pdf_path, run_id=run_id2, timestamp=timestamp2
        )
        writer.commit()

    # Verify attempt_count was incremented twice
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT attempt_count, run_id FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["attempt_count"] == 2  # Incremented twice
    assert row["run_id"] == run_id2  # Updated to latest run_id


def test_finalize_resume_written_clears_last_error(temp_db_with_finalize_columns):
    """Test that last_error is cleared on successful finalization."""
    timestamp = "2024-01-15T12:00:00.000Z"
    resume_pdf_path = "data/applications/test-job/resume/resume.pdf"
    run_id = "run_20240115_abc123"

    # Set up a job with a previous error
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.execute("""
        UPDATE jobs
        SET last_error = 'Previous error message',
            attempt_count = 1
        WHERE id = 1
    """)
    conn.commit()
    conn.close()

    # Finalize the job
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.finalize_resume_written(
            job_id=1, resume_pdf_path=resume_pdf_path, run_id=run_id, timestamp=timestamp
        )
        writer.commit()

    # Verify last_error was cleared
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT last_error, attempt_count FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["last_error"] is None  # Cleared
    assert row["attempt_count"] == 2  # Incremented from 1


def test_finalize_resume_written_handles_null_attempt_count(temp_db_with_finalize_columns):
    """Test that finalization works when attempt_count is NULL."""
    timestamp = "2024-01-15T12:00:00.000Z"
    resume_pdf_path = "data/applications/test-job/resume/resume.pdf"
    run_id = "run_20240115_abc123"

    # Set attempt_count to NULL
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.execute("UPDATE jobs SET attempt_count = NULL WHERE id = 1")
    conn.commit()
    conn.close()

    # Finalize the job
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.finalize_resume_written(
            job_id=1, resume_pdf_path=resume_pdf_path, run_id=run_id, timestamp=timestamp
        )
        writer.commit()

    # Verify attempt_count was set to 1 (COALESCE handles NULL)
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT attempt_count FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["attempt_count"] == 1


def test_finalize_resume_written_rollback_on_exception(temp_db_with_finalize_columns):
    """Test that finalization is rolled back on exception."""
    timestamp = "2024-01-15T12:00:00.000Z"
    resume_pdf_path = "data/applications/test-job/resume/resume.pdf"
    run_id = "run_20240115_abc123"

    try:
        with JobsWriter(temp_db_with_finalize_columns) as writer:
            writer.finalize_resume_written(
                job_id=1, resume_pdf_path=resume_pdf_path, run_id=run_id, timestamp=timestamp
            )
            # Raise exception before commit
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Verify finalization was NOT committed
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT status, resume_pdf_path, run_id FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    # Should still be 'new' (original value)
    assert row["status"] == "new"
    assert row["resume_pdf_path"] is None
    assert row["run_id"] is None


def test_finalize_resume_written_missing_job_raises_db_error(temp_db_with_finalize_columns):
    """Finalization should fail when target job ID does not exist."""
    timestamp = "2024-01-15T12:00:00.000Z"
    resume_pdf_path = "data/applications/test-job/resume/resume.pdf"
    run_id = "run_20240115_abc123"

    with JobsWriter(temp_db_with_finalize_columns) as writer:
        with pytest.raises(ToolError) as exc_info:
            writer.finalize_resume_written(
                job_id=999, resume_pdf_path=resume_pdf_path, run_id=run_id, timestamp=timestamp
            )

    assert exc_info.value.code == ErrorCode.DB_ERROR
    assert "no job found" in exc_info.value.message.lower()


def test_fallback_to_reviewed_success(temp_db_with_finalize_columns):
    """Test fallback to reviewed status with error message."""
    timestamp = "2024-01-15T12:00:00.000Z"
    error_message = "Tracker sync failed: permission denied"

    # Set up a job that was being finalized
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.execute("""
        UPDATE jobs
        SET status = 'resume_written',
            resume_pdf_path = 'data/applications/test/resume/resume.pdf',
            run_id = 'run_123',
            attempt_count = 1
        WHERE id = 1
    """)
    conn.commit()
    conn.close()

    # Apply fallback
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.fallback_to_reviewed(job_id=1, last_error=error_message, timestamp=timestamp)
        writer.commit()

    # Verify fallback was applied correctly
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT status, last_error, attempt_count, updated_at
        FROM jobs WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()

    assert row["status"] == JobDbStatus.REVIEWED
    assert row["last_error"] == error_message
    assert row["attempt_count"] == 1  # Preserved (attempt already counted)
    assert row["updated_at"] == timestamp


def test_fallback_to_reviewed_preserves_attempt_count(temp_db_with_finalize_columns):
    """Fallback should not increment attempt_count a second time."""
    timestamp = "2024-01-15T12:00:00.000Z"
    error_message = "Test error"

    # Set up a job with existing attempt_count
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.execute("""
        UPDATE jobs
        SET attempt_count = 3
        WHERE id = 1
    """)
    conn.commit()
    conn.close()

    # Apply fallback
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.fallback_to_reviewed(job_id=1, last_error=error_message, timestamp=timestamp)
        writer.commit()

    # Verify attempt_count was preserved
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT attempt_count FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["attempt_count"] == 3


def test_fallback_to_reviewed_handles_null_attempt_count(temp_db_with_finalize_columns):
    """Test that fallback preserves NULL attempt_count."""
    timestamp = "2024-01-15T12:00:00.000Z"
    error_message = "Test error"

    # Set attempt_count to NULL
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.execute("UPDATE jobs SET attempt_count = NULL WHERE id = 1")
    conn.commit()
    conn.close()

    # Apply fallback
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.fallback_to_reviewed(job_id=1, last_error=error_message, timestamp=timestamp)
        writer.commit()

    # Verify attempt_count remains unchanged
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT attempt_count FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["attempt_count"] is None


def test_fallback_to_reviewed_preserves_other_fields(temp_db_with_finalize_columns):
    """Test that fallback preserves fields not being updated."""
    timestamp = "2024-01-15T12:00:00.000Z"
    error_message = "Test error"

    # Set up a job with various fields
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.execute("""
        UPDATE jobs
        SET status = 'resume_written',
            resume_pdf_path = 'data/applications/test/resume/resume.pdf',
            resume_written_at = '2024-01-14T10:00:00.000Z',
            run_id = 'run_123',
            attempt_count = 1
        WHERE id = 1
    """)
    conn.commit()
    conn.close()

    # Apply fallback
    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.fallback_to_reviewed(job_id=1, last_error=error_message, timestamp=timestamp)
        writer.commit()

    # Verify other fields were preserved
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT status, resume_pdf_path, resume_written_at, run_id,
               last_error, attempt_count, updated_at
        FROM jobs WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()

    # Status and error fields updated
    assert row["status"] == JobDbStatus.REVIEWED
    assert row["last_error"] == error_message
    assert row["attempt_count"] == 1
    assert row["updated_at"] == timestamp

    # Other fields preserved
    assert row["resume_pdf_path"] == "data/applications/test/resume/resume.pdf"
    assert row["resume_written_at"] == "2024-01-14T10:00:00.000Z"
    assert row["run_id"] == "run_123"


def test_fallback_to_reviewed_missing_job_raises_db_error(temp_db_with_finalize_columns):
    """Fallback should fail when target job ID does not exist."""
    timestamp = "2024-01-15T12:00:00.000Z"

    with JobsWriter(temp_db_with_finalize_columns) as writer:
        with pytest.raises(ToolError) as exc_info:
            writer.fallback_to_reviewed(
                job_id=999, last_error="tracker failed", timestamp=timestamp
            )

    assert exc_info.value.code == ErrorCode.DB_ERROR
    assert "no job found" in exc_info.value.message.lower()


def test_fallback_to_reviewed_rollback_on_exception(temp_db_with_finalize_columns):
    """Test that fallback is rolled back on exception."""
    timestamp = "2024-01-15T12:00:00.000Z"
    error_message = "Test error"

    # Set up initial state
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.execute("""
        UPDATE jobs
        SET status = 'resume_written',
            attempt_count = 1
        WHERE id = 1
    """)
    conn.commit()
    conn.close()

    try:
        with JobsWriter(temp_db_with_finalize_columns) as writer:
            writer.fallback_to_reviewed(job_id=1, last_error=error_message, timestamp=timestamp)
            # Raise exception before commit
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Verify fallback was NOT committed
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT status, last_error, attempt_count FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    # Should still be 'resume_written' (original value)
    assert row["status"] == "resume_written"
    assert row["last_error"] is None
    assert row["attempt_count"] == 1


def test_fallback_to_reviewed_sanitized_error_message(temp_db_with_finalize_columns):
    """Test that error messages are stored as provided (sanitization happens upstream)."""
    timestamp = "2024-01-15T12:00:00.000Z"
    # This would be a sanitized error message from the caller
    sanitized_error = "Tracker sync failed"

    with JobsWriter(temp_db_with_finalize_columns) as writer:
        writer.fallback_to_reviewed(job_id=1, last_error=sanitized_error, timestamp=timestamp)
        writer.commit()

    # Verify error message was stored
    conn = sqlite3.connect(temp_db_with_finalize_columns)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT last_error FROM jobs WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    assert row["last_error"] == sanitized_error
