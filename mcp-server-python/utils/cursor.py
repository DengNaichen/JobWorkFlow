"""
Cursor encoding/decoding utilities for pagination.

Cursors are opaque strings that encode pagination state (captured_at, id).
"""

import base64
import json
from typing import Optional, Tuple
from models.errors import create_validation_error


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

        # Validate structure
        if not isinstance(payload, dict):
            raise create_validation_error("Invalid cursor format: payload must be a JSON object")

        if "captured_at" not in payload:
            raise create_validation_error("Invalid cursor format: missing 'captured_at' field")

        if "id" not in payload:
            raise create_validation_error("Invalid cursor format: missing 'id' field")

        captured_at = payload["captured_at"]
        record_id = payload["id"]

        # Validate types
        if not isinstance(captured_at, str):
            raise create_validation_error("Invalid cursor format: 'captured_at' must be a string")

        if not isinstance(record_id, int):
            raise create_validation_error("Invalid cursor format: 'id' must be an integer")

        return (captured_at, record_id)

    except json.JSONDecodeError as e:
        raise create_validation_error(f"Invalid cursor format: malformed JSON - {str(e)}") from e
    except UnicodeDecodeError as e:
        raise create_validation_error(
            f"Invalid cursor format: invalid UTF-8 encoding - {str(e)}"
        ) from e
    except (base64.binascii.Error, ValueError) as e:
        raise create_validation_error(f"Invalid cursor format: malformed base64 - {str(e)}") from e
