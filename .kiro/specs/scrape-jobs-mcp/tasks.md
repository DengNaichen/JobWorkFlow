# Implementation Plan: scrape_jobs

## Overview

This plan implements `scrape_jobs` as the MCP ingestion tool for pipeline step 1. It executes source scraping, normalization/filtering, idempotent DB insertion, and structured run reporting with partial-success semantics.

## Tasks

- [ ] 1. Add request validation for scrape tool
  - [x] 1.1 Extend `utils/validation.py` with `validate_scrape_jobs_parameters(...)`
    - Validate `terms`, `location`, `sites`, `results_wanted`, `hours_old`
    - Validate `status`, `db_path`, `capture_dir`, `dry_run`, `save_capture_json`
    - Validate retry settings (`preflight_host`, `retry_count`, `retry_sleep_seconds`, `retry_backoff`)
    - Reject unknown request properties
    - _Requirements: 1.1, 1.4, 1.5, 8.2, 11.1, 12.2, 12.3_

  - [x] 1.2 Add validation tests
    - Valid/invalid bounds for `results_wanted`, `hours_old`, retry fields
    - Empty terms, unknown keys, invalid status, invalid path types
    - _Requirements: 1.4, 1.5, 11.1, 12.2_

- [ ] 2. Implement JobSpy adapter layer
  - [x] 2.1 Create `utils/jobspy_adapter.py`
    - Wrap `jobspy.scrape_jobs(...)` invocation
    - Accept per-term config (`sites`, `location`, `results_wanted`, `hours_old`)
    - Return list of raw source records
    - _Requirements: 3.1, 3.3, 3.5_

  - [x] 2.2 Implement preflight DNS helper
    - Add preflight + retry/backoff behavior
    - Return structured term-level failure on preflight exhaustion
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [~]* 2.3 Add adapter tests
    - Mock provider success/failure
    - Verify per-term isolation and deterministic term ordering
    - _Requirements: 3.2, 3.4, 3.5_

- [ ] 3. Implement normalization and filtering utilities
  - [x] 3.1 Create `utils/scrape_normalizer.py`
    - Map raw fields to cleaned schema (`url`, `title`, `description`, `source`, `job_id`, `location`, `company`, `captured_at`, payload)
    - Parse LinkedIn job ID from URL with fallback
    - Normalize timestamps to UTC ISO string
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 3.2 Add filtering pass
    - Skip empty URL records
    - Apply `require_description` filtering
    - Return cleaned list + skip counters
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [~]* 3.3 Add normalization/filter tests
    - URL fallback, job_id parsing, timestamp fallback, serialization guarantees
    - Filter counter correctness
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3_

- [ ] 4. Implement ingestion DB writer
  - [x] 4.1 Create `db/jobs_ingest_writer.py`
    - Resolve DB path with default + overrides
    - Ensure parent dirs exist
    - Bootstrap table/index schema (`jobs`, `idx_jobs_status`)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 4.2 Implement insert/dedupe methods
    - Parameterized `INSERT OR IGNORE`
    - Count inserted vs duplicates
    - Preserve existing rows unchanged on dedupe
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.3_

  - [x] 4.3 Enforce boundary behavior
    - Insert-only semantics; no update/delete statements
    - Initial status default `new` (validated override allowed)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [~]* 4.4 Add DB writer tests
    - Schema bootstrap on empty DB
    - Idempotent re-run yields duplicates not inserts
    - Existing rows unchanged on dedupe hits
    - _Requirements: 6.4, 7.2, 7.5, 8.3_

- [ ] 5. Implement capture artifact writer
  - [x] 5.1 Add optional per-term capture writer (`utils/capture_writer.py`)
    - Write capture JSON when `save_capture_json=true`
    - Deterministic per-term filename strategy
    - Return relative `capture_path` for response
    - _Requirements: 9.1, 9.3, 9.5_

  - [x] 5.2 Add capture write tests
    - Write enabled/disabled behavior
    - Failure mapping does not crash whole run
    - _Requirements: 9.2, 9.4, 11.5_

- [ ] 6. Implement main tool handler
  - [x] 6.1 Create `tools/scrape_jobs.py`
    - Orchestrate validation, preflight, per-term scrape, normalize, capture, insert
    - Support `dry_run=true` (no DB writes)
    - Continue on term-level failures
    - _Requirements: 1.2, 1.3, 3.2, 5.4, 10.4, 11.5_

  - [x] 6.2 Build structured response payload
    - Include run metadata (`run_id`, timestamps, `duration_ms`)
    - Include ordered term results and aggregate totals
    - _Requirements: 10.1, 10.2, 10.3, 10.5_

  - [x] 6.3 Add sanitized error mapping
    - Top-level fatal error object for validation/db/runtime failures
    - Per-term error strings for partial failures
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 7. Register MCP tool in server
  - [x] 7.1 Update `server.py`
    - Register `scrape_jobs` tool name, signature, and docs
    - Wire wrapper to `tools.scrape_jobs.scrape_jobs(...)`
    - _Requirements: 1.1, 12.1_

  - [x] 7.2 Update server instructions
    - Describe scrape tool as ingestion-only boundary
    - _Requirements: 8.4, 8.5, 12.1_

- [ ] 8. Add integration tests
  - [x] 8.1 Create `tests/test_scrape_jobs_tool.py`
    - Happy path with mocked source records
    - Partial term failure while other terms succeed
    - Dry-run behavior (no DB writes)
    - _Requirements: 3.2, 5.4, 10.2, 10.3_

  - [x] 8.2 Add dedupe/idempotency integration tests
    - Same input twice -> inserts then duplicates
    - _Requirements: 7.1, 7.2, 7.5, 12.5_

  - [x] 8.3 Add boundary tests
    - Verify tool does not write tracker files
    - Verify existing rows are not updated on dedupe
    - _Requirements: 8.3, 8.4, 8.5_

  - [~]* 8.4 Add server registration tests
    - Ensure tool is discoverable through MCP server
    - Verify wrapper argument forwarding
    - _Requirements: 12.1_

- [ ] 9. Update documentation
  - [x] 9.1 Update `mcp-server-python/README.md`
    - Add `scrape_jobs` contract, examples, and response schema
    - _Requirements: 10.1, 12.1_

  - [x] 9.2 Update root `README.md`
    - Mark scrape step as MCP-capable path
    - Keep pipeline boundaries explicit
    - _Requirements: 8.5, 12.1_

- [ ] 10. Checkpoint - End-to-end verification
  - [x] 10.1 Run targeted tests for scrape stack
    - Validation, adapter, normalization, DB writer, tool integration
    - _Requirements: 1.4, 4.5, 7.4, 10.5, 11.4_

  - [x] 10.2 Manual smoke test in local DB
    - Confirm inserts arrive as `status='new'`
    - Confirm no tracker/status/finalize side effects
    - _Requirements: 8.1, 8.4, 8.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Keep implementation ingestion-focused and boundary-safe per steering rules
- Prefer reuse of existing script logic (`scripts/jobspy_batch_run.py`, `scripts/import_jobspy_to_db.py`) by extraction/refactor, not reimplementation from scratch
