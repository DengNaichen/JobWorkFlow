# Obsidian Job Application Tracker

This directory is the "Combat Command Center" for your job search. It uses Obsidian + Dataview to provide a real-time dashboard of all active applications.

## Directory Structure
- `Job Application.md`: The main Dataview dashboard. Open this to see your entire pipeline.
- `template.md`: The master template for new job entries.
- `template-a/` & `template-b/`: Organized subfolders for different types of applications.
- `README.md`: This guide.

## 1. Adding a New Job
1. Copy `template.md` into one of the tracker subfolders (e.g., `template-a/`).
2. Rename it to `YYYY-MM-DD-CompanyName.md`.
3. Fill in the frontmatter (`company`, `position`, `status`, etc.).
4. The dashboard in `Job Application.md` will update automatically.

## 2. Linking to Artifacts
Each note links to specific artifacts in the `data/applications/` directory:
- `resume_path`: Points to `data/applications/<company>/resume/resume.pdf`.
- `cover_letter_path`: Points to `data/applications/<company>/cover/cover-letter.pdf`.

## 3. Automation Support
Kaka (the Agent) and the `kaka-job-scout` MCP tool use this folder to automatically initialize new job trackers from scraped LinkedIn data.
