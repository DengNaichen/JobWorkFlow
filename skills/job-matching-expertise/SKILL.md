---
name: job-matching-expertise
description: "Domain expertise for evaluating job-candidate fit for Backend, ML, and AI Engineering roles. Provides rubrics, quality standards, and decision frameworks—no workflow orchestration."
---

# Skill: Job Matching Expertise

## Purpose

This skill encodes domain knowledge for assessing whether a job posting is a good match for a candidate focused on **Backend Engineering**, **Machine Learning**, and **AI Engineering** roles. It provides evaluation criteria, not execution steps.

---

## Target Role Profile

> **Source**: [`data/templates/full_resume.md`](../../data/templates/full_resume.md)

**Summary**: Backend + ML/AI Engineering; Python-first; experienced with LLM integration, RAG pipelines, and production ML systems.

---

## Job Quality Signals

These signals are **secondary**. Use them only to decide between **Reviewed vs Reject** when the JD lacks clear must-have requirements or is too vague to assess. They must **not** override the hard-gate logic in `HR Initial Screen Standard`.

**Strong signals ✅**

- Specific responsibilities + specific stack/tools (not generic “exciting projects”)
- Clear problem space (what is being built, for whom, why it matters)
- Explicit “required/must-have” list (makes screening possible)
- Engineering fundamentals mentioned (testing, code review, docs, observability)
- Reasonable scope (not one person owning 15 unrelated domains)

**Weak signals ⚠️**

- Vague JD; no stack; no concrete deliverables
- No explicit must-have requirements (hard to screen; bias toward Reviewed)
- Skill laundry list / buzzword bingo without context
- Copy-paste corporate template; no team/product specifics

---

## HR Initial Screen Standard

This standard answers one question: **would an HR/recruiter likely filter this candidate out at initial screen, without assuming any upskilling?**

### Policy Overrides (immediate ❌)

- **Company blacklist**: Jerry, Alignerr, TATA
- Intern/internship roles

### Hard Reject Rules (immediate ❌)

Reject if **any** of the following is true.

1) **Role function mismatch**
   - Frontend-only (React/Vue/Angular/Next.js; UI work dominates)
   - Mobile-only (iOS/Android/React Native)
   - Pure DevOps/SRE where infra/oncall dominates and there is no clear backend/app ownership
   - BI/Analyst-heavy “data” roles (dashboards/reporting/stakeholder insights as primary output)

2) **Core stack mismatch (required-by-JD)**
   - JD is strongly bound to Java/Spring, .NET, C++ as the core (Python/ML is absent or only “nice-to-have”)
   - JD lists must-have technologies or domains that are not credibly evidenced in the resume

3) **Seniority / credential hard mismatch**
   - Staff/Principal/Lead role with clear expectations beyond current level (e.g., 10–12+ years + org-wide architecture + multi-team leadership)
   - PhD **required** (not preferred) and the candidate does not have it

4) **Eligibility constraints**
   - Work authorization, location/onsite, security clearance, or language requirements explicitly marked as required and not met

5) **Duplicate**
   - Same company + title already processed in the current run

### Evidence Standard (how to interpret “must-have”)

- Treat JD items labeled **must/required** as hard gates.
- A requirement is “met” only if the resume contains **readable evidence** (role/project ownership + relevant responsibilities + outcomes/scale, where possible).
- Count a requirement as met only if the resume shows at least **two** of: (a) ownership/responsibility, (b) concrete project context, (c) production use, (d) measurable outcomes/scale.
- Familiarity/mentions without the above evidence should be treated as **not met** at HR screen.

### Classification Output (aligned with batch labels)

- **Shortlist**: passes HR initial screen (no policy override; no hard-reject triggered; all JD required items have resume evidence; seniority/eligibility aligned).
- **Reviewed**: cannot confidently decide due to missing/vague JD must-haves, or the resume evidence is weak/implicit but plausibly present.
- **Reject**: any policy override or hard-reject rule triggered, or any JD required item lacks resume evidence.

Mapping note: `Shortlist ≈ Pass initial screen`, `Reviewed ≈ Unclear/Review`, `Reject ≈ Fail initial screen`.

### Workflow Output Contract (Required)

When emitting machine-consumable results (for MCP update steps), use this schema per job:

```json
{
  "id": 12345,
  "status": "shortlist",
  "reason": "Meets Python backend + production ML requirements; no hard reject gates triggered."
}
```

Hard rules:

- `status` must be exactly one of: `shortlist`, `reviewed`, `reject` (lowercase only).
- `reason` is mandatory and concise (1-2 sentences), tied to hard gates/evidence standard.
- If uncertain, use `reviewed` with explicit uncertainty reason; do not force binary decisions.
- Human-readable labels (`Shortlist/Reviewed/Reject`) are for explanation only, never for machine fields.

### Notes on Equivalents (optional, conservative)

Allow limited equivalence only when the JD does not state a strict tool requirement:

- FastAPI or Flask/Django (Python API frameworks)
- AWS or GCP or Azure when the requirement is stated broadly as “cloud experience” (IaaS/PaaS). Do not treat them as equivalent when the JD requires a specific cloud provider or a specific managed service.
- Managed vector DBs (Pinecone/Weaviate) ↔ other managed vector DBs (e.g., Milvus managed) when the requirement is “vector DB” broadly
- Kubernetes ↔ other container schedulers only if JD is not explicit about K8s

If the JD explicitly says “must have X in production,” do **not** substitute equivalents.

---

## Batch Evaluation: Cognitive Biases & Calibration

When evaluating multiple jobs in a batch, be aware of these cognitive risks:

### Consistency Risks

| Bias | Description |
|------|-------------|
| **Standards Drift** | Getting progressively more lenient after weak postings, or harsher after strong ones |
| **Comparison Bias** | Judging relative to batch ("better than last 5") instead of absolute rubric |
| **Fatigue Shortcuts** | Pattern matching on title/company alone; skimming JDs after 30+ jobs |

### Distribution Calibration

A healthy batch typically yields:

| Category | Expected Range |
|----------|---------------|
| **Shortlist** | 15-25% |
| **Reviewed** | 20-30% |
| **Reject** | 45-65% |

**Red flags:**

- **>80% shortlist** → likely too lenient
- **>80% reject** → likely too harsh  
- **<5% reviewed** → forcing binary decisions; embrace uncertainty
