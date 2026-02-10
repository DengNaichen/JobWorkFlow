# Skill: Resume Crafting Expertise

## Purpose

This skill encodes domain knowledge for creating effective technical resumes tailored to Backend, ML, and AI Engineering roles. It provides **content quality principles** and **strategic guidance**, not LaTeX syntax or execution steps.

---

## Core Philosophy: Truth-Grounded Tailoring

### The Golden Rule ✨

**Every word on the resume must be grounded in verifiable facts from this run's `ai_context.md` (`ai_context_path`).**

- ✅ Reframe, re-emphasize, and reorganize true experiences
- ✅ Highlight different aspects based on target role
- ❌ Never fabricate projects, metrics, or technologies
- ❌ Never claim expertise in tools you haven't used

### The Scope Boundary 🚧

**Template source of truth**: [`data/templates/resume_skeleton.tex`](../../data/templates/resume_skeleton.tex)

**LLM may modify ONLY these fields (whitelist):**

- Text inside `\resumeItem{...}` entries under:
  - Project Experience
  - Work Experience
- Placeholder content to replace:
  - Any token matching `*-BULLET-POINT-*` in the active template

**LLM must NOT modify (blacklist):**

- Header/contact block (name, email, links, location, phone)
- Education section
- Technical Skills section
- Section titles/order
- Any LaTeX macros, package imports, spacing/styling commands
- `\resumeSubheading{...}` company/title/date/location metadata

**Change granularity rule:**

- Keep edits minimal and local: replace bullet content only.
- No structural edits unless user explicitly requests them.

---

## Content Writing Principles

### The Impact Formula

Prefer this pattern when it helps clarity: **Action + Context + Impact + Tech Stack**.
Do not force all four elements into every bullet if it makes the sentence unnatural.

Quick check:

- ✅ "Built RAG pipeline for support chatbot; cut response time 4min -> 30sec at 50K+ queries/day using LangChain + Pinecone + GPT-4."
- ❌ "Developed chatbot using AI technologies."

---

### Metrics Matter 📊

**Include quantifiable impact when available**

**If no direct metrics available, use scope indicators**

---

## Tailoring Strategy

### Step 1: Resolve Runtime Inputs (Required)

Primary runtime inputs come from MCP (`career_tailor`) result fields:

- `resume_tex_path` (editing target)
- `ai_context_path` (single-run truth source)

Rules:

- Read and use `ai_context_path` as the factual source for this run.
- Edit only `resume_tex_path` within allowed bullet scope.
- If either path is missing or unreadable, **skip this job**.
- Record skip reason as:
  - `missing_ai_context`
  - `missing_resume_tex`

### Step 2: Parse the Job Description

Identify **3-5 key requirements** from the JD:

- Required technologies (Python, FastAPI, LLMs, etc.)
- Problem domains (distributed systems, ML pipelines, data infra)

### Step 2.5: Build a JD Anchor Set (Required)

From responsibilities + qualifications, extract **5-8 anchor phrases** and tag:

- `must_have`: core hiring signal
- `supporting`: helpful but non-blocking signal

Example anchor set for backend/GenAI SDE roles:

- distributed systems
- data pipelines/services
- GenAI/LLM application
- code quality/testing/reviews
- operational excellence (monitoring/automation)

### Step 3: Map Your Experiences

From `ai_context_path`, find experiences that demonstrate those requirements:

- Which projects used similar tech?
- Which challenges match the problem domain?
- Which roles show appropriate seniority level?

### Step 3.2: Score and Select Evidence (Required)

Before writing bullets, rank candidate evidence from `ai_context_path`:

- `+3` direct match to a `must_have` anchor
- `+2` quantifiable impact (latency, throughput, %, scale)
- `+1` end-to-end ownership (designed + built + operated)
- `-2` technically strong but weak JD relevance

Selection rules:

- Pick highest-ranked evidence first (do not start from section order).
- Include evidence for top `must_have` anchors whenever the source facts exist.
- Do not omit direct-match evidence in favor of niche but less relevant technical details.

### Step 3.5: Section-Scoped Grounding (Hard Constraint)

Apply facts only to the correct section ownership:

- `Project Experience` bullets must come from project facts in `ai_context_path`.
- `Work Experience` internship/job bullets must come from that work experience (or another real work role), not from unrelated projects.
- `Work Experience` research bullets must come from research facts, not from unrelated internships/projects.

Do not move achievements across sections just to optimize keywords. Tailoring is allowed; cross-section fact reassignment is not.

### Step 4: Adjust Emphasis

**For high-relevance experiences:**

- Lead with them (top bullets in each section)
- Add more technical detail
- Highlight metrics related to JD priorities

**For medium-relevance experiences:**

- Include but keep concise
- Frame in terms that bridge to target role
- Focus on transferable skills

**For low-relevance experiences:**

- Minimize or omit (if space-constrained)
- Reframe if possible (e.g., "frontend work" → "full-stack experience")

### Step 4.5: Section Budget (Required)

Use a relevance budget so one section does not dominate:

- Project bullets: primary carrier of JD anchors
- Industry/internship bullets: secondary carrier (real production ownership)
- Research bullets: keep only what strengthens JD anchors (performance/reliability/observability)

If template has fixed section slots, still apply this rule by:

- prioritizing strongest anchor evidence at the top of each section
- avoiding low-relevance research detail when JD needs backend/system execution signals

### Step 5: Keyword Alignment

**Naturally incorporate JD keywords** without keyword stuffing:

If JD mentions "RAG pipelines", and you built semantic search:

- ✅ "Implemented RAG pipeline for semantic search using..."
- ❌ Force "RAG" into every bullet

For platform-specific keywords (example: AWS vs GCP vs AZURE):

- ✅ Whitelist-equivalent cloud mapping is allowed at capability level:
  - AWS <-> GCP <-> Azure for generic cloud requirements (compute, storage, IAM, monitoring, CI/CD).
- ✅ Keep the actual platform truth explicit in bullets (e.g., "on GCP").
- ❌ Do not claim production experience on a platform not present in `ai_context.md`.

---

## Supported Prompt Intents

Absorb and execute these prompt intents within current scope (bullet-level only):

- Bullet rewrite to measurable accomplishments (results-oriented, strong verbs, metrics when available).
- ATS keyword optimization based on JD, with natural phrasing for human readability.
- Work-history language alignment to target JD skills/qualifications (without fabricating experience).
- Transferable-skills reframing for career transitions, limited to existing experience in `ai_context.md`.
- Resume audit feedback focused on vagueness, wordiness, impact, leadership/results signals in bullet content.
- Hiring-manager style critique focused on what to tighten, cut, or emphasize in bullets for interview likelihood.

Out of scope for this skill:

- Resume summary rewrite
- Headline/subheadline writing
- Layout/format redesign
- Technical Skills section rewrite

---

## Quality Control Guardrails

### Final Gate Checklist

Before marking a resume as ready:

- [ ] Truthfulness: every claim is grounded in this run's `ai_context.md`, with no fabricated projects/metrics/platform experience.
- [ ] Section mapping: each bullet's fact source matches its section ownership (project vs work vs research).
- [ ] Scope discipline: only allowed `\resumeItem{}` bullet content was edited; no section/header/macro/style changes.
- [ ] No duplication: no repeated or near-duplicate bullets within the same `resume.tex`.
- [ ] Placeholder cleanup: no placeholder tokens remain (`*-BULLET-POINT-*`, `TODO`, `[Description goes here]`).
- [ ] JD alignment and readability: top bullets align to key JD requirements, wording is specific and natural (no keyword stuffing).
- [ ] Anchor coverage: core `must_have` JD anchors are represented when source evidence exists.
- [ ] Evidence priority: highest-ranked source evidence (from Step 3.2) is included, not displaced by weaker-fit content.
- [ ] Lexical coverage: at least 4 JD anchor phrases are reflected naturally in bullet wording.

### Machine-Check Commands (Required Before Compile)

Use `resume_tex_path` from runtime inputs.

```bash
# 1) Placeholder scan: must return no lines
grep -n -E 'BULLET-POINT|TODO|\[Description goes here\]' "$resume_tex_path"

# 2) Duplicate bullet scan: must return no lines
sed -n 's/^[[:space:]]*\\resumeItem{\(.*\)}[[:space:]]*$/\1/p' "$resume_tex_path" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//' \
  | sort | uniq -d
```
