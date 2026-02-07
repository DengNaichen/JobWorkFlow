"""
JobSpy adapter for scraping job postings.

This module wraps the jobspy.scrape_jobs() invocation to provide a clean
interface for the scrape_jobs MCP tool. It handles per-term configuration
and returns raw source records.

Requirements: 3.1, 3.3, 3.5
"""

import socket
import time
from typing import Any

import jobspy


class PreflightDNSError(Exception):
    """Raised when DNS preflight check fails after all retries."""

    pass


class ScrapeProviderError(Exception):
    """Raised when upstream provider/jobspy scraping fails for a term."""

    pass


def preflight_dns_check(
    host: str,
    retry_count: int = 3,
    retry_sleep_seconds: float = 30.0,
    retry_backoff: float = 2.0,
) -> None:
    """
    Perform DNS preflight check with retry and backoff.

    This function attempts to resolve the given host to verify network
    connectivity before scraping. If the resolution fails, it retries
    according to the specified parameters.

    Args:
        host: Hostname to resolve (e.g., "www.linkedin.com")
        retry_count: Number of retry attempts (default: 3)
        retry_sleep_seconds: Base sleep duration between retries in seconds (default: 30)
        retry_backoff: Backoff multiplier for sleep duration (default: 2.0)

    Raises:
        PreflightDNSError: If DNS resolution fails after all retry attempts

    Requirements:
        - 2.1: Resolve preflight_host before scraping each term
        - 2.2: Retry according to retry_count, retry_sleep_seconds, and retry_backoff
        - 2.3: Mark term as failed/skipped on preflight exhaustion
        - 2.4: Include per-term preflight failures in structured results
        - 2.5: Do not crash entire run due to one term's preflight failure
    """
    attempt = 0
    sleep_duration = retry_sleep_seconds

    while attempt < retry_count:
        try:
            # Attempt to resolve the hostname
            socket.gethostbyname(host)
            # Success - return immediately
            return
        except (socket.gaierror, socket.herror, OSError) as e:
            attempt += 1
            if attempt >= retry_count:
                # All retries exhausted
                raise PreflightDNSError(
                    f"DNS preflight failed for {host} after {retry_count} attempts"
                ) from e

            # Sleep before next retry with exponential backoff
            time.sleep(sleep_duration)
            sleep_duration *= retry_backoff


def scrape_jobs_for_term(
    term: str,
    sites: list[str],
    location: str,
    results_wanted: int,
    hours_old: int,
) -> list[dict[str, Any]]:
    """
    Scrape jobs for a single search term using JobSpy.

    Args:
        term: Search term (e.g., "backend engineer")
        sites: List of site names to scrape (e.g., ["linkedin"])
        location: Search location (e.g., "Ontario, Canada")
        results_wanted: Number of results to fetch per term
        hours_old: Only return jobs posted within the last N hours

    Returns:
        List of raw source records as dictionaries. Returns empty list only
        when provider call succeeds but yields no rows.

    Raises:
        ScrapeProviderError: If provider call fails (network/API/provider issue)

    Requirements:
        - 3.1: Accept per-term config and return raw source records
        - 3.3: Collect per-term fetched_count before cleaning/filtering
        - 3.5: Support configurable site list with default linkedin
    """
    try:
        # Call jobspy.scrape_jobs with the provided configuration
        df = jobspy.scrape_jobs(
            site_name=sites or None,
            search_term=term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            linkedin_fetch_description=True,
            description_format="markdown",
        )

        # Handle empty or None results
        if df is None or df.empty:
            return []

        # Convert DataFrame to list of dictionaries
        records = df.to_dict(orient="records")
        return records

    except Exception as e:
        # Surface provider failures so caller can mark per-term failure instead
        # of silently reporting a successful zero-result scrape.
        raise ScrapeProviderError(f"Provider scrape failed for term '{term}': {e}") from e
