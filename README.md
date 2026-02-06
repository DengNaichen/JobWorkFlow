# JobWorkFlow

JobWorkFlow is a local-first, self-hosted job search operations system built around an MCP server.
It keeps your job pipeline in your own SQLite database and local files, and exposes deterministic tools for agents.

## What It Does

- Ingest jobs from JobSpy into SQLite (`data/capture/jobs.db`)
- Read and triage `new` jobs in batches
- Persist status transitions atomically
- Generate tracker notes for shortlisted jobs
- Enforce resume artifact guardrails before marking completion
- Finalize completion with DB audit fields and tracker sync

## Core Design

- SSOT: database status in SQLite
- Projection: tracker markdown files for Obsidian workflows
- Execution: MCP tools
- Policy: agent prompts/skills

This means decisions and automation should be driven by DB status; trackers are synchronized views.

## End-to-End Flow

1. Collect jobs with `scripts/jobspy_batch_run.py` (default source: LinkedIn).
2. Import/dedupe into `data/capture/jobs.db` with status `new`.
3. Read queue via `bulk_read_new_jobs`.
4. Triage and write status via `bulk_update_job_status`.
5. Create tracker/workspace scaffolding via `initialize_shortlist_trackers` for `status=shortlist`.
6. Compile and validate resume artifacts (outside MCP in current repo flow, `career_tailor` planned).
7. Commit completion via `finalize_resume_batch`:
   - DB -> `resume_written` + audit fields
   - tracker frontmatter -> `Resume Written`
   - on sync failure -> fallback DB status `reviewed` with `last_error`

## Tool Status

- Implemented:
  - `bulk_read_new_jobs`
  - `bulk_update_job_status`
  - `initialize_shortlist_trackers`
  - `update_tracker_status`
  - `finalize_resume_batch`
- Planned:
  - `career_tailor`

## Status Model

### Database Status (SSOT)

- `new`
- `shortlist`
- `reviewed`
- `reject`
- `resume_written`
- `applied`

Typical transitions:

- `new -> shortlist | reviewed | reject`
- `shortlist -> resume_written`
- `shortlist -> reviewed` (failure/retry path)
- `resume_written -> applied`

### Tracker Status (Projection)

- `Reviewed -> Resume Written -> Applied`
- Terminal outcomes include `Rejected`, `Ghosted`, `Interview`, `Offer`

## Repository Structure

```text
JobWorkFlow/
├── mcp-server-python/          # MCP server implementation
│   ├── server.py               # FastMCP entrypoint
│   ├── tools/                  # Tool handlers
│   ├── db/                     # SQLite read/write layers
│   ├── utils/                  # Validation, parser, sync, file ops
│   ├── models/                 # Error and schema models
│   └── tests/                  # Test suite
├── scripts/                    # Ingestion and helper scripts
├── data/                       # Local data (DB, templates, artifacts)
├── trackers/                   # Tracker markdown notes
├── .kiro/specs/                # Feature specs and task breakdowns
└── README.md
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency and task execution
- SQLite
- Optional: LaTeX toolchain (`pdflatex`) for resume compilation

## Quick Start

### 1) Install Dependencies

```bash
uv sync --all-groups
```

### 2) (Optional) Ingest Jobs

```bash
uv run python scripts/jobspy_batch_run.py \
  --terms "backend engineer,machine learning engineer" \
  --location "Ontario, Canada" \
  --results 20
```

Manual import if you already have JobSpy JSON:

```bash
uv run python scripts/import_jobspy_to_db.py \
  --input data/capture/jobspy_linkedin_backend_engineer_ontario_2h.json \
  --db data/capture/jobs.db \
  --require-description
```

### 3) Start MCP Server

From repo root:

```bash
./scripts/run_mcp_server.sh
```

Or directly:

```bash
cd mcp-server-python
./start_server.sh
```

## Configuration

Environment variables:

- `JOBWORKFLOW_ROOT`: base root for data path resolution
- `JOBWORKFLOW_DB`: explicit DB path override
- `JOBWORKFLOW_LOG_LEVEL`: `DEBUG|INFO|WARNING|ERROR`
- `JOBWORKFLOW_LOG_FILE`: optional file log path
- `JOBWORKFLOW_SERVER_NAME`: MCP server name (default `jobworkflow-mcp-server`)

Example:

```bash
export JOBWORKFLOW_DB=data/capture/jobs.db
export JOBWORKFLOW_LOG_LEVEL=DEBUG
export JOBWORKFLOW_LOG_FILE=logs/mcp-server.log
./scripts/run_mcp_server.sh
```

See `.env.example` and `mcp-server-python/mcp-config-example.json` for templates.

## MCP Tool Reference (Summary)

### `bulk_read_new_jobs`

- Purpose: read `status='new'` jobs in deterministic batches
- Key args: `limit`, `cursor`, `db_path`
- Behavior: read-only, cursor pagination

### `bulk_update_job_status`

- Purpose: atomic batch status updates
- Key args: `updates[]`, `db_path`
- Behavior: validates IDs/statuses, all-or-nothing write

### `initialize_shortlist_trackers`

- Purpose: create trackers from shortlisted jobs
- Key args: `limit`, `db_path`, `trackers_dir`, `force`, `dry_run`
- Behavior: idempotent by default, deterministic filenames, atomic file writes, compatibility dedupe by `reference_link` to avoid legacy duplicate trackers

### `update_tracker_status`

- Purpose: update tracker frontmatter status safely
- Key args: `tracker_path`, `target_status`, `dry_run`, `force`
- Behavior: transition policy + Resume Written guardrails

### `finalize_resume_batch`

- Purpose: commit completion state after resume compile succeeds
- Key args: `items[]`, `run_id`, `db_path`, `dry_run`
- Behavior:
  - validates tracker/artifacts/placeholders per item
  - writes DB completion fields
  - syncs tracker status
  - fallback to `reviewed` with `last_error` on sync failure

For full contracts and examples, see `mcp-server-python/README.md`.

## Development

### Run Tests

```bash
uv run pytest -q
```

### Run Lint / Format

```bash
uv run ruff check .
uv run ruff format . --check
```

### Run Pre-commit

```bash
uv run pre-commit run --all-files
```

CI workflow mirrors these checks: `.github/workflows/ci.yml`.

## Related Docs

- Server docs: `mcp-server-python/README.md`
- Deployment: `mcp-server-python/DEPLOYMENT.md`
- Quickstart: `mcp-server-python/QUICKSTART.md`
- Testing notes: `TESTING.md`
- Specs: `.kiro/specs/`

## Troubleshooting

- DB not found:
  - verify `JOBWORKFLOW_DB` and file existence
  - ensure ingestion/import ran successfully
- Tool returns validation errors:
  - check request payload shape and allowed status values
- Resume Written blocked:
  - confirm `resume.pdf` exists and non-zero
  - confirm `resume.tex` exists and placeholder tokens are fully replaced
