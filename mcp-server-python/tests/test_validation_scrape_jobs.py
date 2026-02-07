"""
Unit tests for scrape_jobs validation functions.

Tests validation of scrape_jobs parameters including terms, results_wanted,
hours_old, retry fields, status, and unknown keys.

**Validates: Requirements 1.4, 1.5, 11.1, 12.2**
"""

import pytest
from utils.validation import (
    validate_scrape_terms,
    validate_results_wanted,
    validate_hours_old,
    validate_retry_count,
    validate_retry_sleep_seconds,
    validate_retry_backoff,
    validate_scrape_status,
    validate_scrape_jobs_parameters,
    DEFAULT_SCRAPE_TERMS,
    DEFAULT_RESULTS_WANTED,
    MIN_RESULTS_WANTED,
    MAX_RESULTS_WANTED,
    DEFAULT_HOURS_OLD,
    MIN_HOURS_OLD,
    MAX_HOURS_OLD,
    DEFAULT_RETRY_COUNT,
    MIN_RETRY_COUNT,
    MAX_RETRY_COUNT,
    DEFAULT_RETRY_SLEEP_SECONDS,
    MIN_RETRY_SLEEP_SECONDS,
    MAX_RETRY_SLEEP_SECONDS,
    DEFAULT_RETRY_BACKOFF,
    MIN_RETRY_BACKOFF,
    MAX_RETRY_BACKOFF,
)
from models.errors import ToolError, ErrorCode


class TestValidateScrapeTerms:
    """Tests for terms parameter validation."""

    def test_default_terms_when_none(self):
        """Test that None returns the default terms list."""
        result = validate_scrape_terms(None)
        assert result == DEFAULT_SCRAPE_TERMS
        assert result == ["ai engineer", "backend engineer", "machine learning"]

    def test_valid_single_term(self):
        """Test that single term list is accepted."""
        result = validate_scrape_terms(["python developer"])
        assert result == ["python developer"]

    def test_valid_multiple_terms(self):
        """Test that multiple terms are accepted."""
        terms = ["software engineer", "data scientist", "devops engineer"]
        result = validate_scrape_terms(terms)
        assert result == terms

    def test_empty_terms_list_raises_error(self):
        """Test that empty terms list raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_terms([])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty array" in error.message.lower()
        assert not error.retryable

    def test_terms_invalid_type_string_raises_error(self):
        """Test that string terms raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_terms("software engineer")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()
        assert "array" in error.message.lower()

    def test_terms_with_non_string_element_raises_error(self):
        """Test that terms with non-string element raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_terms(["software engineer", 123, "data scientist"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "terms[1]" in error.message
        assert "type" in error.message.lower()

    def test_terms_with_empty_string_element_raises_error(self):
        """Test that terms with empty string element raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_terms(["software engineer", "", "data scientist"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "terms[1]" in error.message
        assert "cannot be empty string" in error.message.lower()


class TestValidateResultsWanted:
    """Tests for results_wanted parameter validation."""

    def test_default_results_wanted_when_none(self):
        """Test that None returns the default results_wanted."""
        result = validate_results_wanted(None)
        assert result == DEFAULT_RESULTS_WANTED
        assert result == 20

    def test_valid_results_wanted_in_range(self):
        """Test that valid results_wanted within range are accepted."""
        assert validate_results_wanted(1) == 1
        assert validate_results_wanted(20) == 20
        assert validate_results_wanted(100) == 100
        assert validate_results_wanted(200) == 200

    def test_results_wanted_below_minimum_raises_error(self):
        """Test that results_wanted below 1 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_results_wanted(0)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()
        assert str(MIN_RESULTS_WANTED) in error.message
        assert not error.retryable

    def test_results_wanted_negative_raises_error(self):
        """Test that negative results_wanted raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_results_wanted(-1)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()

    def test_results_wanted_above_maximum_raises_error(self):
        """Test that results_wanted above 200 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_results_wanted(201)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()
        assert str(MAX_RESULTS_WANTED) in error.message
        assert not error.retryable

    def test_results_wanted_far_above_maximum_raises_error(self):
        """Test that very large results_wanted raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_results_wanted(1000)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()

    def test_results_wanted_invalid_type_string_raises_error(self):
        """Test that string results_wanted raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_results_wanted("20")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_results_wanted_invalid_type_float_raises_error(self):
        """Test that float results_wanted raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_results_wanted(20.5)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_results_wanted_invalid_type_boolean_raises_error(self):
        """Test that boolean results_wanted raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_results_wanted(True)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateHoursOld:
    """Tests for hours_old parameter validation."""

    def test_default_hours_old_when_none(self):
        """Test that None returns the default hours_old."""
        result = validate_hours_old(None)
        assert result == DEFAULT_HOURS_OLD
        assert result == 2

    def test_valid_hours_old_in_range(self):
        """Test that valid hours_old within range are accepted."""
        assert validate_hours_old(1) == 1
        assert validate_hours_old(2) == 2
        assert validate_hours_old(24) == 24
        assert validate_hours_old(168) == 168

    def test_hours_old_below_minimum_raises_error(self):
        """Test that hours_old below 1 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_hours_old(0)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()
        assert str(MIN_HOURS_OLD) in error.message
        assert not error.retryable

    def test_hours_old_negative_raises_error(self):
        """Test that negative hours_old raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_hours_old(-1)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()

    def test_hours_old_above_maximum_raises_error(self):
        """Test that hours_old above 168 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_hours_old(169)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()
        assert str(MAX_HOURS_OLD) in error.message
        assert not error.retryable

    def test_hours_old_far_above_maximum_raises_error(self):
        """Test that very large hours_old raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_hours_old(1000)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()

    def test_hours_old_invalid_type_string_raises_error(self):
        """Test that string hours_old raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_hours_old("24")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_hours_old_invalid_type_float_raises_error(self):
        """Test that float hours_old raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_hours_old(24.5)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_hours_old_invalid_type_boolean_raises_error(self):
        """Test that boolean hours_old raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_hours_old(False)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateRetryCount:
    """Tests for retry_count parameter validation."""

    def test_default_retry_count_when_none(self):
        """Test that None returns the default retry_count."""
        result = validate_retry_count(None)
        assert result == DEFAULT_RETRY_COUNT
        assert result == 3

    def test_valid_retry_count_in_range(self):
        """Test that valid retry_count within range are accepted."""
        assert validate_retry_count(1) == 1
        assert validate_retry_count(3) == 3
        assert validate_retry_count(5) == 5
        assert validate_retry_count(10) == 10

    def test_retry_count_below_minimum_raises_error(self):
        """Test that retry_count below 1 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_count(0)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()
        assert str(MIN_RETRY_COUNT) in error.message
        assert not error.retryable

    def test_retry_count_negative_raises_error(self):
        """Test that negative retry_count raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_count(-1)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()

    def test_retry_count_above_maximum_raises_error(self):
        """Test that retry_count above 10 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_count(11)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()
        assert str(MAX_RETRY_COUNT) in error.message
        assert not error.retryable

    def test_retry_count_invalid_type_string_raises_error(self):
        """Test that string retry_count raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_count("3")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_retry_count_invalid_type_boolean_raises_error(self):
        """Test that boolean retry_count raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_count(True)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateRetrySleepSeconds:
    """Tests for retry_sleep_seconds parameter validation."""

    def test_default_retry_sleep_seconds_when_none(self):
        """Test that None returns the default retry_sleep_seconds."""
        result = validate_retry_sleep_seconds(None)
        assert result == DEFAULT_RETRY_SLEEP_SECONDS
        assert result == 30

    def test_valid_retry_sleep_seconds_in_range(self):
        """Test that valid retry_sleep_seconds within range are accepted."""
        assert validate_retry_sleep_seconds(0) == 0
        assert validate_retry_sleep_seconds(30) == 30
        assert validate_retry_sleep_seconds(60) == 60
        assert validate_retry_sleep_seconds(300) == 300

    def test_valid_retry_sleep_seconds_float(self):
        """Test that float retry_sleep_seconds are accepted."""
        assert validate_retry_sleep_seconds(30.5) == 30.5
        assert validate_retry_sleep_seconds(0.5) == 0.5

    def test_retry_sleep_seconds_below_minimum_raises_error(self):
        """Test that retry_sleep_seconds below 0 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_sleep_seconds(-1)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()
        assert str(MIN_RETRY_SLEEP_SECONDS) in error.message
        assert not error.retryable

    def test_retry_sleep_seconds_above_maximum_raises_error(self):
        """Test that retry_sleep_seconds above 300 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_sleep_seconds(301)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()
        assert str(MAX_RETRY_SLEEP_SECONDS) in error.message
        assert not error.retryable

    def test_retry_sleep_seconds_invalid_type_string_raises_error(self):
        """Test that string retry_sleep_seconds raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_sleep_seconds("30")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_retry_sleep_seconds_invalid_type_boolean_raises_error(self):
        """Test that boolean retry_sleep_seconds raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_sleep_seconds(False)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateRetryBackoff:
    """Tests for retry_backoff parameter validation."""

    def test_default_retry_backoff_when_none(self):
        """Test that None returns the default retry_backoff."""
        result = validate_retry_backoff(None)
        assert result == DEFAULT_RETRY_BACKOFF
        assert result == 2

    def test_valid_retry_backoff_in_range(self):
        """Test that valid retry_backoff within range are accepted."""
        assert validate_retry_backoff(1) == 1
        assert validate_retry_backoff(2) == 2
        assert validate_retry_backoff(5) == 5
        assert validate_retry_backoff(10) == 10

    def test_valid_retry_backoff_float(self):
        """Test that float retry_backoff are accepted."""
        assert validate_retry_backoff(1.5) == 1.5
        assert validate_retry_backoff(2.5) == 2.5

    def test_retry_backoff_below_minimum_raises_error(self):
        """Test that retry_backoff below 1 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_backoff(0.5)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "below minimum" in error.message.lower()
        assert str(MIN_RETRY_BACKOFF) in error.message
        assert not error.retryable

    def test_retry_backoff_above_maximum_raises_error(self):
        """Test that retry_backoff above 10 raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_backoff(11)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "exceeds maximum" in error.message.lower()
        assert str(MAX_RETRY_BACKOFF) in error.message
        assert not error.retryable

    def test_retry_backoff_invalid_type_string_raises_error(self):
        """Test that string retry_backoff raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_backoff("2")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()

    def test_retry_backoff_invalid_type_boolean_raises_error(self):
        """Test that boolean retry_backoff raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_retry_backoff(True)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateScrapeStatus:
    """Tests for status parameter validation in scrape_jobs."""

    def test_default_status_when_none(self):
        """Test that None returns the default status 'new'."""
        result = validate_scrape_status(None)
        assert result == "new"

    def test_valid_statuses(self):
        """Test that all valid status values are accepted."""
        valid_statuses = ["new", "shortlist", "reviewed", "reject", "resume_written", "applied"]
        for status in valid_statuses:
            result = validate_scrape_status(status)
            assert result == status

    def test_invalid_status_value_raises_error(self):
        """Test that invalid status values raise VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_status("invalid_status")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid status value" in error.message
        assert "invalid_status" in error.message
        assert not error.retryable

    def test_status_case_sensitive(self):
        """Test that status validation is case-sensitive."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_status("NEW")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Invalid status value" in error.message

    def test_status_with_whitespace_raises_error(self):
        """Test that status with whitespace raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_status(" new")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "whitespace" in error.message.lower()

    def test_status_empty_string_raises_error(self):
        """Test that empty string status raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_status("")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "cannot be empty" in error.message.lower()

    def test_status_invalid_type_raises_error(self):
        """Test that non-string status raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_status(123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "type" in error.message.lower()


class TestValidateScrapeJobsParameters:
    """Tests for validating all scrape_jobs parameters together."""

    def test_all_defaults(self):
        """Test validation with all default values."""
        result = validate_scrape_jobs_parameters()
        
        assert result["terms"] == DEFAULT_SCRAPE_TERMS
        assert result["location"] == "Ontario, Canada"
        assert result["sites"] == ["linkedin"]
        assert result["results_wanted"] == 20
        assert result["hours_old"] == 2
        assert result["db_path"] is None
        assert result["status"] == "new"
        assert result["require_description"] is True
        assert result["preflight_host"] == "www.linkedin.com"
        assert result["retry_count"] == 3
        assert result["retry_sleep_seconds"] == 30
        assert result["retry_backoff"] == 2
        assert result["save_capture_json"] is True
        assert result["capture_dir"] == "data/capture"
        assert result["dry_run"] is False

    def test_all_valid_custom_values(self):
        """Test validation with all valid custom values."""
        result = validate_scrape_jobs_parameters(
            terms=["python developer"],
            location="Toronto, Canada",
            sites=["linkedin", "indeed"],
            results_wanted=50,
            hours_old=24,
            db_path="custom/jobs.db",
            status="shortlist",
            require_description=False,
            preflight_host="www.google.com",
            retry_count=5,
            retry_sleep_seconds=60,
            retry_backoff=3,
            save_capture_json=False,
            capture_dir="custom/capture",
            dry_run=True
        )
        
        assert result["terms"] == ["python developer"]
        assert result["location"] == "Toronto, Canada"
        assert result["sites"] == ["linkedin", "indeed"]
        assert result["results_wanted"] == 50
        assert result["hours_old"] == 24
        assert result["db_path"] == "custom/jobs.db"
        assert result["status"] == "shortlist"
        assert result["require_description"] is False
        assert result["preflight_host"] == "www.google.com"
        assert result["retry_count"] == 5
        assert result["retry_sleep_seconds"] == 60
        assert result["retry_backoff"] == 3
        assert result["save_capture_json"] is False
        assert result["capture_dir"] == "custom/capture"
        assert result["dry_run"] is True

    def test_unknown_property_raises_error(self):
        """Test that unknown properties raise VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(
                terms=["python developer"],
                unknown_param="value"
            )

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Unknown input properties" in error.message
        assert "unknown_param" in error.message
        assert not error.retryable

    def test_multiple_unknown_properties_raises_error(self):
        """Test that multiple unknown properties are all reported."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(
                terms=["python developer"],
                unknown1="value1",
                unknown2="value2"
            )

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Unknown input properties" in error.message
        assert "unknown1" in error.message
        assert "unknown2" in error.message

    def test_invalid_results_wanted_raises_error(self):
        """Test that invalid results_wanted raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(results_wanted=0)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "results_wanted" in error.message.lower()

    def test_invalid_hours_old_raises_error(self):
        """Test that invalid hours_old raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(hours_old=200)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "hours_old" in error.message.lower()

    def test_invalid_retry_count_raises_error(self):
        """Test that invalid retry_count raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(retry_count=0)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "retry_count" in error.message.lower()

    def test_invalid_retry_sleep_seconds_raises_error(self):
        """Test that invalid retry_sleep_seconds raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(retry_sleep_seconds=400)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "retry_sleep_seconds" in error.message.lower()

    def test_invalid_retry_backoff_raises_error(self):
        """Test that invalid retry_backoff raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(retry_backoff=15)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "retry_backoff" in error.message.lower()

    def test_invalid_status_raises_error(self):
        """Test that invalid status raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(status="invalid")

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "status" in error.message.lower()

    def test_empty_terms_raises_error(self):
        """Test that empty terms list raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(terms=[])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "terms" in error.message.lower()
        assert "empty" in error.message.lower()

    def test_invalid_db_path_type_raises_error(self):
        """Test that invalid db_path type raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(db_path=123)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "db_path" in error.message.lower()
        assert "type" in error.message.lower()

    def test_invalid_capture_dir_type_raises_error(self):
        """Test that invalid capture_dir type raises error."""
        with pytest.raises(ToolError) as exc_info:
            validate_scrape_jobs_parameters(capture_dir=["path"])

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "capture_dir" in error.message.lower()
        assert "type" in error.message.lower()

    def test_boundary_values_accepted(self):
        """Test that boundary values are accepted."""
        result = validate_scrape_jobs_parameters(
            results_wanted=1,  # MIN
            hours_old=1,  # MIN
            retry_count=1,  # MIN
            retry_sleep_seconds=0,  # MIN
            retry_backoff=1  # MIN
        )
        
        assert result["results_wanted"] == 1
        assert result["hours_old"] == 1
        assert result["retry_count"] == 1
        assert result["retry_sleep_seconds"] == 0
        assert result["retry_backoff"] == 1

        result = validate_scrape_jobs_parameters(
            results_wanted=200,  # MAX
            hours_old=168,  # MAX
            retry_count=10,  # MAX
            retry_sleep_seconds=300,  # MAX
            retry_backoff=10  # MAX
        )
        
        assert result["results_wanted"] == 200
        assert result["hours_old"] == 168
        assert result["retry_count"] == 10
        assert result["retry_sleep_seconds"] == 300
        assert result["retry_backoff"] == 10
