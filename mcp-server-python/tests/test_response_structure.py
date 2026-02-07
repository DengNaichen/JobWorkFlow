"""
Integration test to verify the complete structured response payload.

This test demonstrates that task 6.2 requirements are fully met:
- Run metadata (run_id, timestamps, duration_ms) - Requirement 10.1
- Ordered term results - Requirement 10.2
- Aggregate totals - Requirement 10.3
- JSON-serializable payload - Requirement 10.5
"""

import json
from unittest.mock import MagicMock, patch

from tools.scrape_jobs import scrape_jobs


def test_complete_response_structure():
    """
    Verify the complete structured response payload meets all requirements.
    
    **Validates: Requirements 10.1, 10.2, 10.3, 10.5**
    """
    # Mock raw records for two terms
    raw_records_term1 = [
        {
            "job_url": "https://linkedin.com/jobs/1",
            "title": "Backend Engineer",
            "description": "Great backend role",
            "company": "TechCorp",
            "location": "Toronto",
            "site": "linkedin",
            "id": "job1",
        },
        {
            "job_url": "https://linkedin.com/jobs/2",
            "title": "Senior Backend Engineer",
            "description": "Senior role",
            "company": "StartupCo",
            "location": "Ottawa",
            "site": "linkedin",
            "id": "job2",
        }
    ]
    
    raw_records_term2 = [
        {
            "job_url": "https://linkedin.com/jobs/3",
            "title": "AI Engineer",
            "description": "AI/ML role",
            "company": "AIStartup",
            "location": "Toronto",
            "site": "linkedin",
            "id": "job3",
        }
    ]
    
    def mock_scrape(term, **kwargs):
        if term == "backend engineer":
            return raw_records_term1
        elif term == "ai engineer":
            return raw_records_term2
        return []
    
    with patch("tools.scrape_jobs.scrape_jobs_for_term", side_effect=mock_scrape):
        with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
            mock_writer = MagicMock()
            # First term: 2 inserts, 0 duplicates
            # Second term: 1 insert, 0 duplicates
            mock_writer.insert_cleaned_records.side_effect = [(2, 0), (1, 0)]
            mock_writer_class.return_value.__enter__.return_value = mock_writer
            
            response = scrape_jobs(
                terms=["backend engineer", "ai engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                dry_run=False,
            )
    
    # Verify response is JSON-serializable (Requirement 10.5)
    json_str = json.dumps(response)
    assert json_str is not None
    
    # Verify run metadata (Requirement 10.1)
    assert "run_id" in response
    assert response["run_id"].startswith("scrape_")
    assert "started_at" in response
    assert response["started_at"].endswith("Z")
    assert "finished_at" in response
    assert response["finished_at"].endswith("Z")
    assert "duration_ms" in response
    assert isinstance(response["duration_ms"], int)
    assert response["duration_ms"] >= 0
    
    # Verify dry_run flag
    assert "dry_run" in response
    assert response["dry_run"] is False
    
    # Verify ordered term results (Requirement 10.2)
    assert "results" in response
    assert len(response["results"]) == 2
    
    # First term result
    term1_result = response["results"][0]
    assert term1_result["term"] == "backend engineer"
    assert term1_result["success"] is True
    assert term1_result["fetched_count"] == 2
    assert term1_result["cleaned_count"] == 2
    assert term1_result["inserted_count"] == 2
    assert term1_result["duplicate_count"] == 0
    assert term1_result["skipped_no_url"] == 0
    assert term1_result["skipped_no_description"] == 0
    
    # Second term result
    term2_result = response["results"][1]
    assert term2_result["term"] == "ai engineer"
    assert term2_result["success"] is True
    assert term2_result["fetched_count"] == 1
    assert term2_result["cleaned_count"] == 1
    assert term2_result["inserted_count"] == 1
    assert term2_result["duplicate_count"] == 0
    
    # Verify aggregate totals (Requirement 10.3)
    assert "totals" in response
    totals = response["totals"]
    assert totals["term_count"] == 2
    assert totals["successful_terms"] == 2
    assert totals["failed_terms"] == 0
    assert totals["fetched_count"] == 3
    assert totals["cleaned_count"] == 3
    assert totals["inserted_count"] == 3
    assert totals["duplicate_count"] == 0
    assert totals["skipped_no_url"] == 0
    assert totals["skipped_no_description"] == 0


def test_response_structure_with_partial_failure():
    """
    Verify response structure handles partial failures correctly.
    
    **Validates: Requirements 10.2, 10.3**
    """
    def mock_scrape(term, **kwargs):
        if term == "backend engineer":
            return [
                {
                    "job_url": "https://linkedin.com/jobs/1",
                    "title": "Backend Engineer",
                    "description": "Great role",
                    "company": "TechCorp",
                    "location": "Toronto",
                    "site": "linkedin",
                    "id": "job1",
                }
            ]
        else:
            raise Exception("Network error")
    
    with patch("tools.scrape_jobs.scrape_jobs_for_term", side_effect=mock_scrape):
        with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
            mock_writer = MagicMock()
            mock_writer.insert_cleaned_records.return_value = (1, 0)
            mock_writer_class.return_value.__enter__.return_value = mock_writer
            
            response = scrape_jobs(
                terms=["backend engineer", "ai engineer"],
                location="Ontario, Canada",
                dry_run=False,
            )
    
    # Verify both terms are in results
    assert len(response["results"]) == 2
    
    # First term succeeded
    assert response["results"][0]["success"] is True
    assert response["results"][0]["term"] == "backend engineer"
    
    # Second term failed
    assert response["results"][1]["success"] is False
    assert response["results"][1]["term"] == "ai engineer"
    assert "error" in response["results"][1]
    
    # Verify totals reflect partial success
    assert response["totals"]["term_count"] == 2
    assert response["totals"]["successful_terms"] == 1
    assert response["totals"]["failed_terms"] == 1
    assert response["totals"]["fetched_count"] == 1  # Only from successful term
    assert response["totals"]["inserted_count"] == 1


def test_response_structure_dry_run():
    """
    Verify response structure in dry_run mode.
    
    **Validates: Requirements 10.1, 10.4**
    """
    raw_records = [
        {
            "job_url": "https://linkedin.com/jobs/1",
            "title": "Backend Engineer",
            "description": "Great role",
            "company": "TechCorp",
            "location": "Toronto",
            "site": "linkedin",
            "id": "job1",
        }
    ]
    
    with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
        with patch("tools.scrape_jobs.JobsIngestWriter") as mock_writer_class:
            response = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                dry_run=True,
            )
            
            # Verify writer was not called in dry_run mode
            mock_writer_class.assert_not_called()
    
    # Verify dry_run flag is set (Requirement 10.4)
    assert response["dry_run"] is True
    
    # Verify counts are computed but no DB writes occurred
    assert response["results"][0]["fetched_count"] == 1
    assert response["results"][0]["cleaned_count"] == 1
    assert response["results"][0]["inserted_count"] == 0
    assert response["results"][0]["duplicate_count"] == 0
    
    # Verify totals reflect dry_run behavior
    assert response["totals"]["fetched_count"] == 1
    assert response["totals"]["cleaned_count"] == 1
    assert response["totals"]["inserted_count"] == 0
