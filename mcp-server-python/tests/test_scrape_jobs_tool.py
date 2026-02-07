"""
Unit tests for scrape_jobs MCP tool handler.

Tests the orchestration of validation, preflight, scraping, normalization,
capture, and database insertion.
"""

from unittest.mock import MagicMock, patch
import pytest

from models.errors import ToolError, ErrorCode
from tools.scrape_jobs import (
    scrape_jobs,
    generate_run_id,
    get_utc_timestamp,
    init_term_result,
    process_term,
    aggregate_totals,
)
from utils.jobspy_adapter import PreflightDNSError


class TestGenerateRunId:
    """Tests for generate_run_id function."""

    def test_run_id_format(self):
        """Test that run ID has correct format."""
        run_id = generate_run_id()

        # Format: scrape_YYYYMMDD_<8-char-hex>
        assert run_id.startswith("scrape_")
        parts = run_id.split("_")
        assert len(parts) == 3
        assert parts[0] == "scrape"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 8  # 8-char hex
        assert parts[1].isdigit()
        assert all(c in "0123456789abcdef" for c in parts[2])

    def test_run_id_uniqueness(self):
        """Test that consecutive run IDs are unique."""
        run_id1 = generate_run_id()
        run_id2 = generate_run_id()

        assert run_id1 != run_id2


class TestGetUtcTimestamp:
    """Tests for get_utc_timestamp function."""

    def test_timestamp_format(self):
        """Test that timestamp has correct ISO 8601 format with Z suffix."""
        timestamp = get_utc_timestamp()

        # Format: YYYY-MM-DDTHH:MM:SS.mmmZ
        assert timestamp.endswith("Z")
        assert "T" in timestamp
        assert "." in timestamp  # Has milliseconds


class TestInitTermResult:
    """Tests for init_term_result function."""

    def test_initializes_with_correct_structure(self):
        """Test that term result is initialized with correct structure."""
        result = init_term_result("backend engineer")

        assert result["term"] == "backend engineer"
        assert result["success"] is False
        assert result["fetched_count"] == 0
        assert result["cleaned_count"] == 0
        assert result["inserted_count"] == 0
        assert result["duplicate_count"] == 0
        assert result["skipped_no_url"] == 0
        assert result["skipped_no_description"] == 0


class TestProcessTerm:
    """Tests for process_term function."""

    def test_successful_term_processing(self):
        """Test successful processing of a single term."""
        config = {
            "preflight_host": None,  # Skip preflight
            "sites": ["linkedin"],
            "location": "Ontario, Canada",
            "results_wanted": 20,
            "hours_old": 2,
            "require_description": True,
            "save_capture_json": False,
            "db_path": None,
            "status": "new",
        }

        # Mock raw records from scraper
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (1, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                result = process_term(
                    term="backend engineer",
                    config=config,
                    dry_run=False,
                )

        assert result["success"] is True
        assert result["term"] == "backend engineer"
        assert result["fetched_count"] == 1
        assert result["cleaned_count"] == 1
        assert result["inserted_count"] == 1
        assert result["duplicate_count"] == 0

    def test_preflight_failure_marks_term_failed(self):
        """Test that preflight DNS failure marks term as failed."""
        config = {
            "preflight_host": "www.linkedin.com",
            "retry_count": 1,
            "retry_sleep_seconds": 0.01,
            "retry_backoff": 1.0,
            "sites": ["linkedin"],
            "location": "Ontario, Canada",
            "results_wanted": 20,
            "hours_old": 2,
            "require_description": True,
            "save_capture_json": False,
            "db_path": None,
            "status": "new",
        }

        with patch(
            "tools.scrape_jobs.preflight_dns_check",
            side_effect=PreflightDNSError("DNS failed"),
        ):
            result = process_term(
                term="backend engineer",
                config=config,
                dry_run=False,
            )

        assert result["success"] is False
        assert "error" in result
        assert "DNS failed" in result["error"]
        assert result["fetched_count"] == 0

    def test_dry_run_skips_database_writes(self):
        """Test that dry_run=True skips database writes."""
        config = {
            "preflight_host": None,
            "sites": ["linkedin"],
            "location": "Ontario, Canada",
            "results_wanted": 20,
            "hours_old": 2,
            "require_description": True,
            "save_capture_json": False,
            "db_path": None,
            "status": "new",
        }

        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                result = process_term(
                    term="backend engineer",
                    config=config,
                    dry_run=True,
                )

                # Writer should not be instantiated in dry_run mode
                mock_writer_class.assert_not_called()

        assert result["success"] is True
        assert result["fetched_count"] == 1
        assert result["cleaned_count"] == 1
        assert result["inserted_count"] == 0  # No DB writes
        assert result["duplicate_count"] == 0

    def test_capture_file_written_when_enabled(self):
        """Test that capture file is written when save_capture_json=True."""
        config = {
            "preflight_host": None,
            "sites": ["linkedin"],
            "location": "Ontario, Canada",
            "results_wanted": 20,
            "hours_old": 2,
            "require_description": True,
            "save_capture_json": True,
            "capture_dir": "data/capture",
            "db_path": None,
            "status": "new",
        }

        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch(
                "tools.scrape_jobs.write_capture_file", return_value="data/capture/test.json"
            ) as mock_write:
                with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                    mock_writer = MagicMock()
                    mock_writer.insert_cleaned_records.return_value = (1, 0)
                    mock_writer_class.return_value.__enter__.return_value = mock_writer

                    result = process_term(
                        term="backend engineer",
                        config=config,
                        dry_run=False,
                    )

                    # Verify capture file was written
                    mock_write.assert_called_once()

        assert result["success"] is True
        assert "capture_path" in result
        assert result["capture_path"] == "data/capture/test.json"

    def test_capture_failure_does_not_fail_term(self):
        """Test that capture write failure doesn't fail the term."""
        config = {
            "preflight_host": None,
            "sites": ["linkedin"],
            "location": "Ontario, Canada",
            "results_wanted": 20,
            "hours_old": 2,
            "require_description": True,
            "save_capture_json": True,
            "capture_dir": "data/capture",
            "db_path": None,
            "status": "new",
        }

        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.write_capture_file", side_effect=OSError("Disk full")):
                with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                    mock_writer = MagicMock()
                    mock_writer.insert_cleaned_records.return_value = (1, 0)
                    mock_writer_class.return_value.__enter__.return_value = mock_writer

                    result = process_term(
                        term="backend engineer",
                        config=config,
                        dry_run=False,
                    )

        # Term should still succeed even if capture failed
        assert result["success"] is True
        assert "capture_path" not in result

    def test_filtering_records_without_url(self):
        """Test that records without URL are filtered out."""
        config = {
            "preflight_host": None,
            "sites": ["linkedin"],
            "location": "Ontario, Canada",
            "results_wanted": 20,
            "hours_old": 2,
            "require_description": True,
            "save_capture_json": False,
            "db_path": None,
            "status": "new",
        }

        raw_records = [
            {
                "job_url": "",  # Empty URL
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            },
            {
                "job_url": "https://linkedin.com/jobs/2",
                "title": "AI Engineer",
                "description": "Amazing role",
                "company": "AIStartup",
                "location": "Ottawa",
                "site": "linkedin",
                "id": "job2",
            },
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (1, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                result = process_term(
                    term="backend engineer",
                    config=config,
                    dry_run=False,
                )

        assert result["success"] is True
        assert result["fetched_count"] == 2
        assert result["cleaned_count"] == 1  # One filtered out
        assert result["skipped_no_url"] == 1
        assert result["inserted_count"] == 1

    def test_filtering_records_without_description(self):
        """Test that records without description are filtered when required."""
        config = {
            "preflight_host": None,
            "sites": ["linkedin"],
            "location": "Ontario, Canada",
            "results_wanted": 20,
            "hours_old": 2,
            "require_description": True,
            "save_capture_json": False,
            "db_path": None,
            "status": "new",
        }

        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "",  # Empty description
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            },
            {
                "job_url": "https://linkedin.com/jobs/2",
                "title": "AI Engineer",
                "description": "Amazing role",
                "company": "AIStartup",
                "location": "Ottawa",
                "site": "linkedin",
                "id": "job2",
            },
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (1, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                result = process_term(
                    term="backend engineer",
                    config=config,
                    dry_run=False,
                )

        assert result["success"] is True
        assert result["fetched_count"] == 2
        assert result["cleaned_count"] == 1  # One filtered out
        assert result["skipped_no_description"] == 1
        assert result["inserted_count"] == 1


class TestAggregateTotals:
    """Tests for aggregate_totals function."""

    def test_aggregates_successful_terms(self):
        """Test aggregation of successful term results."""
        results = [
            {
                "term": "backend engineer",
                "success": True,
                "fetched_count": 20,
                "cleaned_count": 18,
                "inserted_count": 10,
                "duplicate_count": 8,
                "skipped_no_url": 1,
                "skipped_no_description": 1,
            },
            {
                "term": "ai engineer",
                "success": True,
                "fetched_count": 15,
                "cleaned_count": 14,
                "inserted_count": 7,
                "duplicate_count": 7,
                "skipped_no_url": 0,
                "skipped_no_description": 1,
            },
        ]

        totals = aggregate_totals(results)

        assert totals["term_count"] == 2
        assert totals["successful_terms"] == 2
        assert totals["failed_terms"] == 0
        assert totals["fetched_count"] == 35
        assert totals["cleaned_count"] == 32
        assert totals["inserted_count"] == 17
        assert totals["duplicate_count"] == 15
        assert totals["skipped_no_url"] == 1
        assert totals["skipped_no_description"] == 2

    def test_aggregates_mixed_success_and_failure(self):
        """Test aggregation with both successful and failed terms."""
        results = [
            {
                "term": "backend engineer",
                "success": True,
                "fetched_count": 20,
                "cleaned_count": 18,
                "inserted_count": 10,
                "duplicate_count": 8,
                "skipped_no_url": 1,
                "skipped_no_description": 1,
            },
            {
                "term": "ai engineer",
                "success": False,
                "fetched_count": 0,
                "cleaned_count": 0,
                "inserted_count": 0,
                "duplicate_count": 0,
                "skipped_no_url": 0,
                "skipped_no_description": 0,
                "error": "DNS preflight failed",
            },
        ]

        totals = aggregate_totals(results)

        assert totals["term_count"] == 2
        assert totals["successful_terms"] == 1
        assert totals["failed_terms"] == 1
        assert totals["fetched_count"] == 20
        assert totals["cleaned_count"] == 18

    def test_empty_results(self):
        """Test aggregation with empty results list."""
        results = []

        totals = aggregate_totals(results)

        assert totals["term_count"] == 0
        assert totals["successful_terms"] == 0
        assert totals["failed_terms"] == 0
        assert totals["fetched_count"] == 0


class TestScrapeJobs:
    """Tests for scrape_jobs main function."""

    def test_validation_error_raised_for_invalid_parameters(self):
        """Test that validation errors are raised for invalid parameters."""
        with pytest.raises(ToolError) as exc_info:
            scrape_jobs(terms=[], location="Ontario")  # Empty terms

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

    def test_successful_single_term_scrape(self):
        """Test successful scrape with single term."""
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (1, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["backend engineer"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=False,
                )

        assert "run_id" in response
        assert response["run_id"].startswith("scrape_")
        assert "started_at" in response
        assert "finished_at" in response
        assert "duration_ms" in response
        assert response["dry_run"] is False
        assert len(response["results"]) == 1
        assert response["results"][0]["success"] is True
        assert response["totals"]["term_count"] == 1
        assert response["totals"]["successful_terms"] == 1

    def test_successful_multi_term_scrape(self):
        """Test successful scrape with multiple terms."""
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (1, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["backend engineer", "ai engineer", "machine learning"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=False,
                )

        assert len(response["results"]) == 3
        assert response["results"][0]["term"] == "backend engineer"
        assert response["results"][1]["term"] == "ai engineer"
        assert response["results"][2]["term"] == "machine learning"
        assert response["totals"]["term_count"] == 3

    def test_partial_success_with_one_term_failure(self):
        """Test partial success when one term fails."""

        def mock_scrape(term, **kwargs):
            if term == "ai engineer":
                raise Exception("Scrape failed")
            return [
                {
                    "job_url": "https://linkedin.com/jobs/1",
                    "title": "Engineer",
                    "description": "Great job",
                    "company": "TechCorp",
                    "location": "Toronto",
                    "site": "linkedin",
                    "id": "job1",
                }
            ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", side_effect=mock_scrape):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (1, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["backend engineer", "ai engineer"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=False,
                )

        assert len(response["results"]) == 2
        assert response["results"][0]["success"] is True
        assert response["results"][1]["success"] is False
        assert "error" in response["results"][1]
        assert response["totals"]["successful_terms"] == 1
        assert response["totals"]["failed_terms"] == 1

    def test_dry_run_mode(self):
        """Test dry_run mode with no database writes."""
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                response = scrape_jobs(
                    terms=["backend engineer"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=True,
                )

                # Writer should not be instantiated in dry_run mode
                mock_writer_class.assert_not_called()

        assert response["dry_run"] is True
        assert response["results"][0]["success"] is True
        assert response["results"][0]["inserted_count"] == 0
        assert response["results"][0]["duplicate_count"] == 0

    def test_uses_default_parameters(self):
        """Test that default parameters are used when not provided."""
        raw_records = []

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (0, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs()  # No parameters

        # Should use default terms
        assert len(response["results"]) == 3
        assert response["results"][0]["term"] == "ai engineer"
        assert response["results"][1]["term"] == "backend engineer"
        assert response["results"][2]["term"] == "machine learning"

    def test_unknown_parameter_rejected(self):
        """Test that unknown parameters are rejected."""
        with pytest.raises(ToolError) as exc_info:
            scrape_jobs(
                terms=["backend engineer"],
                unknown_param="value",
            )

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert "unknown_param" in exc_info.value.message.lower()

    def test_deterministic_term_ordering(self):
        """Test that terms are processed in deterministic order."""
        raw_records = []

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (0, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["term3", "term1", "term2"],
                    dry_run=False,
                )

        # Terms should be in request order
        assert response["results"][0]["term"] == "term3"
        assert response["results"][1]["term"] == "term1"
        assert response["results"][2]["term"] == "term2"

    def test_internal_error_wrapped(self):
        """Test that unexpected exceptions are wrapped as INTERNAL_ERROR."""
        with patch(
            "tools.scrape_jobs.validate_scrape_jobs_parameters",
            side_effect=RuntimeError("Unexpected error"),
        ):
            with pytest.raises(ToolError) as exc_info:
                scrape_jobs(terms=["backend engineer"])

            assert exc_info.value.code == ErrorCode.INTERNAL_ERROR


class TestErrorMapping:
    """Tests for error mapping and sanitization in scrape_jobs.

    Validates Requirements 11.1, 11.2, 11.3, 11.4, 11.5
    """

    def test_validation_error_for_invalid_parameters(self):
        """Test that validation errors return VALIDATION_ERROR code.

        **Validates: Requirements 11.1**
        """
        with pytest.raises(ToolError) as exc_info:
            scrape_jobs(terms=[], location="Ontario")  # Empty terms

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        error_dict = exc_info.value.to_dict()
        assert error_dict["error"]["code"] == "VALIDATION_ERROR"
        assert error_dict["error"]["retryable"] is False

    def test_db_error_on_database_failure(self):
        """Test that database failures return DB_ERROR.

        **Validates: Requirements 11.2**
        """
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                # Simulate database error during insert
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.side_effect = Exception(
                    "Database error: SELECT * FROM jobs"
                )
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["backend engineer"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=False,
                )

        # Should have partial success - term failed but run completed
        assert len(response["results"]) == 1
        assert response["results"][0]["success"] is False
        assert "error" in response["results"][0]
        # Error should be sanitized (no SQL fragments)
        assert "SELECT" not in response["results"][0]["error"]

    def test_internal_error_on_unexpected_exception(self):
        """Test that unexpected exceptions return INTERNAL_ERROR.

        **Validates: Requirements 11.3**
        """
        with patch(
            "tools.scrape_jobs.validate_scrape_jobs_parameters",
            side_effect=RuntimeError("Unexpected runtime error"),
        ):
            with pytest.raises(ToolError) as exc_info:
                scrape_jobs(terms=["backend engineer"])

            assert exc_info.value.code == ErrorCode.INTERNAL_ERROR
            error_dict = exc_info.value.to_dict()
            assert error_dict["error"]["code"] == "INTERNAL_ERROR"
            assert error_dict["error"]["retryable"] is True

    def test_error_sanitization_removes_stack_traces(self):
        """Test that stack traces are removed from error messages.

        **Validates: Requirements 11.4**
        """
        stack_trace_error = """ValueError: Invalid value
        File "/home/user/project/module.py", line 42, in function
        File "/home/user/project/main.py", line 10, in main"""

        with patch(
            "tools.scrape_jobs.validate_scrape_jobs_parameters",
            side_effect=RuntimeError(stack_trace_error),
        ):
            with pytest.raises(ToolError) as exc_info:
                scrape_jobs(terms=["backend engineer"])

            # Error message should only contain first line
            assert "ValueError: Invalid value" in exc_info.value.message
            assert 'File "' not in exc_info.value.message
            assert "line 42" not in exc_info.value.message

    def test_error_sanitization_removes_sql_fragments(self):
        """Test that SQL fragments are removed from error messages.

        **Validates: Requirements 11.4**
        """
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                # Simulate database error with SQL fragment
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.side_effect = Exception(
                    "Error executing: INSERT INTO jobs VALUES (...)"
                )
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["backend engineer"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=False,
                )

        # Error should not contain SQL keywords
        error_msg = response["results"][0]["error"]
        assert "INSERT" not in error_msg
        assert "VALUES" not in error_msg

    def test_error_sanitization_removes_absolute_paths(self):
        """Test that absolute paths are sanitized in error messages.

        **Validates: Requirements 11.4**
        """
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Backend Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                # Simulate error with absolute path
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.side_effect = Exception(
                    "Cannot access /home/user/secret/data/jobs.db"
                )
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["backend engineer"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=False,
                )

        # Error should not contain full absolute path
        error_msg = response["results"][0]["error"]
        assert "/home/user/secret/data/" not in error_msg

    def test_per_term_failures_allow_partial_success(self):
        """Test that per-term failures don't stop other terms from processing.

        **Validates: Requirements 11.5**
        """

        def mock_scrape(term, **kwargs):
            if term == "ai engineer":
                raise Exception("Scrape failed for this term")
            return [
                {
                    "job_url": "https://linkedin.com/jobs/1",
                    "title": "Engineer",
                    "description": "Great job",
                    "company": "TechCorp",
                    "location": "Toronto",
                    "site": "linkedin",
                    "id": "job1",
                }
            ]

        with patch("tools.scrape_jobs.scrape_jobs_for_term", side_effect=mock_scrape):
            with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                mock_writer = MagicMock()
                mock_writer.insert_cleaned_records.return_value = (1, 0)
                mock_writer_class.return_value.__enter__.return_value = mock_writer

                response = scrape_jobs(
                    terms=["backend engineer", "ai engineer", "machine learning"],
                    location="Ontario, Canada",
                    sites=["linkedin"],
                    results_wanted=20,
                    hours_old=2,
                    dry_run=False,
                )

        # Should have all three results
        assert len(response["results"]) == 3

        # First term should succeed
        assert response["results"][0]["term"] == "backend engineer"
        assert response["results"][0]["success"] is True

        # Second term should fail with error
        assert response["results"][1]["term"] == "ai engineer"
        assert response["results"][1]["success"] is False
        assert "error" in response["results"][1]

        # Third term should succeed
        assert response["results"][2]["term"] == "machine learning"
        assert response["results"][2]["success"] is True

        # Totals should reflect partial success
        assert response["totals"]["successful_terms"] == 2
        assert response["totals"]["failed_terms"] == 1

    def test_preflight_failure_recorded_as_per_term_error(self):
        """Test that preflight failures are recorded as per-term errors.

        **Validates: Requirements 11.5**
        """
        config_with_preflight = {
            "terms": ["backend engineer", "ai engineer"],
            "location": "Ontario, Canada",
            "sites": ["linkedin"],
            "results_wanted": 20,
            "hours_old": 2,
            "preflight_host": "www.linkedin.com",
            "retry_count": 1,
            "retry_sleep_seconds": 0.01,
            "retry_backoff": 1.0,
            "dry_run": False,
        }

        def mock_preflight(host, **kwargs):
            # Fail only for second call
            if not hasattr(mock_preflight, "call_count"):
                mock_preflight.call_count = 0
            mock_preflight.call_count += 1

            if mock_preflight.call_count == 2:
                raise PreflightDNSError("DNS resolution failed")

        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/1",
                "title": "Engineer",
                "description": "Great job",
                "company": "TechCorp",
                "location": "Toronto",
                "site": "linkedin",
                "id": "job1",
            }
        ]

        with patch("tools.scrape_jobs.preflight_dns_check", side_effect=mock_preflight):
            with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
                with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
                    mock_writer = MagicMock()
                    mock_writer.insert_cleaned_records.return_value = (1, 0)
                    mock_writer_class.return_value.__enter__.return_value = mock_writer

                    response = scrape_jobs(**config_with_preflight)

        # Should have both results
        assert len(response["results"]) == 2

        # First term should succeed
        assert response["results"][0]["success"] is True

        # Second term should fail with preflight error
        assert response["results"][1]["success"] is False
        assert "error" in response["results"][1]
        assert "DNS" in response["results"][1]["error"]

        # Totals should reflect partial success
        assert response["totals"]["successful_terms"] == 1
        assert response["totals"]["failed_terms"] == 1
