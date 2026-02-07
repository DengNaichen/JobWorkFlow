# Implementation Plan: career_tailor (Batch Full-Only)

## Overview

This plan implements a simplified `career_tailor` MCP tool:

- batch input required (`items[]`)
- full-only execution (always prepare + compile)
- no automatic finalize
- no compensation writes

The tool outputs `successful_items` that can be passed to `finalize_resume_batch` in a separate prompt step.

## Tasks

- [x] 1. Add batch request validation
  - [x] 1.1 Extend `utils/validation.py` with `validate_career_tailor_batch_parameters(...)`
    - Require non-empty `items[]`
    - Validate each item has `tracker_path`
    - Validate optional item `job_db_id` positive integer
    - Validate optional batch fields: `force`, `full_resume_path`, `resume_template_path`, `applications_dir`, `pdflatex_cmd`
    - Reject unknown fields
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [x] 1.2 Add validation tests
    - Empty items
    - Bad item shape
    - Unknown keys
    - _Requirements: 1.6, 8.1_

- [x] 2. Implement per-item tracker parse and context extraction
  - [x] 2.1 Reuse/extend tracker parser for required fields + `## Job Description`
    - _Requirements: 3.1, 3.3, 3.4, 3.6_

  - [x] 2.2 Add item-level error mapping for missing/malformed tracker
    - Missing file -> `FILE_NOT_FOUND`
    - Missing JD section -> `VALIDATION_ERROR`
    - _Requirements: 3.2, 3.5, 8.2_

- [x] 3. Implement deterministic workspace preparation
  - [x] 3.1 Resolve deterministic `application_slug`
    - `resume_path` first, deterministic fallback second
    - _Requirements: 4.1_

  - [x] 3.2 Ensure workspace directories
    - `resume/`, `cover/`, `cv/`
    - _Requirements: 4.2_

  - [x] 3.3 Materialize `resume.tex` with `force` behavior
    - `created|preserved|overwritten`
    - _Requirements: 4.3, 4.4_

  - [x] 3.4 Regenerate `ai_context.md` every run using atomic writes
    - _Requirements: 4.5, 4.6_

- [x] 4. Implement full-only compile gate
  - [x] 4.1 Placeholder scan before compile
    - _Requirements: 5.2, 5.3_

  - [x] 4.2 Run `pdflatex` and verify non-empty `resume.pdf`
    - _Requirements: 5.1, 5.4, 5.5_

  - [x] 4.3 Add compile tests
    - Placeholder failure
    - Compile failure
    - Compile success with valid PDF
    - _Requirements: 5.3, 5.4, 5.5, 8.3_

- [x] 5. Implement batch tool handler
  - [x] 5.1 Create `tools/career_tailor.py` batch orchestration
    - Process items in input order
    - Continue on item failure
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 5.2 Build structured response
    - `run_id`, totals, ordered `results`
    - _Requirements: 2.4, 7.5_

  - [x] 5.3 Build `successful_items` handoff payload
    - Include only items with `job_db_id`
    - Add warning for successful items missing `job_db_id`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 5.4 Enforce boundary behavior in handler
    - No DB status writes
    - No tracker status writes
    - No finalize calls
    - No compensation writes
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

- [x] 6. Register MCP tool and docs
  - [x] 6.1 Register `career_tailor` in `server.py` with batch full-only signature
    - _Requirements: 1.1, 1.5_

  - [x] 6.2 Update `mcp-server-python/README.md` and root `README.md`
    - Mark `career_tailor` implemented
    - Document separate finalize step
    - _Requirements: 6.2, 7.1_

- [x] 7. Add integration tests
  - [x] 7.1 Batch partial success test
    - one success + one failure, batch continues
    - _Requirements: 2.2, 2.5_

  - [x] 7.2 Boundary test
    - verify no DB/tracker status mutation
    - _Requirements: 6.1, 6.3, 6.4_

  - [x] 7.3 Finalize handoff test
    - validate `successful_items` shape for downstream finalize
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 8. Checkpoint
  - [x] 8.1 Run targeted tests for `career_tailor`
    - _Requirements: 8.4_

  - [x] 8.2 Manual smoke run with 2-3 real trackers
    - Confirm output list can feed `finalize_resume_batch`
    - _Requirements: 7.1, 7.2_

## Notes

- This MVP intentionally excludes mode switching and internal finalize orchestration.
- Prompt/workflow should call `finalize_resume_batch` separately after reviewing `successful_items`.
