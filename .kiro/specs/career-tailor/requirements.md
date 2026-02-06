# Requirements Document

## Introduction

The `career_tailor` MCP tool initializes per-job resume workspaces from tracker notes and optionally compiles `resume.tex` into `resume.pdf`. This tool is part of the JobWorkFlow pipeline step 5 (resume tailoring), where tracker context is projected into editable resume artifacts and compile-time validation is enforced before finalization.

This tool is workspace-focused:
- It prepares/validates resume artifacts.
- It does not update DB status or tracker status.

## Glossary

- **MCP_Tool**: A Model Context Protocol tool invokable by an LLM agent
- **Tracker_Note**: Markdown note under `trackers/` containing frontmatter and `## Job Description`
- **Application_Workspace**: Directory under `data/applications/<application_slug>/`
- **Resume_Template**: LaTeX template file at `data/templates/resume_skeleton.tex`
- **Full_Resume_Source**: Source profile context file at `data/templates/full_resume.md`
- **Placeholder_Token**: Unreplaced bullet token in `resume.tex` (for example `PROJECT-AI-*`, `PROJECT-BE-*`, `WORK-BULLET-POINT-*`)

## Requirements

### Requirement 1: Tool Input and Request Validation

**User Story:** As an MCP caller, I want strict parameter validation, so that workspace initialization and compile behavior are predictable.

#### Acceptance Criteria

1. THE MCP_Tool SHALL require `tracker_path` as input
2. WHEN `compile` is omitted, THE MCP_Tool SHALL default `compile=false`
3. WHEN `force` is omitted, THE MCP_Tool SHALL default `force=false`
4. THE MCP_Tool SHALL support optional overrides: `full_resume_path`, `resume_template_path`, `applications_dir`, `pdflatex_cmd`
5. WHEN any input parameter type is invalid, THE MCP_Tool SHALL return `VALIDATION_ERROR`
6. WHEN unknown input properties are provided, THE MCP_Tool SHALL return `VALIDATION_ERROR`

### Requirement 2: Tracker Parsing and Context Extraction

**User Story:** As the tailoring workflow, I want tracker data parsed consistently, so that workspace generation always has company metadata and job description context.

#### Acceptance Criteria

1. THE MCP_Tool SHALL load the tracker markdown file from `tracker_path`
2. WHEN tracker file does not exist or is not readable, THE MCP_Tool SHALL return `FILE_NOT_FOUND`
3. THE MCP_Tool SHALL parse frontmatter fields needed for workspace resolution (`company`, `position`, `resume_path`, `reference_link`, optional `job_db_id`)
4. THE MCP_Tool SHALL require `## Job Description` heading to be present exactly
5. WHEN `## Job Description` is missing, THE MCP_Tool SHALL return `VALIDATION_ERROR`
6. THE MCP_Tool SHALL extract job description content for `ai_context.md`

### Requirement 3: Application Slug Resolution

**User Story:** As a pipeline operator, I want deterministic slug resolution, so that all artifacts for a job are written into stable workspace paths.

#### Acceptance Criteria

1. THE MCP_Tool SHALL resolve `application_slug` from tracker `resume_path` when available
2. WHEN tracker `resume_path` is missing or unparsable, THE MCP_Tool SHALL derive slug deterministically from available metadata (`company`, `position`, `job_db_id`, `reference_link`)
3. THE MCP_Tool SHALL produce stable slug output for identical tracker input
4. THE MCP_Tool SHALL resolve workspace root to `data/applications/<application_slug>/` by default
5. THE MCP_Tool SHALL NOT emit random or time-based slug components

### Requirement 4: Workspace Initialization

**User Story:** As an LLM agent, I want one call to create required workspace structure, so that I can immediately edit and compile per-job resume artifacts.

#### Acceptance Criteria

1. THE MCP_Tool SHALL ensure the following directories exist:
   - `data/applications/<slug>/resume/`
   - `data/applications/<slug>/cover/`
   - `data/applications/<slug>/cv/`
2. THE MCP_Tool SHALL initialize `resume/resume.tex` from `resume_skeleton.tex` when missing
3. THE MCP_Tool SHALL initialize `resume/ai_context.md` in the same workspace
4. THE MCP_Tool SHALL use atomic file write semantics for generated files
5. WHEN `compile=false`, THE MCP_Tool SHALL complete initialization without invoking LaTeX compilation

### Requirement 5: AI Context File Generation

**User Story:** As a tailoring agent, I want deterministic context input, so that rewrite quality is stable and grounded in real resume and JD content.

#### Acceptance Criteria

1. THE MCP_Tool SHALL read `full_resume.md` from configured/default source
2. WHEN `full_resume.md` is missing, THE MCP_Tool SHALL return `FILE_NOT_FOUND`
3. THE generated `ai_context.md` SHALL include sections:
   - `# AI Context`
   - `## Full Resume Source (raw)`
   - `## Job Description`
   - `## Notes`
   - `## Instructions`
4. THE MCP_Tool SHALL include tracker job description content in `## Job Description`
5. THE MCP_Tool SHALL include deterministic tailoring instructions emphasizing truthful, non-fabricated rewrite

### Requirement 6: Idempotency and Force Behavior

**User Story:** As a workflow operator, I want safe retries, so that repeated runs do not accidentally destroy tailored resume content.

#### Acceptance Criteria

1. WHEN `resume.tex` already exists and `force=false`, THE MCP_Tool SHALL preserve existing `resume.tex`
2. WHEN `resume.tex` already exists and `force=true`, THE MCP_Tool SHALL overwrite it from template
3. THE MCP_Tool SHALL regenerate `ai_context.md` on each successful run to reflect latest tracker/full-resume state
4. Repeated runs with unchanged input and `force=false` SHALL produce deterministic outputs and response actions
5. THE MCP_Tool SHALL explicitly report whether `resume.tex` was `created`, `preserved`, or `overwritten`

### Requirement 7: Compile Execution

**User Story:** As an LLM agent, I want optional compile in the same tool, so that I can validate tailored TeX without external manual steps.

#### Acceptance Criteria

1. WHEN `compile=true`, THE MCP_Tool SHALL run `pdflatex` against `resume/resume.tex`
2. WHEN `pdflatex` executable is missing or not runnable, THE MCP_Tool SHALL return `COMPILE_ERROR`
3. ON successful compile, THE MCP_Tool SHALL produce `resume/resume.pdf`
4. THE MCP_Tool SHALL clean common LaTeX auxiliary files after compile (`.aux`, `.log`, `.out`, `.synctex.gz`)
5. WHEN `compile=false`, THE MCP_Tool SHALL not create or modify `resume.pdf`

### Requirement 8: Placeholder Guardrail and Compile Validation

**User Story:** As a quality gate, I want compile blocked when placeholders remain, so that invalid template output never passes as tailored resume.

#### Acceptance Criteria

1. WHEN `compile=true`, THE MCP_Tool SHALL scan `resume.tex` for placeholder tokens before invoking LaTeX
2. WHEN placeholder tokens are detected, THE MCP_Tool SHALL fail the call with `VALIDATION_ERROR`
3. WHEN placeholder detection fails compile gate, THE MCP_Tool SHALL return matched placeholder summary in error message
4. ON successful compile, THE MCP_Tool SHALL verify `resume.pdf` exists and has non-zero size
5. WHEN LaTeX compile fails, THE MCP_Tool SHALL return `COMPILE_ERROR` with sanitized diagnostic summary

### Requirement 9: System Boundary and Side-Effect Constraints

**User Story:** As a system architect, I want clear boundaries, so that tailoring stays separate from status transitions and DB writes.

#### Acceptance Criteria

1. THE MCP_Tool SHALL NOT read or write `jobs.db`
2. THE MCP_Tool SHALL NOT update tracker frontmatter status
3. THE MCP_Tool SHALL NOT mark DB status `resume_written` (finalization is out-of-scope)
4. THE MCP_Tool SHALL only read source files and write under target application workspace
5. THE MCP_Tool SHALL avoid creating artifacts outside configured workspace roots

### Requirement 10: Structured Response Format

**User Story:** As a calling agent, I want explicit workspace and compile outcomes, so that downstream tools can decide next actions reliably.

#### Acceptance Criteria

1. ON success, THE MCP_Tool SHALL return:
   - `application_slug`
   - `workspace_dir`
   - `resume_tex_path`
   - `ai_context_path`
   - `resume_pdf_path` (nullable when `compile=false`)
   - `compiled` (boolean)
   - `resume_tex_action` (`created` | `preserved` | `overwritten`)
2. THE MCP_Tool SHALL include `placeholder_check_passed` when `compile=true`
3. THE MCP_Tool SHALL include optional `warnings` list for non-fatal conditions
4. ALL response fields SHALL be JSON-serializable
5. Response paths SHALL be deterministic for identical input and filesystem state

### Requirement 11: Error Handling

**User Story:** As an operator, I want failure categories that separate user input issues from compile/runtime faults, so that retry behavior is clear.

#### Acceptance Criteria

1. Request-level input failures SHALL return `VALIDATION_ERROR`
2. Missing required files SHALL return `FILE_NOT_FOUND` or `TEMPLATE_NOT_FOUND` as appropriate
3. Compile/toolchain failures SHALL return `COMPILE_ERROR`
4. Unexpected runtime failures SHALL return `INTERNAL_ERROR`
5. Top-level error object SHALL include `retryable` boolean
6. Error messages SHALL be sanitized (no full stack traces, no secrets, no absolute sensitive paths)
7. Compile error details SHALL include actionable but concise diagnostics

