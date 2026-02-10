---
description: "End-to-end job pipeline: intake + tailor + finalize"
---

# Workflow: End-to-End Job Pipeline

## Goal

Run the full pipeline in one document:

1. Scrape jobs
2. Read new jobs
3. Classify jobs
4. Update job statuses
5. Initialize shortlist trackers
6. Collect shortlist trackers
7. Bootstrap resume workspace
8. Fill resume bullets
9. Compile PDFs
10. Finalize DB + tracker status

---

## Prerequisites

- MCP server running (`JOBWORKFLOW_DB`/`JOBWORKFLOW_ROOT` configured)
- Full resume exists (`JOBWORKFLOW_FULL_RESUME_PATH`)
- Resume template exists (`JOBWORKFLOW_RESUME_TEMPLATE_PATH`)
- Trackers dir configured (`JOBWORKFLOW_TRACKERS_DIR`, default `trackers/`)
- Skills available:
  - `job-matching-expertise` (Step 3)
  - `resume-crafting-expertise` (Step 8)

---

## Stage A: Intake

### Step 1: Scrape Jobs

**MCP Tool**: `scrape_jobs`

```python
scrape_jobs(dry_run=False)
```

**SUCCESS CRITERIA**: `inserted > 0` OR `duplicate > 0`

### Step 2: Read New Jobs Queue

**MCP Tool**: `bulk_read_new_jobs`

```python
result_read = bulk_read_new_jobs()
jobs = result_read["jobs"]
```

**SUCCESS CRITERIA**: `len(jobs) > 0`

### Step 3: Classify Jobs

**Reference Skill**: `job-matching-expertise`  
**Mandatory**: load and apply this skill before classification.

For each job, produce `classification` in `shortlist | reviewed | reject`.

### Step 4: Update Job Statuses

**MCP Tool**: `bulk_update_job_status`

```python
updates = [
    {"id": job["id"], "status": classification}
    for job, (classification, reason) in zip(jobs, classifications)
]

bulk_update_job_status(updates=updates)
```

**SUCCESS CRITERIA**: `updated_count > 0`

### Step 5: Initialize Shortlist Trackers

**MCP Tool**: `initialize_shortlist_trackers`

```python
initialize_shortlist_trackers(force=False, dry_run=False)
```

**SUCCESS CRITERIA**: `created_count > 0` OR `skipped_count > 0`

---

## Stage B: Tailor and Finalize

```python
# Important: these two passes must use different force settings
bootstrap_force = True
compile_force = False
```

### Step 6: Collect Shortlist Trackers

```bash
trackers_dir="${JOBWORKFLOW_TRACKERS_DIR:-trackers}"
trackers=$(find "$trackers_dir" -name "*.md" -type f -print0 | \
  xargs -0 grep -Eil "status:[[:space:]]*(shortlist|reviewed)" | \
  head -10)

items=$(echo "$trackers" | jq -R -s -c 'split("\n")[:-1] | map({tracker_path: .})')
```

**SUCCESS CRITERIA**: `len(items) > 0`

### Step 7: Bootstrap Resume Workspace

**MCP Tool**: `career_tailor`

```python
result_bootstrap = career_tailor(items=items, force=bootstrap_force)
```

**SUCCESS CRITERIA**: each item has `resume_tex_path` and `ai_context_path` for Step 8 editing.

### Step 8: Fill Resume Bullets

**Reference Skill**: `resume-crafting-expertise`  
**Mandatory**: load and apply this skill before editing any `resume.tex`.

For each successful item from Step 7:

1. Open `resume_tex_path`
2. Use `ai_context_path` + full resume facts
3. Replace tokens matching `*-BULLET-POINT-*`
4. Keep LaTeX structure unchanged

Hard guardrails (must pass):

1. Section-scoped grounding (no cross-section fact drift):
   - `Project Experience` bullets: only from project facts in `full_resume.md` / `ai_context.md`.
   - `Qishu Data ... Machine Learning Engineer Intern` bullets: only from internship facts.
   - `University of Waterloo ... Researcher (...)` bullets: only from Waterloo research facts.
2. No fabricated claims: every bullet must be traceable to `ai_context.md`.
3. No duplicate bullets in one resume: exact duplicate `\\resumeItem{...}` text is forbidden.
4. If any guardrail fails for one resume, do not proceed that resume to Step 9.

Validation:

```bash
find data/applications -name "resume.tex" | xargs grep -n "BULLET-POINT"
```

Duplicate check:

```bash
for f in data/applications/*/resume/resume.tex; do
  dups=$(rg -o '\\\\resumeItem\\{.*\\}' "$f" | sort | uniq -d)
  if [ -n "$dups" ]; then
    echo "Duplicate bullets in $f"
    echo "$dups"
  fi
done
```

**SUCCESS CRITERIA**:

- no `BULLET-POINT` matches
- duplicate check returns empty
- all edited bullets are section-consistent with `ai_context.md`

### Step 9: Compile PDFs

**MCP Tool**: `career_tailor` (second pass)

```python
result_compile = career_tailor(items=items, force=compile_force)
```

Use only `result_compile["successful_items"]` in the next step.

**SUCCESS CRITERIA**: `result_compile["success_count"] > 0`

### Step 10: Finalize Database and Trackers

**MCP Tool**: `finalize_resume_batch`

```python
result_finalize = finalize_resume_batch(
    items=result_compile["successful_items"],
    dry_run=False,
)
```

**SUCCESS CRITERIA**: `result_finalize["success_count"] > 0`

---

## Workflow Completion Checklist

- [ ] Step 1-5 intake completed
- [ ] Step 6-10 tailor/finalize completed
- [ ] All placeholders removed
- [ ] PDFs compiled successfully
- [ ] Finalization committed to DB + tracker
