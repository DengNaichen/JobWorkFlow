"""Convert Pydantic validation errors to project ToolError contract."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from models.errors import ToolError, create_validation_error


def _loc_to_field(loc: tuple[Any, ...]) -> str:
    parts = [str(part) for part in loc if part != "__root__"]
    return ".".join(parts)


def _clean_pydantic_message(message: str) -> str:
    if message.startswith("Value error, "):
        return message[len("Value error, ") :]
    return message


def map_pydantic_validation_error(error: ValidationError) -> ToolError:
    """Map Pydantic ValidationError to existing validation ToolError."""
    issues = error.errors()
    if not issues:
        return create_validation_error("Invalid input")

    first = issues[0]
    field = _loc_to_field(first.get("loc", ()))
    message = _clean_pydantic_message(first.get("msg", "Invalid input"))

    if field:
        return create_validation_error(f"Invalid {field}: {message}")
    return create_validation_error(message)
