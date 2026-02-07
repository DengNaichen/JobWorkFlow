"""Unit tests for bulk_update_job_status Pydantic schemas."""

import pytest
from pydantic import ValidationError

from models.errors import ErrorCode
from schemas.bulk_update_job_status import BulkUpdateJobStatusRequest
from utils.pydantic_error_mapper import map_pydantic_validation_error


class TestBulkUpdateJobStatusRequest:
    def test_missing_updates_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            BulkUpdateJobStatusRequest.model_validate({})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "updates" in mapped.message.lower()

    def test_extra_fields_ignored_for_compatibility(self):
        model = BulkUpdateJobStatusRequest.model_validate(
            {"updates": [{"id": 1, "status": "new"}], "unknown": "ignored"}
        )
        assert len(model.updates) == 1

    def test_invalid_db_path_type_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            BulkUpdateJobStatusRequest.model_validate({"updates": [], "db_path": 123})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "db_path" in mapped.message.lower()

