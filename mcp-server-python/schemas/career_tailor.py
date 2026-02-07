"""Pydantic schemas for career_tailor tool."""

from __future__ import annotations

from typing import Any, Optional

from schemas.common import StrictAllowRequest, StrictResponse


class CareerTailorRequest(StrictAllowRequest):
    """Request schema for career_tailor."""

    items: Any = None
    force: Optional[bool] = None
    full_resume_path: Optional[str] = None
    resume_template_path: Optional[str] = None
    applications_dir: Optional[str] = None
    pdflatex_cmd: Optional[str] = None


class CareerTailorSuccessfulItem(StrictResponse):
    """Successful finalize handoff item schema."""

    id: int
    tracker_path: str
    resume_pdf_path: str


class CareerTailorResponse(StrictResponse):
    """Response schema for career_tailor."""

    run_id: str
    total_count: int
    success_count: int
    failed_count: int
    results: list[dict[str, Any]]
    successful_items: list[CareerTailorSuccessfulItem]
    warnings: Optional[list[str]] = None
