"""Pydantic schemas for update_tracker_status tool."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from schemas.common import StrictAllowRequest, StrictResponse


class UpdateTrackerStatusRequest(StrictAllowRequest):
    """Request schema for update_tracker_status."""

    tracker_path: str
    target_status: str
    dry_run: Optional[bool] = None
    force: Optional[bool] = None


class UpdateTrackerStatusResponse(StrictResponse):
    """Response schema for update_tracker_status."""

    tracker_path: str
    previous_status: str
    target_status: str
    action: str
    success: bool
    dry_run: bool
    error: Optional[str] = None
    guardrail_check_passed: Optional[bool] = None
    warnings: list[str] = Field(default_factory=list)
