"""Unit tests for scrape_jobs Pydantic schemas."""

import pytest
from pydantic import ValidationError

from models.errors import ErrorCode
from schemas.scrape_jobs import ScrapeJobsRequest
from utils.pydantic_error_mapper import map_pydantic_validation_error


class TestScrapeJobsRequest:
    def test_allows_unknown_fields_for_legacy_validator_path(self):
        model = ScrapeJobsRequest.model_validate({"unknown_param": "value"})
        assert model.model_extra == {"unknown_param": "value"}

    def test_invalid_bool_field_type_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapeJobsRequest.model_validate({"dry_run": "yes"})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "dry_run" in mapped.message.lower()
