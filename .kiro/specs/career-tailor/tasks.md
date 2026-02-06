# Implementation Plan: career_tailor

## Overview

This plan implements `career_tailor` as a workspace bootstrap + optional compile MCP tool. The implementation creates deterministic per-job resume workspaces from tracker notes, regenerates `ai_context.md`, enforces placeholder guardrails, and optionally compiles `resume.pdf` while preserving strict boundaries (no DB/status writes).

## Tasks

- [ ] 1. Add validation for career_tailor inputs
  - [ ] 1.1 Extend `utils/validation.py` with `validate_career_tailor_parameters(...)`
    - Validate required `tracker_path`
    - Validate optional booleans `compile`, `force`
    - Validate optional path overrides: `full_resume_path`, `resume_template_path`, `applications_dir`, `pdflatex_cmd`
    - Reject unknown keys in request payload
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  
  - [ ]* 1.2 Add unit tests for validation edge cases
    - Missing tracker_path
    - Wrong type for booleans and path fields
    - Unknown properties
    - _Requirements: 1.5, 1.6, 11.1_

- [ ] 2. Implement tracker parsing module
  - [ ] 2.1 Create `utils/tracker_parser.py`
    - Parse markdown frontmatter fields (`company`, `position`, `resume_path`, `reference_link`, optional `job_db_id`)
    - Extract body content under exact `## Job Description` heading
    - Return structured tracker context object
    - _Requirements: 2.3, 2.4, 2.6_
  
  - [ ] 2.2 Handle tracker read errors
    - Return `FILE_NOT_FOUND` for missing/unreadable tracker file
    - Return `VALIDATION_ERROR` when `## Job Description` section is missing
    - _Requirements: 2.2, 2.5, 11.1, 11.2_
  
  - [ ]* 2.3 Add tracker parser tests
    - Valid tracker parse
    - Missing frontmatter keys behavior
    - Missing job description heading
    - _Requirements: 2.3, 2.4, 2.5_

- [ ] 3. Implement deterministic slug/workspace resolution
  - [ ] 3.1 Create `utils/slug_resolver.py`
    - Parse slug from tracker `resume_path` wiki-link when available
    - Implement deterministic fallback slug from company/position/job_db_id/reference_link
    - _Requirements: 3.1, 3.2, 3.3, 3.5_
  
  - [ ] 3.2 Create workspace path resolver in `utils/workspace.py`
    - Resolve workspace root and canonical paths for:
      - `resume/resume.tex`
      - `resume/ai_context.md`
      - `resume/resume.pdf`
    - _Requirements: 3.4, 10.1, 10.5_
  
  - [ ]* 3.3 Add determinism tests
    - Same tracker input always yields same slug and paths
    - Multiple fallbacks still deterministic
    - _Requirements: 3.3, 10.5_

- [ ] 4. Implement workspace initialization
  - [ ] 4.1 Add directory bootstrap helper
    - Ensure `resume/`, `cover/`, `cv/` directories exist
    - Keep operations constrained to workspace root
    - _Requirements: 4.1, 9.4, 9.5_
  
  - [ ] 4.2 Add resume template materialization
    - Initialize `resume.tex` from `resume_skeleton.tex` when missing
    - Support `force` overwrite semantics
    - Return action enum (`created`, `preserved`, `overwritten`)
    - _Requirements: 4.2, 6.1, 6.2, 6.5_
  
  - [ ] 4.3 Add atomic write utility reuse/extension
    - Use temp-file + rename for generated workspace files
    - _Requirements: 4.4_

- [ ] 5. Implement ai_context generation
  - [ ] 5.1 Create `utils/ai_context_renderer.py`
    - Load full resume source from default/override path
    - Render deterministic markdown sections:
      - `# AI Context`
      - `## Full Resume Source (raw)`
      - `## Job Description`
      - `## Notes`
      - `## Instructions`
    - _Requirements: 5.1, 5.3, 5.4, 5.5_
  
  - [ ] 5.2 Handle source-file errors
    - Missing `full_resume.md` -> `FILE_NOT_FOUND`
    - Missing template path -> `TEMPLATE_NOT_FOUND`
    - _Requirements: 5.2, 11.2_
  
  - [ ] 5.3 Regenerate `ai_context.md` on every run
    - Write file atomically
    - Preserve deterministic content for unchanged inputs
    - _Requirements: 6.3, 6.4_
  
  - [ ]* 5.4 Add renderer unit tests
    - Section presence and ordering checks
    - Content inclusion checks for full resume + JD
    - _Requirements: 5.3, 5.4, 5.5_

- [ ] 6. Implement placeholder guardrails and compile service
  - [ ] 6.1 Create placeholder scanner in `utils/latex_guardrails.py`
    - Detect unreplaced tokens: `PROJECT-AI-*`, `PROJECT-BE-*`, `WORK-BULLET-POINT-*`
    - Return matched token summary
    - _Requirements: 8.1, 8.3_
  
  - [ ] 6.2 Create compile runner in `utils/latex_compiler.py`
    - Run `pdflatex -interaction=nonstopmode resume.tex` in workspace
    - Support override `pdflatex_cmd`
    - Validate `resume.pdf` exists and non-zero size
    - Cleanup aux files (`.aux`, `.log`, `.out`, `.synctex.gz`)
    - _Requirements: 7.1, 7.3, 7.4, 8.4_
  
  - [ ] 6.3 Enforce compile pre-check
    - If placeholders detected and `compile=true`, return `VALIDATION_ERROR` before compile
    - _Requirements: 8.1, 8.2_
  
  - [ ] 6.4 Map compile failures
    - Missing/unusable pdflatex -> `COMPILE_ERROR`
    - LaTeX execution failure -> sanitized `COMPILE_ERROR`
    - _Requirements: 7.2, 8.5, 11.3, 11.7_

- [ ] 7. Implement main MCP tool handler
  - [ ] 7.1 Create `tools/career_tailor.py`
    - Orchestrate validation, parsing, slug resolution, workspace init, context generation
    - Optionally compile when `compile=true`
    - _Requirements: 1.1, 4.5, 7.5, 9.4_
  
  - [ ] 7.2 Build structured success response
    - Include required output fields and action flags
    - Include `placeholder_check_passed` for compile flow
    - Keep response JSON-serializable
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [ ] 7.3 Add top-level error mapping and sanitization
    - `VALIDATION_ERROR`, `FILE_NOT_FOUND`, `TEMPLATE_NOT_FOUND`, `COMPILE_ERROR`, `INTERNAL_ERROR`
    - Include `retryable` in error object
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

- [ ] 8. Register tool in MCP server
  - [ ] 8.1 Update `server.py` with `career_tailor` registration
    - Define tool name/description
    - Wire function arguments to handler
    - _Requirements: 1.1, 10.1_
  
  - [ ] 8.2 Update server instructions/docs strings
    - Mention workspace + optional compile behavior
    - Mention placeholder guardrail expectation
    - _Requirements: 8.2, 10.2_

- [ ] 9. Add tests for end-to-end behavior
  - [ ] 9.1 Create `tests/test_career_tailor.py`
    - Workspace init success with `compile=false`
    - `resume.tex` action matrix (`created`, `preserved`, `overwritten`)
    - `ai_context.md` regeneration check
    - _Requirements: 4.2, 6.1, 6.2, 6.3, 6.5_
  
  - [ ] 9.2 Add compile path tests
    - Placeholder present -> `VALIDATION_ERROR`
    - Compile success produces PDF
    - Compile command failure -> `COMPILE_ERROR`
    - _Requirements: 7.1, 7.2, 8.1, 8.2, 8.5_
  
  - [ ] 9.3 Add boundary tests
    - Verify tracker file unchanged
    - Verify DB file untouched
    - Verify writes stay in workspace root
    - _Requirements: 9.1, 9.2, 9.3, 9.5_
  
  - [ ]* 9.4 Add server integration test
    - Invoke via MCP registration path
    - Validate response/error schema contracts
    - _Requirements: 10.1, 11.5_

- [ ] 10. Update documentation
  - [ ] 10.1 Update `mcp-server-python/README.md`
    - Add `career_tailor` parameters and examples
    - Add compile and guardrail behavior notes
    - _Requirements: 1.1, 7.1, 8.2, 10.1_
  
  - [ ] 10.2 Update root `README.md` implementation status when complete
    - Move `career_tailor` from planned to implemented
    - Keep separation from finalize step explicit
    - _Requirements: 9.3_

- [ ] 11. Checkpoint - End-to-end verification
  - [ ] 11.1 Run targeted test suite
    - Validate deterministic workspace outputs
    - Validate compile and placeholder guardrails
    - _Requirements: 6.4, 8.2, 10.5_
  
  - [ ] 11.2 Manual smoke check with existing tracker file
    - `compile=false` bootstrap
    - manual bullet rewrite
    - `compile=true` output validation
    - _Requirements: 4.5, 7.1, 8.4_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references requirement IDs for traceability
- Keep layered project structure consistent (`tools/`, `utils/`, `models/`)
- `career_tailor` must remain artifact-focused and must not perform DB/status finalization writes

