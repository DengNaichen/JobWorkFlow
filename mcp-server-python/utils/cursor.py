"""
Cursor encoding/decoding utilities for pagination.

Cursors are opaque strings that encode pagination state (captured_at, id).
"""

import base64
import json
from typing import Optional, Tuple

from models.errors import create_validation_error
from pydantic import BaseModel, ConfigDict, ValidationError


class CursorPayload(BaseModel):
    """Pydantic model for cursor payload validation.

    Uses strict mode so that e.g. ``"123"`` is rejected for ``id``
    (must be a real int) and ``123`` is rejected for ``captured_at``
    (must be a real str).  Extra fields are forbidden.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    captured_at: str
    id: int


def encode_cursor(captured_at: str, record_id: int) -> str:
    """
    Encode pagination state into an opaque cursor string.

    Args:
        captured_at: ISO 8601 timestamp string
        record_id: Database record ID

    Returns:
        Base64-encoded cursor string
    """
    # Create cursor payload
    payload = {"captured_at": captured_at, "id": record_id}

    # Encode as JSON then base64
    json_str = json.dumps(payload, separators=(",", ":"))
    encoded = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

    return encoded


def _map_cursor_validation_error(error: ValidationError) -> Exception:
    """Convert a Pydantic ``ValidationError`` into a ``ToolError``.

    Preserves field names and type keywords (e.g. *string*, *integer*)
    so that existing tests continue to pass.
    """
    issues = error.errors()
    if not issues:
        return create_validation_error("Invalid cursor format")

    first = issues[0]
    field = first.get("loc", ("",))[0]
    error_type = first.get("type", "")
    msg = first.get("msg", "invalid value")

    # Pydantic says "Input should be a valid integer" / "… valid string"
    # which already contains the keywords the tests assert on.
    if error_type == "missing":
        return create_validation_error(f"Invalid cursor format: missing '{field}' field")

    # For type errors, include the Pydantic message directly so that
    # keywords like "string" and "integer" are present.
    return create_validation_error(f"Invalid cursor format: '{field}' {msg.lower()}")


def decode_cursor(cursor: Optional[str]) -> Optional[Tuple[str, int]]:
    """
    Decode an opaque cursor string into pagination state.

    Args:
        cursor: Base64-encoded cursor string (None for first page)

    Returns:
        Tuple of (captured_at, id) or None if cursor is None

    Raises:
        ToolError: If cursor is malformed or invalid
    """
    if cursor is None:
        return None

    try:
        # Decode base64
        decoded_bytes = base64.b64decode(cursor.encode("ascii"))
        json_str = decoded_bytes.decode("utf-8")

        # Parse JSON
        payload = json.loads(json_str)

        # Structural check — must be a JSON object (dict), not array/scalar
        if not isinstance(payload, dict):
            raise create_validation_error("Invalid cursor format: payload must be a JSON object")

        # Validate fields via Pydantic (strict types, no extras)
        cursor_data = CursorPayload.model_validate(payload)
        return (cursor_data.captured_at, cursor_data.id)

    except ValidationError as e:
        raise _map_cursor_validation_error(e) from e
    except json.JSONDecodeError as e:
        raise create_validation_error(f"Invalid cursor format: malformed JSON - {str(e)}") from e
    except UnicodeDecodeError as e:
        raise create_validation_error(
            f"Invalid cursor format: invalid UTF-8 encoding - {str(e)}"
        ) from e
    except (base64.binascii.Error, ValueError) as e:
        raise create_validation_error(f"Invalid cursor format: malformed base64 - {str(e)}") from e
