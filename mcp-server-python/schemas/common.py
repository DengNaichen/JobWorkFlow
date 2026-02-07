"""Shared schema primitives for MCP tool request/response models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


def validate_optional_non_empty_str(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate optional string fields that cannot be empty/whitespace."""
    if value is None:
        return None
    if not value.strip():
        raise ValueError(f"Invalid {field_name}: cannot be empty")
    return value


class StrictIgnoreRequest(BaseModel):
    """Request base with strict typing and ignored unknown fields."""

    model_config = ConfigDict(extra="ignore", strict=True)


class StrictAllowRequest(BaseModel):
    """Request base with strict typing and preserved unknown fields."""

    model_config = ConfigDict(extra="allow", strict=True)


class StrictResponse(BaseModel):
    """Response/result base with strict typing and forbidden unknown fields."""

    model_config = ConfigDict(extra="forbid")


class DbPathMixin(BaseModel):
    """Reusable db_path field validation."""

    db_path: Optional[str] = None

    @field_validator("db_path")
    @classmethod
    def validate_db_path(cls, value: Optional[str]) -> Optional[str]:
        return validate_optional_non_empty_str(value, "db_path")


class RunIdMixin(BaseModel):
    """Reusable run_id field validation."""

    run_id: Optional[str] = None

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: Optional[str]) -> Optional[str]:
        return validate_optional_non_empty_str(value, "run_id")
