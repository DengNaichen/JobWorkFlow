"""
Checkpoint test for Task 4: Verify core components work independently.

This test validates:
1. All unit tests for validation and database writer pass
2. Transaction rollback works correctly
3. Error handling produces structured, sanitized errors
4. Database connections are properly closed
"""

import pytest
import sqlite3
import tempfile
import os

from db.jobs_writer import JobsWriter
from models.errors import ToolError, ErrorCode
from utils.validation import (
    validate_status,
    validate_job_id,
    validate_batch_size,
    validate_unique_job_ids,
    get_current_utc_timestamp,
)


@pytest.fixture
def temp_db():
    """Create a temporary database with jobs table for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

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

    conn.execute("""
        INSERT INTO jobs (url, title, status, payload_json, created_at)
        VALUES
            ('http://example.com/job1', 'Job 1', 'new', '{}', '2024-01-01T00:00:00Z'),
            ('http://example.com/job2', 'Job 2', 'shortlist', '{}', '2024-01-02T00:00:00Z'),
            ('http://example.com/job3', 'Job 3', 'new', '{}', '2024-01-03T00:00:00Z')
    """)
    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass


class TestCheckpointTask4:
    """Checkpoint tests for Task 4."""

    def test_validation_functions_work_correctly(self):
        """Verify all validation functions work as expected."""
        # Test status validation
        assert validate_status("new") == "new"
        assert validate_status("shortlist") == "shortlist"

        with pytest.raises(ToolError) as exc_info:
            validate_status("invalid")
        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

        # Test job ID validation
        assert validate_job_id(1) == 1
        assert validate_job_id(999) == 999

        with pytest.raises(ToolError) as exc_info:
            validate_job_id(0)
        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

        # Test batch size validation
        validate_batch_size([])  # Should not raise
        validate_batch_size([{"id": 1, "status": "new"}])  # Should not raise

        with pytest.raises(ToolError) as exc_info:
            validate_batch_size([{"id": i} for i in range(101)])
        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

        # Test unique job IDs validation
        validate_unique_job_ids([{"id": 1}, {"id": 2}])  # Should not raise

        with pytest.raises(ToolError) as exc_info:
            validate_unique_job_ids([{"id": 1}, {"id": 1}])
        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

    def test_timestamp_generation_works(self):
        """Verify timestamp generation produces correct format."""
        timestamp = get_current_utc_timestamp()

        # Should be a string
        assert isinstance(timestamp, str)

        # Should end with Z
        assert timestamp.endswith("Z")

        # Should have milliseconds
        assert "." in timestamp

        # Should be parseable
        from datetime import datetime

        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed is not None

    def test_transaction_rollback_on_validation_failure(self, temp_db):
        """Verify transaction rollback works when validation fails."""
        timestamp = get_current_utc_timestamp()

        # Attempt to update with one invalid job ID
        try:
            with JobsWriter(temp_db) as writer:
                writer.ensure_updated_at_column()

                # First update is valid
                writer.update_job_status(1, "shortlist", timestamp)

                # Simulate validation failure by checking for non-existent job
                missing = writer.validate_jobs_exist([1, 999])
                if missing:
                    # Rollback should happen
                    writer.rollback()
                    raise ValueError("Job 999 does not exist")
        except ValueError:
            pass

        # Verify first update was NOT committed
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "new"  # Should still be original value

    def test_transaction_rollback_on_exception(self, temp_db):
        """Verify transaction rollback works when exception occurs."""
        timestamp = get_current_utc_timestamp()

        try:
            with JobsWriter(temp_db) as writer:
                writer.update_job_status(1, "shortlist", timestamp)
                writer.update_job_status(2, "reviewed", timestamp)
                # Raise exception before commit
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        # Verify updates were NOT committed
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id IN (1, 2) ORDER BY id")
        rows = cursor.fetchall()
        conn.close()

        assert rows[0][0] == "new"  # Job 1 should still be 'new'
        assert rows[1][0] == "shortlist"  # Job 2 should still be 'shortlist'

    def test_database_connection_cleanup_on_success(self, temp_db):
        """Verify database connection is properly closed after success."""
        writer = JobsWriter(temp_db)

        with writer:
            conn = writer.conn
            assert conn is not None
            writer.ensure_updated_at_column()

        # Connection should be closed
        assert writer.conn is None

        # Verify connection is actually closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_database_connection_cleanup_on_failure(self, temp_db):
        """Verify database connection is properly closed after failure."""
        writer = JobsWriter(temp_db)

        try:
            with writer:
                conn = writer.conn
                assert conn is not None
                raise ValueError("Test error")
        except ValueError:
            pass

        # Connection should be closed
        assert writer.conn is None

        # Verify connection is actually closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_error_handling_produces_structured_errors(self):
        """Verify error handling produces structured, sanitized errors."""
        # Test validation error
        try:
            validate_status("invalid_status")
        except ToolError as e:
            error_dict = e.to_dict()
            assert "error" in error_dict
            assert "code" in error_dict["error"]
            assert "message" in error_dict["error"]
            assert "retryable" in error_dict["error"]
            assert error_dict["error"]["code"] == "VALIDATION_ERROR"
            assert error_dict["error"]["retryable"] is False

        # Test DB not found error
        try:
            with JobsWriter("/nonexistent/path/to/db.db"):
                pass
        except ToolError as e:
            error_dict = e.to_dict()
            assert "error" in error_dict
            assert error_dict["error"]["code"] == "DB_NOT_FOUND"
            assert error_dict["error"]["retryable"] is False
            # Path should be sanitized (only basename shown)
            assert "/nonexistent/path/to/" not in error_dict["error"]["message"]

    def test_error_messages_are_sanitized(self):
        """Verify error messages don't expose sensitive information."""
        # Test that absolute paths are sanitized
        try:
            with JobsWriter("/home/user/secret/data/jobs.db"):
                pass
        except ToolError as e:
            # Should not contain full path
            assert "/home/user/secret/" not in e.message
            # Should contain basename
            assert "jobs.db" in e.message

    def test_complete_workflow_with_validation_and_rollback(self, temp_db):
        """
        Integration test: Complete workflow with validation and rollback.

        This simulates the full workflow:
        1. Validate batch size
        2. Validate unique IDs
        3. Open database connection
        4. Run schema preflight
        5. Validate job IDs and statuses
        6. Check job existence
        7. If any validation fails, rollback
        8. Close connection
        """
        # Prepare updates
        updates = [
            {"id": 1, "status": "shortlist"},
            {"id": 2, "status": "reviewed"},
            {"id": 999, "status": "new"},  # Non-existent job
        ]

        # Step 1: Validate batch size
        validate_batch_size(updates)

        # Step 2: Validate unique IDs
        validate_unique_job_ids(updates)

        # Step 3-8: Database operations
        timestamp = get_current_utc_timestamp()
        validation_errors = []

        try:
            with JobsWriter(temp_db) as writer:
                # Step 4: Schema preflight
                writer.ensure_updated_at_column()

                # Step 5: Validate each update
                for update in updates:
                    try:
                        validate_job_id(update["id"])
                        validate_status(update["status"])
                    except ToolError as e:
                        validation_errors.append({"id": update["id"], "error": e.message})

                # Step 6: Check job existence
                job_ids = [u["id"] for u in updates]
                missing = writer.validate_jobs_exist(job_ids)

                for job_id in missing:
                    validation_errors.append(
                        {"id": job_id, "error": f"Job ID {job_id} does not exist"}
                    )

                # Step 7: If any validation fails, rollback
                if validation_errors:
                    writer.rollback()
                    raise ValueError("Validation failed")

                # Otherwise, execute updates
                for update in updates:
                    writer.update_job_status(update["id"], update["status"], timestamp)

                writer.commit()
        except ValueError:
            pass

        # Verify rollback happened (no updates committed)
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id IN (1, 2) ORDER BY id")
        rows = cursor.fetchall()
        conn.close()

        assert rows[0][0] == "new"  # Job 1 should still be 'new'
        assert rows[1][0] == "shortlist"  # Job 2 should still be 'shortlist'

        # Verify validation errors were collected
        assert len(validation_errors) == 1
        assert validation_errors[0]["id"] == 999

    def test_complete_workflow_with_successful_commit(self, temp_db):
        """
        Integration test: Complete workflow with successful commit.

        This simulates a successful workflow where all validations pass.
        """
        # Prepare valid updates
        updates = [{"id": 1, "status": "shortlist"}, {"id": 3, "status": "reviewed"}]

        # Validate batch size
        validate_batch_size(updates)

        # Validate unique IDs
        validate_unique_job_ids(updates)

        # Database operations
        timestamp = get_current_utc_timestamp()
        validation_errors = []

        with JobsWriter(temp_db) as writer:
            # Schema preflight
            writer.ensure_updated_at_column()

            # Validate each update
            for update in updates:
                try:
                    validate_job_id(update["id"])
                    validate_status(update["status"])
                except ToolError as e:
                    validation_errors.append({"id": update["id"], "error": e.message})

            # Check job existence
            job_ids = [u["id"] for u in updates]
            missing = writer.validate_jobs_exist(job_ids)

            for job_id in missing:
                validation_errors.append({"id": job_id, "error": f"Job ID {job_id} does not exist"})

            # No validation errors, execute updates
            assert len(validation_errors) == 0

            for update in updates:
                writer.update_job_status(update["id"], update["status"], timestamp)

            writer.commit()

        # Verify updates were committed
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, status, updated_at FROM jobs WHERE id IN (1, 3) ORDER BY id"
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0]["id"] == 1
        assert rows[0]["status"] == "shortlist"
        assert rows[0]["updated_at"] == timestamp
        assert rows[1]["id"] == 3
        assert rows[1]["status"] == "reviewed"
        assert rows[1]["updated_at"] == timestamp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
