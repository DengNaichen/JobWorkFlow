"""Unit tests for finalize_resume_batch Pydantic schemas."""

import pytest
from pydantic import ValidationError

from models.errors import ErrorCode
from schemas.finalize_resume_batch import FinalizeResumeBatchRequest
from utils.pydantic_error_mapper import map_pydantic_validation_error


class TestFinalizeResumeBatchRequest:
    def test_missing_items_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            FinalizeResumeBatchRequest.model_validate({})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "items" in mapped.message.lower()

    def test_default_dry_run_false(self):
        model = FinalizeResumeBatchRequest.model_validate({"items": []})
        assert model.dry_run is False

    def test_invalid_run_id_empty_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            FinalizeResumeBatchRequest.model_validate({"items": [], "run_id": "   "})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "run_id" in mapped.message.lower()

