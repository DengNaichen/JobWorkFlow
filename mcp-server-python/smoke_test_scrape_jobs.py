#!/usr/bin/env python3
"""
Manual smoke test for scrape_jobs tool - Task 10.2

Tests:
1. Confirm inserts arrive as status='new'
2. Confirm no tracker/status/finalize side effects

Requirements: 8.1, 8.4, 8.5
"""

import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tools.scrape_jobs import scrape_jobs


def check_db_status(db_path: Path, expected_count: int) -> dict:
    """Check database for inserted records and their status."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get the most recent records (by id DESC)
    cursor.execute(
        """
        SELECT id, job_id, title, company, status, url, created_at
        FROM jobs
        ORDER BY id DESC
        LIMIT ?
    """,
        (expected_count,),
    )

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "count": len(records),
        "records": records,
        "all_status_new": all(r["status"] == "new" for r in records),
    }


def check_no_side_effects(trackers_dir: str = "trackers") -> dict:
    """Check that no tracker files were created."""
    trackers_path = Path(trackers_dir)

    if not trackers_path.exists():
        return {"trackers_dir_exists": False, "tracker_count": 0, "trackers": []}

    # List all markdown files in trackers directory
    tracker_files = list(trackers_path.glob("*.md"))

    return {
        "trackers_dir_exists": True,
        "tracker_count": len(tracker_files),
        "trackers": [str(f) for f in tracker_files],
    }


def main():
    print("=" * 80)
    print("MANUAL SMOKE TEST: scrape_jobs - Task 10.2")
    print("=" * 80)
    print("\nRequirements being tested:")
    print("  - 8.1: Inserts arrive with status='new'")
    print("  - 8.4: No tracker creation side effects")
    print("  - 8.5: No triage/finalization side effects")
    print("=" * 80)

    # Use a test database path (relative to repo root)
    test_db_path = "data/capture/test_scrape_jobs.db"

    # Resolve to absolute path
    repo_root = Path(__file__).parent.parent
    test_db_full_path = repo_root / test_db_path

    # Clean up test database if it exists
    if test_db_full_path.exists():
        print(f"\n🗑️  Removing existing test database: {test_db_full_path}")
        test_db_full_path.unlink()

    # Record tracker state before scrape
    print("\n📊 Checking tracker state BEFORE scrape...")
    trackers_before = check_no_side_effects()
    print(f"   Trackers directory exists: {trackers_before['trackers_dir_exists']}")
    print(f"   Tracker count: {trackers_before['tracker_count']}")

    # Run scrape_jobs with minimal settings
    print("\n🔄 Running scrape_jobs with test configuration...")
    print(f"   Database: {test_db_path}")
    print("   Terms: ['python developer']")
    print("   Results wanted: 5")
    print("   Dry run: False")
    print("   Save capture: False")

    try:
        result = scrape_jobs(
            terms=["python developer"],
            location="Ontario, Canada",
            sites=["linkedin"],
            results_wanted=5,
            hours_old=24,
            db_path=test_db_path,
            status="new",  # Explicitly set to 'new'
            require_description=True,
            save_capture_json=False,  # Don't save capture files
            dry_run=False,
        )

        print("\n✅ scrape_jobs completed successfully")
        print(f"   Run ID: {result['run_id']}")
        print(f"   Duration: {result['duration_ms']}ms")
        print(f"   Dry run: {result['dry_run']}")

        # Print per-term results
        print("\n📊 Per-term results:")
        for term_result in result["results"]:
            print(f"\n   Term: {term_result['term']}")
            print(f"   Success: {term_result['success']}")
            print(f"   Fetched: {term_result['fetched_count']}")
            print(f"   Cleaned: {term_result['cleaned_count']}")
            print(f"   Inserted: {term_result['inserted_count']}")
            print(f"   Duplicates: {term_result['duplicate_count']}")
            if not term_result["success"]:
                print(f"   Error: {term_result.get('error', 'Unknown')}")

        # Print totals
        print("\n📊 Totals:")
        totals = result["totals"]
        print(f"   Terms: {totals['term_count']}")
        print(f"   Successful: {totals['successful_terms']}")
        print(f"   Failed: {totals['failed_terms']}")
        print(f"   Fetched: {totals['fetched_count']}")
        print(f"   Cleaned: {totals['cleaned_count']}")
        print(f"   Inserted: {totals['inserted_count']}")
        print(f"   Duplicates: {totals['duplicate_count']}")

        # TEST 1: Check database status
        print("\n" + "=" * 80)
        print("TEST 1: Verify inserts have status='new' (Requirement 8.1)")
        print("=" * 80)

        # Check for the records we just inserted
        expected_count = totals["inserted_count"]
        db_check = check_db_status(test_db_full_path, expected_count)
        print("\n📊 Database check:")
        print(f"   Records found: {db_check['count']}")
        print(f"   All status='new': {db_check['all_status_new']}")

        if db_check["count"] > 0:
            print("\n   Sample records:")
            for i, record in enumerate(db_check["records"][:3], 1):
                print(
                    f"   {i}. ID={record['id']}, status='{record['status']}', title='{record['title'][:50]}...'"
                )

        if db_check["all_status_new"]:
            print("\n✅ TEST 1 PASSED: All inserted records have status='new'")
        else:
            print("\n❌ TEST 1 FAILED: Some records do not have status='new'")
            for record in db_check["records"]:
                if record["status"] != "new":
                    print(f"   ❌ Record ID {record['id']} has status='{record['status']}'")
            return 1

        # TEST 2: Check for tracker side effects
        print("\n" + "=" * 80)
        print("TEST 2: Verify no tracker side effects (Requirement 8.4)")
        print("=" * 80)

        trackers_after = check_no_side_effects()
        print("\n📊 Tracker check AFTER scrape:")
        print(f"   Trackers directory exists: {trackers_after['trackers_dir_exists']}")
        print(f"   Tracker count: {trackers_after['tracker_count']}")

        # Check if any new trackers were created
        tracker_count_diff = trackers_after["tracker_count"] - trackers_before["tracker_count"]

        if tracker_count_diff == 0:
            print("\n✅ TEST 2 PASSED: No new tracker files created")
        else:
            print(f"\n❌ TEST 2 FAILED: {tracker_count_diff} new tracker file(s) created")
            return 1

        # TEST 3: Verify no status updates to existing records
        print("\n" + "=" * 80)
        print("TEST 3: Verify no status/finalize side effects (Requirement 8.5)")
        print("=" * 80)

        # Check that scrape_jobs only inserts, doesn't update
        # We'll verify this by checking that all records have updated_at IS NULL
        conn = sqlite3.connect(str(test_db_full_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE updated_at IS NOT NULL
        """)

        updated_count = cursor.fetchone()["count"]
        conn.close()

        print("\n📊 Update check:")
        print(f"   Records with updated_at set: {updated_count}")

        if updated_count == 0:
            print("\n✅ TEST 3 PASSED: No records were updated (insert-only behavior)")
        else:
            print(f"\n❌ TEST 3 FAILED: {updated_count} record(s) have updated_at set")
            return 1

        print("\n" + "=" * 80)
        print("✅ ALL SMOKE TESTS PASSED")
        print("=" * 80)
        print("\nSummary:")
        print("  ✅ Requirement 8.1: Inserts arrive with status='new'")
        print("  ✅ Requirement 8.4: No tracker creation side effects")
        print("  ✅ Requirement 8.5: No triage/finalization side effects")

        # Clean up test database
        print(f"\n🗑️  Cleaning up test database: {test_db_path}")
        if test_db_full_path.exists():
            test_db_full_path.unlink()

        return 0

    except Exception as e:
        print("\n❌ ERROR: scrape_jobs failed with exception:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
