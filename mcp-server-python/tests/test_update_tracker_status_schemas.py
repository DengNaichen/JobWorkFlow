"""Unit tests for update_tracker_status Pydantic schemas."""

import pytest
from pydantic import ValidationError

from models.errors import ErrorCode
from schemas.update_tracker_status import UpdateTrackerStatusRequest
from utils.pydantic_error_mapper import map_pydantic_validation_error


class TestUpdateTrackerStatusRequest:
    def test_allows_unknown_fields_for_legacy_unknown_validation(self):
        model = UpdateTrackerStatusRequest.model_validate(
            {"tracker_path": "t.md", "target_status": "Reviewed", "unknown_param": "x"}
        )
        assert model.model_extra == {"unknown_param": "x"}

    def test_missing_target_status_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            UpdateTrackerStatusRequest.model_validate({"tracker_path": "t.md"})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "target_status" in mapped.message.lower()

