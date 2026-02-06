# JobWorkFlow (Self-Hosted Toolchain)

JobWorkFlow is a self-hosted job operations pipeline for technical job search:

1. collect jobs
2. dedupe/store locally
3. filter into actionable queues
4. generate trackers + tailored resume workspace
5. compile and track delivery state

No hosted backend is required. Each user runs it in their own environment.

## Product Positioning

- Deployment model: self-hosted, local-first
- Data ownership: local SQLite + local files
- Execution model: MCP tools as the execution layer
- Strategy model: agent prompt/skills as the policy layer

## Current Pipeline

1. `scripts/jobspy_batch_run.py` scrapes roles (default LinkedIn) and imports them into `data/capture/jobs.db` with status `new`.
2. MCP `bulk_read_new_jobs` (read-only) fetches jobs in `new` in batches (for example, 50 at a time).
3. LLM triage (policy layer) evaluates fit and drives outcomes per job (`shortlist`, `reviewed`, `reject`), then MCP `bulk_update_job_status` persists **DB status only** in this step (no tracker creation).
4. MCP `initialize_shortlist_trackers` reads `status=shortlist` and creates tracker files linked to each application workspace.
5. **Resume Tailoring (two-phase)**:

  - LLM rewrites bullets in `resume.tex` from tracker JD + profile context (`ai_context.md`), and must fully replace placeholders;

  - MCP `career_tailor` compiles and validates the PDF. If rewrite/validation fails, the item is moved back to `reviewed` with an error note for retry.

6. **Finalization (commit/close-loop)**: after compile passes, MCP `finalize_resume_batch` (planned) performs a single write-back step:
  - updates DB status to `resume_written` and stores audit fields (`resume_pdf_path`, `resume_written_at`, `run_id`, `attempt_count`, `last_error`);
  - syncs tracker frontmatter status to `Resume Written`;
  - if any write fails, job stays in `reviewed` with `last_error` set for retry.

### Tool Mapping (Target)

- Read queue (read-only): `bulk_read_new_jobs` (planned)
- Filtering decision (policy): LLM triage
- Batch DB write-back: `bulk_update_job_status` (planned)
- Tracker creation from shortlist: `initialize_shortlist_trackers` (planned)
- Resume workspace + compile: `career_tailor`
- Commit resume result: `finalize_resume_batch` (planned)
- Tracker status update: `update_tracker_status`
- Batch DB status update: `update_jobs_status`

## Status Model

- DB status (SSOT):
  - `new`: imported and waiting for triage
  - `shortlist`: selected for tailoring
  - `reviewed`: parked / needs retry or manual review
  - `reject`: do-not-pursue
  - `resume_written`: resume generation + validation completed
  - `applied` (optional downstream): application submitted
- DB transitions (current target):
  - `new -> shortlist | reviewed | reject`
  - `shortlist -> resume_written` (finalize success)
  - `shortlist -> reviewed` (rewrite/compile/finalize failure, with `last_error`)
  - `resume_written -> applied` (manual submit or later automation)
- Tracker status (projection for Obsidian board):
  - `Reviewed -> Resume Written -> Applied -> Rejected/Ghosted/Interview/Offer`
  - Tracker mirrors DB milestones, but DB remains the authority.

## Guardrails

- Implemented now:
  - `career_tailor` compile step fails if placeholders remain in `resume.tex`.
  - `update_tracker_status` blocks `Resume Written` when:
    - `resume.pdf` is missing
    - `resume.tex` still contains placeholders
- Target next:
  - Finalization writes DB + tracker in one commit step (DB remains SSOT).
  - Any finalize failure falls back to `reviewed` with `last_error` for retry.
  - Automation selection is driven by DB status only; tracker is board projection.

## Requirements

- Python 3.11+
- Go (for MCP server build/runtime)
- SQLite
- LaTeX (`pdflatex`) if PDF compilation is needed
- Obsidian + Dataview plugin for dashboard view
