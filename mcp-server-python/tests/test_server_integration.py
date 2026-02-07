"""
Integration tests for MCP server entry point.

Tests that the server.py file correctly registers the bulk_read_new_jobs tool
with proper metadata and that the tool can be invoked through the MCP interface.
"""

import sqlite3
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch


from server import (
    mcp,
    bulk_read_new_jobs_tool,
    initialize_shortlist_trackers_tool,
    update_tracker_status_tool,
    finalize_resume_batch_tool,
    career_tailor_tool,
    scrape_jobs_tool,
)


class TestServerIntegration:
    """Integration tests for the MCP server."""

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

    def test_server_has_correct_name(self):
        """Test that the MCP server has the correct name."""
        assert mcp.name == "jobworkflow-mcp-server"

    def test_server_name_can_be_overridden_by_env(self):
        """Test that JOBWORKFLOW_SERVER_NAME is applied in a fresh process."""
        server_dir = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["JOBWORKFLOW_SERVER_NAME"] = "custom-server-name"
        env["PYTHONPATH"] = str(server_dir)

        proc = subprocess.run(
            [sys.executable, "-c", "import server; print(server.mcp.name)"],
            cwd=server_dir,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        assert proc.stdout.strip() == "custom-server-name"

    def test_server_has_instructions(self):
        """Test that the MCP server has instructions."""
        assert mcp.instructions is not None
        assert "bulk_read_new_jobs" in mcp.instructions
        assert "scrape_jobs" in mcp.instructions
        assert "JobWorkFlow" in mcp.instructions

    def test_tool_is_registered(self):
        """Test that the bulk_read_new_jobs tool is registered with the server."""
        # The tool should be registered in the tool manager
        assert "bulk_read_new_jobs" in mcp._tool_manager._tools

    def test_tool_has_correct_metadata(self):
        """Test that the tool has correct metadata."""
        tool = mcp._tool_manager._tools["bulk_read_new_jobs"]

        # Check tool name
        assert tool.name == "bulk_read_new_jobs"

        # Check tool has description
        assert tool.description is not None
        assert "status='new'" in tool.description
        assert "pagination" in tool.description.lower()

    def test_tool_function_can_be_called_directly(self, tmp_path):
        """Test that the tool function can be called directly."""
        # Create test database
        db_path = tmp_path / "test.db"
        jobs = [
            {"url": "http://example.com/1", "title": "Job 1"},
            {"url": "http://example.com/2", "title": "Job 2"},
        ]
        self.create_test_db(db_path, jobs)

        # Call the tool function directly
        result = bulk_read_new_jobs_tool(db_path=str(db_path))

        # Should succeed
        assert "error" not in result
        assert "jobs" in result
        assert result["count"] == 2
        assert len(result["jobs"]) == 2

    def test_tool_function_with_default_limit(self, tmp_path):
        """Test that the tool function uses default limit correctly."""
        # Create test database
        db_path = tmp_path / "test.db"
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(10)]
        self.create_test_db(db_path, jobs)

        # Call without specifying limit (should use default 50)
        result = bulk_read_new_jobs_tool(db_path=str(db_path))

        # Should return all 10 jobs (less than default limit)
        assert result["count"] == 10
        assert result["has_more"] is False

    def test_tool_function_with_custom_limit(self, tmp_path):
        """Test that the tool function respects custom limit."""
        # Create test database
        db_path = tmp_path / "test.db"
        jobs = [{"url": f"http://example.com/{i}", "title": f"Job {i}"} for i in range(10)]
        self.create_test_db(db_path, jobs)

        # Call with custom limit
        result = bulk_read_new_jobs_tool(limit=5, db_path=str(db_path))

        # Should return only 5 jobs
        assert result["count"] == 5
        assert result["has_more"] is True

    def test_tool_function_with_cursor(self, tmp_path):
        """Test that the tool function handles cursor correctly."""
        # Create test database
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
        page1 = bulk_read_new_jobs_tool(limit=5, db_path=str(db_path))
        assert page1["has_more"] is True

        # Get second page with cursor
        page2 = bulk_read_new_jobs_tool(limit=5, cursor=page1["next_cursor"], db_path=str(db_path))

        # Should get remaining jobs
        assert page2["count"] == 5
        assert page2["has_more"] is False

        # No overlap
        page1_ids = {job["id"] for job in page1["jobs"]}
        page2_ids = {job["id"] for job in page2["jobs"]}
        assert page1_ids.isdisjoint(page2_ids)

    def test_tool_function_handles_errors(self):
        """Test that the tool function returns structured errors."""
        # Call with non-existent database
        result = bulk_read_new_jobs_tool(db_path="/nonexistent/path.db")

        # Should return error structure
        assert "error" in result
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert "retryable" in result["error"]

    def test_tool_function_parameter_defaults(self, tmp_path):
        """Test that tool function parameters have correct defaults."""
        # Create test database
        db_path = tmp_path / "test.db"
        jobs = [{"url": "http://example.com/1", "title": "Job 1"}]
        self.create_test_db(db_path, jobs)

        # Call with only db_path (all other params should use defaults)
        result = bulk_read_new_jobs_tool(db_path=str(db_path))

        # Should succeed with defaults
        assert "error" not in result
        assert result["count"] == 1

    def test_tool_function_none_parameters(self, tmp_path):
        """Test that tool function handles None parameters correctly."""
        # Create test database
        db_path = tmp_path / "test.db"
        jobs = [{"url": "http://example.com/1", "title": "Job 1"}]
        self.create_test_db(db_path, jobs)

        # Call with explicit None for optional parameters
        result = bulk_read_new_jobs_tool(limit=50, cursor=None, db_path=str(db_path))

        # Should succeed
        assert "error" not in result
        assert result["count"] == 1

    def test_server_can_be_imported(self):
        """Test that the server module can be imported without errors."""
        # This test verifies that all imports in server.py are valid
        # and that the module initializes correctly
        from server import mcp, bulk_read_new_jobs_tool, main

        assert mcp is not None
        assert bulk_read_new_jobs_tool is not None
        assert main is not None
        assert callable(main)

    def test_tool_docstring_includes_requirements(self):
        """Test that the tool function has comprehensive documentation."""
        # Check that the docstring exists and includes key information
        docstring = bulk_read_new_jobs_tool.__doc__

        assert docstring is not None
        assert "Args:" in docstring
        assert "Returns:" in docstring
        assert "Examples:" in docstring
        assert "Requirements:" in docstring

        # Check that key parameters are documented
        assert "limit" in docstring
        assert "cursor" in docstring
        assert "db_path" in docstring

        # Check that return structure is documented
        assert "jobs" in docstring
        assert "count" in docstring
        assert "has_more" in docstring
        assert "next_cursor" in docstring

    def test_tool_function_signature_matches_spec(self):
        """Test that the tool function signature matches the specification."""
        import inspect

        sig = inspect.signature(bulk_read_new_jobs_tool)
        params = sig.parameters

        # Check parameter names
        assert "limit" in params
        assert "cursor" in params
        assert "db_path" in params

        # Check parameter defaults
        assert params["limit"].default == 50
        assert params["cursor"].default is None
        assert params["db_path"].default is None

        # Check return type annotation
        assert sig.return_annotation is dict

    def test_initialize_shortlist_trackers_tool_is_registered(self):
        """Test that initialize_shortlist_trackers is registered and callable."""
        assert "initialize_shortlist_trackers" in mcp._tool_manager._tools

        tool = mcp._tool_manager._tools["initialize_shortlist_trackers"]
        assert tool.name == "initialize_shortlist_trackers"
        assert "shortlist" in tool.description.lower()

    def test_update_tracker_status_tool_is_registered(self):
        """Test that update_tracker_status is registered and callable."""
        assert "update_tracker_status" in mcp._tool_manager._tools

        tool = mcp._tool_manager._tools["update_tracker_status"]
        assert tool.name == "update_tracker_status"
        assert "guardrail" in tool.description.lower()

    def test_finalize_resume_batch_tool_is_registered(self):
        """Test that finalize_resume_batch is registered and callable."""
        assert "finalize_resume_batch" in mcp._tool_manager._tools

        tool = mcp._tool_manager._tools["finalize_resume_batch"]
        assert tool.name == "finalize_resume_batch"
        assert "finalize" in tool.description.lower()

    def test_career_tailor_tool_is_registered(self):
        """Test that career_tailor is registered and callable."""
        assert "career_tailor" in mcp._tool_manager._tools

        tool = mcp._tool_manager._tools["career_tailor"]
        assert tool.name == "career_tailor"
        assert "tailor" in tool.description.lower()
        assert "batch" in tool.description.lower()

    def test_initialize_shortlist_trackers_tool_via_server_wrapper(self, tmp_path):
        """Test initialize_shortlist_trackers wrapper through server entrypoint."""
        db_path = tmp_path / "shortlist.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
            INSERT INTO jobs (id, job_id, title, company, description, url, location, source, status, captured_at)
            VALUES (1, 'job-1', 'Engineer', 'Acme', 'desc', 'https://example.com/1', 'NY', 'test', 'shortlist', '2026-02-05T10:00:00')
            """
        )
        conn.commit()
        conn.close()

        trackers_dir = tmp_path / "trackers"
        result = initialize_shortlist_trackers_tool(
            limit=10,
            db_path=str(db_path),
            trackers_dir=str(trackers_dir),
            force=False,
            dry_run=True,
        )

        assert "error" not in result
        assert result["created_count"] == 1
        assert result["failed_count"] == 0
        assert len(result["results"]) == 1

    def test_update_tracker_status_tool_via_server_wrapper(self, tmp_path):
        """Test update_tracker_status wrapper through server entrypoint."""
        resume_dir = tmp_path / "data" / "applications" / "app" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = resume_dir / "resume.pdf"
        tex_path = resume_dir / "resume.tex"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        tex_path.write_text("real content")

        tracker_path = tmp_path / "tracker.md"
        tracker_path.write_text(
            f"""---
status: Reviewed
resume_path: "{str(pdf_path)}"
---
Body
"""
        )

        result = update_tracker_status_tool(
            tracker_path=str(tracker_path),
            target_status="Resume Written",
            dry_run=True,
            force=False,
        )

        assert "error" not in result
        assert result["success"] is True
        assert result["action"] == "would_update"
        assert result["guardrail_check_passed"] is True

    def test_finalize_resume_batch_tool_via_server_wrapper(self, tmp_path):
        """Test finalize_resume_batch wrapper through server entrypoint."""
        db_path = tmp_path / "finalize.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO jobs (id, status, updated_at) VALUES (1, 'reviewed', '2026-02-06T10:00:00.000Z')"
        )
        conn.commit()
        conn.close()

        resume_dir = tmp_path / "data" / "applications" / "app" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = resume_dir / "resume.pdf"
        tex_path = resume_dir / "resume.tex"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        tex_path.write_text("real content")

        tracker_path = tmp_path / "tracker.md"
        tracker_path.write_text(
            f"""---
status: Reviewed
resume_path: "{str(pdf_path)}"
---
Body
"""
        )

        result = finalize_resume_batch_tool(
            items=[{"id": 1, "tracker_path": str(tracker_path)}],
            db_path=str(db_path),
            dry_run=True,
        )

        assert "error" not in result
        assert result["finalized_count"] == 1
        assert result["failed_count"] == 0
        assert result["results"][0]["action"] == "would_finalize"

    def test_career_tailor_tool_via_server_wrapper(self):
        """Test career_tailor wrapper through server entrypoint."""
        mocked_response = {
            "run_id": "tailor_20260207_ab12cd34",
            "total_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "results": [
                {
                    "tracker_path": "trackers/test.md",
                    "job_db_id": 1,
                    "application_slug": "acme-1",
                    "workspace_dir": "data/applications/acme-1",
                    "resume_tex_path": "data/applications/acme-1/resume/resume.tex",
                    "ai_context_path": "data/applications/acme-1/resume/ai_context.md",
                    "resume_pdf_path": "data/applications/acme-1/resume/resume.pdf",
                    "resume_tex_action": "created",
                    "success": True,
                }
            ],
            "successful_items": [
                {
                    "id": 1,
                    "tracker_path": "trackers/test.md",
                    "resume_pdf_path": "data/applications/acme-1/resume/resume.pdf",
                }
            ],
        }

        with patch("server.career_tailor", return_value=mocked_response) as mock_tool:
            result = career_tailor_tool(
                items=[{"tracker_path": "trackers/test.md", "job_db_id": 1}],
                force=False,
                full_resume_path="data/templates/full_resume_example.md",
                resume_template_path="data/templates/resume_skeleton_example.tex",
                applications_dir="data/applications",
                pdflatex_cmd="pdflatex",
            )

        assert "error" not in result
        assert result["success_count"] == 1
        assert result["failed_count"] == 0
        mock_tool.assert_called_once()

    def test_scrape_jobs_tool_is_registered(self):
        """Test that scrape_jobs is registered and callable."""
        assert "scrape_jobs" in mcp._tool_manager._tools

        tool = mcp._tool_manager._tools["scrape_jobs"]
        assert tool.name == "scrape_jobs"
        assert "scrape" in tool.description.lower()
        assert "ingest" in tool.description.lower()

    def test_scrape_jobs_tool_has_correct_metadata(self):
        """Test that scrape_jobs tool has correct metadata."""
        tool = mcp._tool_manager._tools["scrape_jobs"]

        # Check tool name
        assert tool.name == "scrape_jobs"

        # Check tool has description
        assert tool.description is not None
        assert "scrape" in tool.description.lower()
        assert "multi-term" in tool.description.lower()

    def test_scrape_jobs_tool_docstring_includes_requirements(self):
        """Test that scrape_jobs tool function has comprehensive documentation."""
        # Check that the docstring exists and includes key information
        docstring = scrape_jobs_tool.__doc__

        assert docstring is not None
        assert "Args:" in docstring
        assert "Returns:" in docstring
        assert "Examples:" in docstring
        assert "Requirements:" in docstring

        # Check that key parameters are documented
        assert "terms" in docstring
        assert "location" in docstring
        assert "sites" in docstring
        assert "results_wanted" in docstring
        assert "hours_old" in docstring
        assert "db_path" in docstring
        assert "dry_run" in docstring

        # Check that return structure is documented
        assert "run_id" in docstring
        assert "started_at" in docstring
        assert "finished_at" in docstring
        assert "duration_ms" in docstring
        assert "results" in docstring
        assert "totals" in docstring

    def test_scrape_jobs_tool_function_signature_matches_spec(self):
        """Test that scrape_jobs tool function signature matches the specification."""
        import inspect

        sig = inspect.signature(scrape_jobs_tool)
        params = sig.parameters

        # Check parameter names match design doc
        assert "terms" in params
        assert "location" in params
        assert "sites" in params
        assert "results_wanted" in params
        assert "hours_old" in params
        assert "db_path" in params
        assert "status" in params
        assert "require_description" in params
        assert "preflight_host" in params
        assert "retry_count" in params
        assert "retry_sleep_seconds" in params
        assert "retry_backoff" in params
        assert "save_capture_json" in params
        assert "capture_dir" in params
        assert "dry_run" in params

        # Check all parameters have None defaults (tool handler applies defaults)
        for param_name, param in params.items():
            assert param.default is None, f"Parameter {param_name} should default to None"

        # Check return type annotation
        assert sig.return_annotation is dict
