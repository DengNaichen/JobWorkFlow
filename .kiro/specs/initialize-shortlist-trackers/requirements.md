# Requirements Document

## Introduction

The `initialize_shortlist_trackers` MCP tool creates Obsidian tracker notes for jobs currently in `shortlist` status. This tool is part of the JobWorkFlow pipeline, specifically handling step 4: projecting shortlisted database records into tracker files linked to application workspaces.

This tool is projection-focused:
- Database status remains the SSOT.
- Tracker notes are a file-based board projection for operational workflow in Obsidian.

## Glossary

- **MCP_Tool**: A Model Context Protocol tool invokable by an LLM agent
- **Job_Database**: SQLite database at `data/capture/jobs.db`
- **Shortlist_Job**: A job row where `status='shortlist'`
- **Tracker_Note**: A markdown file under `trackers/` with frontmatter and sections
- **Application_Workspace**: Directory under `data/applications/<application_slug>/`
- **Projection**: File representation derived from DB state, where DB remains authoritative

## Requirements

### Requirement 1: Shortlist Source Selection

**User Story:** As a triage pipeline, I want tracker initialization to consume only shortlisted jobs, so that tracker creation reflects triage outcomes accurately.

#### Acceptance Criteria

1. WHEN the tool is invoked, THE MCP_Tool SHALL select jobs where `status='shortlist'`
2. THE MCP_Tool SHALL order shortlist selection deterministically by `captured_at DESC, id DESC`
3. WHEN `limit` is omitted, THE MCP_Tool SHALL default to 50 jobs
4. WHEN `limit` is provided, THE MCP_Tool SHALL accept values in range 1-200
5. WHEN `limit` is outside 1-200, THE MCP_Tool SHALL return `VALIDATION_ERROR`
6. WHEN no shortlist jobs are available, THE MCP_Tool SHALL return success with zero created trackers

### Requirement 2: Tracker File Generation

**User Story:** As a job seeker, I want each shortlisted job to have a tracker note with required metadata, so that Obsidian dashboards and downstream tools can operate consistently.

#### Acceptance Criteria

1. WHEN creating a tracker, THE MCP_Tool SHALL write a markdown file under `trackers/`
2. THE tracker filename SHALL be deterministic and include job identity to avoid collisions
3. THE tracker frontmatter SHALL include at minimum:
   - `job_db_id`
   - `job_id`
   - `company`
   - `position`
   - `status`
   - `application_date`
   - `reference_link`
   - `resume_path`
   - `cover_letter_path`
4. THE tracker body SHALL include `## Job Description` section populated from job description when available
5. THE tracker body SHALL include `## Notes` section
6. THE initial tracker status SHALL be `Reviewed` for newly initialized shortlist trackers

### Requirement 3: Workspace Linking

**User Story:** As the resume-tailoring pipeline, I want trackers to link to deterministic application workspaces, so that downstream tools can find per-job artifacts reliably.

#### Acceptance Criteria

1. WHEN generating tracker paths, THE MCP_Tool SHALL compute a deterministic `application_slug`
2. THE MCP_Tool SHALL set `resume_path` to `[[data/applications/<application_slug>/resume/resume.pdf]]`
3. THE MCP_Tool SHALL set `cover_letter_path` to `[[data/applications/<application_slug>/cover/cover-letter.pdf]]`
4. THE MCP_Tool SHALL create workspace directories when missing:
   - `data/applications/<application_slug>/resume/`
   - `data/applications/<application_slug>/cover/`
5. THE MCP_Tool SHALL NOT generate resume or cover letter content files

### Requirement 4: Idempotent Initialization

**User Story:** As a pipeline operator, I want repeated tool runs to be safe, so that retries do not create duplicate trackers.

#### Acceptance Criteria

1. WHEN a deterministic tracker file already exists and `force=false`, THE MCP_Tool SHALL mark item as skipped without rewriting
2. WHEN a deterministic tracker file already exists and `force=true`, THE MCP_Tool SHALL overwrite the tracker
3. WHEN the same shortlist set is processed repeatedly with `force=false`, THE MCP_Tool SHALL produce no duplicate files
4. THE MCP_Tool SHALL include skipped items in results with explicit action reason
5. THE MCP_Tool SHALL preserve final filesystem consistency on retries

### Requirement 5: Atomic Per-File Writes

**User Story:** As a system administrator, I want tracker files to never be partially written, so that crashes do not corrupt tracker notes.

#### Acceptance Criteria

1. WHEN writing a tracker file, THE MCP_Tool SHALL write atomically (temporary file + rename)
2. WHEN a write failure occurs for one item, THE MCP_Tool SHALL report that item as failed
3. WHEN one item fails, THE MCP_Tool SHALL continue processing other items in the batch
4. THE MCP_Tool SHALL return per-item actions: `created`, `skipped_exists`, `overwritten`, `failed`
5. THE MCP_Tool SHALL close all file handles even on failure

### Requirement 6: Database and Filesystem Boundaries

**User Story:** As a system architect, I want clear separation of concerns, so that tracker initialization does not mutate triage truth in the database.

#### Acceptance Criteria

1. THE MCP_Tool SHALL NOT update any database row fields
2. THE MCP_Tool SHALL NOT change `status` in database records
3. THE MCP_Tool SHALL execute read queries only for shortlist selection
4. THE MCP_Tool SHALL NOT insert or delete database rows
5. WHEN database operations complete, THE MCP_Tool SHALL close database connection

### Requirement 7: Structured Response Format

**User Story:** As a calling agent, I want itemized outcomes, so that I can decide follow-up actions per job.

#### Acceptance Criteria

1. ON success or partial item failures, THE MCP_Tool SHALL return:
   - `created_count`
   - `skipped_count`
   - `failed_count`
   - `results`
2. EACH `results` item SHALL include:
   - `id`
   - `tracker_path` (optional on hard failure)
   - `action`
   - `success`
   - `error` (optional)
3. THE MCP_Tool SHALL maintain `results` order matching selected input order
4. WHEN all items are skipped, THE MCP_Tool SHALL still return success with correct counts
5. ALL responses SHALL be JSON-serializable
6. WHEN item processing fails before tracker planning completes, THAT item's `results` entry SHALL omit `tracker_path` (and SHALL NOT reuse another item's path)

### Requirement 8: Error Handling

**User Story:** As an operator, I want failures categorized clearly, so that retries and manual intervention are straightforward.

#### Acceptance Criteria

1. WHEN request-level validation fails (`limit`, `db_path`, `trackers_dir`, `force`, `dry_run`), THE MCP_Tool SHALL return top-level `VALIDATION_ERROR`
2. WHEN database file is missing, THE MCP_Tool SHALL return `DB_NOT_FOUND`
3. WHEN database query or connection fails, THE MCP_Tool SHALL return `DB_ERROR`
4. WHEN unexpected runtime exceptions occur, THE MCP_Tool SHALL return `INTERNAL_ERROR`
5. THE top-level error object SHALL include `retryable` boolean
6. Error messages SHALL be sanitized (no raw SQL fragments, no full stack traces, no sensitive absolute paths)
7. Per-item write failures SHALL be represented in `results` (not as top-level fatal error) unless tool cannot initialize core context

### Requirement 9: MCP Tool Interface

**User Story:** As an MCP server, I want this tool to be invokable consistently by agents, so that automated workflows can orchestrate tracker creation.

#### Acceptance Criteria

1. THE MCP_Tool SHALL accept structured input:
   - `limit` (optional int)
   - `db_path` (optional str)
   - `trackers_dir` (optional str)
   - `force` (optional bool, default false)
   - `dry_run` (optional bool, default false)
2. THE MCP_Tool SHALL validate all input parameters before execution
3. THE MCP_Tool SHALL define clear input/output schema documentation
4. THE MCP_Tool SHALL support dry-run mode that computes outcomes without writing files
5. THE MCP_Tool SHALL return deterministic output ordering for identical DB state and inputs

### Requirement 10: Tracker Content Compatibility

**User Story:** As a downstream tool (e.g., `career_tailor`), I want predictable tracker structure, so that I can read tracker notes without custom parsing per file.

#### Acceptance Criteria

1. THE tracker SHALL include `## Job Description` heading exactly
2. THE tracker frontmatter field names SHALL be stable across all created files
3. `reference_link` SHALL store original job URL
4. `application_date` SHALL use ISO date format `YYYY-MM-DD`
5. THE tracker format SHALL be compatible with Obsidian Dataview frontmatter parsing
