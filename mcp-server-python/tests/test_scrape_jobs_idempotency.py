"""
Integration tests for scrape_jobs dedupe/idempotency behavior.

Tests that running scrape_jobs with the same input multiple times
results in inserts on first run and duplicates on subsequent runs,
validating Requirements 7.1, 7.2, 7.5, and 12.5.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from tools.scrape_jobs import scrape_jobs


class TestScrapeJobsIdempotency:
    """
    Integration tests for dedupe/idempotency behavior.
    
    **Validates: Requirements 7.1, 7.2, 7.5, 12.5**
    """
    
    def test_same_input_twice_inserts_then_duplicates(self, tmp_path):
        """
        Test that running scrape_jobs twice with same input yields inserts then duplicates.
        
        First run should insert all records.
        Second run should detect all as duplicates.
        
        **Validates: Requirements 7.1, 7.2, 7.5, 12.5**
        """
        db_path = tmp_path / "test_idempotency.db"
        
        # Mock raw records from scraper
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/view/12345",
                "title": "Backend Engineer",
                "description": "Great backend role",
                "company": "TechCorp",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "12345",
                "date_posted": "2024-01-15",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/67890",
                "title": "Senior Backend Engineer",
                "description": "Senior backend position",
                "company": "StartupCo",
                "location": "Vancouver, BC",
                "site": "linkedin",
                "id": "67890",
                "date_posted": "2024-01-16",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/11111",
                "title": "Backend Developer",
                "description": "Backend development role",
                "company": "BigTech",
                "location": "Montreal, QC",
                "site": "linkedin",
                "id": "11111",
                "date_posted": "2024-01-17",
            }
        ]
        
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            # First run - should insert all records
            response1 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Verify first run results
            assert response1["dry_run"] is False
            assert len(response1["results"]) == 1
            
            term_result1 = response1["results"][0]
            assert term_result1["success"] is True
            assert term_result1["term"] == "backend engineer"
            assert term_result1["fetched_count"] == 3
            assert term_result1["cleaned_count"] == 3
            assert term_result1["inserted_count"] == 3
            assert term_result1["duplicate_count"] == 0
            
            # Verify totals
            assert response1["totals"]["inserted_count"] == 3
            assert response1["totals"]["duplicate_count"] == 0
            
            # Second run - same input, should detect all as duplicates
            response2 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Verify second run results
            assert response2["dry_run"] is False
            assert len(response2["results"]) == 1
            
            term_result2 = response2["results"][0]
            assert term_result2["success"] is True
            assert term_result2["term"] == "backend engineer"
            assert term_result2["fetched_count"] == 3
            assert term_result2["cleaned_count"] == 3
            assert term_result2["inserted_count"] == 0  # No new inserts
            assert term_result2["duplicate_count"] == 3  # All duplicates
            
            # Verify totals
            assert response2["totals"]["inserted_count"] == 0
            assert response2["totals"]["duplicate_count"] == 3
    
    def test_third_run_still_all_duplicates(self, tmp_path):
        """
        Test that third run with same input still detects all as duplicates.
        
        Verifies idempotency is stable across multiple reruns.
        
        **Validates: Requirements 7.2, 7.5, 12.5**
        """
        db_path = tmp_path / "test_triple_run.db"
        
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/view/99999",
                "title": "AI Engineer",
                "description": "AI/ML role",
                "company": "AIStartup",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "99999",
                "date_posted": "2024-01-20",
            }
        ]
        
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            # First run
            response1 = scrape_jobs(
                terms=["ai engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            assert response1["results"][0]["inserted_count"] == 1
            assert response1["results"][0]["duplicate_count"] == 0
            
            # Second run
            response2 = scrape_jobs(
                terms=["ai engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            assert response2["results"][0]["inserted_count"] == 0
            assert response2["results"][0]["duplicate_count"] == 1
            
            # Third run - should still be all duplicates
            response3 = scrape_jobs(
                terms=["ai engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            assert response3["results"][0]["inserted_count"] == 0
            assert response3["results"][0]["duplicate_count"] == 1
    
    def test_partial_overlap_mixed_inserts_and_duplicates(self, tmp_path):
        """
        Test that partial overlap yields correct mix of inserts and duplicates.
        
        First run inserts records A, B, C.
        Second run with records B, C, D should:
        - Detect B, C as duplicates
        - Insert D as new
        
        **Validates: Requirements 7.1, 7.2, 7.5**
        """
        db_path = tmp_path / "test_partial_overlap.db"
        
        # First batch: A, B, C
        first_batch = [
            {
                "job_url": "https://linkedin.com/jobs/view/job-a",
                "title": "Job A",
                "description": "Description A",
                "company": "Company A",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "job-a",
                "date_posted": "2024-01-15",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/job-b",
                "title": "Job B",
                "description": "Description B",
                "company": "Company B",
                "location": "Vancouver, BC",
                "site": "linkedin",
                "id": "job-b",
                "date_posted": "2024-01-16",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/job-c",
                "title": "Job C",
                "description": "Description C",
                "company": "Company C",
                "location": "Montreal, QC",
                "site": "linkedin",
                "id": "job-c",
                "date_posted": "2024-01-17",
            }
        ]
        
        # Second batch: B, C, D (B and C overlap, D is new)
        second_batch = [
            {
                "job_url": "https://linkedin.com/jobs/view/job-b",  # Duplicate
                "title": "Job B Updated",  # Different title
                "description": "Description B Updated",
                "company": "Company B New",
                "location": "Vancouver, BC",
                "site": "linkedin",
                "id": "job-b",
                "date_posted": "2024-01-18",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/job-c",  # Duplicate
                "title": "Job C Updated",
                "description": "Description C Updated",
                "company": "Company C New",
                "location": "Montreal, QC",
                "site": "linkedin",
                "id": "job-c",
                "date_posted": "2024-01-19",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/job-d",  # New
                "title": "Job D",
                "description": "Description D",
                "company": "Company D",
                "location": "Calgary, AB",
                "site": "linkedin",
                "id": "job-d",
                "date_posted": "2024-01-20",
            }
        ]
        
        # First run with first batch
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=first_batch):
            response1 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            assert response1["results"][0]["inserted_count"] == 3
            assert response1["results"][0]["duplicate_count"] == 0
        
        # Second run with second batch (partial overlap)
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=second_batch):
            response2 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Should have 2 duplicates (B, C) and 1 insert (D)
            assert response2["results"][0]["inserted_count"] == 1
            assert response2["results"][0]["duplicate_count"] == 2
    
    def test_multi_term_idempotency(self, tmp_path):
        """
        Test idempotency with multiple search terms.
        
        Each term should have independent dedupe behavior.
        
        **Validates: Requirements 7.1, 7.2, 7.5, 12.5**
        """
        db_path = tmp_path / "test_multi_term.db"
        
        # Different records for different terms
        def mock_scrape(term, **kwargs):
            if term == "backend engineer":
                return [
                    {
                        "job_url": "https://linkedin.com/jobs/view/backend-1",
                        "title": "Backend Engineer",
                        "description": "Backend role",
                        "company": "TechCorp",
                        "location": "Toronto, ON",
                        "site": "linkedin",
                        "id": "backend-1",
                        "date_posted": "2024-01-15",
                    }
                ]
            elif term == "ai engineer":
                return [
                    {
                        "job_url": "https://linkedin.com/jobs/view/ai-1",
                        "title": "AI Engineer",
                        "description": "AI role",
                        "company": "AIStartup",
                        "location": "Vancouver, BC",
                        "site": "linkedin",
                        "id": "ai-1",
                        "date_posted": "2024-01-16",
                    }
                ]
            return []
        
        with patch("tools.scrape_jobs.scrape_jobs_for_term", side_effect=mock_scrape):
            # First run with two terms
            response1 = scrape_jobs(
                terms=["backend engineer", "ai engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Both terms should insert
            assert len(response1["results"]) == 2
            assert response1["results"][0]["inserted_count"] == 1
            assert response1["results"][0]["duplicate_count"] == 0
            assert response1["results"][1]["inserted_count"] == 1
            assert response1["results"][1]["duplicate_count"] == 0
            assert response1["totals"]["inserted_count"] == 2
            assert response1["totals"]["duplicate_count"] == 0
            
            # Second run with same terms
            response2 = scrape_jobs(
                terms=["backend engineer", "ai engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Both terms should detect duplicates
            assert len(response2["results"]) == 2
            assert response2["results"][0]["inserted_count"] == 0
            assert response2["results"][0]["duplicate_count"] == 1
            assert response2["results"][1]["inserted_count"] == 0
            assert response2["results"][1]["duplicate_count"] == 1
            assert response2["totals"]["inserted_count"] == 0
            assert response2["totals"]["duplicate_count"] == 2
    
    def test_url_is_dedupe_key(self, tmp_path):
        """
        Test that URL is the dedupe key, not other fields.
        
        Records with same URL but different other fields should be treated as duplicates.
        
        **Validates: Requirements 7.1, 7.2**
        """
        db_path = tmp_path / "test_url_dedupe.db"
        
        # First record
        first_record = [
            {
                "job_url": "https://linkedin.com/jobs/view/12345",
                "title": "Original Title",
                "description": "Original description",
                "company": "Original Company",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "12345",
                "date_posted": "2024-01-15",
            }
        ]
        
        # Second record - same URL, different everything else
        second_record = [
            {
                "job_url": "https://linkedin.com/jobs/view/12345",  # Same URL
                "title": "Completely Different Title",
                "description": "Completely different description",
                "company": "Different Company",
                "location": "Vancouver, BC",
                "site": "indeed",  # Different site
                "id": "99999",  # Different ID
                "date_posted": "2024-01-20",
            }
        ]
        
        # First run
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=first_record):
            response1 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            assert response1["results"][0]["inserted_count"] == 1
            assert response1["results"][0]["duplicate_count"] == 0
        
        # Second run with different data but same URL
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=second_record):
            response2 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Should be detected as duplicate based on URL
            assert response2["results"][0]["inserted_count"] == 0
            assert response2["results"][0]["duplicate_count"] == 1
    
    def test_existing_rows_unchanged_on_dedupe(self, tmp_path):
        """
        Test that existing rows are not modified when duplicates are detected.
        
        Verifies that INSERT OR IGNORE truly ignores duplicates without updating.
        
        **Validates: Requirements 7.2, 7.5**
        """
        import sqlite3
        
        db_path = tmp_path / "test_no_updates.db"
        
        # First record
        first_record = [
            {
                "job_url": "https://linkedin.com/jobs/view/12345",
                "title": "Original Title",
                "description": "Original description",
                "company": "Original Company",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "12345",
                "date_posted": "2024-01-15",
            }
        ]
        
        # Insert first record
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=first_record):
            response1 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            assert response1["results"][0]["inserted_count"] == 1
        
        # Read original data from database
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT title, company, description FROM jobs WHERE url = ?",
            ("https://linkedin.com/jobs/view/12345",)
        )
        original_row = cursor.fetchone()
        original_title = original_row["title"]
        original_company = original_row["company"]
        original_description = original_row["description"]
        conn.close()
        
        # Second record with same URL but different data
        second_record = [
            {
                "job_url": "https://linkedin.com/jobs/view/12345",  # Same URL
                "title": "Updated Title",
                "description": "Updated description",
                "company": "Updated Company",
                "location": "Vancouver, BC",
                "site": "linkedin",
                "id": "12345",
                "date_posted": "2024-01-20",
            }
        ]
        
        # Try to insert duplicate
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=second_record):
            response2 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            assert response2["results"][0]["duplicate_count"] == 1
        
        # Verify original data is unchanged
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT title, company, description FROM jobs WHERE url = ?",
            ("https://linkedin.com/jobs/view/12345",)
        )
        current_row = cursor.fetchone()
        conn.close()
        
        # Data should match original, not updated values
        assert current_row["title"] == original_title
        assert current_row["company"] == original_company
        assert current_row["description"] == original_description
        assert current_row["title"] == "Original Title"
        assert current_row["company"] == "Original Company"
    
    def test_idempotency_with_filtering(self, tmp_path):
        """
        Test idempotency when filtering is applied.
        
        Filtered records should not affect dedupe counts.
        
        **Validates: Requirements 7.1, 7.2, 7.5**
        """
        db_path = tmp_path / "test_filter_idempotency.db"
        
        # Mix of valid and filtered records
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/view/valid-1",
                "title": "Valid Job",
                "description": "Has description",
                "company": "TechCorp",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "valid-1",
                "date_posted": "2024-01-15",
            },
            {
                "job_url": "",  # Will be filtered (no URL)
                "title": "No URL Job",
                "description": "Has description",
                "company": "Company",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "no-url",
                "date_posted": "2024-01-16",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/no-desc",
                "title": "No Description Job",
                "description": "",  # Will be filtered (no description)
                "company": "Company",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "no-desc",
                "date_posted": "2024-01-17",
            }
        ]
        
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            # First run
            response1 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                require_description=True,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Only 1 valid record should be inserted
            assert response1["results"][0]["fetched_count"] == 3
            assert response1["results"][0]["cleaned_count"] == 1
            assert response1["results"][0]["inserted_count"] == 1
            assert response1["results"][0]["duplicate_count"] == 0
            assert response1["results"][0]["skipped_no_url"] == 1
            assert response1["results"][0]["skipped_no_description"] == 1
            
            # Second run
            response2 = scrape_jobs(
                terms=["backend engineer"],
                location="Ontario, Canada",
                sites=["linkedin"],
                results_wanted=20,
                hours_old=2,
                require_description=True,
                db_path=str(db_path),
                save_capture_json=False,
                dry_run=False,
            )
            
            # Same filtering, but now the valid record is a duplicate
            assert response2["results"][0]["fetched_count"] == 3
            assert response2["results"][0]["cleaned_count"] == 1
            assert response2["results"][0]["inserted_count"] == 0
            assert response2["results"][0]["duplicate_count"] == 1
            assert response2["results"][0]["skipped_no_url"] == 1
            assert response2["results"][0]["skipped_no_description"] == 1
    
    def test_deterministic_behavior_same_request_same_state(self, tmp_path):
        """
        Test that same request against same source state yields deterministic results.
        
        **Validates: Requirements 12.5**
        """
        db_path = tmp_path / "test_deterministic.db"
        
        raw_records = [
            {
                "job_url": "https://linkedin.com/jobs/view/det-1",
                "title": "Job 1",
                "description": "Description 1",
                "company": "Company 1",
                "location": "Toronto, ON",
                "site": "linkedin",
                "id": "det-1",
                "date_posted": "2024-01-15",
            },
            {
                "job_url": "https://linkedin.com/jobs/view/det-2",
                "title": "Job 2",
                "description": "Description 2",
                "company": "Company 2",
                "location": "Vancouver, BC",
                "site": "linkedin",
                "id": "det-2",
                "date_posted": "2024-01-16",
            }
        ]
        
        request_params = {
            "terms": ["backend engineer"],
            "location": "Ontario, Canada",
            "sites": ["linkedin"],
            "results_wanted": 20,
            "hours_old": 2,
            "db_path": str(db_path),
            "save_capture_json": False,
            "dry_run": False,
        }
        
        with patch("tools.scrape_jobs.scrape_jobs_for_term", return_value=raw_records):
            # Run 1
            response1 = scrape_jobs(**request_params)
            
            # Run 2 - same request, same source state
            response2 = scrape_jobs(**request_params)
            
            # Run 3 - same request, same source state
            response3 = scrape_jobs(**request_params)
        
        # First run should insert
        assert response1["results"][0]["inserted_count"] == 2
        assert response1["results"][0]["duplicate_count"] == 0
        
        # Second and third runs should have identical results (all duplicates)
        assert response2["results"][0]["inserted_count"] == 0
        assert response2["results"][0]["duplicate_count"] == 2
        
        assert response3["results"][0]["inserted_count"] == 0
        assert response3["results"][0]["duplicate_count"] == 2
        
        # Verify structure is identical (excluding timestamps and run_id)
        assert response2["results"][0]["fetched_count"] == response3["results"][0]["fetched_count"]
        assert response2["results"][0]["cleaned_count"] == response3["results"][0]["cleaned_count"]
        assert response2["totals"] == response3["totals"]
