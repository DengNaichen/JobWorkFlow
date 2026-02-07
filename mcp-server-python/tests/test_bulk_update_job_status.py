"""
Integration tests for bulk_update_job_status MCP tool.

Tests the complete tool workflow including validation, database operations,
transaction management, and response formatting.
"""

import pytest
import sqlite3
import tempfile
import os

from tools.bulk_update_job_status import bulk_update_job_status
from models.errors import ErrorCode


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
            ('http://example.com/job2', 'Job 2', 'Company B', 'new', '{}', '2024-01-02T00:00:00Z', '2024-01-02T00:00:00Z'),
            ('http://example.com/job3', 'Job 3', 'Company C', 'new', '{}', '2024-01-03T00:00:00Z', '2024-01-03T00:00:00Z'),
            ('http://example.com/job4', 'Job 4', 'Company D', 'shortlist', '{}', '2024-01-04T00:00:00Z', '2024-01-04T00:00:00Z'),
            ('http://example.com/job5', 'Job 5', 'Company E', 'reviewed', '{}', '2024-01-05T00:00:00Z', '2024-01-05T00:00:00Z')
    """)
    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except OSError:
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

    # Insert test data
    conn.execute("""
        INSERT INTO jobs (url, title, status, payload_json, created_at)
        VALUES ('http://example.com/job1', 'Job 1', 'new', '{}', '2024-01-01T00:00:00Z')
    """)
    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except OSError:
        pass


class TestSuccessfulUpdates:
    """Test successful batch update scenarios."""

    def test_empty_batch_returns_success(self, temp_db):
        """Test that empty batch returns success with zero counts."""
        result = bulk_update_job_status({"updates": [], "db_path": temp_db})

        assert result["updated_count"] == 0
        assert result["failed_count"] == 0
        assert result["results"] == []

    def test_single_update_succeeds(self, temp_db):
        """Test updating a single job status."""
        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": "shortlist"}], "db_path": temp_db}
        )

        assert result["updated_count"] == 1
        assert result["failed_count"] == 0
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == 1
        assert result["results"][0]["success"] is True

        # Verify database was updated
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "shortlist"

    def test_multiple_updates_succeed(self, temp_db):
        """Test updating multiple jobs in one batch."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 1, "status": "shortlist"},
                    {"id": 2, "status": "reviewed"},
                    {"id": 3, "status": "reject"},
                ],
                "db_path": temp_db,
            }
        )

        assert result["updated_count"] == 3
        assert result["failed_count"] == 0
        assert len(result["results"]) == 3

        # Verify all results are successful
        for res in result["results"]:
            assert res["success"] is True

        # Verify database was updated
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT id, status FROM jobs WHERE id IN (1, 2, 3) ORDER BY id")
        rows = cursor.fetchall()
        conn.close()

        assert rows[0]["status"] == "shortlist"
        assert rows[1]["status"] == "reviewed"
        assert rows[2]["status"] == "reject"

    def test_idempotent_update_succeeds(self, temp_db):
        """Test updating a job to its current status (idempotent)."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 1, "status": "new"}  # Job 1 already has status 'new'
                ],
                "db_path": temp_db,
            }
        )

        assert result["updated_count"] == 1
        assert result["failed_count"] == 0
        assert result["results"][0]["success"] is True

        # Verify updated_at was refreshed
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT status, updated_at FROM jobs WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row["status"] == "new"
        assert row["updated_at"] is not None

    def test_all_valid_statuses(self, temp_db):
        """Test all valid status values."""
        valid_statuses = ["new", "shortlist", "reviewed", "reject", "resume_written"]

        for i, status in enumerate(valid_statuses, start=1):
            result = bulk_update_job_status(
                {"updates": [{"id": i, "status": status}], "db_path": temp_db}
            )

            assert result["updated_count"] == 1
            assert result["failed_count"] == 0


class TestValidationErrors:
    """Test validation error scenarios."""

    def test_missing_updates_parameter(self, temp_db):
        """Test error when 'updates' parameter is missing."""
        result = bulk_update_job_status({"db_path": temp_db})

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "updates" in result["error"]["message"].lower()

    def test_updates_not_a_list(self, temp_db):
        """Test error when 'updates' is not a list."""
        result = bulk_update_job_status({"updates": "not a list", "db_path": temp_db})

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "list" in result["error"]["message"].lower()

    def test_batch_size_too_large(self, temp_db):
        """Test error when batch size exceeds 100."""
        updates = [{"id": i, "status": "new"} for i in range(1, 102)]

        result = bulk_update_job_status({"updates": updates, "db_path": temp_db})

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "100" in result["error"]["message"]

    def test_duplicate_job_ids(self, temp_db):
        """Test error when duplicate job IDs are present."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 1, "status": "shortlist"},
                    {"id": 2, "status": "reviewed"},
                    {"id": 1, "status": "reject"},  # Duplicate ID
                ],
                "db_path": temp_db,
            }
        )

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "duplicate" in result["error"]["message"].lower()

    def test_duplicate_job_ids_mixed_types_return_validation_error(self, temp_db):
        """Test mixed-type duplicate IDs do not degrade into INTERNAL_ERROR."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": "abc", "status": "new"},
                    {"id": "abc", "status": "shortlist"},
                    {"id": 1, "status": "reviewed"},
                    {"id": 1, "status": "reject"},
                ],
                "db_path": temp_db,
            }
        )

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "duplicate" in result["error"]["message"].lower()


class TestPerItemFailures:
    """Test per-item validation and existence failures."""

    def test_nonexistent_job_id(self, temp_db):
        """Test failure when job ID doesn't exist."""
        result = bulk_update_job_status(
            {"updates": [{"id": 999, "status": "shortlist"}], "db_path": temp_db}
        )

        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == 999
        assert result["results"][0]["success"] is False
        assert "does not exist" in result["results"][0]["error"]

    def test_invalid_status_value(self, temp_db):
        """Test failure when status value is invalid."""
        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": "invalid_status"}], "db_path": temp_db}
        )

        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "invalid status" in result["results"][0]["error"].lower()

    def test_invalid_job_id_type(self, temp_db):
        """Test failure when job ID is not an integer."""
        result = bulk_update_job_status(
            {"updates": [{"id": "not_an_int", "status": "shortlist"}], "db_path": temp_db}
        )

        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "invalid job id" in result["results"][0]["error"].lower()

    def test_negative_job_id(self, temp_db):
        """Test failure when job ID is negative."""
        result = bulk_update_job_status(
            {"updates": [{"id": -1, "status": "shortlist"}], "db_path": temp_db}
        )

        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "positive integer" in result["results"][0]["error"].lower()

    def test_missing_id_field(self, temp_db):
        """Test failure when 'id' field is missing."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"status": "shortlist"}  # Missing 'id'
                ],
                "db_path": temp_db,
            }
        )

        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "id" in result["results"][0]["error"].lower()

    def test_missing_status_field(self, temp_db):
        """Test failure when 'status' field is missing."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 1}  # Missing 'status'
                ],
                "db_path": temp_db,
            }
        )

        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "status" in result["results"][0]["error"].lower()

    def test_status_with_whitespace(self, temp_db):
        """Test failure when status has leading/trailing whitespace."""
        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": " shortlist "}], "db_path": temp_db}
        )

        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "whitespace" in result["results"][0]["error"].lower()

    def test_mixed_valid_and_invalid_updates(self, temp_db):
        """Test that all updates fail when any validation fails (atomicity)."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 1, "status": "shortlist"},  # Valid
                    {"id": 999, "status": "reviewed"},  # Invalid (doesn't exist)
                    {"id": 3, "status": "reject"},  # Valid
                ],
                "db_path": temp_db,
            }
        )

        # All updates should fail due to atomicity
        assert result["updated_count"] == 0
        assert result["failed_count"] == 1  # Only the invalid one is reported

        # Verify no updates were applied
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id IN (1, 3)")
        rows = cursor.fetchall()
        conn.close()

        # Both should still be 'new' (original value)
        assert all(row[0] == "new" for row in rows)


class TestDatabaseErrors:
    """Test database error scenarios."""

    def test_database_not_found(self):
        """Test error when database file doesn't exist."""
        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": "shortlist"}], "db_path": "/nonexistent/path/to/db.db"}
        )

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.DB_NOT_FOUND.value
        assert "not found" in result["error"]["message"].lower()

    def test_missing_updated_at_column(self, temp_db_no_updated_at):
        """Test error when updated_at column is missing."""
        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": "shortlist"}], "db_path": temp_db_no_updated_at}
        )

        assert "error" in result
        assert result["error"]["code"] == ErrorCode.DB_ERROR.value
        assert "updated_at" in result["error"]["message"].lower()
        assert "schema" in result["error"]["message"].lower()


class TestTimestampBehavior:
    """Test timestamp tracking behavior."""

    def test_timestamp_is_set(self, temp_db):
        """Test that updated_at timestamp is set."""
        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": "shortlist"}], "db_path": temp_db}
        )

        assert result["updated_count"] == 1

        # Verify timestamp was set
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT updated_at FROM jobs WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row["updated_at"] is not None
        # Verify timestamp format (ISO 8601 with Z suffix)
        assert row["updated_at"].endswith("Z")
        assert "T" in row["updated_at"]

    def test_same_timestamp_for_batch(self, temp_db):
        """Test that all jobs in a batch get the same timestamp."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 1, "status": "shortlist"},
                    {"id": 2, "status": "reviewed"},
                    {"id": 3, "status": "reject"},
                ],
                "db_path": temp_db,
            }
        )

        assert result["updated_count"] == 3

        # Verify all have the same timestamp
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT DISTINCT updated_at FROM jobs WHERE id IN (1, 2, 3)")
        rows = cursor.fetchall()
        conn.close()

        # Should only be one distinct timestamp
        assert len(rows) == 1


class TestResponseStructure:
    """Test response structure and ordering."""

    def test_result_ordering_matches_input(self, temp_db):
        """Test that results array matches input order."""
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 3, "status": "shortlist"},
                    {"id": 1, "status": "reviewed"},
                    {"id": 2, "status": "reject"},
                ],
                "db_path": temp_db,
            }
        )

        assert len(result["results"]) == 3
        assert result["results"][0]["id"] == 3
        assert result["results"][1]["id"] == 1
        assert result["results"][2]["id"] == 2

    def test_response_has_required_fields(self, temp_db):
        """Test that response has all required fields."""
        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": "shortlist"}], "db_path": temp_db}
        )

        # Check top-level fields
        assert "updated_count" in result
        assert "failed_count" in result
        assert "results" in result

        # Check result item fields
        assert "id" in result["results"][0]
        assert "success" in result["results"][0]

        # 'error' field should not be present for successful updates
        assert "error" not in result["results"][0]


class TestAtomicity:
    """Test atomic transaction behavior."""

    def test_rollback_on_validation_failure(self, temp_db):
        """Test that valid updates are rolled back when any validation fails."""
        # Get initial status
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
        initial_status = cursor.fetchone()[0]
        conn.close()

        # Attempt batch with one invalid update
        result = bulk_update_job_status(
            {
                "updates": [
                    {"id": 1, "status": "shortlist"},  # Valid
                    {"id": 999, "status": "reviewed"},  # Invalid (doesn't exist)
                ],
                "db_path": temp_db,
            }
        )

        assert result["updated_count"] == 0

        # Verify job 1 was NOT updated (rollback occurred)
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
        current_status = cursor.fetchone()[0]
        conn.close()

        assert current_status == initial_status


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""

    def test_sql_injection_in_status(self, temp_db):
        """Test that SQL injection attempts in status are treated as literal values."""
        malicious_status = "'; DROP TABLE jobs; --"

        result = bulk_update_job_status(
            {"updates": [{"id": 1, "status": malicious_status}], "db_path": temp_db}
        )

        # Should fail validation (not in allowed statuses)
        assert result["updated_count"] == 0
        assert result["failed_count"] == 1

        # Verify table still exists
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 5  # All rows still exist
