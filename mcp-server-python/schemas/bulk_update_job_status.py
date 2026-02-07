"""Pydantic schemas for bulk_update_job_status tool."""

from __future__ import annotations

from typing import Any, Optional

from schemas.common import DbPathMixin, StrictIgnoreRequest, StrictResponse


class BulkUpdateJobStatusRequest(DbPathMixin, StrictIgnoreRequest):
    """Request schema for bulk_update_job_status."""

    updates: list[Any]


class BulkUpdateJobStatusResultItem(StrictResponse):
    """Per-item result schema for bulk_update_job_status."""

    id: int | str
    success: bool
    error: Optional[str] = None


class BulkUpdateJobStatusResponse(StrictResponse):
    """Success/failure response schema for bulk_update_job_status."""

    updated_count: int
    failed_count: int
    results: list[BulkUpdateJobStatusResultItem]
