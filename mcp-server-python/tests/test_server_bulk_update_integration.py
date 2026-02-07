"""
Integration tests for bulk_update_job_status MCP server integration.

Tests that the server.py file correctly registers the bulk_update_job_status tool
with proper metadata and that the tool can be invoked through the MCP interface.
"""

import sqlite3
import os
import tempfile

import pytest

from server import mcp, bulk_update_job_status_tool


class TestBulkUpdateServerIntegration:
    """Integration tests for the bulk_update_job_status MCP server tool."""

    @pytest.fixture
    def temp_db(self):
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
        except Exception:
            pass

    def test_server_has_correct_name(self):
        """Test that the MCP server has the correct name."""
        assert mcp.name == "jobworkflow-mcp-server"

    def test_server_has_instructions(self):
        """Test that the MCP server has instructions."""
        assert mcp.instructions is not None
        assert "bulk_update_job_status" in mcp.instructions
        assert "JobWorkFlow" in mcp.instructions

    def test_tool_is_registered(self):
        """Test that the bulk_update_job_status tool is registered with the server."""
        # The tool should be registered in the tool manager
        assert "bulk_update_job_status" in mcp._tool_manager._tools

    def test_tool_has_correct_metadata(self):
        """Test that the tool has correct metadata."""
        tool = mcp._tool_manager._tools["bulk_update_job_status"]

        # Check tool name
        assert tool.name == "bulk_update_job_status"

        # Check tool has description
        assert tool.description is not None
        assert "atomic" in tool.description.lower()
        assert "batch" in tool.description.lower() or "multiple" in tool.description.lower()

    def test_tool_function_can_be_called_directly(self, temp_db):
        """Test that the tool function can be called directly."""
        # Call the tool function directly
        result = bulk_update_job_status_tool(
            updates=[{"id": 1, "status": "shortlist"}], db_path=temp_db
        )

        # Should succeed
        assert "error" not in result
        assert result["updated_count"] == 1
        assert result["failed_count"] == 0
        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is True

    def test_tool_function_with_multiple_updates(self, temp_db):
        """Test that the tool function handles multiple updates."""
        result = bulk_update_job_status_tool(
            updates=[
                {"id": 1, "status": "shortlist"},
                {"id": 2, "status": "reviewed"},
                {"id": 3, "status": "reject"},
            ],
            db_path=temp_db,
        )

        # Should succeed
        assert "error" not in result
        assert result["updated_count"] == 3
        assert result["failed_count"] == 0
        assert len(result["results"]) == 3

    def test_tool_function_with_empty_batch(self, temp_db):
        """Test that the tool function handles empty batch."""
        result = bulk_update_job_status_tool(updates=[], db_path=temp_db)

        # Should succeed with zero counts
        assert "error" not in result
        assert result["updated_count"] == 0
        assert result["failed_count"] == 0
        assert result["results"] == []

    def test_tool_function_handles_validation_errors(self, temp_db):
        """Test that the tool function returns structured validation errors."""
        # Call with invalid status
        result = bulk_update_job_status_tool(
            updates=[{"id": 1, "status": "invalid_status"}], db_path=temp_db
        )

        # Should return per-item failure
        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "error" in result["results"][0]

    def test_tool_function_handles_nonexistent_job(self, temp_db):
        """Test that the tool function handles nonexistent job IDs."""
        result = bulk_update_job_status_tool(
            updates=[{"id": 999, "status": "shortlist"}], db_path=temp_db
        )

        # Should return per-item failure
        assert result["updated_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "does not exist" in result["results"][0]["error"]

    def test_tool_function_handles_database_errors(self):
        """Test that the tool function returns structured database errors."""
        # Call with non-existent database
        result = bulk_update_job_status_tool(
            updates=[{"id": 1, "status": "shortlist"}], db_path="/nonexistent/path/to/db.db"
        )

        # Should return error structure
        assert "error" in result
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert "retryable" in result["error"]

    def test_tool_function_atomicity(self, temp_db):
        """Test that the tool function enforces atomicity."""
        # Get initial status
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
        initial_status = cursor.fetchone()[0]
        conn.close()

        # Attempt batch with one invalid update
        result = bulk_update_job_status_tool(
            updates=[
                {"id": 1, "status": "shortlist"},  # Valid
                {"id": 999, "status": "reviewed"},  # Invalid (doesn't exist)
            ],
            db_path=temp_db,
        )

        # Should fail entire batch
        assert result["updated_count"] == 0

        # Verify job 1 was NOT updated (rollback occurred)
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT status FROM jobs WHERE id = 1")
        current_status = cursor.fetchone()[0]
        conn.close()

        assert current_status == initial_status

    def test_tool_function_idempotency(self, temp_db):
        """Test that the tool function supports idempotent updates."""
        # Update job to its current status
        result = bulk_update_job_status_tool(
            updates=[{"id": 1, "status": "new"}],  # Job 1 already has status 'new'
            db_path=temp_db,
        )

        # Should succeed
        assert result["updated_count"] == 1
        assert result["failed_count"] == 0
        assert result["results"][0]["success"] is True

    def test_tool_function_timestamp_consistency(self, temp_db):
        """Test that all jobs in a batch get the same timestamp."""
        result = bulk_update_job_status_tool(
            updates=[
                {"id": 1, "status": "shortlist"},
                {"id": 2, "status": "reviewed"},
                {"id": 3, "status": "reject"},
            ],
            db_path=temp_db,
        )

        assert result["updated_count"] == 3

        # Verify all have the same timestamp
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT DISTINCT updated_at FROM jobs WHERE id IN (1, 2, 3)")
        rows = cursor.fetchall()
        conn.close()

        # Should only be one distinct timestamp
        assert len(rows) == 1

    def test_tool_function_write_only_guarantee(self, temp_db):
        """Test that the tool function doesn't return job data."""
        result = bulk_update_job_status_tool(
            updates=[{"id": 1, "status": "shortlist"}], db_path=temp_db
        )

        # Should not contain job details (title, company, description, etc.)
        assert "jobs" not in result

        # Should only contain success/failure indicators
        assert "updated_count" in result
        assert "failed_count" in result
        assert "results" in result

        # Results should only have id, success, and optional error
        for item in result["results"]:
            assert "id" in item
            assert "success" in item
            # Should not have job details
            assert "title" not in item
            assert "company" not in item
            assert "description" not in item
            assert "url" not in item

    def test_tool_docstring_includes_requirements(self):
        """Test that the tool function has comprehensive documentation."""
        # Check that the docstring exists and includes key information
        docstring = bulk_update_job_status_tool.__doc__

        assert docstring is not None
        assert "Args:" in docstring
        assert "Returns:" in docstring
        assert "Examples:" in docstring
        assert "Requirements:" in docstring

        # Check that key parameters are documented
        assert "updates" in docstring
        assert "db_path" in docstring

        # Check that return structure is documented
        assert "updated_count" in docstring
        assert "failed_count" in docstring
        assert "results" in docstring

    def test_tool_function_signature_matches_spec(self):
        """Test that the tool function signature matches the specification."""
        import inspect

        sig = inspect.signature(bulk_update_job_status_tool)
        params = sig.parameters

        # Check parameter names
        assert "updates" in params
        assert "db_path" in params

        # Check parameter defaults
        assert params["db_path"].default is None

        # Check return type annotation
        assert sig.return_annotation is dict

    def test_server_can_be_imported(self):
        """Test that the server module can be imported without errors."""
        # This test verifies that all imports in server.py are valid
        # and that the module initializes correctly
        from server import mcp, bulk_update_job_status_tool, main

        assert mcp is not None
        assert bulk_update_job_status_tool is not None
        assert main is not None
        assert callable(main)
