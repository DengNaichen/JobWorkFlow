"""Pydantic schemas for scrape_jobs tool."""

from __future__ import annotations

from typing import Optional

from schemas.common import StrictAllowRequest, StrictResponse


class ScrapeJobsRequest(StrictAllowRequest):
    """Request schema for scrape_jobs."""

    terms: Optional[list] = None
    location: Optional[str] = None
    sites: Optional[list] = None
    results_wanted: Optional[int] = None
    hours_old: Optional[int] = None
    db_path: Optional[str] = None
    status: Optional[str] = None
    require_description: Optional[bool] = None
    preflight_host: Optional[str] = None
    retry_count: Optional[int] = None
    retry_sleep_seconds: Optional[float] = None
    retry_backoff: Optional[float] = None
    save_capture_json: Optional[bool] = None
    capture_dir: Optional[str] = None
    dry_run: Optional[bool] = None


class ScrapeJobsTermResult(StrictResponse):
    """Per-term result schema for scrape_jobs."""

    term: str
    success: bool
    fetched_count: int
    cleaned_count: int
    inserted_count: int
    duplicate_count: int
    skipped_no_url: int
    skipped_no_description: int
    capture_path: Optional[str] = None
    error: Optional[str] = None


class ScrapeJobsTotals(StrictResponse):
    """Aggregated totals schema for scrape_jobs."""

    term_count: int
    successful_terms: int
    failed_terms: int
    fetched_count: int
    cleaned_count: int
    inserted_count: int
    duplicate_count: int
    skipped_no_url: int
    skipped_no_description: int


class ScrapeJobsResponse(StrictResponse):
    """Response schema for scrape_jobs."""

    run_id: str
    started_at: str
    finished_at: str
    duration_ms: int
    dry_run: bool
    results: list[ScrapeJobsTermResult]
    totals: ScrapeJobsTotals
