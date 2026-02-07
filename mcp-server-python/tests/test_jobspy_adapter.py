"""
Unit tests for JobSpy adapter.

Tests the wrapper around jobspy.scrape_jobs() invocation.
"""

from unittest.mock import patch, MagicMock
import socket

import pandas as pd
import pytest

from utils.jobspy_adapter import (
    scrape_jobs_for_term,
    preflight_dns_check,
    PreflightDNSError,
    ScrapeProviderError,
)


class TestScrapeJobsForTerm:
    """Tests for scrape_jobs_for_term function."""

    def test_successful_scrape_returns_records(self):
        """Test that successful scrape returns list of records."""
        # Mock DataFrame with sample data
        mock_df = pd.DataFrame(
            [
                {
                    "job_url": "https://linkedin.com/jobs/1",
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
        )

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df):
            result = scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

        assert len(result) == 2
        assert result[0]["title"] == "Backend Engineer"
        assert result[1]["title"] == "AI Engineer"

    def test_empty_dataframe_returns_empty_list(self):
        """Test that empty DataFrame returns empty list."""
        mock_df = pd.DataFrame()

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df):
            result = scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

        assert result == []

    def test_none_dataframe_returns_empty_list(self):
        """Test that None DataFrame returns empty list."""
        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=None):
            result = scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

        assert result == []

    def test_exception_raises_provider_error(self):
        """Test that provider exceptions are surfaced to caller."""
        with patch(
            "utils.jobspy_adapter.jobspy.scrape_jobs",
            side_effect=Exception("Network error"),
        ):
            with pytest.raises(ScrapeProviderError) as exc_info:
                scrape_jobs_for_term(
                    term="backend engineer",
                    sites=["linkedin"],
                    location="Ontario, Canada",
                    results_wanted=20,
                    hours_old=2,
                )

        assert "provider scrape failed" in str(exc_info.value).lower()

    def test_calls_jobspy_with_correct_parameters(self):
        """Test that jobspy.scrape_jobs is called with correct parameters."""
        mock_df = pd.DataFrame()

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df) as mock_scrape:
            scrape_jobs_for_term(
                term="ai engineer",
                sites=["linkedin", "indeed"],
                location="Toronto, ON",
                results_wanted=50,
                hours_old=24,
            )

            mock_scrape.assert_called_once_with(
                site_name=["linkedin", "indeed"],
                search_term="ai engineer",
                location="Toronto, ON",
                results_wanted=50,
                hours_old=24,
                linkedin_fetch_description=True,
                description_format="markdown",
            )

    def test_empty_sites_list_passes_none(self):
        """Test that empty sites list passes None to jobspy."""
        mock_df = pd.DataFrame()

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df) as mock_scrape:
            scrape_jobs_for_term(
                term="backend engineer",
                sites=[],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

            # Empty list should be passed as None
            call_args = mock_scrape.call_args
            assert call_args[1]["site_name"] is None

    def test_single_site_in_list(self):
        """Test that single site in list is passed correctly."""
        mock_df = pd.DataFrame()

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df) as mock_scrape:
            scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

            call_args = mock_scrape.call_args
            assert call_args[1]["site_name"] == ["linkedin"]

    def test_multiple_sites_in_list(self):
        """Test that multiple sites are passed correctly."""
        mock_df = pd.DataFrame()

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df) as mock_scrape:
            scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin", "indeed", "glassdoor"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

            call_args = mock_scrape.call_args
            assert call_args[1]["site_name"] == ["linkedin", "indeed", "glassdoor"]

    def test_linkedin_fetch_description_always_true(self):
        """Test that linkedin_fetch_description is always set to True."""
        mock_df = pd.DataFrame()

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df) as mock_scrape:
            scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

            call_args = mock_scrape.call_args
            assert call_args[1]["linkedin_fetch_description"] is True

    def test_description_format_always_markdown(self):
        """Test that description_format is always set to markdown."""
        mock_df = pd.DataFrame()

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df) as mock_scrape:
            scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

            call_args = mock_scrape.call_args
            assert call_args[1]["description_format"] == "markdown"

    def test_dataframe_to_dict_conversion(self):
        """Test that DataFrame is correctly converted to list of dicts."""
        mock_df = pd.DataFrame(
            [
                {"id": 1, "title": "Job 1", "company": "Company A"},
                {"id": 2, "title": "Job 2", "company": "Company B"},
                {"id": 3, "title": "Job 3", "company": "Company C"},
            ]
        )

        with patch("utils.jobspy_adapter.jobspy.scrape_jobs", return_value=mock_df):
            result = scrape_jobs_for_term(
                term="backend engineer",
                sites=["linkedin"],
                location="Ontario, Canada",
                results_wanted=20,
                hours_old=2,
            )

        assert len(result) == 3
        assert all(isinstance(record, dict) for record in result)
        assert result[0]["id"] == 1
        assert result[1]["title"] == "Job 2"
        assert result[2]["company"] == "Company C"


class TestPreflightDNSCheck:
    """Tests for preflight_dns_check function."""

    def test_successful_dns_resolution(self):
        """Test that successful DNS resolution returns without error."""
        with patch("utils.jobspy_adapter.socket.gethostbyname", return_value="1.2.3.4"):
            # Should not raise any exception
            preflight_dns_check("www.linkedin.com")

    def test_dns_failure_raises_preflight_error(self):
        """Test that DNS failure after retries raises PreflightDNSError."""
        with patch(
            "utils.jobspy_adapter.socket.gethostbyname",
            side_effect=socket.gaierror("Name resolution failed"),
        ):
            with pytest.raises(PreflightDNSError) as exc_info:
                preflight_dns_check(
                    "invalid.host.example",
                    retry_count=2,
                    retry_sleep_seconds=0.01,
                    retry_backoff=1.0,
                )

            assert "DNS preflight failed" in str(exc_info.value)
            assert "after 2 attempts" in str(exc_info.value)

    def test_retry_count_respected(self):
        """Test that retry_count parameter is respected."""
        mock_gethostbyname = MagicMock(side_effect=socket.gaierror("Failed"))

        with patch("utils.jobspy_adapter.socket.gethostbyname", mock_gethostbyname):
            with patch("utils.jobspy_adapter.time.sleep"):
                with pytest.raises(PreflightDNSError):
                    preflight_dns_check(
                        "test.host",
                        retry_count=5,
                        retry_sleep_seconds=0.01,
                        retry_backoff=1.0,
                    )

                # Should be called exactly retry_count times
                assert mock_gethostbyname.call_count == 5

    def test_retry_with_exponential_backoff(self):
        """Test that retry uses exponential backoff for sleep duration."""
        mock_sleep = MagicMock()

        with patch(
            "utils.jobspy_adapter.socket.gethostbyname", side_effect=socket.gaierror("Failed")
        ):
            with patch("utils.jobspy_adapter.time.sleep", mock_sleep):
                with pytest.raises(PreflightDNSError):
                    preflight_dns_check(
                        "test.host",
                        retry_count=4,
                        retry_sleep_seconds=1.0,
                        retry_backoff=2.0,
                    )

                # Should sleep 3 times (retry_count - 1)
                assert mock_sleep.call_count == 3

                # Check exponential backoff: 1.0, 2.0, 4.0
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_calls[0] == 1.0
                assert sleep_calls[1] == 2.0
                assert sleep_calls[2] == 4.0

    def test_success_on_second_attempt(self):
        """Test that function succeeds if DNS resolves on a retry."""
        call_count = 0

        def mock_gethostbyname(_host):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise socket.gaierror("First attempt fails")
            return "1.2.3.4"

        with patch("utils.jobspy_adapter.socket.gethostbyname", side_effect=mock_gethostbyname):
            with patch("utils.jobspy_adapter.time.sleep"):
                # Should succeed without raising
                preflight_dns_check(
                    "test.host",
                    retry_count=3,
                    retry_sleep_seconds=0.01,
                    retry_backoff=1.0,
                )

        assert call_count == 2

    def test_success_on_last_attempt(self):
        """Test that function succeeds if DNS resolves on the last retry."""
        call_count = 0

        def mock_gethostbyname(_host):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise socket.gaierror("Attempt fails")
            return "1.2.3.4"

        with patch("utils.jobspy_adapter.socket.gethostbyname", side_effect=mock_gethostbyname):
            with patch("utils.jobspy_adapter.time.sleep"):
                # Should succeed on the 3rd attempt
                preflight_dns_check(
                    "test.host",
                    retry_count=3,
                    retry_sleep_seconds=0.01,
                    retry_backoff=1.0,
                )

        assert call_count == 3

    def test_handles_socket_herror(self):
        """Test that socket.herror is handled correctly."""
        with patch(
            "utils.jobspy_adapter.socket.gethostbyname",
            side_effect=socket.herror("Host error"),
        ):
            with pytest.raises(PreflightDNSError):
                preflight_dns_check(
                    "test.host",
                    retry_count=1,
                    retry_sleep_seconds=0.01,
                    retry_backoff=1.0,
                )

    def test_handles_os_error(self):
        """Test that OSError is handled correctly."""
        with patch(
            "utils.jobspy_adapter.socket.gethostbyname",
            side_effect=OSError("Network unreachable"),
        ):
            with pytest.raises(PreflightDNSError):
                preflight_dns_check(
                    "test.host",
                    retry_count=1,
                    retry_sleep_seconds=0.01,
                    retry_backoff=1.0,
                )

    def test_default_parameters(self):
        """Test that default parameters work correctly."""
        with patch("utils.jobspy_adapter.socket.gethostbyname", return_value="1.2.3.4"):
            # Should use defaults: retry_count=3, retry_sleep_seconds=30.0, retry_backoff=2.0
            preflight_dns_check("www.linkedin.com")

    def test_zero_backoff_multiplier(self):
        """Test behavior with backoff multiplier of 1.0 (no exponential growth)."""
        mock_sleep = MagicMock()

        with patch(
            "utils.jobspy_adapter.socket.gethostbyname", side_effect=socket.gaierror("Failed")
        ):
            with patch("utils.jobspy_adapter.time.sleep", mock_sleep):
                with pytest.raises(PreflightDNSError):
                    preflight_dns_check(
                        "test.host",
                        retry_count=3,
                        retry_sleep_seconds=5.0,
                        retry_backoff=1.0,
                    )

                # With backoff=1.0, sleep should be constant
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert all(duration == 5.0 for duration in sleep_calls)

    def test_error_message_includes_host_and_retry_count(self):
        """Test that error message includes host and retry count."""
        with patch(
            "utils.jobspy_adapter.socket.gethostbyname",
            side_effect=socket.gaierror("Failed"),
        ):
            with pytest.raises(PreflightDNSError) as exc_info:
                preflight_dns_check(
                    "example.com",
                    retry_count=7,
                    retry_sleep_seconds=0.01,
                    retry_backoff=1.0,
                )

            error_message = str(exc_info.value)
            assert "example.com" in error_message
            assert "7 attempts" in error_message
