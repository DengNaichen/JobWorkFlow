"""
Integration tests for tracker parser with resume path resolution.

Tests the resolve_resume_pdf_path_from_tracker function in realistic scenarios.
"""

import pytest

from utils.tracker_parser import resolve_resume_pdf_path_from_tracker


class TestResolveResumePdfPathFromTrackerIntegration:
    """Integration tests for resolve_resume_pdf_path_from_tracker."""

    def test_finalize_item_with_override(self, tmp_path):
        """
        Test finalize scenario where item provides explicit resume_pdf_path override.
        
        This simulates the case where the finalize_resume_batch tool receives
        an item with an explicit resume_pdf_path that should take precedence
        over the tracker's frontmatter value.
        """
        # Create a tracker with resume_path in frontmatter
        tracker_path = tmp_path / "trackers" / "2026-02-05-amazon-3629.md"
        tracker_path.parent.mkdir(parents=True)
        tracker_path.write_text("""---
job_db_id: 3629
job_id: li-4331530278
company: Amazon
position: Software Engineer
status: Reviewed
application_date: '2026-02-05'
reference_link: https://example.com/job/123
resume_path: '[[data/applications/amazon-3629/resume/resume.pdf]]'
cover_letter_path: '[[data/applications/amazon-3629/cover/cover-letter.pdf]]'
next_action:
- Wait for feedback
salary: 0
website: ''
---

## Job Description

Build scalable systems for AWS.

## Notes

Strong candidate.
""", encoding='utf-8')
        
        # Simulate finalize item with explicit override
        item_override = "data/applications/amazon-3629-v2/resume/resume.pdf"
        
        # Resolve - should use the override
        result = resolve_resume_pdf_path_from_tracker(
            str(tracker_path),
            item_resume_pdf_path=item_override
        )
        
        assert result == item_override
        assert result != "data/applications/amazon-3629/resume/resume.pdf"

    def test_finalize_item_without_override(self, tmp_path):
        """
        Test finalize scenario where item does NOT provide resume_pdf_path.
        
        This simulates the case where the finalize_resume_batch tool receives
        an item without resume_pdf_path and must resolve it from the tracker's
        frontmatter resume_path field.
        """
        # Create a tracker with resume_path in frontmatter
        tracker_path = tmp_path / "trackers" / "2026-02-05-meta-3630.md"
        tracker_path.parent.mkdir(parents=True)
        tracker_path.write_text("""---
job_db_id: 3630
job_id: li-4331530279
company: Meta
position: Senior Software Engineer
status: Reviewed
application_date: '2026-02-05'
reference_link: https://example.com/job/124
resume_path: '[[data/applications/meta-3630/resume/resume.pdf]]'
cover_letter_path: '[[data/applications/meta-3630/cover/cover-letter.pdf]]'
next_action:
- Wait for feedback
salary: 0
website: ''
---

## Job Description

Build social networking infrastructure.

## Notes

Excellent fit.
""", encoding='utf-8')
        
        # Simulate finalize item without override (None)
        result = resolve_resume_pdf_path_from_tracker(
            str(tracker_path),
            item_resume_pdf_path=None
        )
        
        # Should resolve from tracker frontmatter
        assert result == "data/applications/meta-3630/resume/resume.pdf"

    def test_finalize_batch_mixed_items(self, tmp_path):
        """
        Test finalize batch scenario with mixed items (some with override, some without).
        
        This simulates a realistic finalize_resume_batch call where some items
        provide explicit resume_pdf_path and others rely on tracker resolution.
        """
        # Create two trackers
        tracker1_path = tmp_path / "trackers" / "2026-02-05-google-3631.md"
        tracker1_path.parent.mkdir(parents=True, exist_ok=True)
        tracker1_path.write_text("""---
job_db_id: 3631
company: Google
status: Reviewed
resume_path: '[[data/applications/google-3631/resume/resume.pdf]]'
---

## Job Description
""", encoding='utf-8')
        
        tracker2_path = tmp_path / "trackers" / "2026-02-05-apple-3632.md"
        tracker2_path.write_text("""---
job_db_id: 3632
company: Apple
status: Reviewed
resume_path: data/applications/apple-3632/resume/resume.pdf
---

## Job Description
""", encoding='utf-8')
        
        # Simulate batch items
        items = [
            {
                "id": 3631,
                "tracker_path": str(tracker1_path),
                "resume_pdf_path": "data/applications/google-3631-custom/resume/resume.pdf"
            },
            {
                "id": 3632,
                "tracker_path": str(tracker2_path),
                # No resume_pdf_path - should resolve from tracker
            }
        ]
        
        # Process each item
        results = []
        for item in items:
            resolved_path = resolve_resume_pdf_path_from_tracker(
                item["tracker_path"],
                item_resume_pdf_path=item.get("resume_pdf_path")
            )
            results.append({
                "id": item["id"],
                "resume_pdf_path": resolved_path
            })
        
        # Verify results
        assert len(results) == 2
        
        # First item used override
        assert results[0]["id"] == 3631
        assert results[0]["resume_pdf_path"] == "data/applications/google-3631-custom/resume/resume.pdf"
        
        # Second item resolved from tracker
        assert results[1]["id"] == 3632
        assert results[1]["resume_pdf_path"] == "data/applications/apple-3632/resume/resume.pdf"

    def test_finalize_with_plain_path_format(self, tmp_path):
        """
        Test finalize scenario with plain path format (no wiki-link brackets).
        
        Some trackers may use plain path format instead of wiki-link format.
        The resolver should handle both formats transparently.
        """
        # Create tracker with plain path format
        tracker_path = tmp_path / "trackers" / "2026-02-05-microsoft-3633.md"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text("""---
job_db_id: 3633
company: Microsoft
status: Reviewed
resume_path: data/applications/microsoft-3633/resume/resume.pdf
---

## Job Description
""", encoding='utf-8')
        
        # Resolve without override
        result = resolve_resume_pdf_path_from_tracker(str(tracker_path))
        
        # Should resolve plain path correctly
        assert result == "data/applications/microsoft-3633/resume/resume.pdf"

    def test_error_handling_missing_resume_path(self, tmp_path):
        """
        Test error handling when tracker is missing resume_path field.
        
        This simulates a validation failure scenario where the tracker
        doesn't have the required resume_path field.
        """
        # Create tracker without resume_path
        tracker_path = tmp_path / "trackers" / "2026-02-05-invalid-3634.md"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text("""---
job_db_id: 3634
company: Invalid Corp
status: Reviewed
---

## Job Description
""", encoding='utf-8')
        
        # Should raise ValueError when resume_path is missing
        with pytest.raises(ValueError) as exc_info:
            resolve_resume_pdf_path_from_tracker(str(tracker_path))
        
        assert "missing 'resume_path' field" in str(exc_info.value)

    def test_requirement_3_6_resolve_from_tracker_when_not_provided(self, tmp_path):
        """
        Requirement 3.6: Resolve resume_pdf_path from tracker frontmatter
        when item override is not provided.
        
        This test validates that the function correctly implements the
        requirement to resolve resume_pdf_path from tracker's resume_path
        wiki-link when the finalize item doesn't provide an override.
        """
        # Create tracker
        tracker_path = tmp_path / "trackers" / "2026-02-05-netflix-3635.md"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text("""---
job_db_id: 3635
company: Netflix
status: Reviewed
resume_path: '[[data/applications/netflix-3635/resume/resume.pdf]]'
---

## Job Description
""", encoding='utf-8')
        
        # Case 1: Item provides override - use it
        override_path = "data/applications/netflix-3635-v2/resume/resume.pdf"
        result_with_override = resolve_resume_pdf_path_from_tracker(
            str(tracker_path),
            item_resume_pdf_path=override_path
        )
        assert result_with_override == override_path
        
        # Case 2: Item does not provide override - resolve from tracker
        result_without_override = resolve_resume_pdf_path_from_tracker(
            str(tracker_path),
            item_resume_pdf_path=None
        )
        assert result_without_override == "data/applications/netflix-3635/resume/resume.pdf"
        
        # Case 3: Omit parameter entirely - resolve from tracker
        result_omitted = resolve_resume_pdf_path_from_tracker(str(tracker_path))
        assert result_omitted == "data/applications/netflix-3635/resume/resume.pdf"

    def test_requirement_10_2_include_resume_pdf_path_in_results(self, tmp_path):
        """
        Requirement 10.2: Include resume_pdf_path in results.
        
        This test validates that the resolved resume_pdf_path can be
        included in the finalize results as required by the spec.
        """
        # Create tracker
        tracker_path = tmp_path / "trackers" / "2026-02-05-uber-3636.md"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text("""---
job_db_id: 3636
company: Uber
status: Reviewed
resume_path: '[[data/applications/uber-3636/resume/resume.pdf]]'
---

## Job Description
""", encoding='utf-8')
        
        # Simulate finalize item processing
        item = {
            "id": 3636,
            "tracker_path": str(tracker_path)
        }
        
        # Resolve resume_pdf_path
        resume_pdf_path = resolve_resume_pdf_path_from_tracker(
            item["tracker_path"],
            item_resume_pdf_path=item.get("resume_pdf_path")
        )
        
        # Build result structure (as would be done in finalize tool)
        result = {
            "id": item["id"],
            "tracker_path": item["tracker_path"],
            "resume_pdf_path": resume_pdf_path,  # Requirement 10.2
            "action": "finalized",
            "success": True
        }
        
        # Verify result includes resume_pdf_path
        assert "resume_pdf_path" in result
        assert result["resume_pdf_path"] == "data/applications/uber-3636/resume/resume.pdf"
        assert result["resume_pdf_path"] is not None
