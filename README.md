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

1. **Ingest jobs** (MCP):
   - Use `scrape_jobs` (scrapes + normalizes + inserts with idempotent dedupe)
   - Result: jobs inserted into `data/capture/jobs.db` with `status='new'`
2. Read queue via `bulk_read_new_jobs`.
3. Triage and write status via `bulk_update_job_status`.
4. Create tracker/workspace scaffolding via `initialize_shortlist_trackers` for `status=shortlist`.
5. Run `career_tailor` to batch-generate tailoring artifacts (`ai_context.md`, `resume.tex`, `resume.pdf`) for shortlist trackers.
6. Commit completion via `finalize_resume_batch`:
   - DB -> `resume_written` + audit fields
   - tracker frontmatter -> `Resume Written`
   - on sync failure -> fallback DB status `reviewed` with `last_error`

## Tool Status

- Implemented:
  - `scrape_jobs` (ingestion: scrape + normalize + insert with dedupe)
  - `bulk_read_new_jobs`
  - `bulk_update_job_status`
  - `initialize_shortlist_trackers`
  - `career_tailor`
  - `update_tracker_status`
  - `finalize_resume_batch`

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
├── skills/                     # Project-owned Codex skills
│   ├── job-pipeline-intake/    # scrape/read/triage/status/tracker init policy
│   └── career-tailor-finalize/ # tailoring + artifact guardrails + finalize policy
├── scripts/                    # Operational helper scripts
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

### 2) (Optional) Ingest Jobs via MCP

Use the `scrape_jobs` MCP tool for integrated scrape + ingest:

```json
# Example MCP call (via agent or client)
scrape_jobs({
  "terms": ["backend engineer", "machine learning engineer"],
  "location": "Ontario, Canada",
  "results_wanted": 20,
  "hours_old": 2,
  "save_capture_json": true
})
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

### `scrape_jobs`

- Purpose: ingest jobs from external sources (JobSpy-backed) into SQLite
- Key args: `terms`, `location`, `sites`, `results_wanted`, `hours_old`, `db_path`, `dry_run`
- Behavior: scrapes sources, normalizes records, inserts with idempotent dedupe by URL, returns structured run metrics
- Boundary: **ingestion only** (inserts `status='new'`; no triage/tracker/finalize side effects)

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

### `career_tailor`

- Purpose: batch full-tailor tracker items into resume artifacts
- Key args: `items[]`, `force`, `full_resume_path`, `resume_template_path`, `applications_dir`, `pdflatex_cmd`
- Behavior: per item does tracker parse + workspace bootstrap + `ai_context.md` regeneration + LaTeX compile, returns `successful_items` for downstream `finalize_resume_batch`
- Boundary: artifact-focused only; no DB status writes and no tracker status writes

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

## Pipeline Prompt

Use a single end-to-end execution prompt from:

- `docs/pipeline-prompt.md` (versioned, copy-paste ready full workflow prompt)

## Project Skills

Project skills live in this repo under:

- `skills/job-pipeline-intake/SKILL.md`
- `skills/career-tailor-finalize/SKILL.md`

Recommended runtime setup is to expose these repo skills through your Codex skills directory:

```bash
ln -s /Users/nd/Developer/JobWorkFlow/skills/job-pipeline-intake /Users/nd/.codex/skills/job-pipeline-intake
ln -s /Users/nd/Developer/JobWorkFlow/skills/career-tailor-finalize /Users/nd/.codex/skills/career-tailor-finalize
```

This keeps skills versioned in Git while making them available as first-class skills in Codex.

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
- Pipeline prompt: `docs/pipeline-prompt.md`
- Testing notes: `TESTING.md`
- Specs: `.kiro/specs/`

## Troubleshooting

- DB not found:
  - verify `JOBWORKFLOW_DB` and file existence
  - ensure `scrape_jobs` ingestion ran successfully
- Tool returns validation errors:
  - check request payload shape and allowed status values
- Resume Written blocked:
  - confirm `resume.pdf` exists and non-zero
  - confirm `resume.tex` exists and placeholder tokens are fully replaced
