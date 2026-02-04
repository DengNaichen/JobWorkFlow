# JobWorkFlow: Recruitment Pipeline

A technical workflow for scouting roles, initializing application artifacts, and tracking pipeline state. The core automation is a Go-based MCP server (`kaka-job-scout`) plus an Obsidian/Dataview tracker and LaTeX resume templates.

## Architecture

1. **Scout**: External agent/browser finds a job post and extracts structured fields.
2. **Initialize**: `kaka-job-scout` creates an Obsidian tracker note and a per-company folder.
3. **Tailor**: LaTeX template is edited and compiled into a PDF resume.
4. **Monitor**: Obsidian + Dataview renders the pipeline dashboard.

## Requirements

- Go (for `mcp-server`)
- LaTeX + `latexmk` (for resume builds)
- Obsidian with Dataview plugin (for tracking)

## Quickstart

### 1) Start the MCP server

```bash
cd mcp-server
go run .
```

### 2) Initialize a job entry

The MCP tool accepts:
- `company` (string)
- `position` (string)
- `url` (string)
- `jd` (string)

On success, it writes a tracker note under `trackers/` and creates:
```
data/applications/<company>/resume/
data/applications/<company>/cover/
```

### 3) Build a resume PDF
```bash
latexmk -pdf -output-directory=data/templates data/templates/resume.tex
latexmk -c -output-directory=data/templates data/templates/resume.tex
```

### 4) Track applications
Open `trackers/Job Application.md` in Obsidian. Add new entries by copying
`trackers/template.md` into a tracker folder and filling frontmatter.

## Utility
Check for duplicates before initializing a tracker:
```bash
./scripts/check_job.sh "<job_url>" "<Company Name>" "<Position Name>"
```

## Directory Map
- `data/templates/` LaTeX sources and template content
- `data/applications/` Per-company resume/cover letter output
- `trackers/` Obsidian vault and Dataview dashboard
- `mcp-server/` Go MCP server (`kaka-job-scout`)
- `docs/skills/` Operational docs for automation/skills
- `scripts/` Local helper scripts

## Notes
- Build artifacts (`*.pdf`, `*.aux`, `*.log`, `*.out`, `*.synctex.gz`) are ignored via `.gitignore`.
