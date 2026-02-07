"""
Integration tests for slug resolver with tracker parser.

Tests the complete flow of parsing a tracker and resolving its application_slug.
"""

import pytest

from utils.tracker_parser import parse_tracker_for_career_tailor
from utils.slug_resolver import resolve_application_slug


class TestSlugResolverWithTrackerParser:
    """Integration tests combining tracker parsing and slug resolution."""

    def test_resolve_slug_from_parsed_tracker_with_resume_path(self, tmp_path):
        """Test resolving slug from tracker with resume_path."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
job_db_id: 3629
company: Amazon
position: Software Engineer
status: Reviewed
resume_path: '[[data/applications/amazon-3629/resume/resume.pdf]]'
---

## Job Description

Build scalable distributed systems.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Resolve slug
        slug = resolve_application_slug(tracker_data)

        # Should extract from resume_path
        assert slug == "amazon-3629"

    def test_resolve_slug_from_parsed_tracker_without_resume_path(self, tmp_path):
        """Test resolving slug from tracker without resume_path (fallback)."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
job_db_id: 100
company: Meta
position: Senior Engineer
status: Applied
---

## Job Description

Lead technical initiatives.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Resolve slug
        slug = resolve_application_slug(tracker_data)

        # Should use fallback: company-id
        assert slug == "meta-100"

    def test_resolve_slug_without_job_db_id(self, tmp_path):
        """Test resolving slug from tracker without job_db_id."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
company: Google
position: Staff Engineer
status: Applied
---

## Job Description

Design infrastructure.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Resolve slug
        slug = resolve_application_slug(tracker_data)

        # Should use fallback: company-position
        assert slug == "google-staff_engineer"

    def test_resolve_slug_with_item_override(self, tmp_path):
        """Test resolving slug with item job_db_id override."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
company: Startup
position: Founding Engineer
status: Applied
---

## Job Description

Build from scratch.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Resolve slug with item override
        slug = resolve_application_slug(tracker_data, item_job_db_id=5000)

        # Should use item override
        assert slug == "startup-5000"

    def test_resolve_slug_complex_company_name(self, tmp_path):
        """Test resolving slug with complex company name."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
job_db_id: 3711
company: General Motors
position: AI Engineer
status: Reviewed
resume_path: '[[data/applications/general_motors-3711/resume/resume.pdf]]'
---

## Job Description

Develop autonomous driving systems.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Resolve slug
        slug = resolve_application_slug(tracker_data)

        # Should extract from resume_path
        assert slug == "general_motors-3711"

    def test_resolve_slug_special_characters_in_position(self, tmp_path):
        """Test resolving slug with special characters in position."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
company: Tech Corp
position: Backend/Full-Stack Developer
status: Applied
---

## Job Description

Build web applications.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Resolve slug
        slug = resolve_application_slug(tracker_data)

        # Should normalize position
        assert slug == "tech_corp-backend_full_stack_developer"

    def test_resolve_slug_invalid_resume_path_falls_back(self, tmp_path):
        """Test that invalid resume_path triggers fallback generation."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
job_db_id: 200
company: Company X
position: Engineer
status: Applied
resume_path: 'invalid/path/format'
---

## Job Description

Work on projects.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Resolve slug
        slug = resolve_application_slug(tracker_data)

        # Should fall back to company-id
        assert slug == "company_x-200"

    def test_resolve_slug_deterministic_across_parses(self, tmp_path):
        """Test that slug resolution is deterministic across multiple parses."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
job_db_id: 777
company: Consistent Corp
position: Engineer
status: Applied
---

## Job Description

Maintain systems.
""",
            encoding="utf-8",
        )

        # Parse and resolve multiple times
        slugs = []
        for _ in range(3):
            tracker_data = parse_tracker_for_career_tailor(str(tracker_path))
            slug = resolve_application_slug(tracker_data)
            slugs.append(slug)

        # All should be identical
        assert len(set(slugs)) == 1
        assert slugs[0] == "consistent_corp-777"

    def test_resolve_slug_preserves_all_tracker_data(self, tmp_path):
        """Test that slug resolution doesn't modify tracker data."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
job_db_id: 999
company: Test Company
position: Test Position
status: Applied
application_date: '2026-02-05'
salary: 150000
---

## Job Description

Test description.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Store original data
        original_company = tracker_data["company"]
        original_position = tracker_data["position"]
        original_job_db_id = tracker_data["job_db_id"]

        # Resolve slug
        slug = resolve_application_slug(tracker_data)

        # Verify tracker data is unchanged
        assert tracker_data["company"] == original_company
        assert tracker_data["position"] == original_position
        assert tracker_data["job_db_id"] == original_job_db_id
        assert tracker_data["frontmatter"]["application_date"] == "2026-02-05"
        assert tracker_data["frontmatter"]["salary"] == 150000

        # Verify slug is correct
        assert slug == "test_company-999"


class TestSlugResolverErrorHandling:
    """Test error handling in slug resolution with parsed tracker data."""

    def test_resolve_slug_missing_company_in_tracker(self, tmp_path):
        """Test that missing company in tracker raises error during parsing."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
position: Engineer
status: Applied
---

## Job Description

Content.
""",
            encoding="utf-8",
        )

        # Should raise error during parsing (not slug resolution)
        from utils.tracker_parser import TrackerParseError

        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_for_career_tailor(str(tracker_path))

        assert "missing required 'company' field" in str(exc_info.value)

    def test_resolve_slug_missing_position_in_tracker(self, tmp_path):
        """Test that missing position in tracker raises error during parsing."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(
            """---
company: Amazon
status: Applied
---

## Job Description

Content.
""",
            encoding="utf-8",
        )

        # Should raise error during parsing (not slug resolution)
        from utils.tracker_parser import TrackerParseError

        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_for_career_tailor(str(tracker_path))

        assert "missing required 'position' field" in str(exc_info.value)


class TestSlugResolverRealWorldScenarios:
    """Test slug resolver with real-world tracker scenarios."""

    def test_scenario_new_job_from_scraper(self, tmp_path):
        """Test slug resolution for new job from scraper (has job_db_id, no resume_path)."""
        tracker_path = tmp_path / "2026-02-05-amazon-3629.md"
        tracker_path.write_text(
            """---
job_db_id: 3629
job_id: li-4331530278
company: Amazon
position: Software Engineer
status: Shortlist
application_date: '2026-02-05'
reference_link: https://example.com/job/123
next_action:
- Review job description
- Tailor resume
salary: 0
website: ''
---

## Job Description

We are looking for a Software Engineer to build scalable systems.

## Notes

Interesting opportunity.
""",
            encoding="utf-8",
        )

        # Parse and resolve
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))
        slug = resolve_application_slug(tracker_data)

        # Should use company-id format
        assert slug == "amazon-3629"
        assert "build scalable systems" in tracker_data["job_description"]

    def test_scenario_existing_job_with_workspace(self, tmp_path):
        """Test slug resolution for existing job with initialized workspace."""
        tracker_path = tmp_path / "2026-02-05-meta-100.md"
        tracker_path.write_text(
            """---
job_db_id: 100
company: Meta
position: Senior Engineer
status: Resume Written
application_date: '2026-02-05'
resume_path: '[[data/applications/meta-100/resume/resume.pdf]]'
cover_letter_path: '[[data/applications/meta-100/cover/cover-letter.pdf]]'
---

## Job Description

Lead technical initiatives and mentor junior engineers.

## Notes

Resume tailored and ready.
""",
            encoding="utf-8",
        )

        # Parse and resolve
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))
        slug = resolve_application_slug(tracker_data)

        # Should extract from resume_path
        assert slug == "meta-100"
        assert "Lead technical initiatives" in tracker_data["job_description"]

    def test_scenario_manual_tracker_no_db_record(self, tmp_path):
        """Test slug resolution for manually created tracker without DB record."""
        tracker_path = tmp_path / "2026-02-05-referral-company.md"
        tracker_path.write_text(
            """---
company: Referral Company
position: Staff Engineer
status: Applied
application_date: '2026-02-05'
reference_link: https://referral-company.com/careers
---

## Job Description

Join our team through employee referral.

## Notes

Applied through referral from John.
""",
            encoding="utf-8",
        )

        # Parse and resolve
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))
        slug = resolve_application_slug(tracker_data)

        # Should use company-position format (no job_db_id)
        assert slug == "referral_company-staff_engineer"
        assert "employee referral" in tracker_data["job_description"]

    def test_scenario_batch_item_provides_job_db_id(self, tmp_path):
        """Test slug resolution when batch item provides job_db_id override."""
        tracker_path = tmp_path / "2026-02-05-startup.md"
        tracker_path.write_text(
            """---
company: Startup Inc
position: Founding Engineer
status: Applied
---

## Job Description

Build the product from scratch.

## Notes

Exciting opportunity.
""",
            encoding="utf-8",
        )

        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))

        # Batch item provides job_db_id
        slug = resolve_application_slug(tracker_data, item_job_db_id=9999)

        # Should use item override
        assert slug == "startup_inc-9999"
