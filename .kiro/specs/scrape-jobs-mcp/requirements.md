# Requirements Document

## Introduction

The `scrape_jobs` MCP tool provides step-1 ingestion for JobWorkFlow: scrape fresh postings from external job sources (JobSpy-backed), normalize records, and insert them into SQLite as `status='new'` items for downstream triage. This tool replaces manual script execution in the same local-first pipeline while preserving DB-as-SSOT boundaries.

## Glossary

- **MCP_Tool**: A Model Context Protocol tool callable by an LLM agent
- **Scrape_Run**: One invocation of `scrape_jobs` with a single request payload
- **Source_Record**: A raw posting record returned by JobSpy/source adapters
- **Cleaned_Record**: A normalized job object derived from raw source fields
- **Ingestion_DB**: SQLite database at `data/capture/jobs.db` (default)
- **Dedup_Key**: Unique identity used for idempotent insertion (`url`)
- **Capture_File**: Optional JSON snapshot persisted under `data/capture/`
- **Queue_Status**: Initial status for newly inserted jobs (`new`)

## Requirements

### Requirement 1: Scrape Invocation Interface

**User Story:** As an automation agent, I want a single MCP call to scrape jobs for multiple search terms, so that ingestion can run without shell scripts.

#### Acceptance Criteria

1. THE MCP_Tool SHALL expose a tool named `scrape_jobs`
2. WHEN invoked without optional parameters, THE MCP_Tool SHALL use defaults for terms, location, sites, and time window
3. WHEN invoked with multiple terms, THE MCP_Tool SHALL process each term in one run
4. THE MCP_Tool SHALL validate parameter types and ranges before network/database operations
5. WHEN unknown request fields are provided, THE MCP_Tool SHALL return `VALIDATION_ERROR`

### Requirement 2: Network Preflight and Retry

**User Story:** As a pipeline operator, I want transient DNS/network issues to be retried safely, so that one network glitch does not invalidate the full run.

#### Acceptance Criteria

1. WHEN `preflight_host` is configured, THE MCP_Tool SHALL resolve it before scraping each term
2. WHEN preflight fails, THE MCP_Tool SHALL retry according to `retry_count`, `retry_sleep_seconds`, and `retry_backoff`
3. WHEN preflight still fails for a term, THE MCP_Tool SHALL mark that term as failed/skipped and continue remaining terms
4. THE MCP_Tool SHALL include per-term preflight failures in structured run results
5. THE MCP_Tool SHALL NOT crash the entire run due to one term’s preflight failure

### Requirement 3: Source Retrieval and Term Isolation

**User Story:** As an ingestion pipeline, I want each term scrape to be isolated, so that a single source error does not block all terms.

#### Acceptance Criteria

1. WHEN scraping one term succeeds, THE MCP_Tool SHALL continue to the next term
2. WHEN scraping one term fails (adapter error/provider error), THE MCP_Tool SHALL record failure for that term and continue
3. THE MCP_Tool SHALL collect per-term `fetched_count` before cleaning/filtering
4. THE MCP_Tool SHALL support configurable site list with default `linkedin`
5. THE MCP_Tool SHALL preserve deterministic term ordering in response results

### Requirement 4: Record Normalization

**User Story:** As downstream tooling, I want stable field mapping from raw source records, so that triage tools receive predictable DB records.

#### Acceptance Criteria

1. THE MCP_Tool SHALL map normalized fields: `url`, `title`, `description`, `source`, `job_id`, `location`, `company`, `captured_at`, `payload_json`
2. WHEN `job_url` is missing and `job_url_direct` exists, THE MCP_Tool SHALL use `job_url_direct` as `url`
3. WHEN LinkedIn job ID can be parsed from URL, THE MCP_Tool SHALL set `job_id` from URL; otherwise fallback to source `id`
4. WHEN `date_posted` is invalid/missing, THE MCP_Tool SHALL set `captured_at` to current UTC timestamp
5. THE MCP_Tool SHALL ensure normalized records are JSON-serializable

### Requirement 5: Filtering Rules

**User Story:** As a quality gate, I want optional filtering before insert, so that low-value records can be excluded from the `new` queue.

#### Acceptance Criteria

1. THE MCP_Tool SHALL skip records with empty `url`
2. WHEN `require_description=true`, THE MCP_Tool SHALL skip records with empty descriptions
3. THE MCP_Tool SHALL return skip counters (`skipped_no_url`, `skipped_no_description`) per term and in totals
4. WHEN `dry_run=true`, THE MCP_Tool SHALL execute filtering logic and return counts without DB writes
5. THE MCP_Tool SHALL include `cleaned_count` after filtering and before insert

### Requirement 6: Database Path and Schema Bootstrap

**User Story:** As a local-first system, I want ingestion to create/validate the DB schema automatically, so that first-run setup is reliable.

#### Acceptance Criteria

1. WHEN no `db_path` is provided, THE MCP_Tool SHALL use default `data/capture/jobs.db`
2. WHEN `db_path` is provided, THE MCP_Tool SHALL use that override path
3. THE MCP_Tool SHALL ensure parent directories exist before opening the DB file
4. THE MCP_Tool SHALL create required `jobs` table and `idx_jobs_status` index if missing
5. THE MCP_Tool SHALL return `DB_ERROR` when schema/bootstrap operations fail

### Requirement 7: Insert + Dedup Semantics

**User Story:** As an operator, I want repeated scrape runs to be idempotent, so that retries do not duplicate queue records.

#### Acceptance Criteria

1. THE MCP_Tool SHALL use `url` uniqueness as the dedup key
2. WHEN a normalized record URL already exists, THE MCP_Tool SHALL count it as `duplicate_count`
3. WHEN a normalized record URL is new, THE MCP_Tool SHALL insert one row into `jobs`
4. THE MCP_Tool SHALL use parameterized SQL for insert operations
5. THE MCP_Tool SHALL return `inserted_count` and `duplicate_count` per term and in totals

### Requirement 8: Queue Status and Boundary Rules

**User Story:** As a pipeline architect, I want scrape ingestion to only feed the `new` queue, so that triage ownership remains in downstream tools.

#### Acceptance Criteria

1. WHEN inserting new rows, THE MCP_Tool SHALL default `status='new'`
2. WHEN a `status` override is provided, THE MCP_Tool SHALL validate against allowed DB status set
3. THE MCP_Tool SHALL NOT update status for existing rows during dedup hits
4. THE MCP_Tool SHALL NOT invoke tracker creation/finalization/status tools
5. THE MCP_Tool SHALL NOT perform triage decisions

### Requirement 9: Optional Capture Artifact Output

**User Story:** As an operator, I want optional raw scrape snapshots, so that ingestion runs are auditable and reproducible.

#### Acceptance Criteria

1. WHEN `save_capture_json=true`, THE MCP_Tool SHALL write per-term JSON capture files
2. WHEN `save_capture_json=false`, THE MCP_Tool SHALL skip capture file writes
3. THE MCP_Tool SHALL return capture file paths in per-term results when written
4. THE MCP_Tool SHALL sanitize path strings in errors while keeping usable relative paths in success payloads
5. THE MCP_Tool SHALL keep capture writing independent from DB insertion results

### Requirement 10: Structured Response Contract

**User Story:** As an orchestrating agent, I want complete structured run metrics, so that I can decide downstream steps programmatically.

#### Acceptance Criteria

1. THE MCP_Tool SHALL return `run_id`, `started_at`, `finished_at`, and `duration_ms`
2. THE MCP_Tool SHALL return ordered per-term `results` with success/failure and counters
3. THE MCP_Tool SHALL return aggregate totals: `fetched_count`, `cleaned_count`, `inserted_count`, `duplicate_count`, `failed_terms`
4. WHEN `dry_run=true`, THE MCP_Tool SHALL set `dry_run=true` and zero DB mutations
5. THE MCP_Tool SHALL return JSON-serializable payloads only

### Requirement 11: Error Handling and Sanitization

**User Story:** As a user, I want actionable failures without leaking internals, so that operations are debuggable and safe.

#### Acceptance Criteria

1. WHEN request validation fails, THE MCP_Tool SHALL return top-level `VALIDATION_ERROR`
2. WHEN DB open/query/insert/bootstrap fails, THE MCP_Tool SHALL return top-level `DB_ERROR` or `DB_NOT_FOUND` as appropriate
3. WHEN unexpected exceptions occur, THE MCP_Tool SHALL return top-level `INTERNAL_ERROR`
4. THE MCP_Tool SHALL sanitize stack traces, SQL fragments, and sensitive absolute paths in error messages
5. THE MCP_Tool SHALL keep per-term scrape failures in `results` while allowing partial success for other terms

### Requirement 12: MCP Registration and Operational Limits

**User Story:** As an MCP client, I want stable tool metadata and bounded resource usage, so that the tool can run predictably in automation.

#### Acceptance Criteria

1. THE MCP server SHALL register `scrape_jobs` with clear parameter docs and defaults
2. THE MCP_Tool SHALL enforce bounds for `results_wanted`, `hours_old`, and retry parameters
3. THE MCP_Tool SHALL enforce maximum term count per run to avoid unbounded execution
4. THE MCP_Tool SHALL expose deterministic behavior for same request + same source state
5. THE MCP_Tool SHALL be safe to retry (idempotent insert semantics)
