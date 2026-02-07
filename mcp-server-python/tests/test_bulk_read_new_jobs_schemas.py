"""Unit tests for bulk_read_new_jobs Pydantic schemas."""

import pytest
from pydantic import ValidationError

from schemas.bulk_read_new_jobs import BulkReadNewJobsRequest
from utils.validation import DEFAULT_LIMIT
from utils.pydantic_error_mapper import map_pydantic_validation_error
from models.errors import ErrorCode


class TestBulkReadNewJobsRequest:
    def test_defaults_limit_when_missing(self):
        model = BulkReadNewJobsRequest.model_validate({})
        assert model.limit == DEFAULT_LIMIT
        assert model.cursor is None
        assert model.db_path is None

    def test_ignores_unknown_fields_for_compatibility(self):
        model = BulkReadNewJobsRequest.model_validate({"extra_field": "ignored"})
        assert model.limit == DEFAULT_LIMIT

    def test_invalid_limit_type_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            BulkReadNewJobsRequest.model_validate({"limit": "50"})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "limit" in mapped.message.lower()
