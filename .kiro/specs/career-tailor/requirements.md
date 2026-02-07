# Requirements Document

## Introduction

The `career_tailor` MCP tool performs **batch full-run tailoring**: for each tracker item, initialize workspace artifacts, generate `ai_context.md`, and compile `resume.tex` into `resume.pdf`.

This simplified spec intentionally fixes scope:

- batch input is required (`items[]`)
- mode is always full (no `prepare` or `compile` mode switches)
- no DB status writes
- no tracker status writes
- no internal compensation/fallback writes

`finalize_resume_batch` remains a separate step, invoked by prompt/workflow after successful tailoring.

## Glossary

- **MCP_Tool**: Model Context Protocol tool callable by an agent
- **Batch_Item**: one requested tracker entry in `items[]`
- **Tracker_Note**: markdown file under `trackers/` containing frontmatter and `## Job Description`
- **Application_Workspace**: directory under `data/applications/<application_slug>/`
- **Successful_Item**: a batch item that completed full run and produced valid `resume.pdf`
- **Finalize_Input_Item**: object shape consumed later by `finalize_resume_batch` (`id`, `tracker_path`, optional `resume_pdf_path`)

## Requirements

### Requirement 1: Batch Input Contract (Full-Only)

**User Story:** As a pipeline caller, I want one MCP call to process multiple trackers in full mode, so that I can avoid per-tracker manual calls.

#### Acceptance Criteria

1. THE MCP_Tool SHALL require `items` as a non-empty array
2. EACH Batch_Item SHALL require `tracker_path`
3. EACH Batch_Item MAY include optional `job_db_id` override for finalize handoff
4. THE MCP_Tool SHALL support optional batch-level overrides: `force`, `full_resume_path`, `resume_template_path`, `applications_dir`, `pdflatex_cmd`
5. THE MCP_Tool SHALL NOT expose mode flags (`prepare`, `compile`, `full`); execution SHALL always be full-run
6. WHEN request fields are invalid or unknown, THE MCP_Tool SHALL return `VALIDATION_ERROR`

### Requirement 2: Per-Item Isolation and Deterministic Ordering

**User Story:** As an operator, I want partial success behavior, so that one bad tracker does not block the entire batch.

#### Acceptance Criteria

1. THE MCP_Tool SHALL process items in input order
2. WHEN one item fails, THE MCP_Tool SHALL record item failure and continue next item
3. THE MCP_Tool SHALL preserve input order in `results`
4. THE MCP_Tool SHALL return top-level counts (`success_count`, `failed_count`, `total_count`)
5. THE MCP_Tool SHALL NOT abort the whole batch due to one item-level failure

### Requirement 3: Tracker Parsing and Context Extraction

**User Story:** As the tailoring workflow, I want stable tracker parsing, so that generated context remains grounded in the tracker note.

#### Acceptance Criteria

1. THE MCP_Tool SHALL load tracker markdown from `tracker_path`
2. WHEN tracker file is missing/unreadable, THE item SHALL fail with `FILE_NOT_FOUND`
3. THE MCP_Tool SHALL extract frontmatter fields needed for workspace resolution (`company`, `position`, `resume_path`, optional `job_db_id`)
4. THE MCP_Tool SHALL require `## Job Description` heading
5. WHEN `## Job Description` is missing, THE item SHALL fail with `VALIDATION_ERROR`
6. THE MCP_Tool SHALL extract job description content for `ai_context.md`

### Requirement 4: Deterministic Workspace and Artifact Initialization

**User Story:** As a caller, I want consistent workspace paths and bootstrap behavior, so that reruns are predictable and safe.

#### Acceptance Criteria

1. THE MCP_Tool SHALL resolve deterministic `application_slug` from tracker metadata (`resume_path` first, deterministic fallback second)
2. THE MCP_Tool SHALL ensure directories exist:
   - `data/applications/<slug>/resume/`
   - `data/applications/<slug>/cover/`
   - `data/applications/<slug>/cv/`
3. THE MCP_Tool SHALL initialize `resume/resume.tex` from template when missing
4. WHEN `force=true`, THE MCP_Tool SHALL overwrite existing `resume.tex` from template
5. THE MCP_Tool SHALL regenerate `resume/ai_context.md` on each successful item run
6. Generated files SHALL be written atomically

### Requirement 5: Full-Run Compile Gate

**User Story:** As a pipeline, I want every successful item to be truly compilable, so that downstream finalize only sees valid artifacts.

#### Acceptance Criteria

1. FOR every item that passes initialization, THE MCP_Tool SHALL run LaTeX compile (`pdflatex`) on `resume.tex`
2. BEFORE compile, THE MCP_Tool SHALL scan placeholders in `resume.tex`
3. WHEN placeholders exist, THE item SHALL fail with `VALIDATION_ERROR` and skip compile
4. WHEN compile succeeds, THE MCP_Tool SHALL verify `resume.pdf` exists and has non-zero size
5. WHEN compile/toolchain fails, THE item SHALL fail with `COMPILE_ERROR`

### Requirement 6: Boundary Rules (No Finalization)

**User Story:** As system design policy, I want tailoring isolated from state commits, so that DB/tracker authority remains explicit.

#### Acceptance Criteria

1. THE MCP_Tool SHALL NOT read or write job status in `jobs.db`
2. THE MCP_Tool SHALL NOT call `finalize_resume_batch`
3. THE MCP_Tool SHALL NOT update tracker frontmatter status
4. THE MCP_Tool SHALL only write workspace artifacts
5. THE MCP_Tool SHALL NOT implement compensation/fallback writes for failed items

### Requirement 7: Finalize Handoff Output

**User Story:** As an orchestration prompt, I want ready-to-use finalize inputs, so that successful items can be committed in a separate step.

#### Acceptance Criteria

1. THE MCP_Tool SHALL return `successful_items` for downstream `finalize_resume_batch`
2. EACH Successful_Item SHALL include `tracker_path` and `resume_pdf_path`
3. WHEN item `job_db_id` is available/resolved, Successful_Item SHALL include `id`
4. WHEN `job_db_id` is missing, item SHALL still be successful for tailoring, but SHALL be excluded from `successful_items` and reported in warnings
5. THE MCP_Tool SHALL return machine-consumable per-item fields (`application_slug`, `resume_tex_path`, `ai_context_path`, `resume_pdf_path`, `action`, `success`, optional `error`)

### Requirement 8: Error Model and Sanitization

**User Story:** As an operator, I want clear and safe failure categories, so that retry and debugging are straightforward.

#### Acceptance Criteria

1. Request-level failures SHALL return top-level `VALIDATION_ERROR`
2. Missing source files SHALL map to `FILE_NOT_FOUND` or `TEMPLATE_NOT_FOUND`
3. Compile failures SHALL map to `COMPILE_ERROR`
4. Unexpected runtime failures SHALL map to `INTERNAL_ERROR`
5. Top-level error object SHALL include `retryable`
6. Error messages SHALL be sanitized (no stack traces, no sensitive absolute paths, no secrets)
