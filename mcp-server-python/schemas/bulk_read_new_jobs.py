"""Pydantic schemas for bulk_read_new_jobs tool."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import ConfigDict, field_validator, model_validator
from schemas.common import DbPathMixin, StrictIgnoreRequest, StrictResponse
from utils.validation import DEFAULT_LIMIT, MAX_LIMIT, MIN_LIMIT

_BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/=]+$")


class BulkReadNewJobsRequest(DbPathMixin, StrictIgnoreRequest):
    """Request schema for bulk_read_new_jobs."""

    limit: int = DEFAULT_LIMIT
    cursor: Optional[str] = None

    @field_validator("limit", mode="before")
    @classmethod
    def coerce_limit_none(cls, value: Any) -> Any:
        """Treat explicit ``None`` (or missing) as 'use the default'."""
        if value is None:
            return DEFAULT_LIMIT
        return value

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        """Validate limit range."""
        if value < MIN_LIMIT:
            raise ValueError(f"Invalid limit: {value} is below minimum of {MIN_LIMIT}")
        if value > MAX_LIMIT:
            raise ValueError(f"Invalid limit: {value} exceeds maximum of {MAX_LIMIT}")
        return value

    @field_validator("cursor")
    @classmethod
    def validate_cursor(cls, value: Optional[str]) -> Optional[str]:
        """Validate cursor format if provided."""
        if value is None:
            return None
        if not value.strip():
            raise ValueError("Invalid cursor: cannot be empty")
        if not _BASE64_PATTERN.match(value):
            raise ValueError("Invalid cursor format: must be a valid base64 string")
        return value


class JobRecord(StrictResponse):
    """Job record schema returned by bulk_read_new_jobs.

    Accepts raw database rows: extra columns are silently ignored
    and empty strings are normalised to None for consistency.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    job_id: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    captured_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def empty_strings_to_none(cls, data: Any) -> Any:
        """Convert empty-string values to None for optional fields."""
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data


class BulkReadNewJobsResponse(StrictResponse):
    """Success response schema for bulk_read_new_jobs."""

    jobs: list[JobRecord]
    count: int
    has_more: bool
    next_cursor: Optional[str] = None
