"""Pydantic schemas for finalize_resume_batch tool."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import model_validator

from schemas.common import DbPathMixin, RunIdMixin, StrictIgnoreRequest, StrictResponse


class FinalizeResumeBatchRequest(DbPathMixin, RunIdMixin, StrictIgnoreRequest):
    """Request schema for finalize_resume_batch."""

    items: Any
    dry_run: Optional[bool] = None

    @model_validator(mode="after")
    def apply_defaults(self) -> "FinalizeResumeBatchRequest":
        if self.dry_run is None:
            self.dry_run = False
        return self


class FinalizeResumeBatchResultItem(StrictResponse):
    """Per-item result schema for finalize_resume_batch."""

    id: Any
    tracker_path: Any
    resume_pdf_path: Optional[str] = None
    action: str
    success: bool
    error: Optional[str] = None


class FinalizeResumeBatchResponse(StrictResponse):
    """Response schema for finalize_resume_batch."""

    run_id: str
    finalized_count: int
    failed_count: int
    dry_run: bool
    warnings: Optional[list[str]] = None
    results: list[FinalizeResumeBatchResultItem]
