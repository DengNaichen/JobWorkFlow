"""Unit tests for career_tailor Pydantic schemas."""

import pytest
from pydantic import ValidationError

from models.errors import ErrorCode
from schemas.career_tailor import CareerTailorRequest
from utils.pydantic_error_mapper import map_pydantic_validation_error


class TestCareerTailorRequest:
    def test_missing_items_defaults_none_for_legacy_validation(self):
        model = CareerTailorRequest.model_validate({})
        assert model.items is None

    def test_unknown_field_is_preserved_for_legacy_unknown_check(self):
        model = CareerTailorRequest.model_validate({"items": [], "unknown_field": "x"})
        assert model.model_extra == {"unknown_field": "x"}

    def test_invalid_force_type_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            CareerTailorRequest.model_validate({"items": [], "force": "yes"})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "force" in mapped.message.lower()
