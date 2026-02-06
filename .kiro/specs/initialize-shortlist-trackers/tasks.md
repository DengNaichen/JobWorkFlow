# Implementation Plan: initialize_shortlist_trackers

## Overview

This plan implements a projection-oriented MCP tool that reads shortlisted jobs from SQLite and initializes deterministic tracker markdown files plus workspace directories for downstream resume tailoring. The design preserves DB-as-SSOT and guarantees idempotent, atomic file operations.

## Tasks

- [ ] 1. Extend validation and parameter handling
  - [x] 1.1 Add initialize tool parameter validators in `utils/validation.py`
    - Implement validation for `limit` (1-200, default 50)
    - Implement validation for `trackers_dir` (optional non-empty string)
    - Implement validation for `force` and `dry_run` (boolean with defaults)
    - Add combined validator `validate_initialize_shortlist_trackers_parameters(...)`
    - _Requirements: 1.3, 1.4, 1.5, 8.1, 9.1, 9.2_
  
  - [ ]* 1.2 Write unit tests for parameter validation
    - Valid/invalid `limit` values and types
    - Invalid `trackers_dir` types/empty values
    - Invalid `force`/`dry_run` types
    - Unknown argument handling
    - _Requirements: 1.4, 8.1, 9.2_

- [ ] 2. Implement shortlist DB query path
  - [x] 2.1 Extend `db/jobs_reader.py` with shortlist query function
    - Add `query_shortlist_jobs(conn, limit)` using deterministic order: `captured_at DESC, id DESC`
    - Return fixed fields required for tracker generation
    - Keep read-only query semantics
    - _Requirements: 1.1, 1.2, 6.1, 6.2, 6.3_
  
  - [ ]* 2.2 Write tests for shortlist query behavior
    - Returns only `status='shortlist'`
    - Deterministic ordering and limit application
    - Empty shortlist returns empty set without error
    - _Requirements: 1.1, 1.2, 1.6_

- [ ] 3. Implement deterministic planning utilities
  - [x] 3.1 Add slug and filename planning module (`utils/tracker_planner.py`)
    - Implement deterministic `application_slug` generation
    - Implement deterministic tracker filename generation with job identity
    - Compute tracker path from `trackers_dir`
    - _Requirements: 2.2, 3.1, 4.3, 9.5_
  
  - [x] 3.2 Add workspace path planning helpers
    - Compute `resume_path` and `cover_letter_path` wiki-link strings
    - Compute required workspace directories for each job
    - _Requirements: 3.2, 3.3, 10.2, 10.3_
  
  - [ ]* 3.3 Write unit tests for planner determinism
    - Same input -> same slug, filename, tracker path
    - Collision resistance for same company with different IDs
    - Path formatting compatibility for downstream tools
    - _Requirements: 2.2, 3.1, 9.5_

- [ ] 4. Implement tracker markdown renderer
  - [x] 4.1 Add renderer module (`utils/tracker_renderer.py`)
    - Render stable frontmatter keys including required fields
    - Set initial tracker status to `Reviewed`
    - Emit exact `## Job Description` and `## Notes` headings
    - Insert description text or fallback when missing
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 10.1, 10.2, 10.5_
  
  - [ ]* 4.2 Write renderer unit tests
    - Verify required frontmatter keys
    - Verify exact section headers and content layout
    - Verify ISO `application_date` formatting
    - Verify dataview-friendly YAML formatting
    - _Requirements: 2.3, 10.1, 10.4, 10.5_

- [ ] 5. Implement filesystem operations (atomic + idempotent)
  - [x] 5.1 Add atomic write helper in `utils/file_ops.py`
    - Write using temporary file + atomic replace
    - Ensure cleanup on failure
    - _Requirements: 5.1, 5.5_
  
  - [x] 5.2 Add workspace bootstrap helper
    - Create `data/applications/<slug>/resume/` and `cover/` dirs when needed
    - Do not create resume/cover content files
    - _Requirements: 3.4, 3.5_
  
  - [x] 5.3 Implement idempotent action resolution
    - Existing file + `force=false` -> `skipped_exists`
    - Existing file + `force=true` -> `overwritten`
    - Missing file -> `created`
    - _Requirements: 4.1, 4.2, 4.4, 5.4_
  
  - [ ]* 5.4 Write filesystem behavior tests
    - Idempotent repeated runs with `force=false`
    - Overwrite behavior with `force=true`
    - Atomic write leaves no partial file on failure injection
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2_

- [ ] 6. Implement main MCP tool handler
  - [x] 6.1 Create `tools/initialize_shortlist_trackers.py`
    - Validate request parameters
    - Read shortlist jobs from DB
    - Plan file/workspace operations per job
    - Execute writes when not `dry_run`
    - Continue batch on per-item failures
    - _Requirements: 1.1, 1.6, 5.2, 5.3, 8.7, 9.1, 9.4_
  
  - [x] 6.2 Build structured response and counters
    - Return `created_count`, `skipped_count`, `failed_count`, `results`
    - Include per-item `id`, `tracker_path`, `action`, `success`, optional `error`
    - Preserve input/selection order in `results`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [x] 6.3 Implement dry-run behavior
    - Compute deterministic outcomes and actions without creating dirs/files
    - Ensure response shape/counts match non-dry-run semantics
    - _Requirements: 9.4, 9.5_
  
  - [x] 6.4 Add top-level error mapping
    - Map validation failures to `VALIDATION_ERROR`
    - Map DB missing/query failures to `DB_NOT_FOUND`/`DB_ERROR`
    - Map unexpected exceptions to `INTERNAL_ERROR`
    - Ensure sanitized messages and `retryable` flag
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
  
  - [x] 6.5 Prevent stale planner state leaking into failed-item results
    - Reset per-item planning state each loop iteration
    - Ensure `tracker_path` is omitted on hard planning failures
    - _Requirements: 7.2_

- [ ] 7. Register tool in MCP server
  - [x] 7.1 Update `server.py` tool registration
    - Add `initialize_shortlist_trackers` tool with schema-aligned signature
    - Wire arguments into new tool handler
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [x] 7.2 Update server instructions and tool metadata
    - Document behavior as projection-only tracker initializer
    - Clarify idempotent and dry-run semantics in description
    - _Requirements: 9.3, 10.5_

- [ ] 8. Add integration and regression tests
  - [x] 8.1 Create `tests/test_initialize_shortlist_trackers.py`
    - Happy path: creates trackers for shortlist jobs
    - Empty shortlist path: zero counts, success
    - Existing files skip/overwrite behavior with `force`
    - Dry-run computes outcomes with no writes
    - Per-item write failure does not stop batch
    - _Requirements: 1.6, 4.1, 4.2, 5.2, 5.3, 7.1_
  
  - [x] 8.2 Add read-only boundary test
    - Snapshot DB before/after tool call
    - Verify no row field changes (status and others unchanged)
    - _Requirements: 6.1, 6.2, 6.4_
  
  - [ ]* 8.3 Add server-level integration test
    - Invoke tool through MCP registration path
    - Verify response schema and error schema
    - _Requirements: 9.1, 9.3_
  
  - [x] 8.4 Add hard-failure result isolation test
    - Simulate planner failure and verify failed item does not reuse prior `tracker_path`
    - _Requirements: 7.2_

- [ ] 9. Update documentation
  - [x] 9.1 Update `mcp-server-python/README.md`
    - Add tool summary, parameters, and response examples
    - Add dry-run and force usage examples
    - _Requirements: 9.3, 9.4_
  
  - [x] 9.2 Update root `README.md` status
    - Move `initialize_shortlist_trackers` from planned to implemented when complete
    - Keep DB-SSOT guardrail language intact
    - _Requirements: 6.1, 10.5_

- [ ] 10. Checkpoint - End-to-end verification
  - [x] 10.1 Run targeted test suite for new tool
    - Validate deterministic outputs across repeated runs
    - Validate idempotency and partial-failure behavior
    - _Requirements: 4.3, 5.3, 7.3_
  
  - [x] 10.2 Manual smoke check with sample shortlist data
    - Confirm tracker files parse in Obsidian Dataview
    - Confirm workspace directory bootstrap correctness
    - _Requirements: 3.4, 10.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task maps back to requirements for traceability
- Implementation should preserve current layered structure (`tools/`, `db/`, `utils/`, `models/`)
- DB status remains SSOT; tracker files are projection artifacts only
