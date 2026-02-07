"""
Integration tests for bulk_read_new_jobs MCP tool handler.

Tests the complete tool integration including validation, cursor handling,
database reading, pagination, and schema mapping.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


from tools.bulk_read_new_jobs import bulk_read_new_jobs
from models.errors import ErrorCode


class TestBulkReadNewJobsIntegration:
    """Integration tests for the complete tool handler."""

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
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, title, company, description, url, location,
                    source, status, captured_at, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
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
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        conn.commit()
        conn.close()

    def test_tool_with_default_parameters(self, tmp_path):
        """Test tool with default parameters (limit=50, no cursor)."""
        # Create test database with some jobs
        db_path = tmp_path / "test.db"
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(10)]
        self.create_test_db(db_path, jobs)

        # Call tool with only db_path
        result = bulk_read_new_jobs({"db_path": str(db_path)})

        # Should succeed
        assert "error" not in result
        assert "jobs" in result
        assert "count" in result
        assert "has_more" in result
        assert "next_cursor" in result

        # Should return all 10 jobs (less than default limit of 50)
        assert result["count"] == 10
        assert len(result["jobs"]) == 10
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    def test_tool_with_custom_limit(self, tmp_path):
        """Test tool with custom limit parameter."""
        # Create test database with 10 jobs
        db_path = tmp_path / "test.db"
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(10)]
        self.create_test_db(db_path, jobs)

        # Call tool with limit=5
        result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 5})

        # Should return 5 jobs with has_more=True
        assert result["count"] == 5
        assert len(result["jobs"]) == 5
        assert result["has_more"] is True
        assert result["next_cursor"] is not None

    def test_tool_with_cursor_for_second_page(self, tmp_path):
        """Test tool with cursor to retrieve second page."""
        # Create test database with 10 jobs
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)
        jobs = [
            {
                "url": f"http://example.com/{i}",
                "title": f"Job {i}",
                "captured_at": base_time.replace(hour=10 + i).isoformat(),
            }
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        # Get first page
        page1 = bulk_read_new_jobs({"db_path": str(db_path), "limit": 5})

        assert page1["has_more"] is True
        assert page1["next_cursor"] is not None

        # Get second page using cursor
        page2 = bulk_read_new_jobs(
            {"db_path": str(db_path), "limit": 5, "cursor": page1["next_cursor"]}
        )

        # Should get remaining jobs
        assert page2["count"] == 5
        assert page2["has_more"] is False
        assert page2["next_cursor"] is None

        # No overlap between pages
        page1_ids = {job["id"] for job in page1["jobs"]}
        page2_ids = {job["id"] for job in page2["jobs"]}
        assert page1_ids.isdisjoint(page2_ids)

    def test_tool_with_nonexistent_database(self):
        """Test tool with non-existent database returns DB_NOT_FOUND error."""
        result = bulk_read_new_jobs({"db_path": "/nonexistent/path/to/database.db"})

        # Should return error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.DB_NOT_FOUND.value
        assert result["error"]["retryable"] is False
        assert "not found" in result["error"]["message"].lower()

    def test_tool_with_invalid_limit_below_minimum(self, tmp_path):
        """Test tool with limit below minimum returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 0})

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert result["error"]["retryable"] is False
        assert "limit" in result["error"]["message"].lower()

    def test_tool_with_invalid_limit_above_maximum(self, tmp_path):
        """Test tool with limit above maximum returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 1001})

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert result["error"]["retryable"] is False
        assert "limit" in result["error"]["message"].lower()

    def test_tool_with_malformed_cursor(self, tmp_path):
        """Test tool with malformed cursor returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({"db_path": str(db_path), "cursor": "not-a-valid-cursor!!!"})

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert result["error"]["retryable"] is False
        assert "cursor" in result["error"]["message"].lower()

    def test_tool_returns_empty_result_when_no_new_jobs(self, tmp_path):
        """Test tool returns empty result set without error when no new jobs exist."""
        # Create database with only non-new jobs
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": "http://example.com/1", "status": "applied"},
            {"url": "http://example.com/2", "status": "rejected"},
        ]
        self.create_test_db(db_path, jobs)

        result = bulk_read_new_jobs({"db_path": str(db_path)})

        # Should succeed with empty results
        assert "error" not in result
        assert result["jobs"] == []
        assert result["count"] == 0
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    def test_tool_returns_stable_schema(self, tmp_path):
        """Test tool returns jobs with stable schema fields."""
        db_path = tmp_path / "test.db"
        jobs = [
            {
                "url": "http://example.com/1",
                "job_id": "12345",
                "title": "Software Engineer",
                "company": "Example Corp",
                "description": "Great job",
                "location": "Toronto, ON",
                "source": "linkedin",
            }
        ]
        self.create_test_db(db_path, jobs)

        result = bulk_read_new_jobs({"db_path": str(db_path)})

        # Check schema
        assert result["count"] == 1
        job = result["jobs"][0]

        # All fixed fields should be present
        expected_fields = {
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
        }
        assert set(job.keys()) == expected_fields

        # Check values
        assert job["job_id"] == "12345"
        assert job["title"] == "Software Engineer"
        assert job["company"] == "Example Corp"
        assert job["description"] == "Great job"
        assert job["url"] == "http://example.com/1"
        assert job["location"] == "Toronto, ON"
        assert job["source"] == "linkedin"
        assert job["status"] == "new"

    def test_tool_handles_missing_fields(self, tmp_path):
        """Test tool handles missing/null fields correctly."""
        db_path = tmp_path / "test.db"
        jobs = [
            {
                "url": "http://example.com/1",
                "job_id": None,
                "title": None,
                "company": None,
                "description": None,
                "location": None,
                "source": None,
            }
        ]
        self.create_test_db(db_path, jobs)

        result = bulk_read_new_jobs({"db_path": str(db_path)})

        # Should succeed
        assert result["count"] == 1
        job = result["jobs"][0]

        # Null fields should be None
        assert job["job_id"] is None
        assert job["title"] is None
        assert job["company"] is None
        assert job["description"] is None
        assert job["location"] is None
        assert job["source"] is None

    def test_tool_count_matches_jobs_length(self, tmp_path):
        """Test that count field always matches length of jobs array."""
        db_path = tmp_path / "test.db"

        # Test with various sizes
        for size in [0, 1, 5, 10]:
            jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(size)]
            self.create_test_db(db_path, jobs)

            result = bulk_read_new_jobs({"db_path": str(db_path)})

            assert result["count"] == len(result["jobs"])
            assert result["count"] == size

            # Clean up for next iteration
            db_path.unlink()

    def test_tool_pagination_no_duplicates(self, tmp_path):
        """Test that pagination produces no duplicate records across pages."""
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        # Create 20 jobs
        jobs = [
            {
                "url": f"http://example.com/{i}",
                "title": f"Job {i}",
                "captured_at": base_time.replace(hour=10 + i % 10, minute=i).isoformat(),
            }
            for i in range(20)
        ]
        self.create_test_db(db_path, jobs)

        # Paginate through all results
        all_ids = set()
        cursor = None
        page_count = 0

        while True:
            result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 5, "cursor": cursor})

            page_count += 1
            page_ids = {job["id"] for job in result["jobs"]}

            # Check no duplicates
            assert all_ids.isdisjoint(page_ids), f"Found duplicates in page {page_count}"
            all_ids.update(page_ids)

            if not result["has_more"]:
                break

            cursor = result["next_cursor"]

        # Should have retrieved all 20 jobs
        assert len(all_ids) == 20

    def test_tool_deterministic_ordering(self, tmp_path):
        """Test that repeated queries return results in same order."""
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        jobs = [
            {
                "url": f"http://example.com/{i}",
                "title": f"Job {i}",
                "captured_at": base_time.replace(hour=10 + i).isoformat(),
            }
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        # Query multiple times
        result1 = bulk_read_new_jobs({"db_path": str(db_path)})
        result2 = bulk_read_new_jobs({"db_path": str(db_path)})

        # Results should be identical
        assert result1["count"] == result2["count"]
        for job1, job2 in zip(result1["jobs"], result2["jobs"]):
            assert job1["id"] == job2["id"]
            assert job1["title"] == job2["title"]

    def test_tool_with_invalid_db_path_type(self, tmp_path):
        """Test tool with invalid db_path type returns VALIDATION_ERROR."""
        result = bulk_read_new_jobs(
            {
                "db_path": 123  # Should be string
            }
        )

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "db_path" in result["error"]["message"].lower()

    def test_tool_with_invalid_limit_type(self, tmp_path):
        """Test tool with invalid limit type returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({"db_path": str(db_path), "limit": "not-a-number"})

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "limit" in result["error"]["message"].lower()

    def test_tool_with_empty_cursor_string(self, tmp_path):
        """Test tool with empty cursor string returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({"db_path": str(db_path), "cursor": ""})

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "cursor" in result["error"]["message"].lower()

    def test_tool_next_cursor_null_on_terminal_page(self, tmp_path):
        """Test that next_cursor is null only on the terminal page."""
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        # Create exactly 10 jobs
        jobs = [
            {
                "url": f"http://example.com/{i}",
                "title": f"Job {i}",
                "captured_at": base_time.replace(hour=10 + i).isoformat(),
            }
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        # Get first page (5 jobs)
        page1 = bulk_read_new_jobs({"db_path": str(db_path), "limit": 5})

        # First page should have next_cursor
        assert page1["has_more"] is True
        assert page1["next_cursor"] is not None

        # Get second page (remaining 5 jobs)
        page2 = bulk_read_new_jobs(
            {"db_path": str(db_path), "limit": 5, "cursor": page1["next_cursor"]}
        )

        # Second page should NOT have next_cursor (terminal page)
        assert page2["has_more"] is False
        assert page2["next_cursor"] is None

    def test_tool_with_exactly_limit_results(self, tmp_path):
        """Test tool with exactly limit results (no more pages)."""
        db_path = tmp_path / "test.db"

        # Create exactly 5 jobs
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(5)]
        self.create_test_db(db_path, jobs)

        # Request with limit=5
        result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 5})

        # Should return all 5 jobs with no more pages
        assert result["count"] == 5
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    def test_tool_with_fewer_than_limit_results(self, tmp_path):
        """Test tool with fewer results than limit."""
        db_path = tmp_path / "test.db"

        # Create only 3 jobs
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(3)]
        self.create_test_db(db_path, jobs)

        # Request with limit=10
        result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 10})

        # Should return all 3 jobs with no more pages
        assert result["count"] == 3
        assert result["has_more"] is False
        assert result["next_cursor"] is None


class TestBoundaryBehavior:
    """
    Test boundary behavior enforcement for bulk_read_new_jobs.

    Validates Requirements 8.3, 8.4, 8.5:
    - Tool does not modify database rows (read-only)
    - Tool does not write tracker files
    - Tool does not perform triage decisions

    **Validates: Requirements 8.3, 8.4, 8.5**
    """

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
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)

        for job in jobs:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, title, company, description, url, location,
                    source, status, captured_at, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
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
                    datetime.now(timezone.utc).isoformat(),
                    job.get("updated_at"),
                ),
            )

        conn.commit()
        conn.close()

    def test_tool_does_not_modify_database_rows(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not modify any database rows.

        Verifies read-only behavior by checking that all row data remains
        unchanged after tool invocation.

        **Validates: Requirements 8.3**
        """
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        # Create test jobs with specific data
        jobs = [
            {
                "url": f"http://example.com/{i}",
                "job_id": f"job-{i}",
                "title": f"Original Title {i}",
                "company": f"Original Company {i}",
                "description": f"Original Description {i}",
                "location": f"Original Location {i}",
                "source": "linkedin",
                "status": "new",
                "captured_at": base_time.replace(hour=10 + i).isoformat(),
                "updated_at": base_time.isoformat(),
            }
            for i in range(5)
        ]
        self.create_test_db(db_path, jobs)

        # Capture original state
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT id, job_id, title, company, description, url, location,
                   source, status, captured_at, updated_at
            FROM jobs
            ORDER BY id
        """)
        original_rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Call bulk_read_new_jobs multiple times
        for _ in range(3):
            result = bulk_read_new_jobs({"db_path": str(db_path)})
            assert "error" not in result
            assert result["count"] == 5

        # Verify database state is unchanged
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT id, job_id, title, company, description, url, location,
                   source, status, captured_at, updated_at
            FROM jobs
            ORDER BY id
        """)
        current_rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # All fields should be identical
        assert len(current_rows) == len(original_rows)
        for original, current in zip(original_rows, current_rows):
            assert original == current, f"Row {original['id']} was modified"

    def test_tool_does_not_update_status_field(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not update the status field.

        Verifies that status remains unchanged even when reading jobs,
        ensuring no implicit status transitions occur.

        **Validates: Requirements 8.3**
        """
        db_path = tmp_path / "test.db"

        # Create jobs with status='new'
        jobs = [
            {"url": f"http://example.com/{i}", "title": f"Job {i}", "status": "new"}
            for i in range(5)
        ]
        self.create_test_db(db_path, jobs)

        # Read jobs multiple times
        for _ in range(5):
            result = bulk_read_new_jobs({"db_path": str(db_path)})
            assert result["count"] == 5

        # Verify all jobs still have status='new'
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT status FROM jobs")
        statuses = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert all(status == "new" for status in statuses)
        assert len(statuses) == 5

    def test_tool_does_not_write_tracker_files(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not create or modify tracker files.

        Verifies that no tracker files are created in the workspace during
        tool execution, maintaining strict read-only boundary.

        **Validates: Requirements 8.4**
        """
        db_path = tmp_path / "test.db"
        tracker_dir = tmp_path / "trackers"
        tracker_dir.mkdir()

        # Create test jobs
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(10)]
        self.create_test_db(db_path, jobs)

        # Capture initial tracker directory state
        initial_files = set(tracker_dir.iterdir())

        # Call tool multiple times
        for _ in range(3):
            result = bulk_read_new_jobs({"db_path": str(db_path)})
            assert "error" not in result

        # Verify no new tracker files were created
        final_files = set(tracker_dir.iterdir())
        assert final_files == initial_files, "Tracker files were created"

        # Verify tracker directory is still empty
        assert len(list(tracker_dir.iterdir())) == 0

    def test_tool_does_not_create_tracker_directories(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not create tracker directories.

        Verifies that no tracker-related directories are created during
        tool execution.

        **Validates: Requirements 8.4**
        """
        db_path = tmp_path / "test.db"

        # Create test jobs
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(5)]
        self.create_test_db(db_path, jobs)

        # Capture initial directory state
        initial_dirs = set(tmp_path.iterdir())

        # Call tool
        result = bulk_read_new_jobs({"db_path": str(db_path)})
        assert "error" not in result

        # Verify no new directories were created
        final_dirs = set(tmp_path.iterdir())
        new_dirs = final_dirs - initial_dirs

        # Filter out any __pycache__ or .pytest_cache directories
        new_dirs = {d for d in new_dirs if not d.name.startswith((".", "__"))}

        assert len(new_dirs) == 0, f"New directories created: {new_dirs}"

    def test_tool_does_not_modify_row_count(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not insert or delete rows.

        Verifies that the total row count remains constant across multiple
        tool invocations.

        **Validates: Requirements 8.3**
        """
        db_path = tmp_path / "test.db"

        # Create test jobs
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(10)]
        self.create_test_db(db_path, jobs)

        # Get initial row count
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        initial_count = cursor.fetchone()[0]
        conn.close()

        assert initial_count == 10

        # Call tool multiple times
        for _ in range(5):
            result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 3})
            assert "error" not in result

        # Verify row count is unchanged
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM jobs")
        final_count = cursor.fetchone()[0]
        conn.close()

        assert final_count == initial_count

    def test_tool_does_not_perform_triage_decisions(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not perform triage decisions.

        Verifies that jobs are returned as-is without any filtering,
        scoring, or ranking based on triage criteria. The tool should
        return all jobs with status='new' without making decisions about
        their suitability.

        **Validates: Requirements 8.5**
        """
        db_path = tmp_path / "test.db"

        # Create jobs with varying quality indicators
        # (e.g., missing descriptions, different sources)
        jobs = [
            {
                "url": "http://example.com/1",
                "title": "Great Job with Description",
                "description": "This is a detailed job description",
                "company": "Top Company",
                "source": "linkedin",
            },
            {
                "url": "http://example.com/2",
                "title": "Job Without Description",
                "description": "",  # Empty description
                "company": "Some Company",
                "source": "indeed",
            },
            {
                "url": "http://example.com/3",
                "title": "Job with Minimal Info",
                "description": None,  # Null description
                "company": None,
                "source": "other",
            },
        ]
        self.create_test_db(db_path, jobs)

        # Call tool
        result = bulk_read_new_jobs({"db_path": str(db_path)})

        # Verify all jobs are returned without filtering
        assert result["count"] == 3
        assert len(result["jobs"]) == 3

        # Verify all expected URLs are present (order may vary based on captured_at)
        urls = {job["url"] for job in result["jobs"]}
        expected_urls = {"http://example.com/1", "http://example.com/2", "http://example.com/3"}
        assert urls == expected_urls

        # Verify no triage-related fields are added to response
        for job in result["jobs"]:
            # Should not have triage decision fields
            assert "triage_score" not in job
            assert "triage_decision" not in job
            assert "recommended" not in job
            assert "priority" not in job

    def test_tool_does_not_update_timestamps(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not update timestamp fields.

        Verifies that created_at and updated_at timestamps remain unchanged
        after reading jobs.

        **Validates: Requirements 8.3**
        """
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Create jobs with specific timestamps
        jobs = [
            {
                "url": f"http://example.com/{i}",
                "title": f"Job {i}",
                "captured_at": base_time.replace(day=i + 1).isoformat(),
                "updated_at": base_time.replace(day=i + 1).isoformat(),
            }
            for i in range(5)
        ]
        self.create_test_db(db_path, jobs)

        # Capture original timestamps
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT id, captured_at, updated_at
            FROM jobs
            ORDER BY id
        """)
        original_timestamps = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Call tool multiple times
        for _ in range(3):
            result = bulk_read_new_jobs({"db_path": str(db_path)})
            assert result["count"] == 5

        # Verify timestamps are unchanged
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT id, captured_at, updated_at
            FROM jobs
            ORDER BY id
        """)
        current_timestamps = [dict(row) for row in cursor.fetchall()]
        conn.close()

        assert current_timestamps == original_timestamps

    def test_tool_read_only_with_pagination(self, tmp_path):
        """
        Test that bulk_read_new_jobs maintains read-only behavior during pagination.

        Verifies that paginating through results does not modify any database
        rows, even when using cursors.

        **Validates: Requirements 8.3**
        """
        db_path = tmp_path / "test.db"
        base_time = datetime(2026, 2, 5, 12, 0, 0, tzinfo=timezone.utc)

        # Create 20 jobs
        jobs = [
            {
                "url": f"http://example.com/{i}",
                "title": f"Job {i}",
                "status": "new",
                "captured_at": base_time.replace(hour=10 + i % 10, minute=i).isoformat(),
            }
            for i in range(20)
        ]
        self.create_test_db(db_path, jobs)

        # Capture original state
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM jobs ORDER BY id")
        original_rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Paginate through all results
        cursor = None
        pages_read = 0
        while True:
            result = bulk_read_new_jobs({"db_path": str(db_path), "limit": 5, "cursor": cursor})

            assert "error" not in result
            pages_read += 1

            if not result["has_more"]:
                break

            cursor = result["next_cursor"]

        assert pages_read == 4  # 20 jobs / 5 per page

        # Verify database state is unchanged
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM jobs ORDER BY id")
        current_rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        assert current_rows == original_rows

    def test_tool_does_not_create_side_effect_files(self, tmp_path):
        """
        Test that bulk_read_new_jobs does not create any side-effect files.

        Verifies that no log files, cache files, or other artifacts are
        created during tool execution.

        **Validates: Requirements 8.4**
        """
        db_path = tmp_path / "test.db"

        # Create test jobs
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(5)]
        self.create_test_db(db_path, jobs)

        # Capture initial file list
        initial_files = set(tmp_path.rglob("*"))

        # Call tool
        result = bulk_read_new_jobs({"db_path": str(db_path)})
        assert "error" not in result

        # Verify no new files were created
        final_files = set(tmp_path.rglob("*"))
        new_files = final_files - initial_files

        # Filter out Python cache files
        new_files = {
            f for f in new_files if not any(part.startswith((".", "__")) for part in f.parts)
        }

        assert len(new_files) == 0, f"New files created: {new_files}"
