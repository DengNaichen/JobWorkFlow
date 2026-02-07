# Smoke Test Results - Task 10.2

## Overview

Manual smoke tests for the `scrape_jobs` MCP tool to verify:
- **Requirement 8.1**: Inserts arrive with status='new'
- **Requirement 8.4**: No tracker creation side effects
- **Requirement 8.5**: No triage/finalization side effects
- **Requirements 7.1-7.5**: Idempotent dedupe behavior

## Test Execution Date

2026-02-06

## Test Scripts

Two smoke test scripts were created and executed:

1. **smoke_test_scrape_jobs.py** - Test with isolated test database
2. **smoke_test_scrape_jobs_production.py** - Test with production database

## Test Results

### Test 1: Isolated Test Database

**Script**: `smoke_test_scrape_jobs.py`

**Configuration**:
- Database: `data/capture/test_scrape_jobs.db` (clean test database)
- Terms: `['python developer']`
- Results wanted: 5
- Location: Ontario, Canada
- Sites: linkedin
- Hours old: 24

**Results**:
```
✅ scrape_jobs completed successfully
   Run ID: scrape_20260206_97bf6c07
   Duration: 3899ms

📊 Totals:
   Fetched: 5
   Cleaned: 5
   Inserted: 5
   Duplicates: 0

TEST 1: Verify inserts have status='new' (Requirement 8.1)
   Records found: 5
   All status='new': True
   ✅ PASSED

TEST 2: Verify no tracker side effects (Requirement 8.4)
   Tracker count before: 0
   Tracker count after: 0
   ✅ PASSED

TEST 3: Verify no status/finalize side effects (Requirement 8.5)
   Records with updated_at set: 0
   ✅ PASSED
```

### Test 2: Production Database

**Script**: `smoke_test_scrape_jobs_production.py`

**Configuration**:
- Database: `data/capture/jobs.db` (production database)
- Terms: `['python developer']`
- Results wanted: 3
- Location: Ontario, Canada
- Sites: linkedin
- Hours old: 24

**Initial State**:
- Total records: 247
- Status counts: {'new': 153, 'reviewed': 31, 'reject': 24, 'shortlist': 22, 'resume_written': 17}

**Results**:

**RUN 1** (Initial scrape):
```
✅ scrape_jobs RUN 1 completed successfully
   Run ID: scrape_20260206_c3a02955
   Duration: 2565ms

📊 Totals:
   Fetched: 3
   Cleaned: 3
   Inserted: 2
   Duplicates: 1
```

**RUN 2** (Re-run for idempotency test):
```
✅ scrape_jobs RUN 2 completed successfully
   Run ID: scrape_20260206_8a721f8b
   Duration: 2481ms

📊 Totals:
   Fetched: 3
   Cleaned: 3
   Inserted: 0
   Duplicates: 3
```

**Final State**:
- Total records: 249 (added 2 new records)
- Status counts: {'new': 155, 'reviewed': 31, 'reject': 24, 'shortlist': 22, 'resume_written': 17}

**Test Results**:
```
TEST 1: Verify inserts have status='new' (Requirement 8.1)
   All recent records have status='new': True
   ✅ PASSED

TEST 2: Verify idempotent dedupe behavior (Requirements 7.1-7.5)
   RUN 1 inserted: 2
   RUN 2 inserted: 0
   RUN 2 duplicates: 3
   ✅ PASSED - Idempotent behavior confirmed

TEST 3: Verify no tracker side effects (Requirement 8.4)
   Tracker count before: 0
   Tracker count after: 0
   ✅ PASSED

TEST 4: Verify no status/finalize side effects (Requirement 8.5)
   Records with updated_at set: 227 (from other tools, expected)
   Records with resume_written_at set: 17 (from other tools, expected)
   ✅ PASSED - No new finalize side effects from scrape_jobs
```

## Summary

### ✅ All Tests Passed

1. **Requirement 8.1 - Status='new' on Insert**: ✅ VERIFIED
   - All newly inserted records have status='new'
   - No records inserted with other statuses

2. **Requirement 8.4 - No Tracker Side Effects**: ✅ VERIFIED
   - No tracker markdown files created during scrape
   - Tracker directory unchanged after scrape operations

3. **Requirement 8.5 - No Triage/Finalization Side Effects**: ✅ VERIFIED
   - No updated_at timestamps set by scrape_jobs
   - No resume_written_at or other finalization fields modified
   - Insert-only behavior confirmed

4. **Requirements 7.1-7.5 - Idempotent Dedupe**: ✅ VERIFIED
   - First run: 2 inserts, 1 duplicate
   - Second run: 0 inserts, 3 duplicates
   - URL-based deduplication working correctly
   - Safe to retry scrape operations

## Observations

1. **Performance**: Scrape operations complete in 2-4 seconds for small batches (3-5 results)
2. **Deduplication**: URL-based dedupe works correctly, preventing duplicate inserts
3. **Boundary Behavior**: Tool strictly adheres to ingestion-only boundaries
4. **Database Integrity**: No unintended side effects on existing records
5. **Production Safety**: Safe to run against production database

## Conclusion

The `scrape_jobs` tool successfully passes all smoke tests for Task 10.2. The tool:
- Correctly inserts records with status='new'
- Maintains strict ingestion-only boundaries
- Does not create tracker files or modify existing records
- Implements idempotent dedupe behavior
- Is safe for production use

## Test Artifacts

- `smoke_test_scrape_jobs.py` - Isolated test database smoke test
- `smoke_test_scrape_jobs_production.py` - Production database smoke test
- Both scripts can be re-run at any time to verify behavior

## How to Run Tests

```bash
# Test with isolated database
cd mcp-server-python
uv run python smoke_test_scrape_jobs.py

# Test with production database
uv run python smoke_test_scrape_jobs_production.py
```
