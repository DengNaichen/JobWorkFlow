# Skill: TeX Build

**Goal:** Compile the resume TeX source into a local PDF, clean intermediates, and keep the repo free of build artifacts.

**Relevant files**
- `data/templates/resume.tex` (source)
- `data/templates/resume.pdf` (local output)
- `.gitignore` (keeps PDFs/logs out of Git)

### Triggers / Inputs
1. Update `data/templates/resume.tex` content.
2. Run the build command manually when you need a fresh PDF.

### Outputs / Effects
- Generates `data/templates/resume.pdf` for local sharing.
- Intermediate files (`*.aux`, `*.log`, `*.out`, `*.synctex.gz`) are cleaned after build.
- No artifacts should be committed.

### Steps / Workflow
1. Build:
   ```bash
   latexmk -pdf -output-directory=data/templates data/templates/resume.tex
   ```
2. Clean intermediates:
   ```bash
   latexmk -c -output-directory=data/templates data/templates/resume.tex
   ```
3. (Optional) Copy into an application folder:
   ```bash
   cp data/templates/resume.pdf data/applications/<company>/resume/resume.pdf
   ```

### Related Questions
- Should we run this skill before publishing an update? Yes—always rebuild after editing `resume.tex`.
- How does it interact with the Job Application tracker? The PDF is referenced in applications or shared offline, but never inserted into Obsidian notes automatically.
- Should we keep the PDF in Git? No—PDFs and build artifacts are ignored by `.gitignore`.

### Health Checks
- `data/templates/resume.pdf` timestamp matches the last edit.
- `git status` shows no PDFs or LaTeX build artifacts.
- Build logs free of “undefined control sequence” errors.

Keep this skill around any time you adjust the TeX source or want reproducible CV outputs.
