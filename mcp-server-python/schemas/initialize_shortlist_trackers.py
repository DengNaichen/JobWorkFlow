"""Pydantic schemas for initialize_shortlist_trackers tool."""

from __future__ import annotations

from typing import Optional

from schemas.common import StrictIgnoreRequest, StrictResponse


class InitializeShortlistTrackersRequest(StrictIgnoreRequest):
    """Request schema for initialize_shortlist_trackers."""

    limit: Optional[int] = None
    db_path: Optional[str] = None
    trackers_dir: Optional[str] = None
    force: Optional[bool] = None
    dry_run: Optional[bool] = None


class InitializeShortlistTrackersResultItem(StrictResponse):
    """Per-item result schema for initialize_shortlist_trackers."""

    id: int
    job_id: str
    tracker_path: Optional[str] = None
    action: str
    success: bool
    error: Optional[str] = None


class InitializeShortlistTrackersResponse(StrictResponse):
    """Response schema for initialize_shortlist_trackers."""

    created_count: int
    skipped_count: int
    failed_count: int
    results: list[InitializeShortlistTrackersResultItem]
