"""Unit tests for initialize_shortlist_trackers Pydantic schemas."""

import pytest
from pydantic import ValidationError

from models.errors import ErrorCode
from schemas.initialize_shortlist_trackers import InitializeShortlistTrackersRequest
from utils.pydantic_error_mapper import map_pydantic_validation_error


class TestInitializeShortlistTrackersRequest:
    def test_defaults_preserved_when_args_missing(self):
        model = InitializeShortlistTrackersRequest.model_validate({})
        assert model.limit is None
        assert model.db_path is None
        assert model.trackers_dir is None
        assert model.force is None
        assert model.dry_run is None

    def test_invalid_limit_type_maps_to_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            InitializeShortlistTrackersRequest.model_validate({"limit": "10"})

        mapped = map_pydantic_validation_error(exc_info.value)
        assert mapped.code == ErrorCode.VALIDATION_ERROR
        assert "limit" in mapped.message.lower()

