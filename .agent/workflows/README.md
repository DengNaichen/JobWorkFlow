# Job Workflow Orchestration

This directory contains workflow definitions for the job application pipeline.

## Entrypoint

Use the merged workflow as the primary entrypoint:

- `intake-pipeline.md` (end-to-end: intake + tailor + finalize)

Legacy file:

- `tailor-finalize.md` (deprecated shim; points to `intake-pipeline.md`)

## Skills Used

- `job-matching-expertise` (classification stage)
- `resume-crafting-expertise` (resume bullet stage)

## Tools Used

- `scrape_jobs`
- `bulk_read_new_jobs`
- `bulk_update_job_status`
- `initialize_shortlist_trackers`
- `career_tailor`
- `finalize_resume_batch`

## Quick Start

```bash
# Open and execute the merged workflow
/intake-pipeline
```
