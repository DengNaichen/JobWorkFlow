---
name: career-tailor-finalize
description: "Use when generating tailored resume artifacts from shortlist trackers and committing completion safely: run career_tailor, validate outputs, and finalize status sync."
---

# Skill: Career Tailor Finalize

## Goal
Run the artifact and commit half of the pipeline:
1. Build per-job resume artifacts from trackers
2. Enforce resume quality/validity guardrails
3. Finalize DB + tracker sync only for successful items

## MCP Tools In Scope
- `career_tailor`
- `finalize_resume_batch`
- `update_tracker_status` (fallback/manual correction only)

Do not run ingestion or triage tools in this skill.

## Inputs
- Shortlist tracker paths (and `job_db_id` when available)
- Optional path overrides for templates/applications root

## Workflow
1. Build one `items[]` batch from shortlisted trackers.
2. Run `career_tailor` bootstrap pass to materialize per-item workspace files (`resume.tex`, `ai_context.md`, `resume.pdf` attempt).
3. Run an LLM fill pass on the materialized `resume.tex` files to replace placeholder bullets.
4. Run `career_tailor` again for compile/validation on edited files.
5. Use only second-pass `career_tailor.successful_items` for `finalize_resume_batch`.
6. Keep failed items in `shortlist`/`reviewed` with explicit reasons.
7. Use `update_tracker_status` only for targeted repair actions.

## LLM Fill Pass (Required Between Two `career_tailor` Passes)
- Target files: `data/applications/<slug>/resume/resume.tex`
- Context files: `data/templates/full_resume.md` and each tracker's Job Description
- Edit scope: bullet text only (Project Experience + Work Experience)
- Must replace all placeholders like `WORK-BULLET-POINT-*`, `PROJECT-AI-*`, `PROJECT-BE-*`
- Never change macros/sections/header/education/skills

Use this execution prompt for each resume file:

```text
You are filling LaTeX resume bullets.
Inputs:
- full resume facts: data/templates/full_resume.md
- target job description: from tracker markdown
- target tex file: data/applications/<slug>/resume/resume.tex

Rules:
1) Replace placeholder bullet tokens only with truthful content grounded in the full resume.
2) Keep every bullet in \\resumeItem{...} format.
3) Do not add new sections or macros.
4) Prefer impact + metric + stack phrasing.
5) No fabrication.

Output:
- Apply direct edits to resume.tex.
- Ensure zero remaining placeholder tokens matching:
  WORK-BULLET-POINT-|PROJECT-AI-|PROJECT-BE-
```

Preflight check before second `career_tailor` pass:

```bash
files="$(find data/applications -type f -path '*/resume/resume.tex')"
if [ -z "$files" ]; then
  echo "No resume.tex files yet. Run first-pass career_tailor bootstrap first."
else
  echo "$files" | xargs rg -n "WORK-BULLET-POINT-|PROJECT-AI-|PROJECT-BE-"
fi
```

Expected:
- On first-time runs before bootstrap: informational message above.
- After bootstrap: no matches.

## Tailoring Rules (Spirit Preserved)
- Source of truth content: `data/templates/full_resume.md` + tracker JD.
- Keep LaTeX structure intact; edit bullet text only.
- Focus edits on Project Experience and Work Experience.
- Prefer impact + metric + stack; no fabrication.
- Keep one-page resume target where possible.

## LaTeX Safety
- Keep `\\resumeItem{...}` macro shape unchanged.
- Escape special characters when needed: `\\ % & _ # $ ~ ^ { }`.
- Use math mode for complexity notation (example: `$O(n^2)$`).

## Guardrails (Hard)
- Never mark Resume Written/resume_written without valid artifacts.
- If `resume.pdf` missing/zero-byte or placeholders remain in `resume.tex`, do not finalize.
- Continue batch on item-level failures and return structured errors.

## Manual Build Fallback (from legacy tex-build)
Only when explicit manual compile is needed:
```bash
latexmk -pdf -output-directory=data/templates data/templates/resume.tex
latexmk -c -output-directory=data/templates data/templates/resume.tex
```
Use fallback as diagnostics; primary path remains `career_tailor`.

## Required Output Shape
- `run_id`
- `tailor_totals`: total/success/failed
- `finalize_totals`: success/failed
- `failed_items` with concrete reason
- `errors_by_step`
- `next_actions`
