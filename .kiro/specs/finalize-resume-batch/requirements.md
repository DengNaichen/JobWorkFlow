# Requirements Document

## Introduction

The `finalize_resume_batch` MCP tool performs the final write-back step after resume compile succeeds. It commits durable completion state by updating DB status/audit fields and synchronizing tracker frontmatter status in one operational step.

This tool is commit-focused:
- Database status remains the SSOT.
- Tracker status is a synchronized projection for Obsidian workflow.

## Glossary

- **MCP_Tool**: A Model Context Protocol tool invokable by an LLM agent
- **Finalization_Item**: One job finalize request entry in the batch
- **Job_Database**: SQLite database at `data/capture/jobs.db`
- **Tracker_Note**: Markdown note under `trackers/` with frontmatter `status`
- **Resume_Artifact**: Files `resume.tex` and `resume.pdf` under `data/applications/<slug>/resume/`
- **Compensation_Fallback**: Automatic fallback to DB `reviewed` status with `last_error` on finalize failure

## Requirements

### Requirement 1: Batch Finalization Interface

**User Story:** As a calling agent, I want to finalize multiple jobs in one call, so that commit/write-back is efficient and traceable.

#### Acceptance Criteria

1. THE MCP_Tool SHALL accept `items` as an array of finalization entries
2. WHEN `items` is empty, THE MCP_Tool SHALL return success with zero finalized items
3. THE MCP_Tool SHALL support batches from 1 to 100 items
4. WHEN batch size exceeds 100, THE MCP_Tool SHALL return `VALIDATION_ERROR`
5. THE MCP_Tool SHALL support optional `run_id`, `db_path`, and `dry_run` parameters
6. WHEN `run_id` is omitted, THE MCP_Tool SHALL generate one deterministic batch run identifier for the call

### Requirement 2: Item Input Validation

**User Story:** As an operator, I want each finalization item validated up front, so that malformed requests fail clearly.

#### Acceptance Criteria

1. EACH item SHALL require `id` (job DB id) and `tracker_path`
2. EACH item MAY include optional `resume_pdf_path` override
3. WHEN item `id` is not a positive integer, THE MCP_Tool SHALL report item failure
4. WHEN item `tracker_path` is missing/empty, THE MCP_Tool SHALL report item failure
5. WHEN duplicate `id` values exist in one request, THE MCP_Tool SHALL return request-level `VALIDATION_ERROR`
6. THE MCP_Tool SHALL preserve result order matching input order

### Requirement 3: Precondition Validation Before Commit

**User Story:** As a quality gate, I want finalization blocked unless resume artifacts are valid, so that incomplete output is never marked as completed.

#### Acceptance Criteria

1. THE MCP_Tool SHALL verify `tracker_path` file exists and is readable
2. THE MCP_Tool SHALL verify `resume.pdf` exists and has non-zero file size
3. THE MCP_Tool SHALL verify companion `resume.tex` exists
4. THE MCP_Tool SHALL scan `resume.tex` for known placeholder tokens before commit
5. WHEN placeholder tokens are present, THE MCP_Tool SHALL mark item as failed and SHALL NOT finalize that item
6. THE MCP_Tool SHALL resolve `resume_pdf_path` from tracker frontmatter when item override is not provided

### Requirement 4: Database Schema and Connection Preconditions

**User Story:** As a system administrator, I want schema preflight checks, so that finalization does not partially run against incompatible DB schemas.

#### Acceptance Criteria

1. THE MCP_Tool SHALL connect to `data/capture/jobs.db` by default
2. THE MCP_Tool SHALL support `db_path` override
3. WHEN DB file is missing, THE MCP_Tool SHALL return `DB_NOT_FOUND`
4. THE MCP_Tool SHALL preflight required columns before processing:
   - `status`
   - `updated_at`
   - `resume_pdf_path`
   - `resume_written_at`
   - `run_id`
   - `attempt_count`
   - `last_error`
5. WHEN required columns are missing, THE MCP_Tool SHALL fail with schema/migration-required error before applying updates
6. DB connections SHALL always be closed

### Requirement 5: Finalization Write Semantics (Success Path)

**User Story:** As a pipeline, I want successful finalize to update durable completion fields, so that downstream automation can rely on SSOT status and audit metadata.

#### Acceptance Criteria

1. ON successful item finalization, THE MCP_Tool SHALL set DB `status='resume_written'`
2. THE MCP_Tool SHALL set `resume_pdf_path` to the validated PDF path
3. THE MCP_Tool SHALL set `resume_written_at` to current UTC timestamp
4. THE MCP_Tool SHALL set `run_id` to batch run id for the invocation
5. THE MCP_Tool SHALL increment `attempt_count` by 1 for each finalization attempt
6. THE MCP_Tool SHALL clear `last_error` on successful finalization

### Requirement 6: Tracker Synchronization

**User Story:** As an Obsidian workflow user, I want tracker status synchronized to completion, so that board view matches DB milestones.

#### Acceptance Criteria

1. ON successful item finalization, THE MCP_Tool SHALL update tracker frontmatter `status` to `Resume Written`
2. THE MCP_Tool SHALL preserve all other frontmatter fields and body content
3. Tracker updates SHALL be atomic (temp file + rename)
4. WHEN tracker write succeeds, THE item SHALL be marked finalized
5. WHEN tracker write fails, THE item SHALL enter failure compensation flow

### Requirement 7: Failure Compensation and Fallback

**User Story:** As an operator, I want any finalize failure to return job to retryable state, so that failures never leave ambiguous completion state.

#### Acceptance Criteria

1. WHEN any finalize write step fails for an item, THE MCP_Tool SHALL set DB `status='reviewed'` for that item
2. THE MCP_Tool SHALL write `last_error` with sanitized failure reason
3. THE fallback update SHALL include `updated_at` timestamp
4. THE MCP_Tool SHALL continue processing remaining items after one item fails
5. Fallback behavior SHALL be applied per-item (not all-or-nothing for the entire batch)

### Requirement 8: Idempotency and Retry Behavior

**User Story:** As a pipeline operator, I want safe retries on finalize, so that repeated calls do not corrupt state.

#### Acceptance Criteria

1. Re-running the same valid item SHALL keep final status as `resume_written`
2. Re-running a failed item after fixing artifacts SHALL allow successful finalization
3. `attempt_count` SHALL increment on each finalize attempt (success or failure)
4. Repeated calls SHALL NOT duplicate tracker files or create additional tracker notes
5. THE MCP_Tool SHALL return explicit per-item actions (for example `finalized`, `already_finalized`, `failed`)

### Requirement 9: Dry-Run Support

**User Story:** As an operator, I want to preview finalize outcomes without writes, so that I can validate readiness before committing.

#### Acceptance Criteria

1. WHEN `dry_run=true`, THE MCP_Tool SHALL run all item validations and planning steps
2. WHEN `dry_run=true`, THE MCP_Tool SHALL NOT mutate DB rows
3. WHEN `dry_run=true`, THE MCP_Tool SHALL NOT write tracker files
4. Dry-run responses SHALL include predicted per-item actions and failure reasons
5. Dry-run response ordering SHALL match input ordering

### Requirement 10: Structured Response Format

**User Story:** As a calling agent, I want detailed per-item finalize outcomes, so that I can trigger retries or next-step automation accurately.

#### Acceptance Criteria

1. THE MCP_Tool SHALL return:
   - `run_id`
   - `finalized_count`
   - `failed_count`
   - `dry_run`
   - `results`
2. EACH `results` item SHALL include:
   - `id`
   - `tracker_path`
   - `resume_pdf_path` (nullable on early failure)
   - `action`
   - `success`
   - `error` (optional)
3. THE MCP_Tool SHALL keep `results` ordered exactly as input
4. ALL response values SHALL be JSON-serializable
5. THE MCP_Tool SHALL include non-fatal `warnings` when applicable

### Requirement 11: Error Handling

**User Story:** As an operator, I want clear error categories, so that retry strategies are consistent and safe.

#### Acceptance Criteria

1. Request-level validation failures SHALL return top-level `VALIDATION_ERROR`
2. Missing DB SHALL return top-level `DB_NOT_FOUND`
3. DB operation failures SHALL return top-level `DB_ERROR`
4. Unexpected runtime failures SHALL return top-level `INTERNAL_ERROR`
5. Top-level errors SHALL include `retryable` boolean
6. Per-item precondition/finalization failures SHALL be represented in `results` (not top-level fatal) when tool context is otherwise usable
7. Error messages SHALL be sanitized (no stack traces, no SQL fragments, no sensitive absolute paths)
8. Duplicate-ID request validation SHALL remain `VALIDATION_ERROR` even when duplicate IDs include mixed value types

### Requirement 12: System Boundaries

**User Story:** As a system architect, I want strict separation between finalize and earlier pipeline stages, so that responsibilities remain clear.

#### Acceptance Criteria

1. THE MCP_Tool SHALL NOT perform resume compilation
2. THE MCP_Tool SHALL NOT rewrite resume bullet content
3. THE MCP_Tool SHALL NOT create new trackers
4. THE MCP_Tool SHALL NOT change jobs unrelated to provided item IDs
5. THE MCP_Tool SHALL only operate on provided batch items and associated artifacts
