"""
Tests for capture_writer module.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 11.5
"""

import json
from pathlib import Path

import pytest

from utils.capture_writer import (
    build_capture_filename,
    slugify,
    write_capture_file,
)


class TestSlugify:
    """Test slugify function."""

    def test_basic_text(self):
        """Test basic text slugification."""
        assert slugify("AI Engineer") == "ai_engineer"
        assert slugify("Backend Engineer") == "backend_engineer"

    def test_special_characters(self):
        """Test handling of special characters."""
        assert slugify("Backend/Full-Stack Developer") == "backend_full_stack_developer"
        assert slugify("C++ Developer") == "c_developer"
        assert slugify("Data Scientist (ML/AI)") == "data_scientist_ml_ai"

    def test_whitespace_handling(self):
        """Test whitespace normalization."""
        assert slugify("  ai   engineer  ") == "ai_engineer"
        assert slugify("backend\tengine\ner") == "backend_engine_er"

    def test_empty_and_edge_cases(self):
        """Test empty and edge case inputs."""
        assert slugify("") == "query"
        assert slugify("   ") == "query"
        assert slugify("!!!") == "query"

    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        assert slugify("Python 3.11 Developer") == "python_3_11_developer"
        assert slugify("Level 2 Engineer") == "level_2_engineer"


class TestBuildCaptureFilename:
    """Test build_capture_filename function."""

    def test_basic_filename(self):
        """Test basic filename generation."""
        filename = build_capture_filename(
            term="ai engineer", location="Ontario, Canada", hours_old=2, sites=["linkedin"]
        )
        assert filename == "jobspy_linkedin_ai_engineer_ontario_canada_2h.json"

    def test_different_hours(self):
        """Test filename with different hours_old values."""
        filename = build_capture_filename(
            term="backend engineer", location="Toronto", hours_old=24, sites=["linkedin"]
        )
        assert filename == "jobspy_linkedin_backend_engineer_toronto_24h.json"

    def test_multiple_sites_uses_first(self):
        """Test that multiple sites uses first site in filename."""
        filename = build_capture_filename(
            term="ml engineer",
            location="Ontario",
            hours_old=2,
            sites=["indeed", "linkedin", "glassdoor"],
        )
        assert filename == "jobspy_indeed_ml_engineer_ontario_2h.json"

    def test_empty_sites_list(self):
        """Test handling of empty sites list."""
        filename = build_capture_filename(
            term="engineer", location="Ontario", hours_old=2, sites=[]
        )
        assert filename == "jobspy_unknown_engineer_ontario_2h.json"

    def test_complex_term_and_location(self):
        """Test filename with complex term and location."""
        filename = build_capture_filename(
            term="Senior Backend/Full-Stack Engineer",
            location="Toronto, Ontario, Canada",
            hours_old=48,
            sites=["linkedin"],
        )
        assert (
            filename
            == "jobspy_linkedin_senior_backend_full_stack_engineer_toronto_ontario_canada_48h.json"
        )

    def test_deterministic_output(self):
        """Test that same inputs produce same filename."""
        filename1 = build_capture_filename("ai engineer", "Ontario", 2, ["linkedin"])
        filename2 = build_capture_filename("ai engineer", "Ontario", 2, ["linkedin"])
        assert filename1 == filename2


class TestWriteCaptureFile:
    """Test write_capture_file function."""

    def test_write_basic_records(self, tmp_path):
        """Test writing basic records to capture file."""
        records = [
            {
                "url": "https://example.com/job1",
                "title": "AI Engineer",
                "company": "TechCorp",
                "description": "Great job",
            },
            {
                "url": "https://example.com/job2",
                "title": "Backend Engineer",
                "company": "StartupCo",
                "description": "Another great job",
            },
        ]

        capture_dir = str(tmp_path / "capture")

        result_path = write_capture_file(
            records=records,
            term="ai engineer",
            location="Ontario, Canada",
            hours_old=2,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        # Verify path is returned
        assert result_path is not None
        assert "jobspy_linkedin_ai_engineer_ontario_canada_2h.json" in result_path

        # Verify file exists
        file_path = Path(capture_dir) / "jobspy_linkedin_ai_engineer_ontario_canada_2h.json"
        assert file_path.exists()

        # Verify content
        content = json.loads(file_path.read_text(encoding="utf-8"))
        assert len(content) == 2
        assert content[0]["url"] == "https://example.com/job1"
        assert content[1]["title"] == "Backend Engineer"

    def test_write_empty_records(self, tmp_path):
        """Test writing empty records list."""
        records = []

        capture_dir = str(tmp_path / "capture")

        write_capture_file(
            records=records,
            term="backend engineer",
            location="Toronto",
            hours_old=24,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        # Verify file exists
        file_path = Path(capture_dir) / "jobspy_linkedin_backend_engineer_toronto_24h.json"
        assert file_path.exists()

        # Verify content is empty array
        content = json.loads(file_path.read_text(encoding="utf-8"))
        assert content == []

    def test_creates_directory_if_missing(self, tmp_path):
        """Test that capture directory is created if it doesn't exist."""
        capture_dir = str(tmp_path / "nested" / "capture" / "dir")

        records = [{"url": "https://example.com/job1", "title": "Engineer"}]

        write_capture_file(
            records=records,
            term="engineer",
            location="Ontario",
            hours_old=2,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        # Verify directory was created
        assert Path(capture_dir).exists()
        assert Path(capture_dir).is_dir()

        # Verify file exists
        file_path = Path(capture_dir) / "jobspy_linkedin_engineer_ontario_2h.json"
        assert file_path.exists()

    def test_overwrites_existing_file(self, tmp_path):
        """Test that existing file is overwritten."""
        capture_dir = str(tmp_path / "capture")
        Path(capture_dir).mkdir(parents=True)

        # Write first version
        records1 = [{"url": "https://example.com/job1", "title": "First"}]
        write_capture_file(
            records=records1,
            term="engineer",
            location="Ontario",
            hours_old=2,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        # Write second version (should overwrite)
        records2 = [{"url": "https://example.com/job2", "title": "Second"}]
        write_capture_file(
            records=records2,
            term="engineer",
            location="Ontario",
            hours_old=2,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        # Verify only second version exists
        file_path = Path(capture_dir) / "jobspy_linkedin_engineer_ontario_2h.json"
        content = json.loads(file_path.read_text(encoding="utf-8"))
        assert len(content) == 1
        assert content[0]["title"] == "Second"

    def test_json_formatting(self, tmp_path):
        """Test that JSON is formatted with indentation."""
        records = [{"url": "https://example.com/job1", "title": "Engineer"}]

        capture_dir = str(tmp_path / "capture")

        write_capture_file(
            records=records,
            term="engineer",
            location="Ontario",
            hours_old=2,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        file_path = Path(capture_dir) / "jobspy_linkedin_engineer_ontario_2h.json"
        content = file_path.read_text(encoding="utf-8")

        # Verify indentation exists (pretty printed)
        assert "\n" in content
        assert "  " in content  # 2-space indentation

    def test_unicode_handling(self, tmp_path):
        """Test that unicode characters are preserved."""
        records = [
            {
                "url": "https://example.com/job1",
                "title": "Développeur Backend",
                "company": "Société Française",
                "description": "Poste à Montréal",
            }
        ]

        capture_dir = str(tmp_path / "capture")

        write_capture_file(
            records=records,
            term="développeur",
            location="Montréal",
            hours_old=2,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        file_path = Path(capture_dir) / "jobspy_linkedin_d_veloppeur_montr_al_2h.json"
        content = json.loads(file_path.read_text(encoding="utf-8"))

        # Verify unicode is preserved
        assert content[0]["title"] == "Développeur Backend"
        assert content[0]["company"] == "Société Française"

    def test_relative_path_handling(self, tmp_path, monkeypatch):
        """Test handling of relative capture directory paths."""
        # Mock repo root to tmp_path
        monkeypatch.setenv("JOBWORKFLOW_ROOT", str(tmp_path))

        records = [{"url": "https://example.com/job1", "title": "Engineer"}]

        # Use relative path
        result_path = write_capture_file(
            records=records,
            term="engineer",
            location="Ontario",
            hours_old=2,
            sites=["linkedin"],
            capture_dir="data/capture",
        )

        # Verify relative path is returned
        assert result_path == "data/capture/jobspy_linkedin_engineer_ontario_2h.json"

        # Verify file exists at expected location
        file_path = tmp_path / "data" / "capture" / "jobspy_linkedin_engineer_ontario_2h.json"
        assert file_path.exists()

    def test_absolute_path_handling(self, tmp_path):
        """Test handling of absolute capture directory paths."""
        capture_dir = str(tmp_path / "absolute" / "capture")

        records = [{"url": "https://example.com/job1", "title": "Engineer"}]

        result_path = write_capture_file(
            records=records,
            term="engineer",
            location="Ontario",
            hours_old=2,
            sites=["linkedin"],
            capture_dir=capture_dir,
        )

        # Verify file exists
        file_path = Path(capture_dir) / "jobspy_linkedin_engineer_ontario_2h.json"
        assert file_path.exists()

        # Path should be returned (may be absolute or relative depending on location)
        assert "jobspy_linkedin_engineer_ontario_2h.json" in result_path


class TestCaptureWriteFailureHandling:
    """
    Test failure handling for capture write operations.

    Requirements: 9.4, 11.5
    """

    def test_write_to_readonly_directory_raises_error(self, tmp_path):
        """
        Test that write failure raises OSError without crashing.

        This verifies that capture write failures can be caught and handled
        by the calling code without crashing the entire run.

        **Validates: Requirements 9.4, 11.5**
        """
        import os
        import stat

        # Create a read-only directory
        capture_dir = tmp_path / "readonly_capture"
        capture_dir.mkdir(parents=True)

        # Make directory read-only (remove write permissions)
        os.chmod(capture_dir, stat.S_IRUSR | stat.S_IXUSR)

        records = [{"url": "https://example.com/job1", "title": "Engineer"}]

        try:
            # Attempt to write should raise OSError
            with pytest.raises(OSError):
                write_capture_file(
                    records=records,
                    term="engineer",
                    location="Ontario",
                    hours_old=2,
                    sites=["linkedin"],
                    capture_dir=str(capture_dir),
                )
        finally:
            # Restore write permissions for cleanup
            os.chmod(capture_dir, stat.S_IRWXU)

    def test_write_with_invalid_json_data_raises_error(self, tmp_path):
        """
        Test that invalid JSON data raises TypeError without crashing.

        This ensures that data validation errors are properly propagated
        and can be handled by the calling code.

        **Validates: Requirements 9.4, 11.5**
        """
        capture_dir = str(tmp_path / "capture")

        # Create records with non-serializable data
        class NonSerializable:
            pass

        records = [{"url": "https://example.com/job1", "data": NonSerializable()}]

        # Attempt to write should raise TypeError from json.dumps
        with pytest.raises(TypeError):
            write_capture_file(
                records=records,
                term="engineer",
                location="Ontario",
                hours_old=2,
                sites=["linkedin"],
                capture_dir=capture_dir,
            )

    def test_error_propagation_allows_graceful_handling(self, tmp_path):
        """
        Test that errors can be caught and handled gracefully by calling code.

        This demonstrates the pattern where capture write failures don't crash
        the whole run - they can be caught, logged, and the run can continue.

        **Validates: Requirements 9.4, 11.5**
        """
        import os
        import stat

        capture_dir = tmp_path / "readonly_capture"
        capture_dir.mkdir(parents=True)
        os.chmod(capture_dir, stat.S_IRUSR | stat.S_IXUSR)

        records = [{"url": "https://example.com/job1", "title": "Engineer"}]

        # Simulate calling code that handles capture write failures gracefully
        capture_path = None
        capture_error = None

        try:
            capture_path = write_capture_file(
                records=records,
                term="engineer",
                location="Ontario",
                hours_old=2,
                sites=["linkedin"],
                capture_dir=str(capture_dir),
            )
        except OSError as e:
            # Capture write failed, but we can continue with the run
            capture_error = str(e)

        # Restore permissions for cleanup
        os.chmod(capture_dir, stat.S_IRWXU)

        # Verify that error was caught and can be handled
        assert capture_path is None
        assert capture_error is not None
        assert "Permission denied" in capture_error or "Read-only" in capture_error

    def test_partial_success_pattern(self, tmp_path):
        """
        Test pattern where some terms succeed and some fail in capture writing.

        This demonstrates how the tool can continue processing other terms
        even if one term's capture write fails.

        **Validates: Requirements 9.4, 11.5**
        """
        import os
        import stat

        # Create two capture directories - one writable, one read-only
        writable_dir = tmp_path / "writable"
        readonly_dir = tmp_path / "readonly"

        writable_dir.mkdir(parents=True)
        readonly_dir.mkdir(parents=True)
        os.chmod(readonly_dir, stat.S_IRUSR | stat.S_IXUSR)

        records = [{"url": "https://example.com/job1", "title": "Engineer"}]

        # Simulate processing multiple terms
        results = []

        # Term 1: Success
        try:
            path = write_capture_file(
                records=records,
                term="backend engineer",
                location="Ontario",
                hours_old=2,
                sites=["linkedin"],
                capture_dir=str(writable_dir),
            )
            results.append({"term": "backend engineer", "success": True, "capture_path": path})
        except OSError as e:
            results.append({"term": "backend engineer", "success": False, "error": str(e)})

        # Term 2: Failure (read-only directory)
        try:
            path = write_capture_file(
                records=records,
                term="ai engineer",
                location="Ontario",
                hours_old=2,
                sites=["linkedin"],
                capture_dir=str(readonly_dir),
            )
            results.append({"term": "ai engineer", "success": True, "capture_path": path})
        except OSError as e:
            results.append({"term": "ai engineer", "success": False, "error": str(e)})

        # Restore permissions for cleanup
        os.chmod(readonly_dir, stat.S_IRWXU)

        # Verify partial success: first term succeeded, second failed
        assert len(results) == 2
        assert results[0]["success"] is True
        assert "jobspy_linkedin_backend_engineer_ontario_2h.json" in results[0]["capture_path"]
        assert results[1]["success"] is False
        assert "error" in results[1]
