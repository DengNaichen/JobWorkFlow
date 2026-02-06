"""
Integration tests for bulk_read_new_jobs MCP tool handler.

Tests the complete tool integration including validation, cursor handling,
database reading, pagination, and schema mapping.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import pytest

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

    def test_tool_with_default_parameters(self, tmp_path):
        """Test tool with default parameters (limit=50, no cursor)."""
        # Create test database with some jobs
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": f"http://example.com/{i}", "title": f"Job {i}"}
            for i in range(10)
        ]
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
        jobs = [
            {"url": f"http://example.com/{i}", "title": f"Job {i}"}
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        # Call tool with limit=5
        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 5
        })

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
                "captured_at": base_time.replace(hour=10 + i).isoformat()
            }
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        # Get first page
        page1 = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 5
        })

        assert page1["has_more"] is True
        assert page1["next_cursor"] is not None

        # Get second page using cursor
        page2 = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 5,
            "cursor": page1["next_cursor"]
        })

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
        result = bulk_read_new_jobs({
            "db_path": "/nonexistent/path/to/database.db"
        })

        # Should return error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.DB_NOT_FOUND.value
        assert result["error"]["retryable"] is False
        assert "not found" in result["error"]["message"].lower()

    def test_tool_with_invalid_limit_below_minimum(self, tmp_path):
        """Test tool with limit below minimum returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 0
        })

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert result["error"]["retryable"] is False
        assert "limit" in result["error"]["message"].lower()

    def test_tool_with_invalid_limit_above_maximum(self, tmp_path):
        """Test tool with limit above maximum returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 1001
        })

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert result["error"]["retryable"] is False
        assert "limit" in result["error"]["message"].lower()

    def test_tool_with_malformed_cursor(self, tmp_path):
        """Test tool with malformed cursor returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "cursor": "not-a-valid-cursor!!!"
        })

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

        result = bulk_read_new_jobs({"db_path": str(db_path)})

        # Check schema
        assert result["count"] == 1
        job = result["jobs"][0]

        # All fixed fields should be present
        expected_fields = {
            "id", "job_id", "title", "company", "description",
            "url", "location", "source", "status", "captured_at"
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
            jobs = [
                {"url": f"http://example.com/{i}", "title": f"Job {i}"}
                for i in range(size)
            ]
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
                "captured_at": base_time.replace(hour=10 + i % 10, minute=i).isoformat()
            }
            for i in range(20)
        ]
        self.create_test_db(db_path, jobs)

        # Paginate through all results
        all_ids = set()
        cursor = None
        page_count = 0

        while True:
            result = bulk_read_new_jobs({
                "db_path": str(db_path),
                "limit": 5,
                "cursor": cursor
            })

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
                "captured_at": base_time.replace(hour=10 + i).isoformat()
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
        result = bulk_read_new_jobs({
            "db_path": 123  # Should be string
        })

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "db_path" in result["error"]["message"].lower()

    def test_tool_with_invalid_limit_type(self, tmp_path):
        """Test tool with invalid limit type returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": "not-a-number"
        })

        # Should return validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR.value
        assert "limit" in result["error"]["message"].lower()

    def test_tool_with_empty_cursor_string(self, tmp_path):
        """Test tool with empty cursor string returns VALIDATION_ERROR."""
        db_path = tmp_path / "test.db"
        self.create_test_db(db_path, [])

        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "cursor": ""
        })

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
                "captured_at": base_time.replace(hour=10 + i).isoformat()
            }
            for i in range(10)
        ]
        self.create_test_db(db_path, jobs)

        # Get first page (5 jobs)
        page1 = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 5
        })

        # First page should have next_cursor
        assert page1["has_more"] is True
        assert page1["next_cursor"] is not None

        # Get second page (remaining 5 jobs)
        page2 = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 5,
            "cursor": page1["next_cursor"]
        })

        # Second page should NOT have next_cursor (terminal page)
        assert page2["has_more"] is False
        assert page2["next_cursor"] is None

    def test_tool_with_exactly_limit_results(self, tmp_path):
        """Test tool with exactly limit results (no more pages)."""
        db_path = tmp_path / "test.db"

        # Create exactly 5 jobs
        jobs = [
            {"url": f"http://example.com/{i}", "title": f"Job {i}"}
            for i in range(5)
        ]
        self.create_test_db(db_path, jobs)

        # Request with limit=5
        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 5
        })

        # Should return all 5 jobs with no more pages
        assert result["count"] == 5
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    def test_tool_with_fewer_than_limit_results(self, tmp_path):
        """Test tool with fewer results than limit."""
        db_path = tmp_path / "test.db"

        # Create only 3 jobs
        jobs = [
            {"url": f"http://example.com/{i}", "title": f"Job {i}"}
            for i in range(3)
        ]
        self.create_test_db(db_path, jobs)

        # Request with limit=10
        result = bulk_read_new_jobs({
            "db_path": str(db_path),
            "limit": 10
        })

        # Should return all 3 jobs with no more pages
        assert result["count"] == 3
        assert result["has_more"] is False
        assert result["next_cursor"] is None
