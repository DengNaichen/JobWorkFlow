---
name: job-pipeline-intake
description: "Use when running intake and triage in JobWorkFlow: scrape jobs, read the new queue, classify shortlist/reviewed/reject, apply atomic status updates, and initialize shortlist trackers."
---

# Skill: Job Pipeline Intake

## Goal
Run the intake half of the pipeline with deterministic state handling:
1. Ingest jobs into DB as `new`
2. Read `new` queue in batches
3. Classify each job
4. Write one atomic status update batch
5. Initialize trackers for `shortlist`

DB status is SSOT; tracker files are projection.

## MCP Tools In Scope
- `scrape_jobs`
- `bulk_read_new_jobs`
- `bulk_update_job_status`
- `initialize_shortlist_trackers`

Do not run `career_tailor` or `finalize_resume_batch` in this skill.

## Inputs
- Optional triage policy from user (preferred)
- Optional ingestion parameters (`terms`, `location`, `hours_old`, `results_wanted`)

If no policy is provided, produce recommendation-only output and skip status writes.

## Workflow
1. Run `scrape_jobs` (ingestion only).
2. Run `bulk_read_new_jobs(limit=50)`.
3. Classify each item into one of:
   - `shortlist`
   - `reviewed`
   - `reject`
4. If classification is final, call `bulk_update_job_status` once with all updates.
5. Run `initialize_shortlist_trackers(limit=50, force=false, dry_run=false)`.

## Triage Rubric (Keep This Tight)
Prioritize roles matching evidence in `data/templates/full_resume.md`:
- Strong fit: Python backend, FastAPI, LLM/RAG, knowledge graph, data infra, platform
- Medium fit: general backend/data roles with partial overlap
- Low fit: frontend-only, clearly junior-misaligned, or hard requirements not met

Decision rule:
- `shortlist`: strong fit and valid job details
- `reviewed`: maybe fit, needs manual review, or incomplete confidence
- `reject`: clear non-fit or duplicate/low-quality posting

## Guardrails
- Use one atomic write via `bulk_update_job_status`; avoid fragmented updates.
- Never change DB status when policy/confidence is missing.
- Treat tracker creation as projection only; DB is authoritative.
- Continue on partial failures and report per-step errors.

## Required Output Shape
- `run_id` (if available)
- `scrape_totals`: fetched/cleaned/inserted/duplicate
- `triage_totals`: shortlist/reviewed/reject
- `tracker_totals`: created/skipped/failed
- `errors_by_step`
- `next_actions`

## Optional Scouting Mode (Human-in-the-loop)
If user explicitly asks for active scouting patrol:
- Use the same quality bar as triage
- De-duplicate before creating tracker work
- Feed only high-signal jobs into this intake workflow
