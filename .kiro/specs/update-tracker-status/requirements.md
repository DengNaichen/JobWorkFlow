# Requirements Document

## Introduction

The `update_tracker_status` MCP tool updates tracker frontmatter status for Obsidian board workflow while enforcing status-specific guardrails. This tool is projection-focused and operates on tracker files only.

This tool exists to keep tracker progression safe and predictable:
- Tracker status is a board projection.
- DB status remains the authoritative source.

## Glossary

- **MCP_Tool**: A Model Context Protocol tool invokable by an LLM agent
- **Tracker_Note**: Markdown file under `trackers/` with YAML frontmatter
- **Tracker_Status**: Frontmatter `status` field value in tracker note
- **Resume_Artifact**: `resume.tex` and `resume.pdf` under application workspace
- **Guardrail_Check**: Validation checks required before allowing specific status transitions

## Requirements

### Requirement 1: Tool Input Interface

**User Story:** As a calling agent, I want a clear and minimal API, so that status updates are deterministic and easy to automate.

#### Acceptance Criteria

1. THE MCP_Tool SHALL require `tracker_path`
2. THE MCP_Tool SHALL require `target_status`
3. WHEN `dry_run` is omitted, THE MCP_Tool SHALL default `dry_run=false`
4. WHEN `force` is omitted, THE MCP_Tool SHALL default `force=false`
5. THE MCP_Tool SHALL reject unknown input properties with `VALIDATION_ERROR`
6. THE MCP_Tool SHALL validate all inputs before file writes

### Requirement 2: Tracker File Parsing and Validation

**User Story:** As an operator, I want robust tracker parsing, so that malformed tracker files fail safely before mutation.

#### Acceptance Criteria

1. THE MCP_Tool SHALL verify `tracker_path` exists and is readable
2. WHEN tracker file is missing, THE MCP_Tool SHALL return `FILE_NOT_FOUND`
3. THE MCP_Tool SHALL require YAML frontmatter with `status` field
4. WHEN frontmatter is malformed or missing `status`, THE MCP_Tool SHALL return `VALIDATION_ERROR`
5. THE MCP_Tool SHALL preserve non-status frontmatter fields and body content during update

### Requirement 3: Allowed Tracker Status Set

**User Story:** As a workflow owner, I want a controlled status vocabulary, so that dashboards and automations remain consistent.

#### Acceptance Criteria

1. THE MCP_Tool SHALL accept only these canonical tracker statuses:
   - `Reviewed`
   - `Resume Written`
   - `Applied`
   - `Interview`
   - `Offer`
   - `Rejected`
   - `Ghosted`
2. WHEN `target_status` is outside allowed set, THE MCP_Tool SHALL return `VALIDATION_ERROR`
3. Status matching SHALL be case-sensitive
4. THE MCP_Tool SHALL reject leading/trailing whitespace in `target_status`

### Requirement 4: Transition Policy

**User Story:** As an operator, I want transition safety checks, so that accidental backwards or invalid workflow moves are blocked.

#### Acceptance Criteria

1. WHEN `target_status` equals current status, THE MCP_Tool SHALL return success with action `noop`
2. THE MCP_Tool SHALL apply transition checks for non-terminal progression statuses:
   - `Reviewed -> Resume Written`
   - `Resume Written -> Applied`
3. THE MCP_Tool SHALL allow terminal outcomes (`Rejected`, `Ghosted`) from any current status
4. WHEN a transition violates policy and `force=false`, THE MCP_Tool SHALL return a structured blocked response (`action='blocked'`, `success=false`) without mutating the tracker
5. WHEN `force=true`, THE MCP_Tool SHALL allow policy-violating transition but include warning in response

### Requirement 5: Resume Written Guardrails

**User Story:** As a quality gate, I want strict checks before setting `Resume Written`, so that tracker completion is never marked without valid artifacts.

#### Acceptance Criteria

1. WHEN `target_status='Resume Written'`, THE MCP_Tool SHALL verify `resume.pdf` exists
2. WHEN `target_status='Resume Written'`, THE MCP_Tool SHALL verify `resume.pdf` size is greater than zero
3. WHEN `target_status='Resume Written'`, THE MCP_Tool SHALL verify companion `resume.tex` exists
4. WHEN `target_status='Resume Written'`, THE MCP_Tool SHALL scan `resume.tex` for placeholder tokens
5. WHEN any guardrail check fails, THE MCP_Tool SHALL block update and return failure
6. Placeholder guardrail tokens SHALL include at minimum:
   - `PROJECT-AI-`
   - `PROJECT-BE-`
   - `WORK-BULLET-POINT-`

### Requirement 6: Artifact Path Resolution

**User Story:** As a tool integrator, I want deterministic artifact path resolution, so that guardrails work with tracker-linked workspaces.

#### Acceptance Criteria

1. THE MCP_Tool SHALL resolve `resume.pdf` path from tracker frontmatter `resume_path` when possible
2. THE MCP_Tool SHALL support wiki-link path format (`[[...]]`) and plain path format
3. THE MCP_Tool SHALL derive `resume.tex` from resolved resume workspace directory
4. WHEN `resume_path` is missing or unparsable for `Resume Written` checks, THE MCP_Tool SHALL return `VALIDATION_ERROR`
5. Path resolution SHALL be deterministic for identical tracker content

### Requirement 7: File Write Semantics

**User Story:** As a system administrator, I want safe file writes, so that tracker data is not corrupted on crashes or interruptions.

#### Acceptance Criteria

1. THE MCP_Tool SHALL update only the `status` field in frontmatter
2. Tracker write SHALL be atomic (temporary file + rename)
3. THE MCP_Tool SHALL preserve original body content exactly
4. THE MCP_Tool SHALL preserve original frontmatter keys/values except `status`
5. WHEN write fails, original tracker file SHALL remain intact
6. Temporary file handling SHALL use unique non-predictable temp paths in the target directory to prevent symlink clobbering

### Requirement 8: Dry-Run Behavior

**User Story:** As an operator, I want to preview status changes, so that I can safely validate transitions and guardrails before mutating files.

#### Acceptance Criteria

1. WHEN `dry_run=true`, THE MCP_Tool SHALL perform all parsing, transition checks, and guardrails
2. WHEN `dry_run=true`, THE MCP_Tool SHALL NOT write tracker file
3. Dry-run response SHALL include predicted action and validation outcomes
4. Dry-run response SHALL include guardrail failure reasons when checks fail

### Requirement 9: Structured Response Format

**User Story:** As a calling agent, I want explicit update outcomes, so that downstream orchestration can decide next actions reliably.

#### Acceptance Criteria

1. ON completion, THE MCP_Tool SHALL return:
   - `tracker_path`
   - `previous_status`
   - `target_status`
   - `action` (`updated` | `noop` | `blocked`)
   - `success`
   - `dry_run`
2. WHEN guardrails are evaluated, THE MCP_Tool SHALL return `guardrail_check_passed`
3. THE MCP_Tool SHALL include optional `warnings` list
4. THE MCP_Tool SHALL include optional `error` for blocked/failed updates
5. ALL response fields SHALL be JSON-serializable

### Requirement 10: Error Handling

**User Story:** As an operator, I want clear and sanitized errors, so that retries and manual intervention are straightforward.

#### Acceptance Criteria

1. Request-level input validation failures SHALL return top-level `VALIDATION_ERROR`
2. Missing tracker file SHALL return top-level `FILE_NOT_FOUND`
3. Guardrail violations SHALL be represented as structured blocked failure (not internal crash)
4. Unexpected runtime failures SHALL return top-level `INTERNAL_ERROR`
5. Top-level error responses SHALL include `retryable` boolean
6. Error messages SHALL be sanitized (no stack traces, no sensitive absolute paths)

### Requirement 11: System Boundaries

**User Story:** As a system architect, I want strict boundaries, so that this tool remains focused and does not violate SSOT design.

#### Acceptance Criteria

1. THE MCP_Tool SHALL NOT read or write `jobs.db`
2. THE MCP_Tool SHALL NOT compile resumes
3. THE MCP_Tool SHALL NOT rewrite resume content
4. THE MCP_Tool SHALL NOT create or delete tracker files
5. THE MCP_Tool SHALL operate only on the provided tracker file
