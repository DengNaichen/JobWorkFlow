"""
Unit tests for scrape_normalizer module.

Tests record normalization, field mapping, filtering, and timestamp handling.
"""

import json
from datetime import datetime, timezone

from utils.scrape_normalizer import (
    JOB_URL_ID_RE,
    clean_record,
    filter_records,
    normalize_and_filter,
    normalize_text,
    parse_captured_at,
    parse_job_id,
    serialize_payload,
)


class TestNormalizeText:
    """Tests for text normalization."""

    def test_none_returns_empty_string(self):
        """Test that None returns empty string."""
        assert normalize_text(None) == ""

    def test_empty_string_returns_empty(self):
        """Test that empty string returns empty."""
        assert normalize_text("") == ""

    def test_whitespace_only_returns_empty(self):
        """Test that whitespace-only string returns empty."""
        assert normalize_text("   ") == ""
        assert normalize_text("\t\n") == ""

    def test_strips_leading_whitespace(self):
        """Test that leading whitespace is stripped."""
        assert normalize_text("  hello") == "hello"

    def test_strips_trailing_whitespace(self):
        """Test that trailing whitespace is stripped."""
        assert normalize_text("hello  ") == "hello"

    def test_strips_both_whitespace(self):
        """Test that both leading and trailing whitespace is stripped."""
        assert normalize_text("  hello  ") == "hello"

    def test_preserves_internal_whitespace(self):
        """Test that internal whitespace is preserved."""
        assert normalize_text("hello world") == "hello world"

    def test_converts_integer_to_string(self):
        """Test that integers are converted to strings."""
        assert normalize_text(123) == "123"

    def test_converts_float_to_string(self):
        """Test that floats are converted to strings."""
        assert normalize_text(123.45) == "123.45"

    def test_converts_boolean_to_string(self):
        """Test that booleans are converted to strings."""
        assert normalize_text(True) == "True"
        assert normalize_text(False) == "False"


class TestParseJobId:
    """Tests for LinkedIn job ID parsing."""

    def test_extracts_id_from_linkedin_url(self):
        """Test extraction of job ID from LinkedIn URL."""
        url = "https://www.linkedin.com/jobs/view/1234567890"
        assert parse_job_id(url, None) == "1234567890"

    def test_extracts_id_from_url_with_query_params(self):
        """Test extraction from URL with query parameters."""
        url = "https://www.linkedin.com/jobs/view/9876543210?refId=abc123"
        assert parse_job_id(url, None) == "9876543210"

    def test_extracts_id_from_url_with_path_suffix(self):
        """Test extraction from URL with additional path segments."""
        url = "https://www.linkedin.com/jobs/view/1111111111/apply"
        assert parse_job_id(url, None) == "1111111111"

    def test_fallback_when_no_match(self):
        """Test fallback to source ID when URL doesn't match pattern."""
        url = "https://example.com/job/abc"
        assert parse_job_id(url, "source-123") == "source-123"

    def test_fallback_when_empty_url(self):
        """Test fallback when URL is empty."""
        assert parse_job_id("", "fallback-id") == "fallback-id"

    def test_fallback_when_none_url(self):
        """Test fallback when URL is None."""
        assert parse_job_id(None, "fallback-id") == "fallback-id"

    def test_normalizes_fallback_value(self):
        """Test that fallback value is normalized."""
        assert parse_job_id("", "  fallback  ") == "fallback"
        assert parse_job_id("", None) == ""

    def test_handles_numeric_fallback(self):
        """Test that numeric fallback is converted to string."""
        assert parse_job_id("", 12345) == "12345"


class TestParseCapturedAt:
    """Tests for timestamp normalization."""

    def test_none_returns_current_utc(self):
        """Test that None returns current UTC timestamp."""
        result = parse_captured_at(None)
        # Verify it's a valid ISO format
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_empty_string_returns_current_utc(self):
        """Test that empty string returns current UTC timestamp."""
        result = parse_captured_at("")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_parses_iso_format_with_z_suffix(self):
        """Test parsing ISO format with Z suffix."""
        input_date = "2024-01-15T10:30:00Z"
        result = parse_captured_at(input_date)
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_parses_iso_format_with_timezone(self):
        """Test parsing ISO format with timezone offset."""
        input_date = "2024-01-15T10:30:00+00:00"
        result = parse_captured_at(input_date)
        assert "2024-01-15" in result

    def test_converts_to_utc(self):
        """Test that timestamps are converted to UTC."""
        input_date = "2024-01-15T10:30:00-05:00"
        result = parse_captured_at(input_date)
        # Should be converted to UTC (15:30:00)
        assert "2024-01-15" in result
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo == timezone.utc

    def test_invalid_format_returns_current_utc(self):
        """Test that invalid format returns current UTC timestamp."""
        result = parse_captured_at("invalid-date")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_non_string_returns_current_utc(self):
        """Test that non-string values return current UTC timestamp."""
        result = parse_captured_at(12345)
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None


class TestCleanRecord:
    """Tests for record cleaning and field mapping."""

    def test_maps_all_fields(self):
        """Test that all fields are mapped correctly."""
        raw = {
            "job_url": "https://example.com/job/123",
            "title": "Software Engineer",
            "description": "Great job opportunity",
            "company": "Tech Corp",
            "location": "San Francisco, CA",
            "site": "linkedin",
            "id": "src-123",
            "date_posted": "2024-01-15T10:00:00Z",
        }

        result = clean_record(raw)

        assert result["url"] == "https://example.com/job/123"
        assert result["title"] == "Software Engineer"
        assert result["description"] == "Great job opportunity"
        assert result["company"] == "Tech Corp"
        assert result["location"] == "San Francisco, CA"
        assert result["source"] == "linkedin"
        assert result["jobId"] == "src-123"
        assert "2024-01-15" in result["capturedAt"]
        assert "id" in result

    def test_uses_job_url_direct_fallback(self):
        """Test that job_url_direct is used when job_url is missing."""
        raw = {
            "job_url_direct": "https://example.com/direct/456",
            "title": "Engineer",
            "site": "indeed",
        }

        result = clean_record(raw)
        assert result["url"] == "https://example.com/direct/456"

    def test_prefers_job_url_over_direct(self):
        """Test that job_url is preferred over job_url_direct."""
        raw = {
            "job_url": "https://example.com/job/123",
            "job_url_direct": "https://example.com/direct/456",
            "title": "Engineer",
        }

        result = clean_record(raw)
        assert result["url"] == "https://example.com/job/123"

    def test_source_override(self):
        """Test that source_override takes precedence."""
        raw = {"job_url": "https://example.com/job/123", "site": "linkedin"}

        result = clean_record(raw, source_override="custom_source")
        assert result["source"] == "custom_source"

    def test_source_defaults_to_unknown(self):
        """Test that source defaults to 'unknown' when missing."""
        raw = {"job_url": "https://example.com/job/123", "title": "Engineer"}

        result = clean_record(raw)
        assert result["source"] == "unknown"

    def test_parses_linkedin_job_id_from_url(self):
        """Test that LinkedIn job ID is parsed from URL."""
        raw = {"job_url": "https://www.linkedin.com/jobs/view/1234567890", "id": "fallback-id"}

        result = clean_record(raw)
        assert result["jobId"] == "1234567890"

    def test_uses_fallback_job_id(self):
        """Test that fallback ID is used when URL parsing fails."""
        raw = {"job_url": "https://example.com/job/abc", "id": "fallback-123"}

        result = clean_record(raw)
        assert result["jobId"] == "fallback-123"

    def test_normalizes_whitespace_in_fields(self):
        """Test that whitespace is normalized in all text fields."""
        raw = {
            "job_url": "  https://example.com/job/123  ",
            "title": "  Software Engineer  ",
            "company": "  Tech Corp  ",
            "location": "  SF  ",
        }

        result = clean_record(raw)
        assert result["url"] == "https://example.com/job/123"
        assert result["title"] == "Software Engineer"
        assert result["company"] == "Tech Corp"
        assert result["location"] == "SF"

    def test_handles_missing_fields(self):
        """Test that missing fields are handled gracefully."""
        raw = {"job_url": "https://example.com/job/123"}

        result = clean_record(raw)
        assert result["url"] == "https://example.com/job/123"
        assert result["title"] == ""
        assert result["description"] == ""
        assert result["company"] == ""
        assert result["location"] == ""

    def test_generates_unique_id(self):
        """Test that each record gets a unique UUID."""
        raw = {"job_url": "https://example.com/job/123"}

        result1 = clean_record(raw)
        result2 = clean_record(raw)

        assert result1["id"] != result2["id"]
        # Verify UUID format
        assert len(result1["id"]) == 36
        assert result1["id"].count("-") == 4


class TestFilterRecords:
    """Tests for record filtering."""

    def test_empty_list_returns_empty(self):
        """Test that empty list returns empty results."""
        filtered, counts = filter_records([])
        assert filtered == []
        assert counts["skipped_no_url"] == 0
        assert counts["skipped_no_description"] == 0

    def test_filters_records_without_url(self):
        """Test that records without URL are filtered."""
        records = [
            {"url": "", "description": "Has description"},
            {"url": "https://example.com/job/1", "description": "Valid"},
        ]

        filtered, counts = filter_records(records)
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://example.com/job/1"
        assert counts["skipped_no_url"] == 1

    def test_filters_records_without_description_when_required(self):
        """Test that records without description are filtered when required."""
        records = [
            {"url": "https://example.com/job/1", "description": ""},
            {"url": "https://example.com/job/2", "description": "Valid"},
        ]

        filtered, counts = filter_records(records, require_description=True)
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://example.com/job/2"
        assert counts["skipped_no_description"] == 1

    def test_keeps_records_without_description_when_not_required(self):
        """Test that records without description are kept when not required."""
        records = [
            {"url": "https://example.com/job/1", "description": ""},
            {"url": "https://example.com/job/2", "description": "Valid"},
        ]

        filtered, counts = filter_records(records, require_description=False)
        assert len(filtered) == 2
        assert counts["skipped_no_description"] == 0

    def test_counts_multiple_skips(self):
        """Test that multiple skips are counted correctly."""
        records = [
            {"url": "", "description": "Has description"},
            {"url": "https://example.com/job/1", "description": ""},
            {"url": "", "description": ""},
            {"url": "https://example.com/job/2", "description": "Valid"},
        ]

        filtered, counts = filter_records(records, require_description=True)
        assert len(filtered) == 1
        assert counts["skipped_no_url"] == 2
        assert counts["skipped_no_description"] == 1

    def test_url_check_takes_precedence(self):
        """Test that URL check happens before description check."""
        records = [{"url": "", "description": ""}]

        filtered, counts = filter_records(records, require_description=True)
        assert len(filtered) == 0
        # Should be counted as no URL, not no description
        assert counts["skipped_no_url"] == 1
        assert counts["skipped_no_description"] == 0


class TestNormalizeAndFilter:
    """Tests for combined normalize and filter operation."""

    def test_cleans_and_filters_in_one_pass(self):
        """Test that records are cleaned and filtered together."""
        raw_records = [
            {
                "job_url": "https://example.com/job/1",
                "title": "Engineer",
                "description": "Great job",
            },
            {"job_url": "", "title": "No URL", "description": "Should be filtered"},
        ]

        filtered, counts = normalize_and_filter(raw_records)
        assert len(filtered) == 1
        assert filtered[0]["url"] == "https://example.com/job/1"
        assert counts["skipped_no_url"] == 1

    def test_applies_source_override(self):
        """Test that source override is applied during cleaning."""
        raw_records = [
            {"job_url": "https://example.com/job/1", "site": "linkedin", "description": "Job"}
        ]

        filtered, _counts = normalize_and_filter(raw_records, source_override="custom")
        assert filtered[0]["source"] == "custom"

    def test_respects_require_description_flag(self):
        """Test that require_description flag is respected."""
        raw_records = [{"job_url": "https://example.com/job/1", "title": "No description"}]

        # With require_description=True (default)
        filtered_true, counts_true = normalize_and_filter(raw_records, require_description=True)
        assert len(filtered_true) == 0
        assert counts_true["skipped_no_description"] == 1

        # With require_description=False
        filtered_false, counts_false = normalize_and_filter(raw_records, require_description=False)
        assert len(filtered_false) == 1
        assert counts_false["skipped_no_description"] == 0


class TestSerializePayload:
    """Tests for JSON serialization."""

    def test_serializes_simple_record(self):
        """Test serialization of simple record."""
        record = {"url": "https://example.com/job/1", "title": "Engineer"}

        result = serialize_payload(record)
        assert isinstance(result, str)

        # Verify it can be deserialized
        parsed = json.loads(result)
        assert parsed["url"] == "https://example.com/job/1"
        assert parsed["title"] == "Engineer"

    def test_preserves_unicode_characters(self):
        """Test that Unicode characters are preserved."""
        record = {"title": "Développeur", "company": "Société"}

        result = serialize_payload(record)
        parsed = json.loads(result)
        assert parsed["title"] == "Développeur"
        assert parsed["company"] == "Société"

    def test_handles_nested_structures(self):
        """Test serialization of nested structures."""
        record = {
            "url": "https://example.com/job/1",
            "metadata": {"source": "linkedin", "tags": ["remote", "senior"]},
        }

        result = serialize_payload(record)
        parsed = json.loads(result)
        assert parsed["metadata"]["source"] == "linkedin"
        assert parsed["metadata"]["tags"] == ["remote", "senior"]


class TestJobUrlIdRegex:
    """Tests for LinkedIn job URL regex pattern."""

    def test_matches_standard_linkedin_url(self):
        """Test that standard LinkedIn URL is matched."""
        url = "https://www.linkedin.com/jobs/view/1234567890"
        match = JOB_URL_ID_RE.search(url)
        assert match is not None
        assert match.group(1) == "1234567890"

    def test_matches_url_with_query_params(self):
        """Test matching URL with query parameters."""
        url = "https://www.linkedin.com/jobs/view/9876543210?refId=abc"
        match = JOB_URL_ID_RE.search(url)
        assert match is not None
        assert match.group(1) == "9876543210"

    def test_matches_url_with_path_suffix(self):
        """Test matching URL with additional path segments."""
        url = "https://www.linkedin.com/jobs/view/1111111111/apply"
        match = JOB_URL_ID_RE.search(url)
        assert match is not None
        assert match.group(1) == "1111111111"

    def test_no_match_for_non_linkedin_url(self):
        """Test that non-LinkedIn URLs don't match."""
        url = "https://example.com/job/123"
        match = JOB_URL_ID_RE.search(url)
        assert match is None

    def test_no_match_for_invalid_pattern(self):
        """Test that invalid patterns don't match."""
        url = "https://www.linkedin.com/jobs/abc"
        match = JOB_URL_ID_RE.search(url)
        assert match is None
