"""
Unit tests for database reader layer.

Tests connection management, path resolution, and query execution.
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone

from db.jobs_reader import (
    resolve_db_path,
    get_connection,
    query_new_jobs,
    DEFAULT_DB_PATH
)
from models.errors import ToolError, ErrorCode


class TestResolveDbPath:
    """Tests for database path resolution."""

    def test_default_path_when_none(self):
        """Test that None returns the default path."""
        result = resolve_db_path(None)
        assert result.name == "jobs.db"
        assert "data/capture" in str(result)

    def test_explicit_relative_path(self):
        """Test that relative paths are resolved from repo root."""
        result = resolve_db_path("test/data.db")
        assert result.is_absolute()
        assert result.name == "data.db"

    def test_explicit_absolute_path(self):
        """Test that absolute paths are preserved."""
        abs_path = "/tmp/test.db"
        result = resolve_db_path(abs_path)
        assert result == Path(abs_path)
        assert result.is_absolute()

    def test_environment_variable_override(self, monkeypatch):
        """Test that JOBWORKFLOW_DB environment variable is used."""
        test_path = "custom/path/jobs.db"
        monkeypatch.setenv("JOBWORKFLOW_DB", test_path)
        result = resolve_db_path(None)
        assert "custom/path" in str(result)
        assert result.name == "jobs.db"

    def test_jobworkflow_root_fallback(self, monkeypatch):
        """Test that JOBWORKFLOW_ROOT is used when JOBWORKFLOW_DB is not set."""
        monkeypatch.delenv("JOBWORKFLOW_DB", raising=False)
        monkeypatch.setenv("JOBWORKFLOW_ROOT", "/opt/jobworkflow")

        result = resolve_db_path(None)
        assert result == Path("/opt/jobworkflow/data/capture/jobs.db")

    def test_parameter_overrides_environment(self, monkeypatch):
        """Test that explicit parameter overrides environment variable."""
        monkeypatch.setenv("JOBWORKFLOW_DB", "env/path.db")
        result = resolve_db_path("param/path.db")
        assert "param/path.db" in str(result)


class TestGetConnection:
    """Tests for database connection management."""

    def test_connection_with_nonexistent_database(self):
        """Test that non-existent database raises DB_NOT_FOUND error."""
        with pytest.raises(ToolError) as exc_info:
            with get_connection("/nonexistent/path/to/database.db"):
                pass

        error = exc_info.value
        assert error.code == ErrorCode.DB_NOT_FOUND
        assert not error.retryable

    def test_connection_with_directory_instead_of_file(self, tmp_path):
        """Test that directory path raises DB_NOT_FOUND error."""
        # Create a directory instead of a file
        dir_path = tmp_path / "not_a_file"
        dir_path.mkdir()

        with pytest.raises(ToolError) as exc_info:
            with get_connection(str(dir_path)):
                pass

        error = exc_info.value
        assert error.code == ErrorCode.DB_NOT_FOUND

    def test_connection_is_read_only(self, tmp_path):
        """Test that connection is opened in read-only mode."""
        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        # Try to write through the read-only connection
        with get_connection(str(db_path)) as conn:
            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn.execute("INSERT INTO test VALUES (1)")

            assert "readonly" in str(exc_info.value).lower() or "read-only" in str(exc_info.value).lower()

    def test_connection_returns_dict_rows(self, tmp_path):
        """Test that connection is configured for dictionary-style row access."""
        # Create a test database with data
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'test')")
        conn.commit()
        conn.close()

        # Query through our connection manager
        with get_connection(str(db_path)) as conn:
            cursor = conn.execute("SELECT * FROM test")
            row = cursor.fetchone()

            # Should be able to access by column name
            assert row["id"] == 1
            assert row["name"] == "test"

    def test_connection_is_closed_after_context(self, tmp_path):
        """Test that connection is properly closed after context exit."""
        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        # Use connection in context
        with get_connection(str(db_path)) as conn:
            test_conn = conn

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError):
            test_conn.execute("SELECT 1")

    def test_connection_closed_on_error(self, tmp_path):
        """Test that connection is closed even when error occurs."""
        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        # Use connection and raise error
        test_conn = None
        try:
            with get_connection(str(db_path)) as conn:
                test_conn = conn
                raise ValueError("Test error")
        except ValueError:
            pass

        # Connection should still be closed
        with pytest.raises(sqlite3.ProgrammingError):
            test_conn.execute("SELECT 1")


class TestQueryNewJobs:
    """Tests for querying new jobs."""

    def create_test_db(self, db_path: Path, jobs: list):
        """Helper to create a test database with job records."""
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
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
                created_at TEXT NOT NULL
            )
        """)

        for job in jobs:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, title, company, description, url, location,
                    source, status, captured_at, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("job_id", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("description", ""),
                job["url"],  # Required
                job.get("location", ""),
                job.get("source", ""),
                job.get("status", "new"),
                job.get("captured_at", datetime.now(timezone.utc).isoformat()),
                "{}",  # payload_json
                datetime.now(timezone.utc).isoformat()
            ))

        conn.commit()
        conn.close()

    def test_query_empty_database(self, tmp_path):
        """Test query returns empty list when no jobs exist."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        with get_connection(str(db_path)) as conn:
            results = query_new_jobs(conn, limit=50)

        assert results == []

    def test_query_returns_only_new_status(self, tmp_path):
        """Test query filters by status='new'."""
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": "http://example.com/1", "status": "new", "title": "Job 1"},
            {"url": "http://example.com/2", "status": "new", "title": "Job 2"},
            {"url": "http://example.com/3", "status": "applied", "title": "Job 3"},
            {"url": "http://example.com/4", "status": "rejected", "title": "Job 4"},
        ]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            results = query_new_jobs(conn, limit=50)

        assert len(results) == 2
        assert all(r["status"] == "new" for r in results)
        assert {r["title"] for r in results} == {"Job 1", "Job 2"}

    def test_query_respects_limit(self, tmp_path):
        """Test query respects the limit parameter."""
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": f"http://example.com/{i}", "title": f"Job {i}"}
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            # Query limit+1 to check has_more logic
            results = query_new_jobs(conn, limit=5)

        # Should return 6 rows (limit + 1)
        assert len(results) == 6

    def test_query_deterministic_ordering(self, tmp_path):
        """Test query returns results in deterministic order."""
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        jobs = [
            {
                "url": "http://example.com/1",
                "title": "Job 1",
                "captured_at": base_time.replace(hour=10).isoformat()
            },
            {
                "url": "http://example.com/2",
                "title": "Job 2",
                "captured_at": base_time.replace(hour=12).isoformat()
            },
            {
                "url": "http://example.com/3",
                "title": "Job 3",
                "captured_at": base_time.replace(hour=14).isoformat()
            },
        ]
        self.create_test_db(db_path, jobs)

        # Query multiple times
        with get_connection(str(db_path)) as conn:
            results1 = query_new_jobs(conn, limit=10)

        with get_connection(str(db_path)) as conn:
            results2 = query_new_jobs(conn, limit=10)

        # Results should be identical
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1["id"] == r2["id"]
            assert r1["title"] == r2["title"]

        # Should be ordered by captured_at DESC (newest first)
        assert results1[0]["title"] == "Job 3"
        assert results1[1]["title"] == "Job 2"
        assert results1[2]["title"] == "Job 1"

    def test_query_with_cursor_pagination(self, tmp_path):
        """Test query with cursor returns next page correctly."""
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        jobs = [
            {
                "url": f"http://example.com/{i}",
                "title": f"Job {i}",
                "captured_at": base_time.replace(hour=10 + i).isoformat()
            }
            for i in range(5)
        ]
        self.create_test_db(db_path, jobs)

        # Get first page
        with get_connection(str(db_path)) as conn:
            page1 = query_new_jobs(conn, limit=2)

        assert len(page1) == 3  # limit + 1

        # Use last row of first page as cursor
        cursor = (page1[1]["captured_at"], page1[1]["id"])

        # Get second page
        with get_connection(str(db_path)) as conn:
            page2 = query_new_jobs(conn, limit=2, cursor=cursor)

        # Should get remaining jobs
        assert len(page2) > 0
        # No overlap between pages
        page1_ids = {r["id"] for r in page1[:2]}
        page2_ids = {r["id"] for r in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_query_returns_fixed_schema_fields(self, tmp_path):
        """Test query returns only the fixed schema fields."""
        db_path = tmp_path / "test.db"
        jobs = [{
            "url": "http://example.com/1",
            "job_id": "12345",
            "title": "Software Engineer",
            "company": "Example Corp",
            "description": "Great job",
            "location": "Toronto, ON",
            "source": "linkedin"
        }]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            results = query_new_jobs(conn, limit=50)

        assert len(results) == 1
        job = results[0]

        # Check all required fields are present
        expected_fields = {
            "id", "job_id", "title", "company", "description",
            "url", "location", "source", "status", "captured_at"
        }
        assert set(job.keys()) == expected_fields

        # Check field values
        assert job["job_id"] == "12345"
        assert job["title"] == "Software Engineer"
        assert job["company"] == "Example Corp"
        assert job["description"] == "Great job"
        assert job["url"] == "http://example.com/1"
        assert job["location"] == "Toronto, ON"
        assert job["source"] == "linkedin"
        assert job["status"] == "new"

    def test_query_handles_null_fields(self, tmp_path):
        """Test query handles null/missing fields correctly."""
        db_path = tmp_path / "test.db"
        jobs = [{
            "url": "http://example.com/1",
            "job_id": None,
            "title": None,
            "company": None,
            "description": None,
            "location": None,
            "source": None
        }]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            results = query_new_jobs(conn, limit=50)

        assert len(results) == 1
        job = results[0]

        # Null fields should be None
        assert job["job_id"] is None
        assert job["title"] is None
        assert job["company"] is None
        assert job["description"] is None
        assert job["location"] is None
        assert job["source"] is None

    def test_query_with_same_captured_at_uses_id_tiebreaker(self, tmp_path):
        """Test that jobs with same captured_at are ordered by id DESC."""
        db_path = tmp_path / "test.db"
        same_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc).isoformat()

        jobs = [
            {"url": "http://example.com/1", "title": "Job 1", "captured_at": same_time},
            {"url": "http://example.com/2", "title": "Job 2", "captured_at": same_time},
            {"url": "http://example.com/3", "title": "Job 3", "captured_at": same_time},
        ]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            results = query_new_jobs(conn, limit=10)

        # All have same captured_at, so should be ordered by id DESC
        assert len(results) == 3
        assert results[0]["id"] > results[1]["id"]
        assert results[1]["id"] > results[2]["id"]


class TestQueryShortlistJobs:
    """Tests for querying shortlist jobs."""

    def create_test_db(self, db_path: Path, jobs: list):
        """Helper to create a test database with job records."""
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
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
                created_at TEXT NOT NULL
            )
        """)

        for job in jobs:
            conn.execute("""
                INSERT INTO jobs (
                    job_id, title, company, description, url, location,
                    source, status, captured_at, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("job_id", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("description", ""),
                job["url"],  # Required
                job.get("location", ""),
                job.get("source", ""),
                job.get("status", "new"),
                job.get("captured_at", datetime.now(timezone.utc).isoformat()),
                "{}",  # payload_json
                datetime.now(timezone.utc).isoformat()
            ))

        conn.commit()
        conn.close()

    def test_query_empty_database(self, tmp_path):
        """Test query returns empty list when no shortlist jobs exist."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results = query_shortlist_jobs(conn, limit=50)

        assert results == []

    def test_query_returns_only_shortlist_status(self, tmp_path):
        """Test query filters by status='shortlist'."""
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": "http://example.com/1", "status": "shortlist", "title": "Job 1"},
            {"url": "http://example.com/2", "status": "shortlist", "title": "Job 2"},
            {"url": "http://example.com/3", "status": "new", "title": "Job 3"},
            {"url": "http://example.com/4", "status": "applied", "title": "Job 4"},
        ]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results = query_shortlist_jobs(conn, limit=50)

        assert len(results) == 2
        assert all(r["status"] == "shortlist" for r in results)
        assert {r["title"] for r in results} == {"Job 1", "Job 2"}

    def test_query_respects_limit(self, tmp_path):
        """Test query respects the limit parameter."""
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": f"http://example.com/{i}", "title": f"Job {i}", "status": "shortlist"}
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results = query_shortlist_jobs(conn, limit=5)

        # Should return exactly 5 rows (unlike query_new_jobs which returns limit+1)
        assert len(results) == 5

    def test_query_deterministic_ordering(self, tmp_path):
        """Test query returns results in deterministic order (captured_at DESC, id DESC)."""
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        jobs = [
            {
                "url": "http://example.com/1",
                "title": "Job 1",
                "status": "shortlist",
                "captured_at": base_time.replace(hour=10).isoformat()
            },
            {
                "url": "http://example.com/2",
                "title": "Job 2",
                "status": "shortlist",
                "captured_at": base_time.replace(hour=12).isoformat()
            },
            {
                "url": "http://example.com/3",
                "title": "Job 3",
                "status": "shortlist",
                "captured_at": base_time.replace(hour=14).isoformat()
            },
        ]
        self.create_test_db(db_path, jobs)

        # Query multiple times
        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results1 = query_shortlist_jobs(conn, limit=10)

        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results2 = query_shortlist_jobs(conn, limit=10)

        # Results should be identical
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1["id"] == r2["id"]
            assert r1["title"] == r2["title"]

        # Should be ordered by captured_at DESC (newest first)
        assert results1[0]["title"] == "Job 3"
        assert results1[1]["title"] == "Job 2"
        assert results1[2]["title"] == "Job 1"

    def test_query_returns_fixed_schema_fields(self, tmp_path):
        """Test query returns only the required fields for tracker generation."""
        db_path = tmp_path / "test.db"
        jobs = [{
            "url": "http://example.com/1",
            "job_id": "12345",
            "title": "Software Engineer",
            "company": "Example Corp",
            "description": "Great job",
            "location": "Toronto, ON",
            "source": "linkedin",
            "status": "shortlist"
        }]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results = query_shortlist_jobs(conn, limit=50)

        assert len(results) == 1
        job = results[0]

        # Check all required fields are present
        expected_fields = {
            "id", "job_id", "title", "company", "description",
            "url", "captured_at", "status"
        }
        assert set(job.keys()) == expected_fields

        # Check field values
        assert job["job_id"] == "12345"
        assert job["title"] == "Software Engineer"
        assert job["company"] == "Example Corp"
        assert job["description"] == "Great job"
        assert job["url"] == "http://example.com/1"
        assert job["status"] == "shortlist"

    def test_query_handles_null_fields(self, tmp_path):
        """Test query handles null/missing fields correctly."""
        db_path = tmp_path / "test.db"
        jobs = [{
            "url": "http://example.com/1",
            "job_id": None,
            "title": None,
            "company": None,
            "description": None,
            "status": "shortlist"
        }]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results = query_shortlist_jobs(conn, limit=50)

        assert len(results) == 1
        job = results[0]

        # Null fields should be None
        assert job["job_id"] is None
        assert job["title"] is None
        assert job["company"] is None
        assert job["description"] is None

    def test_query_with_same_captured_at_uses_id_tiebreaker(self, tmp_path):
        """Test that jobs with same captured_at are ordered by id DESC."""
        db_path = tmp_path / "test.db"
        same_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc).isoformat()

        jobs = [
            {"url": "http://example.com/1", "title": "Job 1", "status": "shortlist", "captured_at": same_time},
            {"url": "http://example.com/2", "title": "Job 2", "status": "shortlist", "captured_at": same_time},
            {"url": "http://example.com/3", "title": "Job 3", "status": "shortlist", "captured_at": same_time},
        ]
        self.create_test_db(db_path, jobs)

        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results = query_shortlist_jobs(conn, limit=10)

        # All have same captured_at, so should be ordered by id DESC
        assert len(results) == 3
        assert results[0]["id"] > results[1]["id"]
        assert results[1]["id"] > results[2]["id"]

    def test_query_is_read_only(self, tmp_path):
        """Test that query does not modify database records."""
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": "http://example.com/1", "title": "Job 1", "status": "shortlist"},
            {"url": "http://example.com/2", "title": "Job 2", "status": "shortlist"},
        ]
        self.create_test_db(db_path, jobs)

        # Snapshot database before query
        conn_snapshot = sqlite3.connect(str(db_path))
        before = conn_snapshot.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        conn_snapshot.close()

        # Execute query
        with get_connection(str(db_path)) as conn:
            from db.jobs_reader import query_shortlist_jobs
            results = query_shortlist_jobs(conn, limit=50)

        # Snapshot database after query
        conn_snapshot = sqlite3.connect(str(db_path))
        after = conn_snapshot.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        conn_snapshot.close()

        # Database should be unchanged
        assert before == after
        assert len(results) == 2
