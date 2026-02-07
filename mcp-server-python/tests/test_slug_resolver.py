"""
Unit tests for slug resolution utilities.

Tests slug extraction from resume_path, fallback generation, and
deterministic resolution logic for career_tailor tool.
"""

import pytest

from utils.slug_resolver import (
    extract_slug_from_resume_path,
    generate_fallback_slug,
    resolve_application_slug,
    _normalize_text,
)


class TestNormalizeText:
    """Tests for _normalize_text helper function."""

    def test_normalize_simple_text(self):
        """Test normalizing simple text with spaces."""
        assert _normalize_text("General Motors") == "general_motors"
        assert _normalize_text("Amazon Web Services") == "amazon_web_services"

    def test_normalize_special_characters(self):
        """Test normalizing text with special characters."""
        assert _normalize_text("L'Oréal") == "l_or_al"
        assert _normalize_text("AT&T Inc.") == "at_t_inc"
        assert _normalize_text("Procter & Gamble") == "procter_gamble"

    def test_normalize_slashes_and_hyphens(self):
        """Test normalizing text with slashes and hyphens."""
        assert _normalize_text("Backend/Full-Stack Developer") == "backend_full_stack_developer"
        assert _normalize_text("AI/ML Engineer") == "ai_ml_engineer"

    def test_normalize_consecutive_special_chars(self):
        """Test that consecutive special characters collapse to single underscore."""
        assert _normalize_text("Test  --  Multiple") == "test_multiple"
        assert _normalize_text("A & B / C") == "a_b_c"

    def test_normalize_leading_trailing_special_chars(self):
        """Test that leading/trailing special characters are stripped."""
        assert _normalize_text("  Amazon  ") == "amazon"
        assert _normalize_text("--Meta--") == "meta"
        assert _normalize_text("(Google)") == "google"

    def test_normalize_already_normalized(self):
        """Test normalizing already normalized text."""
        assert _normalize_text("amazon") == "amazon"
        assert _normalize_text("software_engineer") == "software_engineer"

    def test_normalize_numbers(self):
        """Test that numbers are preserved."""
        assert _normalize_text("Company 123") == "company_123"
        assert _normalize_text("Engineer v2.0") == "engineer_v2_0"


class TestExtractSlugFromResumePath:
    """Tests for extract_slug_from_resume_path function."""

    def test_extract_from_wiki_link_format(self):
        """Test extracting slug from wiki-link format resume_path."""
        resume_path = "[[data/applications/amazon-3629/resume/resume.pdf]]"
        assert extract_slug_from_resume_path(resume_path) == "amazon-3629"

    def test_extract_from_plain_path_format(self):
        """Test extracting slug from plain path format resume_path."""
        resume_path = "data/applications/meta-100/resume/resume.pdf"
        assert extract_slug_from_resume_path(resume_path) == "meta-100"

    def test_extract_complex_slug(self):
        """Test extracting complex slug with underscores."""
        resume_path = "[[data/applications/general_motors-3711/resume/resume.pdf]]"
        assert extract_slug_from_resume_path(resume_path) == "general_motors-3711"

    def test_extract_slug_with_position(self):
        """Test extracting slug that includes position."""
        resume_path = "data/applications/google-staff_engineer/resume/resume.pdf"
        assert extract_slug_from_resume_path(resume_path) == "google-staff_engineer"

    def test_extract_from_none_returns_none(self):
        """Test that None input returns None."""
        assert extract_slug_from_resume_path(None) is None

    def test_extract_from_empty_string_returns_none(self):
        """Test that empty string returns None."""
        assert extract_slug_from_resume_path("") is None

    def test_extract_from_invalid_path_returns_none(self):
        """Test that invalid path format returns None."""
        # Wrong directory structure
        assert extract_slug_from_resume_path("invalid/path/resume.pdf") is None

        # Missing resume.pdf filename
        assert extract_slug_from_resume_path("data/applications/amazon-3629/resume/") is None

        # Wrong filename
        assert (
            extract_slug_from_resume_path("data/applications/amazon-3629/resume/other.pdf") is None
        )

    def test_extract_from_malformed_wiki_link_returns_none(self):
        """Test that malformed wiki-link returns None."""
        # Missing closing brackets
        assert (
            extract_slug_from_resume_path("[[data/applications/amazon-3629/resume/resume.pdf")
            is None
        )

        # Extra brackets
        assert (
            extract_slug_from_resume_path("[[[data/applications/amazon-3629/resume/resume.pdf]]]")
            is None
        )

    def test_extract_handles_whitespace(self):
        """Test that whitespace is handled correctly."""
        resume_path = "  [[data/applications/amazon-3629/resume/resume.pdf]]  "
        assert extract_slug_from_resume_path(resume_path) == "amazon-3629"


class TestGenerateFallbackSlug:
    """Tests for generate_fallback_slug function."""

    def test_generate_with_job_db_id(self):
        """Test generating slug with job_db_id (preferred format)."""
        slug = generate_fallback_slug("Amazon", "Software Engineer", 3629)
        assert slug == "amazon-3629"

    def test_generate_without_job_db_id(self):
        """Test generating slug without job_db_id (fallback format)."""
        slug = generate_fallback_slug("Meta", "Senior Engineer", None)
        assert slug == "meta-senior_engineer"

    def test_generate_complex_company_name(self):
        """Test generating slug with complex company name."""
        slug = generate_fallback_slug("General Motors", "AI Engineer", 3711)
        assert slug == "general_motors-3711"

    def test_generate_special_characters_in_position(self):
        """Test generating slug with special characters in position."""
        slug = generate_fallback_slug("Google", "Backend/Full-Stack Developer", None)
        assert slug == "google-backend_full_stack_developer"

    def test_generate_special_characters_in_company(self):
        """Test generating slug with special characters in company."""
        slug = generate_fallback_slug("AT&T Inc.", "Network Engineer", 500)
        assert slug == "at_t_inc-500"

    def test_generate_with_zero_job_db_id(self):
        """Test that zero job_db_id is treated as valid (not None)."""
        # Edge case: job_db_id=0 should use the id format, not fallback to position
        slug = generate_fallback_slug("Amazon", "Engineer", 0)
        assert slug == "amazon-0"

    def test_generate_deterministic(self):
        """Test that slug generation is deterministic."""
        slug1 = generate_fallback_slug("Amazon", "Software Engineer", 3629)
        slug2 = generate_fallback_slug("Amazon", "Software Engineer", 3629)
        assert slug1 == slug2

    def test_generate_different_positions_same_company(self):
        """Test that different positions produce different slugs when no job_db_id."""
        slug1 = generate_fallback_slug("Amazon", "Software Engineer", None)
        slug2 = generate_fallback_slug("Amazon", "Senior Engineer", None)
        assert slug1 != slug2
        assert slug1 == "amazon-software_engineer"
        assert slug2 == "amazon-senior_engineer"


class TestResolveApplicationSlug:
    """Tests for resolve_application_slug function."""

    def test_resolve_from_resume_path_priority(self):
        """Test that resume_path takes priority over fallback generation."""
        tracker = {
            "company": "Amazon",
            "position": "Software Engineer",
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "job_db_id": 3629,
        }
        slug = resolve_application_slug(tracker)
        assert slug == "amazon-3629"

    def test_resolve_fallback_with_job_db_id(self):
        """Test fallback slug generation with job_db_id."""
        tracker = {
            "company": "Meta",
            "position": "Senior Engineer",
            "resume_path": None,
            "job_db_id": 100,
        }
        slug = resolve_application_slug(tracker)
        assert slug == "meta-100"

    def test_resolve_fallback_without_job_db_id(self):
        """Test fallback slug generation without job_db_id."""
        tracker = {
            "company": "Google",
            "position": "Staff Engineer",
            "resume_path": None,
            "job_db_id": None,
        }
        slug = resolve_application_slug(tracker)
        assert slug == "google-staff_engineer"

    def test_resolve_with_item_job_db_id_override(self):
        """Test that item_job_db_id overrides tracker job_db_id in fallback."""
        tracker = {
            "company": "Amazon",
            "position": "Engineer",
            "resume_path": None,
            "job_db_id": None,
        }
        slug = resolve_application_slug(tracker, item_job_db_id=5000)
        assert slug == "amazon-5000"

    def test_resolve_item_override_with_tracker_id(self):
        """Test that item_job_db_id takes precedence over tracker job_db_id."""
        tracker = {"company": "Meta", "position": "Engineer", "resume_path": None, "job_db_id": 100}
        # Item override should take precedence
        slug = resolve_application_slug(tracker, item_job_db_id=200)
        assert slug == "meta-200"

    def test_resolve_invalid_resume_path_falls_back(self):
        """Test that invalid resume_path triggers fallback generation."""
        tracker = {
            "company": "Amazon",
            "position": "Engineer",
            "resume_path": "invalid/path/format",
            "job_db_id": 3629,
        }
        # Should fall back to company-id format
        slug = resolve_application_slug(tracker)
        assert slug == "amazon-3629"

    def test_resolve_empty_resume_path_falls_back(self):
        """Test that empty resume_path triggers fallback generation."""
        tracker = {"company": "Google", "position": "Engineer", "resume_path": "", "job_db_id": 500}
        slug = resolve_application_slug(tracker)
        assert slug == "google-500"

    def test_resolve_missing_company_raises_error(self):
        """Test that missing company field raises ValueError."""
        tracker = {"position": "Software Engineer", "resume_path": None, "job_db_id": 100}
        with pytest.raises(ValueError) as exc_info:
            resolve_application_slug(tracker)
        assert "missing required 'company' field" in str(exc_info.value)

    def test_resolve_missing_position_raises_error(self):
        """Test that missing position field raises ValueError."""
        tracker = {"company": "Amazon", "resume_path": None, "job_db_id": 100}
        with pytest.raises(ValueError) as exc_info:
            resolve_application_slug(tracker)
        assert "missing required 'position' field" in str(exc_info.value)

    def test_resolve_empty_company_raises_error(self):
        """Test that empty company field raises ValueError."""
        tracker = {"company": "", "position": "Engineer", "resume_path": None, "job_db_id": 100}
        with pytest.raises(ValueError) as exc_info:
            resolve_application_slug(tracker)
        assert "missing required 'company' field" in str(exc_info.value)

    def test_resolve_empty_position_raises_error(self):
        """Test that empty position field raises ValueError."""
        tracker = {"company": "Amazon", "position": "", "resume_path": None, "job_db_id": 100}
        with pytest.raises(ValueError) as exc_info:
            resolve_application_slug(tracker)
        assert "missing required 'position' field" in str(exc_info.value)

    def test_resolve_deterministic_same_inputs(self):
        """Test that resolution is deterministic for same inputs."""
        tracker = {
            "company": "Amazon",
            "position": "Software Engineer",
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "job_db_id": 3629,
        }
        slug1 = resolve_application_slug(tracker)
        slug2 = resolve_application_slug(tracker)
        assert slug1 == slug2

    def test_resolve_with_complex_tracker_data(self):
        """Test resolution with complex real-world tracker data."""
        tracker = {
            "job_db_id": 3629,
            "company": "Amazon Web Services",
            "position": "Senior Software Engineer - AI/ML",
            "status": "Reviewed",
            "resume_path": "[[data/applications/amazon_web_services-3629/resume/resume.pdf]]",
            "application_date": "2026-02-05",
            "salary": 200000,
        }
        slug = resolve_application_slug(tracker)
        assert slug == "amazon_web_services-3629"

    def test_resolve_resume_path_mismatch_uses_path(self):
        """Test that resume_path slug is used even if it doesn't match fallback."""
        # This tests the priority: resume_path always wins
        tracker = {
            "company": "Amazon",
            "position": "Engineer",
            "resume_path": "[[data/applications/custom-slug-123/resume/resume.pdf]]",
            "job_db_id": 3629,
        }
        # Should use slug from resume_path, not generate amazon-3629
        slug = resolve_application_slug(tracker)
        assert slug == "custom-slug-123"

    def test_resolve_with_none_item_override(self):
        """Test that explicit None item_job_db_id uses tracker job_db_id."""
        tracker = {"company": "Meta", "position": "Engineer", "resume_path": None, "job_db_id": 100}
        # Explicit None should use tracker job_db_id
        slug = resolve_application_slug(tracker, item_job_db_id=None)
        assert slug == "meta-100"


class TestSlugResolverIntegration:
    """Integration tests for slug resolver with real-world scenarios."""

    def test_new_tracker_without_resume_path(self):
        """Test slug resolution for new tracker without resume_path."""
        # Scenario: First time creating workspace for a job
        tracker = {
            "company": "Startup Inc.",
            "position": "Founding Engineer",
            "resume_path": None,
            "job_db_id": 1,
        }
        slug = resolve_application_slug(tracker)
        assert slug == "startup_inc-1"

    def test_existing_tracker_with_resume_path(self):
        """Test slug resolution for existing tracker with resume_path."""
        # Scenario: Tracker already has workspace initialized
        tracker = {
            "company": "Big Corp",
            "position": "Senior Engineer",
            "resume_path": "[[data/applications/big_corp-5000/resume/resume.pdf]]",
            "job_db_id": 5000,
        }
        slug = resolve_application_slug(tracker)
        assert slug == "big_corp-5000"

    def test_batch_processing_with_item_override(self):
        """Test slug resolution in batch processing with item override."""
        # Scenario: Batch item provides job_db_id override
        tracker = {
            "company": "Tech Company",
            "position": "Engineer",
            "resume_path": None,
            "job_db_id": None,  # Tracker doesn't have it
        }
        # Batch item provides the ID
        slug = resolve_application_slug(tracker, item_job_db_id=9999)
        assert slug == "tech_company-9999"

    def test_manual_tracker_without_job_db_id(self):
        """Test slug resolution for manually created tracker without job_db_id."""
        # Scenario: User manually created tracker, no DB record
        tracker = {
            "company": "Referral Company",
            "position": "Staff Engineer",
            "resume_path": None,
            "job_db_id": None,
        }
        slug = resolve_application_slug(tracker)
        assert slug == "referral_company-staff_engineer"

    def test_slug_consistency_across_runs(self):
        """Test that slug remains consistent across multiple resolutions."""
        tracker = {
            "company": "Consistent Corp",
            "position": "Engineer",
            "resume_path": None,
            "job_db_id": 777,
        }

        # Resolve multiple times
        slugs = [resolve_application_slug(tracker) for _ in range(5)]

        # All should be identical
        assert len(set(slugs)) == 1
        assert slugs[0] == "consistent_corp-777"
