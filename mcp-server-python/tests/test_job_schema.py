"""
Unit tests for job schema mapping.

Tests mapping of database rows to the fixed output schema with
consistent handling of missing values and JSON serialization.
"""

import json
from models.job import to_job_schema


class TestToJobSchema:
    """Tests for to_job_schema function."""

    def test_complete_row_mapping(self):
        """Test mapping a complete row with all fields present."""
        row = {
            "id": 123,
            "job_id": "4368663835",
            "title": "Machine Learning Engineer",
            "company": "Example Corp",
            "description": "Exciting ML role with great benefits",
            "url": "https://www.linkedin.com/jobs/view/4368663835/",
            "location": "Toronto, ON",
            "source": "linkedin",
            "status": "new",
            "captured_at": "2026-02-04T03:47:36.966Z",
        }

        result = to_job_schema(row)

        # All fields should be present
        assert result["id"] == 123
        assert result["job_id"] == "4368663835"
        assert result["title"] == "Machine Learning Engineer"
        assert result["company"] == "Example Corp"
        assert result["description"] == "Exciting ML role with great benefits"
        assert result["url"] == "https://www.linkedin.com/jobs/view/4368663835/"
        assert result["location"] == "Toronto, ON"
        assert result["source"] == "linkedin"
        assert result["status"] == "new"
        assert result["captured_at"] == "2026-02-04T03:47:36.966Z"

    def test_missing_fields_return_none(self):
        """Test that missing fields are returned as None."""
        row = {
            "id": 456,
            "url": "https://example.com/job",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # Present fields should have values
        assert result["id"] == 456
        assert result["url"] == "https://example.com/job"
        assert result["status"] == "new"
        assert result["captured_at"] == "2026-02-05T10:00:00.000Z"

        # Missing fields should be None
        assert result["job_id"] is None
        assert result["title"] is None
        assert result["company"] is None
        assert result["description"] is None
        assert result["location"] is None
        assert result["source"] is None

    def test_null_fields_return_none(self):
        """Test that null field values are returned as None."""
        row = {
            "id": 789,
            "job_id": None,
            "title": None,
            "company": None,
            "description": None,
            "url": "https://example.com/job",
            "location": None,
            "source": None,
            "status": "new",
            "captured_at": None,
        }

        result = to_job_schema(row)

        # All null fields should be None
        assert result["id"] == 789
        assert result["job_id"] is None
        assert result["title"] is None
        assert result["company"] is None
        assert result["description"] is None
        assert result["url"] == "https://example.com/job"
        assert result["location"] is None
        assert result["source"] is None
        assert result["status"] == "new"
        assert result["captured_at"] is None

    def test_empty_strings_return_none(self):
        """Test that empty string values are converted to None for consistency."""
        row = {
            "id": 101,
            "job_id": "",
            "title": "",
            "company": "",
            "description": "",
            "url": "https://example.com/job",
            "location": "",
            "source": "",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # Empty strings should be converted to None
        assert result["id"] == 101
        assert result["job_id"] is None
        assert result["title"] is None
        assert result["company"] is None
        assert result["description"] is None
        assert result["url"] == "https://example.com/job"
        assert result["location"] is None
        assert result["source"] is None
        assert result["status"] == "new"
        assert result["captured_at"] == "2026-02-05T10:00:00.000Z"

    def test_schema_stability_no_extra_fields(self):
        """Test that only fixed schema fields are included, no extras."""
        row = {
            "id": 202,
            "job_id": "12345",
            "title": "Software Engineer",
            "company": "Tech Co",
            "description": "Great job",
            "url": "https://example.com/job",
            "location": "San Francisco, CA",
            "source": "indeed",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
            # Extra fields that should NOT appear in output
            "extra_field": "should not appear",
            "payload_json": '{"data": "value"}',
            "created_at": "2026-02-05T09:00:00.000Z",
        }

        result = to_job_schema(row)

        # Only fixed schema fields should be present
        expected_fields = {
            "id",
            "job_id",
            "title",
            "company",
            "description",
            "url",
            "location",
            "source",
            "status",
            "captured_at",
        }
        assert set(result.keys()) == expected_fields

        # Extra fields should not be present
        assert "extra_field" not in result
        assert "payload_json" not in result
        assert "created_at" not in result

    def test_json_serializability(self):
        """Test that output is JSON-serializable."""
        row = {
            "id": 303,
            "job_id": "67890",
            "title": "Data Scientist",
            "company": "Data Corp",
            "description": "Analyze data",
            "url": "https://example.com/job",
            "location": "New York, NY",
            "source": "glassdoor",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # Should be JSON-serializable without errors
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed == result

    def test_json_serializability_with_none_values(self):
        """Test that output with None values is JSON-serializable."""
        row = {
            "id": 404,
            "job_id": None,
            "title": None,
            "company": None,
            "description": None,
            "url": "https://example.com/job",
            "location": None,
            "source": None,
            "status": "new",
            "captured_at": None,
        }

        result = to_job_schema(row)

        # Should be JSON-serializable with None values
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # None should be serialized as null
        assert "null" in json_str

        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed == result

    def test_special_characters_in_strings(self):
        """Test that special characters in strings are handled correctly."""
        row = {
            "id": 505,
            "job_id": "abc-123",
            "title": "Engineer & Developer",
            "company": 'Company "Name" Inc.',
            "description": "Job with\nnewlines\tand\ttabs",
            "url": "https://example.com/job?id=123&ref=abc",
            "location": "City, ST",
            "source": "source/name",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # Special characters should be preserved
        assert result["title"] == "Engineer & Developer"
        assert result["company"] == 'Company "Name" Inc.'
        assert result["description"] == "Job with\nnewlines\tand\ttabs"
        assert result["url"] == "https://example.com/job?id=123&ref=abc"

        # Should still be JSON-serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed == result

    def test_unicode_characters(self):
        """Test that unicode characters are handled correctly."""
        row = {
            "id": 606,
            "job_id": "unicode-123",
            "title": "Développeur Senior",
            "company": "Société Française",
            "description": "Travail intéressant avec café ☕",
            "url": "https://example.com/job",
            "location": "Montréal, QC",
            "source": "linkedin",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # Unicode should be preserved
        assert result["title"] == "Développeur Senior"
        assert result["company"] == "Société Française"
        assert result["description"] == "Travail intéressant avec café ☕"
        assert result["location"] == "Montréal, QC"

        # Should be JSON-serializable
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed == result

    def test_long_description(self):
        """Test that long descriptions are handled correctly."""
        long_text = "A" * 10000  # 10k character description
        row = {
            "id": 707,
            "job_id": "long-123",
            "title": "Job Title",
            "company": "Company",
            "description": long_text,
            "url": "https://example.com/job",
            "location": "Location",
            "source": "source",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # Long text should be preserved
        assert result["description"] == long_text
        assert len(result["description"]) == 10000

        # Should still be JSON-serializable
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_integer_id_types(self):
        """Test that integer IDs are preserved as integers."""
        row = {
            "id": 808,
            "job_id": "12345",
            "title": "Job",
            "company": "Company",
            "description": "Description",
            "url": "https://example.com/job",
            "location": "Location",
            "source": "source",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # id should be an integer
        assert isinstance(result["id"], int)
        assert result["id"] == 808

        # job_id should be a string
        assert isinstance(result["job_id"], str)
        assert result["job_id"] == "12345"

    def test_consistent_field_order(self):
        """Test that output fields are in consistent order."""
        row = {
            "id": 909,
            "job_id": "order-test",
            "title": "Title",
            "company": "Company",
            "description": "Description",
            "url": "https://example.com/job",
            "location": "Location",
            "source": "source",
            "status": "new",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result1 = to_job_schema(row)
        result2 = to_job_schema(row)

        # Field order should be consistent
        assert list(result1.keys()) == list(result2.keys())

        # Expected order based on schema definition
        expected_order = [
            "id",
            "job_id",
            "title",
            "company",
            "description",
            "url",
            "location",
            "source",
            "status",
            "captured_at",
        ]
        assert list(result1.keys()) == expected_order


class TestSchemaRequirements:
    """Tests for specific requirements validation."""

    def test_requirement_3_1_all_fixed_fields_included(self):
        """Requirement 3.1: Include all fixed fields."""
        row = {
            "id": 1,
            "job_id": "test",
            "title": "test",
            "company": "test",
            "description": "test",
            "url": "test",
            "location": "test",
            "source": "test",
            "status": "test",
            "captured_at": "test",
        }

        result = to_job_schema(row)

        # All 10 fixed fields must be present
        required_fields = [
            "id",
            "job_id",
            "title",
            "company",
            "description",
            "url",
            "location",
            "source",
            "status",
            "captured_at",
        ]
        for field in required_fields:
            assert field in result

    def test_requirement_3_2_no_arbitrary_columns(self):
        """Requirement 3.2: Do not include arbitrary additional columns."""
        row = {
            "id": 1,
            "job_id": "test",
            "title": "test",
            "company": "test",
            "description": "test",
            "url": "test",
            "location": "test",
            "source": "test",
            "status": "test",
            "captured_at": "test",
            "extra_column_1": "should not appear",
            "extra_column_2": "should not appear",
            "payload_json": "should not appear",
        }

        result = to_job_schema(row)

        # Only fixed fields should be present
        assert len(result) == 10
        assert "extra_column_1" not in result
        assert "extra_column_2" not in result
        assert "payload_json" not in result

    def test_requirement_3_3_missing_values_consistent(self):
        """Requirement 3.3: Handle missing values consistently."""
        # Test with missing fields
        row1 = {"id": 1, "url": "test", "status": "new"}
        result1 = to_job_schema(row1)

        # Test with None fields
        row2 = {
            "id": 1,
            "job_id": None,
            "title": None,
            "company": None,
            "description": None,
            "url": "test",
            "location": None,
            "source": None,
            "status": "new",
            "captured_at": None,
        }
        result2 = to_job_schema(row2)

        # Both should return None for missing/null fields
        assert result1["job_id"] is None
        assert result2["job_id"] is None
        assert result1["title"] is None
        assert result2["title"] is None

    def test_requirement_3_4_json_serializable(self):
        """Requirement 3.4: All fields are JSON-serializable."""
        row = {
            "id": 1,
            "job_id": "test",
            "title": "test",
            "company": "test",
            "description": "test",
            "url": "test",
            "location": "test",
            "source": "test",
            "status": "test",
            "captured_at": "2026-02-05T10:00:00.000Z",
        }

        result = to_job_schema(row)

        # Should serialize without errors
        try:
            json.dumps(result)
            serializable = True
        except (TypeError, ValueError):
            serializable = False

        assert serializable

    def test_requirement_3_5_stable_schema_contract(self):
        """Requirement 3.5: Maintain stable schema contract."""
        row = {
            "id": 1,
            "job_id": "test",
            "title": "test",
            "company": "test",
            "description": "test",
            "url": "test",
            "location": "test",
            "source": "test",
            "status": "test",
            "captured_at": "test",
        }

        # Call multiple times
        results = [to_job_schema(row) for _ in range(5)]

        # All results should have identical structure
        for result in results:
            assert set(result.keys()) == set(results[0].keys())
            assert list(result.keys()) == list(results[0].keys())
