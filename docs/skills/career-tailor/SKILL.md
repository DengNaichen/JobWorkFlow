---
name: career-tailor
description: Use when generating per-job resume workspaces, tailoring resume bullets from full_resume + JD, and compiling PDFs.
---

# Skill: Career Tailor

**Goal:** Generate a per-job resume workspace from a tracker, then tailor and compile a resume PDF.

**Relevant files**
- `data/templates/full_resume.md` (source of truth)
- `data/templates/resume_skeleton.tex` (LaTeX template)
- `mcp-server` tool: `career_tailor`
- `data/applications/<company_or_job>/resume/resume.tex` (per-job resume)
- `data/applications/<company_or_job>/resume/resume.pdf` (compiled output)

### Triggers / Inputs
1. A tracker note exists with frontmatter + `## Job Description`.
2. Call the MCP tool to generate a per-job workspace.
3. (Optional) Use an AI prompt to rewrite `resume.tex` based on JD + `full_resume.md`.

### Outputs / Effects
- Creates `data/applications/<slug>/resume/` and `data/applications/<slug>/cv/`.
- Copies `resume_skeleton.tex` → `resume.tex`.
- Writes `ai_context.md` containing `full_resume.md` + Job Description.
- (Optional) Compiles PDF from the tailored TeX.

### Steps / Workflow
1. Bootstrap workspace from a tracker:
   ```json
   {
     "tool": "career_tailor",
     "arguments": {
       "tracker_path": "trackers/YYYY-MM-DD-<job>.md",
       "compile": false,
       "force": false
     }
   }
   ```
2. Use `resume/ai_context.md` to tailor `resume/resume.tex` with the rules below. **LLM rewrite required** (do not just copy template bullets).
3. Compile when ready (set `compile: true`).
4. After the tailored resume is written, update the tracker status to `Resume Written` using MCP `update_tracker_status`.

### Tailoring rules (make it deterministic)
**Goal:** Replace placeholder content in `resume.tex` using only facts in `full_resume.md` + JD. Do not invent.

**Do**
- Keep the LaTeX structure intact. Only replace bullet text.
- Edit bullets under **Project Experience** (AI/LLM track + Backend/Platform track) and **Work Experience** only.
- Prioritize JD keywords in bullets (same meaning, concise).
- Prefer impact + metric + tech stack.
- Keep 2–4 bullets per role/project (avoid long lists).
- Keep to one page; trim low‑signal bullets first.
- Rewrite bullets in your own words to match the JD phrasing (truthful, no fabrication).
- If content exceeds one page, remove bullets from the oldest or least relevant roles first, based on JD fit.

**Don’t**
- Add new sections or LaTeX packages.
- Copy JD verbatim; paraphrase and match to existing experience.
- Fabricate skills, companies, or dates.
- Do not change header, Education, Skills, or section headings.

**LaTeX safety (mandatory)**
- Keep the macro intact: every bullet must stay in the form `\resumeItem{...}`.
- Only replace the text *inside* the braces; never delete the leading backslash.
- If you mention complexity or math, wrap it in math mode (e.g., `$O(n^2)$`) instead of writing `O(n\textasciicircum{}2)`.
- Escape special characters outside math mode: `\ % & _ # $ ~ ^ { }`.

**Mapping procedure**
1. Extract JD must‑haves and top 5 keywords.
2. Map each JD requirement to an existing bullet in `full_resume.md`.
3. Rewrite bullets to mirror JD phrasing while preserving truth.
4. Fill **AI-PROJECT-BULLET-*` with AI/LLM/RAG/Graph content.
5. Fill **BE-PROJECT-BULLET-*` with backend/platform/infra content.
6. Update **WORK-BULLET-*` with research bullets.

**One-page check (deterministic)**
1. Compile PDF (pdflatex).
2. Determine page count using one of:
   - `mdls -name kMDItemNumberOfPages resume.pdf` (macOS)
   - `python - <<'PY'\nfrom pathlib import Path\nimport subprocess\nout = subprocess.check_output(['mdls','-name','kMDItemNumberOfPages','resume.pdf']).decode()\nprint(out)\nPY`
3. If pages > 1, remove the lowest‑relevance bullet from the oldest role and recompile.
4. Repeat compile until 1 page or 2 bullets remain per role.

### Example rewrite pattern (bullet)
Before:
```
\resumeItem{PROJECT-BULLET-1}
```
After (example):
```
\resumeItem{Built LLM-driven knowledge graph pipeline (PDF→Markdown→entity/edge extraction) using FastAPI, SQLAlchemy, and pgvector; improved concept de-duplication with HNSW similarity search.}
```

### Strategic Coaching Mode (role switch)
Use this when the user asks for interview/story guidance, personal brand, or narrative strategy.

**Required inputs**
- Resume source: `data/templates/full_resume.md`
- Target role or JD (ask if missing)

**Rules**
- Use only facts from the resume; do not invent.
- Anchor each story with explicit resume evidence.
- If information is missing, ask instead of guessing.

**Output format (must follow)**
1) **Personal brand statement (1 sentence)**
2) **Signature stories (2–3)**
   - Title
   - STAR bullets (Situation/Task/Action/Result)
   - 30-second version
   - 2-minute version
   - Evidence (cite resume bullets)
3) **Reframe disadvantages**
   - Issue -> Reframe -> “Say this” sentence

### Related Questions
- Should we keep PDFs in Git? No—build artifacts are ignored by `.gitignore`.
- Where does the slug come from? If tracker `resume_path` exists, it is used; otherwise derived from company/position or URL hash.

### Health Checks
- `data/applications/<slug>/resume/resume.tex` exists.
- `data/applications/<slug>/resume/ai_context.md` includes full resume + JD.
- `git status` shows no PDFs or LaTeX build artifacts.

Keep this skill around any time you adjust the TeX source or want reproducible CV outputs.
