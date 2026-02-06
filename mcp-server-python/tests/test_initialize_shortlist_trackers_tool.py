"""
Integration tests for initialize_shortlist_trackers tool.

Tests verify the complete tool workflow including validation, database reading,
tracker planning, rendering, and atomic file operations.
"""

import sqlite3
from pathlib import Path
import pytest
from tools.initialize_shortlist_trackers import initialize_shortlist_trackers


class TestInitializeShortlistTrackersTool:
    """Integration tests for the initialize_shortlist_trackers tool."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with sample shortlist jobs."""
        db_path = tmp_path / "test_jobs.db"
        
        # Create database schema
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                job_id TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                description TEXT,
                url TEXT NOT NULL,
                location TEXT,
                source TEXT,
                status TEXT NOT NULL,
                captured_at TEXT NOT NULL
            )
        """)
        
        # Insert test data with shortlist status
        test_jobs = [
            (3629, "4368663835", "Software Engineer", "Amazon", 
             "Build scalable systems...", "https://example.com/job/123",
             "Seattle, WA", "linkedin", "shortlist", "2026-02-04T15:30:00"),
            (3630, "4368669999", "Senior Engineer", "Meta",
             "Work on social platforms...", "https://example.com/job/456",
             "Menlo Park, CA", "indeed", "shortlist", "2026-02-04T16:00:00"),
            (3631, "4368670000", "Backend Engineer", "Google",
             None, "https://example.com/job/789",
             "Mountain View, CA", "company_site", "shortlist", "2026-02-05T10:00:00"),
            # Add a non-shortlist job to verify filtering
            (3632, "4368670001", "DevOps Engineer", "Apple",
             "Manage infrastructure...", "https://example.com/job/999",
             "Cupertino, CA", "linkedin", "new", "2026-02-05T11:00:00"),
        ]
        
        conn.executemany("""
            INSERT INTO jobs (id, job_id, title, company, description, url, 
                            location, source, status, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_jobs)
        
        conn.commit()
        conn.close()
        
        return str(db_path)

    def test_basic_tracker_initialization(self, tmp_path, test_db):
        """Test basic tracker initialization for shortlist jobs."""
        trackers_dir = tmp_path / "trackers"
        
        # Call the tool
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify response structure
        assert "created_count" in result
        assert "skipped_count" in result
        assert "failed_count" in result
        assert "results" in result
        
        # Verify counts (3 shortlist jobs should be created)
        assert result["created_count"] == 3
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0
        
        # Verify results list
        assert len(result["results"]) == 3
        
        # Verify first result (most recent by captured_at DESC, then id DESC)
        first_result = result["results"][0]
        assert first_result["id"] == 3631  # 2026-02-05T10:00:00 (most recent)
        assert first_result["job_id"] == "4368670000"
        assert first_result["action"] == "created"
        assert first_result["success"] is True
        assert "tracker_path" in first_result
        
        # Verify tracker files were created
        for item in result["results"]:
            tracker_path = Path(item["tracker_path"])
            assert tracker_path.exists()
            
            # Verify content
            content = tracker_path.read_text()
            assert "## Job Description" in content
            assert "## Notes" in content
            assert "status: Reviewed" in content
            assert f"job_db_id: {item['id']}" in content

    def test_default_trackers_dir_resolves_from_repo_root_not_cwd(self, tmp_path, test_db, monkeypatch):
        """Test default trackers_dir is anchored to JOBWORKFLOW_ROOT/repo root."""
        work_cwd = tmp_path / "work-cwd"
        work_cwd.mkdir(parents=True, exist_ok=True)

        monkeypatch.setenv("JOBWORKFLOW_ROOT", str(tmp_path))
        monkeypatch.chdir(work_cwd)

        result = initialize_shortlist_trackers({
            "limit": 1,
            "db_path": test_db,
            "force": False,
            "dry_run": False
        })

        assert result["created_count"] == 1
        assert result["failed_count"] == 0

        tracker_path = Path(result["results"][0]["tracker_path"])
        assert tracker_path.exists()
        assert tracker_path.is_relative_to(tmp_path / "trackers")

        # Ensure no tracker directory was created under current working directory.
        assert not (work_cwd / "trackers").exists()

    def test_idempotent_initialization(self, tmp_path, test_db):
        """Test idempotent behavior - second run should skip existing files."""
        trackers_dir = tmp_path / "trackers"
        
        # First run
        result1 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        assert result1["created_count"] == 3
        assert result1["skipped_count"] == 0
        
        # Second run - should skip all existing files
        result2 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        assert result2["created_count"] == 0
        assert result2["skipped_count"] == 3
        assert result2["failed_count"] == 0
        
        # Verify all results have skipped_exists action
        for item in result2["results"]:
            assert item["action"] == "skipped_exists"
            assert item["success"] is True

    def test_existing_tracker_with_same_reference_link_is_treated_as_existing(self, tmp_path, test_db):
        """Test compatibility dedupe when a legacy tracker exists for the same job URL."""
        trackers_dir = tmp_path / "trackers"
        trackers_dir.mkdir(parents=True, exist_ok=True)

        legacy_tracker = trackers_dir / "2026-02-04-amazon.md"
        legacy_tracker.write_text(
            """---
company: Amazon
position: Software Engineer
status: Resume Written
application_date: 2026-02-04
reference_link: https://example.com/job/123
resume_path: "[[data/applications/amazon/resume/resume.pdf]]"
cover_letter_path: "[[data/applications/amazon/cover/cover-letter.pdf]]"
---

## Job Description

Existing legacy tracker.

## Notes
""",
            encoding="utf-8",
        )

        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })

        assert result["created_count"] == 2
        assert result["skipped_count"] == 1
        assert result["failed_count"] == 0

        amazon_result = next(item for item in result["results"] if item["id"] == 3629)
        assert amazon_result["action"] == "skipped_exists"
        assert amazon_result["tracker_path"] == str(legacy_tracker)

        # Ensure no new deterministic duplicate file was created for the same job.
        assert not (trackers_dir / "2026-02-04-amazon-3629.md").exists()

    def test_force_overwrite(self, tmp_path, test_db):
        """Test force=True overwrites existing tracker files."""
        trackers_dir = tmp_path / "trackers"
        
        # First run
        result1 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        assert result1["created_count"] == 3
        
        # Modify one tracker file to verify overwrite
        first_tracker = Path(result1["results"][0]["tracker_path"])
        first_tracker.write_text("MODIFIED CONTENT")
        
        # Second run with force=True
        result2 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": True,
            "dry_run": False
        })
        
        assert result2["created_count"] == 3  # All overwritten
        assert result2["skipped_count"] == 0
        assert result2["failed_count"] == 0
        
        # Verify file was overwritten (not modified content anymore)
        restored_content = first_tracker.read_text()
        assert restored_content != "MODIFIED CONTENT"
        assert "## Job Description" in restored_content

    def test_dry_run_mode(self, tmp_path, test_db):
        """Test dry_run=True computes outcomes without writing files."""
        trackers_dir = tmp_path / "trackers"
        
        # Run in dry-run mode
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": True
        })
        
        # Verify response structure and counts
        assert result["created_count"] == 3
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0
        
        # Verify results list
        assert len(result["results"]) == 3
        for item in result["results"]:
            assert item["action"] == "created"
            assert item["success"] is True
            
            # Verify files were NOT created
            tracker_path = Path(item["tracker_path"])
            assert not tracker_path.exists()

    def test_workspace_directories_created(self, tmp_path, test_db, monkeypatch):
        """Test that workspace directories are created for each job."""
        # Change to tmp_path so relative paths work correctly
        monkeypatch.chdir(tmp_path)
        
        trackers_dir = tmp_path / "trackers"
        
        # Call the tool
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        assert result["created_count"] == 3
        
        # Verify workspace directories exist (relative to tmp_path since we changed cwd)
        applications_dir = tmp_path / "data" / "applications"
        
        # Check for each job's workspace
        expected_slugs = ["meta-3630", "amazon-3629", "google-3631"]
        for slug in expected_slugs:
            workspace_root = applications_dir / slug
            assert workspace_root.exists()
            assert (workspace_root / "resume").exists()
            assert (workspace_root / "resume").is_dir()
            assert (workspace_root / "cover").exists()
            assert (workspace_root / "cover").is_dir()

    def test_limit_parameter(self, tmp_path, test_db):
        """Test limit parameter restricts number of jobs processed."""
        trackers_dir = tmp_path / "trackers"
        
        # Process only 2 jobs
        result = initialize_shortlist_trackers({
            "limit": 2,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify only 2 jobs were processed
        assert result["created_count"] == 2
        assert len(result["results"]) == 2

    def test_empty_shortlist(self, tmp_path):
        """Test behavior when no shortlist jobs are available."""
        # Create empty database
        db_path = tmp_path / "empty_jobs.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                job_id TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                description TEXT,
                url TEXT NOT NULL,
                location TEXT,
                source TEXT,
                status TEXT NOT NULL,
                captured_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        
        trackers_dir = tmp_path / "trackers"
        
        # Call the tool
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": str(db_path),
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify success with zero counts
        assert result["created_count"] == 0
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 0
        assert result["results"] == []

    def test_validation_error_invalid_limit(self):
        """Test validation error for invalid limit.
        
        Validates Requirement 8.1: When request-level validation fails,
        the tool SHALL return top-level VALIDATION_ERROR.
        """
        result = initialize_shortlist_trackers({
            "limit": 300,  # Exceeds maximum of 200
        })
        
        # Verify error response
        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "limit" in result["error"]["message"].lower()
        assert result["error"]["retryable"] is False
        assert "message" in result["error"]
        
        # Verify no results field in error response
        assert "results" not in result
        assert "created_count" not in result

    def test_db_not_found_error(self, tmp_path):
        """Test DB_NOT_FOUND error for missing database.
        
        Validates Requirement 8.2: When database file is missing, the tool
        SHALL return DB_NOT_FOUND.
        """
        result = initialize_shortlist_trackers({
            "db_path": str(tmp_path / "nonexistent.db"),
        })
        
        # Verify error response
        assert "error" in result
        assert result["error"]["code"] == "DB_NOT_FOUND"
        assert result["error"]["retryable"] is False
        assert "message" in result["error"]
        
        # Verify no results field in error response
        assert "results" not in result
        assert "created_count" not in result

    def test_db_error_corrupted_database(self, tmp_path):
        """Test DB_ERROR for corrupted database file.
        
        Validates Requirement 8.3: When database query or connection fails,
        the tool SHALL return DB_ERROR.
        Validates Requirement 8.5: Top-level error object SHALL include retryable boolean.
        Validates Requirement 8.6: Error messages SHALL be sanitized.
        """
        # Create a corrupted database file (not a valid SQLite database)
        db_path = tmp_path / "corrupted.db"
        db_path.write_text("This is not a valid SQLite database file")
        
        result = initialize_shortlist_trackers({
            "db_path": str(db_path),
        })
        
        # Verify error response
        assert "error" in result
        assert result["error"]["code"] == "DB_ERROR"
        assert "message" in result["error"]
        assert "retryable" in result["error"]
        
        # Verify no results field in error response
        assert "results" not in result
        assert "created_count" not in result
        
        # Verify message is sanitized (no SQL fragments)
        assert "SELECT" not in result["error"]["message"]
        assert "FROM" not in result["error"]["message"]

    def test_db_error_missing_table(self, tmp_path):
        """Test DB_ERROR when database is missing required table.
        
        Validates Requirement 8.3: When database query fails, the tool
        SHALL return DB_ERROR.
        Validates Requirement 8.6: Error messages SHALL be sanitized (no SQL fragments).
        """
        # Create a valid SQLite database but without the jobs table
        db_path = tmp_path / "no_table.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()
        
        result = initialize_shortlist_trackers({
            "db_path": str(db_path),
        })
        
        # Verify error response
        assert "error" in result
        assert result["error"]["code"] == "DB_ERROR"
        assert "message" in result["error"]
        assert "retryable" in result["error"]
        
        # Verify no results field in error response
        assert "results" not in result
        assert "created_count" not in result
        
        # Verify message is sanitized (no SQL fragments, no table names in SQL context)
        message = result["error"]["message"]
        # Should not contain raw SQL statements
        assert not any(keyword in message for keyword in ["SELECT id", "FROM jobs", "WHERE status"])

    def test_internal_error_unexpected_exception(self, tmp_path, test_db, monkeypatch):
        """Test INTERNAL_ERROR for unexpected runtime exceptions.
        
        Validates Requirement 8.4: When unexpected runtime exceptions occur,
        the tool SHALL return INTERNAL_ERROR.
        Validates Requirement 8.5: Top-level error object SHALL include retryable boolean.
        Validates Requirement 8.6: Error messages SHALL be sanitized (no stack traces).
        """
        # Mock a function to raise an unexpected exception
        def mock_validate_params(*args, **kwargs):
            raise RuntimeError("Unexpected internal error during validation")
        
        monkeypatch.setattr(
            "tools.initialize_shortlist_trackers.validate_initialize_shortlist_trackers_parameters",
            mock_validate_params
        )
        
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
        })
        
        # Verify error response
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert "message" in result["error"]
        assert result["error"]["retryable"] is True  # Internal errors are retryable
        
        # Verify no results field in error response
        assert "results" not in result
        assert "created_count" not in result
        
        # Verify message is sanitized (no stack traces)
        message = result["error"]["message"]
        # Should not contain stack trace indicators
        assert "Traceback" not in message
        assert "File \"" not in message
        assert "line " not in message.lower() or "line" not in message.split()[0].lower()

    def test_error_message_sanitization_no_absolute_paths(self, tmp_path):
        """Test that error messages don't expose absolute paths.
        
        Validates Requirement 8.6: Error messages SHALL be sanitized
        (no sensitive absolute paths).
        """
        # Use a deeply nested path to ensure absolute path would be long
        nested_path = tmp_path / "very" / "deeply" / "nested" / "path" / "nonexistent.db"
        
        result = initialize_shortlist_trackers({
            "db_path": str(nested_path),
        })
        
        # Verify error response
        assert "error" in result
        assert result["error"]["code"] == "DB_NOT_FOUND"
        
        # Verify message doesn't contain the full absolute path
        message = result["error"]["message"]
        # Should only contain basename, not full path
        assert "nonexistent.db" in message
        # Should not contain parent directories from absolute path
        assert str(tmp_path) not in message
        assert "very/deeply/nested" not in message

    def test_deterministic_ordering(self, tmp_path, test_db):
        """Test that results are in deterministic order (captured_at DESC, id DESC)."""
        trackers_dir = tmp_path / "trackers"
        
        # Call the tool
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify ordering: most recent first, then by ID descending
        assert len(result["results"]) == 3
        assert result["results"][0]["id"] == 3631  # 2026-02-05T10:00:00
        assert result["results"][1]["id"] == 3630  # 2026-02-04T16:00:00
        assert result["results"][2]["id"] == 3629  # 2026-02-04T15:30:00

    def test_per_item_failure_continues_batch(self, tmp_path, test_db, monkeypatch):
        """Test that per-item failures don't stop batch processing.
        
        Validates Requirement 5.2: When one item fails, the tool SHALL continue
        processing other items in the batch.
        Validates Requirement 7.2: Failed items include error field.
        """
        trackers_dir = tmp_path / "trackers"
        
        # Create a scenario where one item will fail
        # We'll make the tracker directory read-only after creating it
        trackers_dir.mkdir(parents=True)
        
        # Mock atomic_write to fail for a specific job ID
        from utils import file_ops
        original_atomic_write = file_ops.atomic_write
        
        def mock_atomic_write(path, content):
            # Fail for job ID 3630 (Meta)
            if "meta-3630" in str(path):
                raise IOError("Simulated write failure for testing")
            return original_atomic_write(path, content)
        
        # Patch at the module where it's used
        monkeypatch.setattr("tools.initialize_shortlist_trackers.atomic_write", mock_atomic_write)
        
        # Call the tool
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify response structure
        assert "created_count" in result
        assert "skipped_count" in result
        assert "failed_count" in result
        assert "results" in result
        
        # Verify counts: 2 created, 1 failed
        assert result["created_count"] == 2
        assert result["skipped_count"] == 0
        assert result["failed_count"] == 1
        
        # Verify results list has all 3 items
        assert len(result["results"]) == 3
        
        # Find the failed item (Meta job)
        failed_items = [r for r in result["results"] if not r["success"]]
        assert len(failed_items) == 1
        assert failed_items[0]["id"] == 3630
        assert failed_items[0]["action"] == "failed"
        assert "error" in failed_items[0]
        assert "write failure" in failed_items[0]["error"].lower()
        
        # Verify successful items
        successful_items = [r for r in result["results"] if r["success"]]
        assert len(successful_items) == 2
        for item in successful_items:
            assert item["action"] == "created"
            assert "tracker_path" in item
            # Verify the files were actually created
            assert Path(item["tracker_path"]).exists()

    def test_hard_failure_does_not_reuse_previous_tracker_path(self, tmp_path, test_db, monkeypatch):
        """Test hard failure result does not leak tracker_path from previous item."""
        trackers_dir = tmp_path / "trackers"

        import tools.initialize_shortlist_trackers as tool_module

        original_plan_tracker = tool_module.plan_tracker
        call_count = {"n": 0}

        def flaky_plan_tracker(job, trackers_dir_arg):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("Simulated planner hard failure")
            return original_plan_tracker(job, trackers_dir_arg)

        monkeypatch.setattr(tool_module, "plan_tracker", flaky_plan_tracker)

        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })

        assert result["failed_count"] == 1
        failed_items = [r for r in result["results"] if not r["success"]]
        assert len(failed_items) == 1
        failed_item = failed_items[0]
        assert failed_item["action"] == "failed"
        # Hard failure happened before planning output existed for this item.
        assert "tracker_path" not in failed_item

    def test_all_items_skipped_returns_success(self, tmp_path, test_db):
        """Test that all items skipped still returns success.
        
        Validates Requirement 7.4: When all items are skipped, the tool SHALL
        still return success with correct counts.
        """
        trackers_dir = tmp_path / "trackers"
        
        # First run to create all trackers
        result1 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        assert result1["created_count"] == 3
        
        # Second run - all should be skipped
        result2 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify success response (no error field)
        assert "error" not in result2
        assert result2["created_count"] == 0
        assert result2["skipped_count"] == 3
        assert result2["failed_count"] == 0
        assert len(result2["results"]) == 3
        
        # All items should have success=True
        for item in result2["results"]:
            assert item["success"] is True
            assert item["action"] == "skipped_exists"

    def test_result_fields_structure(self, tmp_path, test_db):
        """Test that result items have all required fields.
        
        Validates Requirement 7.2: Each results item SHALL include:
        - id
        - tracker_path (optional on hard failure)
        - action
        - success
        - error (optional)
        """
        trackers_dir = tmp_path / "trackers"
        
        # Call the tool
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify each result has required fields
        for item in result["results"]:
            # Required fields
            assert "id" in item
            assert "action" in item
            assert "success" in item
            
            # tracker_path should be present for successful operations
            if item["success"]:
                assert "tracker_path" in item
                assert item["tracker_path"]  # Not empty
            
            # error field should only be present on failures
            if not item["success"]:
                assert "error" in item
            else:
                # Success items should not have error field
                assert "error" not in item

    def test_dry_run_with_existing_files(self, tmp_path, test_db):
        """Test dry_run mode correctly identifies existing files without writing.
        
        Validates Requirement 9.4: Dry-run mode computes outcomes without writing files.
        Validates that dry-run respects file existence checks.
        """
        trackers_dir = tmp_path / "trackers"
        
        # First run: create actual tracker files
        result1 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        assert result1["created_count"] == 3
        
        # Verify files exist
        for item in result1["results"]:
            assert Path(item["tracker_path"]).exists()
        
        # Second run: dry-run should detect existing files
        result2 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": True
        })
        
        # Verify response shows files would be skipped
        assert result2["created_count"] == 0
        assert result2["skipped_count"] == 3
        assert result2["failed_count"] == 0
        
        # All items should have skipped_exists action
        for item in result2["results"]:
            assert item["action"] == "skipped_exists"
            assert item["success"] is True

    def test_dry_run_with_force(self, tmp_path, test_db):
        """Test dry_run mode with force=True shows overwrite actions.
        
        Validates Requirement 9.4: Dry-run mode computes outcomes without writing.
        Validates that dry-run correctly computes overwrite actions.
        """
        trackers_dir = tmp_path / "trackers"
        
        # First run: create actual tracker files
        result1 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        assert result1["created_count"] == 3
        
        # Modify one file to verify it's not actually overwritten in dry-run
        first_tracker = Path(result1["results"][0]["tracker_path"])
        first_tracker.write_text("MODIFIED CONTENT", encoding="utf-8")
        
        # Dry-run with force=True should show overwrite actions
        result2 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": True,
            "dry_run": True
        })
        
        # Verify response shows files would be overwritten
        assert result2["created_count"] == 3  # overwritten counts as created
        assert result2["skipped_count"] == 0
        assert result2["failed_count"] == 0
        
        # All items should have overwritten action
        for item in result2["results"]:
            assert item["action"] == "overwritten"
            assert item["success"] is True
        
        # Verify files were NOT actually modified
        modified_content = first_tracker.read_text(encoding="utf-8")
        assert modified_content == "MODIFIED CONTENT"

    def test_dry_run_no_workspace_directories_created(self, tmp_path, test_db, monkeypatch):
        """Test dry_run mode does not create workspace directories.
        
        Validates Requirement 9.4: Dry-run mode computes outcomes without creating directories.
        """
        # Change to tmp_path so relative paths work correctly
        monkeypatch.chdir(tmp_path)
        
        trackers_dir = tmp_path / "trackers"
        
        # Run in dry-run mode
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": True
        })
        
        assert result["created_count"] == 3
        
        # Verify workspace directories were NOT created
        applications_dir = tmp_path / "data" / "applications"
        
        # Applications directory should not exist at all
        assert not applications_dir.exists()

    def test_dry_run_deterministic_output(self, tmp_path, test_db):
        """Test dry_run mode produces deterministic output for identical inputs.
        
        Validates Requirement 9.5: Tool returns deterministic output ordering
        for identical DB state and inputs.
        """
        trackers_dir = tmp_path / "trackers"
        
        # Run dry-run multiple times with same parameters
        result1 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": True
        })
        
        result2 = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": True
        })
        
        # Verify identical counts
        assert result1["created_count"] == result2["created_count"]
        assert result1["skipped_count"] == result2["skipped_count"]
        assert result1["failed_count"] == result2["failed_count"]
        
        # Verify identical results list
        assert len(result1["results"]) == len(result2["results"])
        
        for item1, item2 in zip(result1["results"], result2["results"]):
            assert item1["id"] == item2["id"]
            assert item1["job_id"] == item2["job_id"]
            assert item1["tracker_path"] == item2["tracker_path"]
            assert item1["action"] == item2["action"]
            assert item1["success"] == item2["success"]

    def test_dry_run_response_shape_matches_normal(self, tmp_path, test_db):
        """Test dry_run response shape matches non-dry-run response.
        
        Validates Requirement 9.4: Dry-run response shape/counts match
        non-dry-run semantics.
        """
        trackers_dir = tmp_path / "trackers"
        
        # Run in dry-run mode
        dry_result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": True
        })
        
        # Run in normal mode
        normal_result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify response structure is identical
        assert set(dry_result.keys()) == set(normal_result.keys())
        assert set(dry_result.keys()) == {"created_count", "skipped_count", "failed_count", "results"}
        
        # Verify counts match (both should show 3 created)
        assert dry_result["created_count"] == normal_result["created_count"]
        assert dry_result["skipped_count"] == normal_result["skipped_count"]
        assert dry_result["failed_count"] == normal_result["failed_count"]
        
        # Verify results list structure
        assert len(dry_result["results"]) == len(normal_result["results"])
        
        for dry_item, normal_item in zip(dry_result["results"], normal_result["results"]):
            # Same fields present
            assert set(dry_item.keys()) == set(normal_item.keys())
            # Same values (except files don't exist in dry-run)
            assert dry_item["id"] == normal_item["id"]
            assert dry_item["job_id"] == normal_item["job_id"]
            assert dry_item["tracker_path"] == normal_item["tracker_path"]
            assert dry_item["action"] == normal_item["action"]
            assert dry_item["success"] == normal_item["success"]

    def test_database_read_only_boundary(self, tmp_path, test_db):
        """Test that database remains unchanged after tool execution.
        
        Validates Requirement 6.1: THE MCP_Tool SHALL NOT update any database row fields.
        Validates Requirement 6.2: THE MCP_Tool SHALL NOT change status in database records.
        Validates Requirement 6.4: THE MCP_Tool SHALL NOT insert or delete database rows.
        
        This test snapshots the database before and after tool execution and verifies
        that no rows were modified, inserted, or deleted.
        """
        trackers_dir = tmp_path / "trackers"
        
        # Snapshot database state before tool execution
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        
        # Get all rows with all fields
        cursor.execute("""
            SELECT id, job_id, title, company, description, url, 
                   location, source, status, captured_at
            FROM jobs
            ORDER BY id
        """)
        before_rows = cursor.fetchall()
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM jobs")
        before_count = cursor.fetchone()[0]
        
        conn.close()
        
        # Execute the tool
        result = initialize_shortlist_trackers({
            "limit": 10,
            "db_path": test_db,
            "trackers_dir": str(trackers_dir),
            "force": False,
            "dry_run": False
        })
        
        # Verify tool executed successfully
        assert result["created_count"] == 3
        assert result["failed_count"] == 0
        
        # Snapshot database state after tool execution
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        
        # Get all rows with all fields
        cursor.execute("""
            SELECT id, job_id, title, company, description, url, 
                   location, source, status, captured_at
            FROM jobs
            ORDER BY id
        """)
        after_rows = cursor.fetchall()
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM jobs")
        after_count = cursor.fetchone()[0]
        
        conn.close()
        
        # Verify no rows were inserted or deleted
        assert before_count == after_count, \
            f"Row count changed: before={before_count}, after={after_count}"
        
        # Verify all rows are identical (no field changes)
        assert len(before_rows) == len(after_rows), \
            "Number of rows changed"
        
        for i, (before_row, after_row) in enumerate(zip(before_rows, after_rows)):
            assert before_row == after_row, \
                f"Row {i} (id={before_row[0]}) was modified:\n" \
                f"  Before: {before_row}\n" \
                f"  After:  {after_row}"
        
        # Specifically verify status field unchanged for shortlist jobs
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM jobs WHERE id IN (3629, 3630, 3631)")
        status_rows = cursor.fetchall()
        conn.close()
        
        for job_id, status in status_rows:
            assert status == "shortlist", \
                f"Job {job_id} status changed from 'shortlist' to '{status}'"
