#!/usr/bin/env python3
"""
Manual smoke test for update_tracker_status tool.

Tests:
1. Block Resume Written without valid artifacts
2. Allow update after artifacts are valid
"""

import os
import shutil
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tools.update_tracker_status import update_tracker_status


def main():
    print("=" * 80)
    print("MANUAL SMOKE TEST: update_tracker_status")
    print("=" * 80)

    # Test tracker path
    tracker_path = "trackers/2026-02-05-amazon.md"
    pdf_path = "data/applications/amazon/resume/resume.pdf"
    pdf_backup = "data/applications/amazon/resume/resume.pdf.backup"

    # Verify tracker exists
    if not os.path.exists(tracker_path):
        print(f"❌ ERROR: Tracker not found: {tracker_path}")
        return 1

    print(f"\n📄 Using tracker: {tracker_path}")
    print(f"📄 PDF path: {pdf_path}")

    # Test 1: Try to update to Resume Written with missing PDF
    print("\n" + "=" * 80)
    print("TEST 1: Block Resume Written without valid artifacts")
    print("=" * 80)

    # Backup and remove PDF
    if os.path.exists(pdf_path):
        print(f"📦 Backing up PDF to: {pdf_backup}")
        shutil.copy2(pdf_path, pdf_backup)
        os.remove(pdf_path)
        print(f"🗑️  Removed PDF: {pdf_path}")

    # First, set status to Reviewed so we can test the transition
    print("\n🔄 Setting tracker status to 'Reviewed' for test setup...")
    result = update_tracker_status(
        {
            "tracker_path": tracker_path,
            "target_status": "Reviewed",
            "force": True,  # Use force to bypass policy
        }
    )

    if result.get("success"):
        print(
            f"✅ Setup complete: status set to '{result['previous_status']}' -> '{result['target_status']}'"
        )
    else:
        print(f"❌ Setup failed: {result}")
        # Restore PDF before exiting
        if os.path.exists(pdf_backup):
            shutil.move(pdf_backup, pdf_path)
        return 1

    # Now try to update to Resume Written (should be blocked)
    print("\n🔄 Attempting to update to 'Resume Written' without PDF...")
    result = update_tracker_status(
        {"tracker_path": tracker_path, "target_status": "Resume Written"}
    )

    if result.get("success"):
        print("❌ TEST 1 FAILED: Update should have been blocked but succeeded!")
        print(f"   Result: {result}")
        # Restore PDF before exiting
        if os.path.exists(pdf_backup):
            shutil.move(pdf_backup, pdf_path)
        return 1
    else:
        print("✅ TEST 1 PASSED: Update blocked as expected")
        print(f"   Action: {result.get('action')}")
        print(f"   Error: {result.get('error')}")
        print(f"   Guardrail check passed: {result.get('guardrail_check_passed')}")

    # Test 2: Restore PDF and allow update
    print("\n" + "=" * 80)
    print("TEST 2: Allow update after artifacts are valid")
    print("=" * 80)

    # Restore PDF
    if os.path.exists(pdf_backup):
        print(f"📦 Restoring PDF from: {pdf_backup}")
        shutil.move(pdf_backup, pdf_path)
        print(f"✅ PDF restored: {pdf_path}")

    # Try to update to Resume Written (should succeed)
    print("\n🔄 Attempting to update to 'Resume Written' with valid artifacts...")
    result = update_tracker_status(
        {"tracker_path": tracker_path, "target_status": "Resume Written"}
    )

    if not result.get("success"):
        print("❌ TEST 2 FAILED: Update should have succeeded but was blocked!")
        print(f"   Result: {result}")
        return 1
    else:
        print("✅ TEST 2 PASSED: Update succeeded as expected")
        print(f"   Action: {result.get('action')}")
        print(f"   Previous status: {result.get('previous_status')}")
        print(f"   Target status: {result.get('target_status')}")
        print(f"   Guardrail check passed: {result.get('guardrail_check_passed')}")

    print("\n" + "=" * 80)
    print("✅ ALL SMOKE TESTS PASSED")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
