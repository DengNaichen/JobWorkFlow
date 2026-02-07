"""
Tests for db/jobs_ingest_writer.py

Validates schema bootstrap, path resolution, insert/dedupe semantics,
and boundary behavior for ingestion operations.
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from db.jobs_ingest_writer import (
    resolve_db_path,
    ensure_parent_dirs,
    bootstrap_schema,
    JobsIngestWriter,
)


class TestResolveDbPath:
    """Test database path resolution with defaults and overrides."""

    def test_explicit_path_override(self):
        """Explicit db_path parameter takes precedence."""
        result = resolve_db_path("/custom/path/jobs.db")
        assert result == Path("/custom/path/jobs.db")

    def test_env_override(self, monkeypatch):
        """JOBWORKFLOW_DB environment variable is used when no explicit path."""
        monkeypatch.setenv("JOBWORKFLOW_DB", "/env/path/jobs.db")
        result = resolve_db_path()
        assert result == Path("/env/path/jobs.db")

    def test_jobworkflow_root_fallback(self, monkeypatch):
        """JOBWORKFLOW_ROOT is used to construct default path."""
        monkeypatch.delenv("JOBWORKFLOW_DB", raising=False)
        monkeypatch.setenv("JOBWORKFLOW_ROOT", "/root/path")
        result = resolve_db_path()
        assert result == Path("/root/path/data/capture/jobs.db")

    def test_relative_path_resolution(self):
        """Relative paths are resolved from repository root."""
        result = resolve_db_path("data/test.db")
        # Should be absolute and contain the relative path
        assert result.is_absolute()
        assert result.name == "test.db"
        assert "data" in str(result)


class TestEnsureParentDirs:
    """Test parent directory creation."""

    def test_creates_missing_directories(self, tmp_path):
        """Parent directories are created if they don't exist."""
        db_path = tmp_path / "nested" / "dirs" / "jobs.db"
        ensure_parent_dirs(db_path)
        assert db_path.parent.exists()
        assert db_path.parent.is_dir()

    def test_idempotent_on_existing_dirs(self, tmp_path):
        """No error when directories already exist."""
        db_path = tmp_path / "existing" / "jobs.db"
        db_path.parent.mkdir(parents=True)
        # Should not raise
        ensure_parent_dirs(db_path)
        assert db_path.parent.exists()


class TestBootstrapSchema:
    """Test schema bootstrap operations."""

    def test_creates_jobs_table(self, tmp_path):
        """Bootstrap creates jobs table with all required columns."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        bootstrap_schema(conn)

        # Verify table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cursor.fetchone() is not None

        # Verify columns
        cursor = conn.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {
            "id",
            "job_id",
            "title",
            "company",
            "description",
            "url",
            "location",
            "source",
            "status",
            "captured_at",
            "payload_json",
            "created_at",
            "updated_at",
            "resume_pdf_path",
            "resume_written_at",
            "run_id",
            "attempt_count",
            "last_error",
        }
        assert required_columns.issubset(columns)

        conn.close()

    def test_creates_status_index(self, tmp_path):
        """Bootstrap creates idx_jobs_status index."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        bootstrap_schema(conn)

        # Verify index exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_jobs_status'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_idempotent_on_existing_schema(self, tmp_path):
        """Bootstrap is safe to call on existing database."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Bootstrap twice
        bootstrap_schema(conn)
        bootstrap_schema(conn)

        # Should still have exactly one jobs table
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='jobs'"
        )
        assert cursor.fetchone()[0] == 1

        conn.close()


class TestJobsIngestWriter:
    """Test JobsIngestWriter context manager and insert operations."""

    def test_context_manager_creates_db_and_schema(self, tmp_path):
        """Context manager creates database file and bootstraps schema."""
        db_path = tmp_path / "new.db"

        with JobsIngestWriter(str(db_path)) as writer:
            assert writer.conn is not None

        # Verify file was created
        assert db_path.exists()

        # Verify schema was bootstrapped
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_context_manager_creates_parent_dirs(self, tmp_path):
        """Context manager creates parent directories if needed."""
        db_path = tmp_path / "nested" / "path" / "jobs.db"

        with JobsIngestWriter(str(db_path)) as writer:
            assert writer.conn is not None

        assert db_path.exists()
        assert db_path.parent.exists()

    def test_insert_cleaned_records_success(self, tmp_path):
        """Insert new records successfully."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        records = [
            {
                "url": "https://example.com/job1",
                "title": "Software Engineer",
                "description": "Great job",
                "source": "linkedin",
                "job_id": "12345",
                "location": "Toronto",
                "company": "TechCorp",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
            {
                "url": "https://example.com/job2",
                "title": "Backend Developer",
                "description": "Another great job",
                "source": "linkedin",
                "job_id": "67890",
                "location": "Vancouver",
                "company": "StartupCo",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
        ]

        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records(records)
            writer.commit()

        assert inserted == 2
        assert duplicates == 0

        # Verify records in database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 2
        conn.close()

    def test_insert_with_custom_status(self, tmp_path):
        """Insert records with custom status."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        records = [
            {
                "url": "https://example.com/job1",
                "title": "Test Job",
                "description": "Test",
                "source": "test",
                "job_id": "123",
                "location": "Test",
                "company": "Test",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            }
        ]

        with JobsIngestWriter(str(db_path)) as writer:
            writer.insert_cleaned_records(records, status="shortlist")
            writer.commit()

        # Verify status
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT status FROM jobs WHERE url = ?", ("https://example.com/job1",)
        )
        assert cursor.fetchone()[0] == "shortlist"
        conn.close()

    def test_dedupe_by_url(self, tmp_path):
        """Duplicate URLs are detected and counted."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Software Engineer",
            "description": "Great job",
            "source": "linkedin",
            "job_id": "12345",
            "location": "Toronto",
            "company": "TechCorp",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        # First insert
        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records([record])
            writer.commit()

        assert inserted == 1
        assert duplicates == 0

        # Second insert (duplicate)
        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records([record])
            writer.commit()

        assert inserted == 0
        assert duplicates == 1

        # Verify only one record in database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_existing_rows_unchanged_on_dedupe(self, tmp_path):
        """Existing rows are not modified when duplicate URL is inserted."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        original_record = {
            "url": "https://example.com/job1",
            "title": "Original Title",
            "description": "Original description",
            "source": "linkedin",
            "job_id": "12345",
            "location": "Toronto",
            "company": "OriginalCorp",
            "captured_at": now,
            "payload_json": '{"original": true}',
            "created_at": now,
        }

        # Insert original
        with JobsIngestWriter(str(db_path)) as writer:
            writer.insert_cleaned_records([original_record])
            writer.commit()

        # Try to insert with different data but same URL
        duplicate_record = {
            "url": "https://example.com/job1",  # Same URL
            "title": "New Title",
            "description": "New description",
            "source": "indeed",
            "job_id": "99999",
            "location": "Vancouver",
            "company": "NewCorp",
            "captured_at": now,
            "payload_json": '{"new": true}',
            "created_at": now,
        }

        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records([duplicate_record])
            writer.commit()

        assert inserted == 0
        assert duplicates == 1

        # Verify original data is unchanged
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM jobs WHERE url = ?", ("https://example.com/job1",))
        row = cursor.fetchone()

        assert row["title"] == "Original Title"
        assert row["company"] == "OriginalCorp"
        assert row["payload_json"] == '{"original": true}'
        conn.close()

    def test_empty_records_list(self, tmp_path):
        """Empty records list returns zero counts."""
        db_path = tmp_path / "test.db"

        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records([])
            writer.commit()

        assert inserted == 0
        assert duplicates == 0

    def test_rollback_on_exception(self, tmp_path):
        """Transaction is rolled back on exception."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Test",
            "description": "Test",
            "source": "test",
            "job_id": "123",
            "location": "Test",
            "company": "Test",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        try:
            with JobsIngestWriter(str(db_path)) as writer:
                writer.insert_cleaned_records([record])
                # Raise exception before commit
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify no records were committed
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 0
        conn.close()

    def test_connection_closed_after_context(self, tmp_path):
        """Connection is closed after exiting context."""
        db_path = tmp_path / "test.db"

        writer = JobsIngestWriter(str(db_path))
        with writer:
            assert writer.conn is not None

        # Connection should be closed
        assert writer.conn is None or not writer.conn

    def test_idempotent_reruns(self, tmp_path):
        """Multiple runs with same data yield inserts then duplicates."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        records = [
            {
                "url": "https://example.com/job1",
                "title": "Job 1",
                "description": "Desc 1",
                "source": "linkedin",
                "job_id": "1",
                "location": "Toronto",
                "company": "Corp1",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
            {
                "url": "https://example.com/job2",
                "title": "Job 2",
                "description": "Desc 2",
                "source": "linkedin",
                "job_id": "2",
                "location": "Vancouver",
                "company": "Corp2",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
        ]

        # First run - all inserts
        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records(records)
            writer.commit()

        assert inserted == 2
        assert duplicates == 0

        # Second run - all duplicates
        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records(records)
            writer.commit()

        assert inserted == 0
        assert duplicates == 2

        # Third run - still all duplicates
        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records(records)
            writer.commit()

        assert inserted == 0
        assert duplicates == 2

        # Verify total count
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 2
        conn.close()

    def test_partial_duplicates(self, tmp_path):
        """Mix of new and duplicate records are counted correctly."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        # Insert first batch
        first_batch = [
            {
                "url": "https://example.com/job1",
                "title": "Job 1",
                "description": "Desc 1",
                "source": "linkedin",
                "job_id": "1",
                "location": "Toronto",
                "company": "Corp1",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            }
        ]

        with JobsIngestWriter(str(db_path)) as writer:
            writer.insert_cleaned_records(first_batch)
            writer.commit()

        # Insert second batch with one duplicate and one new
        second_batch = [
            {
                "url": "https://example.com/job1",  # Duplicate
                "title": "Job 1",
                "description": "Desc 1",
                "source": "linkedin",
                "job_id": "1",
                "location": "Toronto",
                "company": "Corp1",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
            {
                "url": "https://example.com/job2",  # New
                "title": "Job 2",
                "description": "Desc 2",
                "source": "linkedin",
                "job_id": "2",
                "location": "Vancouver",
                "company": "Corp2",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
        ]

        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records(second_batch)
            writer.commit()

        assert inserted == 1
        assert duplicates == 1

        # Verify total count
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        assert cursor.fetchone()[0] == 2
        conn.close()


class TestBoundaryBehavior:
    """Test boundary behavior enforcement (Requirements 8.1, 8.2, 8.3)."""

    def test_default_status_is_new(self, tmp_path):
        """Default status is 'new' when not specified (Requirement 8.1)."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Test Job",
            "description": "Test",
            "source": "test",
            "job_id": "123",
            "location": "Test",
            "company": "Test",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        # Insert without specifying status
        with JobsIngestWriter(str(db_path)) as writer:
            writer.insert_cleaned_records([record])
            writer.commit()

        # Verify status is 'new'
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT status FROM jobs WHERE url = ?", ("https://example.com/job1",)
        )
        assert cursor.fetchone()[0] == "new"
        conn.close()

    def test_valid_status_override(self, tmp_path):
        """Valid status overrides are accepted (Requirement 8.2)."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        valid_statuses = ["new", "shortlist", "reviewed", "reject", "resume_written", "applied"]

        for idx, status in enumerate(valid_statuses):
            record = {
                "url": f"https://example.com/job{idx}",
                "title": f"Job {idx}",
                "description": "Test",
                "source": "test",
                "job_id": str(idx),
                "location": "Test",
                "company": "Test",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            }

            with JobsIngestWriter(str(db_path)) as writer:
                inserted, duplicates = writer.insert_cleaned_records([record], status=status)
                writer.commit()

            assert inserted == 1
            assert duplicates == 0

            # Verify status
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT status FROM jobs WHERE url = ?", (record["url"],))
            assert cursor.fetchone()[0] == status
            conn.close()

    def test_invalid_status_raises_validation_error(self, tmp_path):
        """Invalid status values raise VALIDATION_ERROR (Requirement 8.2)."""
        from models.errors import ToolError

        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Test Job",
            "description": "Test",
            "source": "test",
            "job_id": "123",
            "location": "Test",
            "company": "Test",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status="invalid_status")

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"
            assert "invalid_status" in error.message.lower()
            assert "allowed values" in error.message.lower()

    def test_status_case_sensitive(self, tmp_path):
        """Status validation is case-sensitive (Requirement 8.2)."""
        from models.errors import ToolError

        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Test Job",
            "description": "Test",
            "source": "test",
            "job_id": "123",
            "location": "Test",
            "company": "Test",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        # Uppercase should fail
        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status="NEW")

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"

        # Mixed case should fail
        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status="New")

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"

    def test_status_with_whitespace_rejected(self, tmp_path):
        """Status with leading/trailing whitespace is rejected (Requirement 8.2)."""
        from models.errors import ToolError

        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Test Job",
            "description": "Test",
            "source": "test",
            "job_id": "123",
            "location": "Test",
            "company": "Test",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        # Leading whitespace
        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status=" new")

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"
            assert "whitespace" in error.message.lower()

        # Trailing whitespace
        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status="new ")

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"
            assert "whitespace" in error.message.lower()

    def test_empty_status_rejected(self, tmp_path):
        """Empty status string is rejected (Requirement 8.2)."""
        from models.errors import ToolError

        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Test Job",
            "description": "Test",
            "source": "test",
            "job_id": "123",
            "location": "Test",
            "company": "Test",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status="")

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"
            assert "empty" in error.message.lower()

    def test_non_string_status_rejected(self, tmp_path):
        """Non-string status values are rejected (Requirement 8.2)."""
        from models.errors import ToolError

        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "url": "https://example.com/job1",
            "title": "Test Job",
            "description": "Test",
            "source": "test",
            "job_id": "123",
            "location": "Test",
            "company": "Test",
            "captured_at": now,
            "payload_json": "{}",
            "created_at": now,
        }

        # Integer status
        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status=123)

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"
            assert "type" in error.message.lower()

        # List status
        with JobsIngestWriter(str(db_path)) as writer:
            with pytest.raises(ToolError) as exc_info:
                writer.insert_cleaned_records([record], status=["new"])

            error = exc_info.value
            assert error.code == "VALIDATION_ERROR"
            assert "type" in error.message.lower()

    def test_insert_only_no_updates(self, tmp_path):
        """Verify INSERT OR IGNORE never updates existing rows (Requirement 8.3)."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        # Insert with status='new'
        original_record = {
            "url": "https://example.com/job1",
            "title": "Original Title",
            "description": "Original description",
            "source": "linkedin",
            "job_id": "12345",
            "location": "Toronto",
            "company": "OriginalCorp",
            "captured_at": now,
            "payload_json": '{"original": true}',
            "created_at": now,
        }

        with JobsIngestWriter(str(db_path)) as writer:
            writer.insert_cleaned_records([original_record], status="new")
            writer.commit()

        # Try to insert with different status and data
        duplicate_record = {
            "url": "https://example.com/job1",  # Same URL
            "title": "New Title",
            "description": "New description",
            "source": "indeed",
            "job_id": "99999",
            "location": "Vancouver",
            "company": "NewCorp",
            "captured_at": now,
            "payload_json": '{"new": true}',
            "created_at": now,
        }

        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records(
                [duplicate_record], status="shortlist"
            )
            writer.commit()

        assert inserted == 0
        assert duplicates == 1

        # Verify ALL fields remain unchanged (not just data, but status too)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM jobs WHERE url = ?", ("https://example.com/job1",))
        row = cursor.fetchone()

        assert row["title"] == "Original Title"
        assert row["company"] == "OriginalCorp"
        assert row["status"] == "new"  # Status not updated
        assert row["payload_json"] == '{"original": true}'
        conn.close()

    def test_no_delete_operations(self, tmp_path):
        """Verify writer only performs INSERT operations, never DELETE (Requirement 8.3)."""
        db_path = tmp_path / "test.db"
        now = datetime.now(timezone.utc).isoformat()

        # Insert some records
        records = [
            {
                "url": f"https://example.com/job{i}",
                "title": f"Job {i}",
                "description": "Test",
                "source": "test",
                "job_id": str(i),
                "location": "Test",
                "company": "Test",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            }
            for i in range(5)
        ]

        with JobsIngestWriter(str(db_path)) as writer:
            writer.insert_cleaned_records(records)
            writer.commit()

        # Verify all records exist
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        initial_count = cursor.fetchone()[0]
        assert initial_count == 5

        # Insert more records (some duplicates)
        more_records = [
            {
                "url": "https://example.com/job0",  # Duplicate
                "title": "Job 0",
                "description": "Test",
                "source": "test",
                "job_id": "0",
                "location": "Test",
                "company": "Test",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
            {
                "url": "https://example.com/job10",  # New
                "title": "Job 10",
                "description": "Test",
                "source": "test",
                "job_id": "10",
                "location": "Test",
                "company": "Test",
                "captured_at": now,
                "payload_json": "{}",
                "created_at": now,
            },
        ]

        with JobsIngestWriter(str(db_path)) as writer:
            inserted, duplicates = writer.insert_cleaned_records(more_records)
            writer.commit()

        assert inserted == 1
        assert duplicates == 1

        # Verify count increased by 1 (no deletions)
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        final_count = cursor.fetchone()[0]
        assert final_count == initial_count + 1

        # Verify all original records still exist
        for i in range(5):
            cursor = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE url = ?", (f"https://example.com/job{i}",)
            )
            assert cursor.fetchone()[0] == 1

        conn.close()
