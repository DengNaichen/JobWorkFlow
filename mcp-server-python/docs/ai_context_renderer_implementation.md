# AI Context Renderer Implementation

## Overview

This document describes the implementation of task 3.4 from the career-tailor spec: "Regenerate `ai_context.md` every run using atomic writes".

## Requirements Addressed

- **Requirement 4.5**: Regenerate `resume/ai_context.md` on each successful item run
- **Requirement 4.6**: Generated files SHALL be written atomically

## Implementation

### Module: `utils/ai_context_renderer.py`

Created a new module that provides two main functions:

#### 1. `render_ai_context()`

Renders ai_context.md content with full resume and job description.

**Parameters:**
- `company`: Company name from tracker frontmatter
- `position`: Position title from tracker frontmatter
- `job_description`: Job description content extracted from tracker
- `full_resume_path`: Path to full resume markdown file (default: `data/templates/full_resume_example.md`)
- `output_path`: Target path for ai_context.md (optional, if None returns content without writing)

**Returns:** Rendered ai_context.md content as string

**Features:**
- Reads full resume content from template
- Builds structured ai_context.md with sections:
  - Full Resume Source (raw)
  - Job Description
  - Notes (company, position, creation metadata)
  - Instructions for AI-assisted tailoring
- Uses atomic writes via `utils.file_ops.atomic_write()` to ensure files are never partially written
- Creates parent directories automatically if needed

#### 2. `regenerate_ai_context()`

Convenience function that combines tracker data extraction and ai_context rendering.

**Parameters:**
- `tracker_data`: Parsed tracker data from `parse_tracker_for_career_tailor`
- `workspace_dir`: Application workspace directory (e.g., `data/applications/amazon-3629`)
- `full_resume_path`: Path to full resume markdown file

**Returns:** Path to the generated ai_context.md file

**Features:**
- Extracts required fields from tracker data (company, position, job_description)
- Constructs output path: `{workspace_dir}/resume/ai_context.md`
- Calls `render_ai_context()` to generate and write the file
- Designed for use by career_tailor tool during batch processing

## File Structure

The generated `ai_context.md` file has the following structure:

```markdown
# AI Context

## Full Resume Source (raw)
<full resume content from template>

## Job Description
<job description from tracker>

## Notes
- Company: <company name>
- Position: <position title>
- Created via career_tailor MCP Tool

## Instructions
- Tailor the resume content to match the job description.
- Keep content truthful and consistent with the source resume.
- Update resume.tex in this folder accordingly.
```

## Atomic Write Behavior

The implementation uses `utils.file_ops.atomic_write()` which ensures:

1. Content is written to a temporary file in the same directory
2. File is synced to disk (fsync)
3. Temporary file is atomically renamed to target path
4. Target file is never in a partially written state
5. File handles are always closed, even on failure

This satisfies Requirement 4.6 for atomic writes.

## Integration with Career Tailor Workflow

The ai_context_renderer integrates with the career_tailor tool workflow:

1. **Parse tracker**: `parse_tracker_for_career_tailor()` extracts company, position, and job description
2. **Create workspace**: `ensure_workspace_directories()` creates resume/, cover/, cv/ directories
3. **Regenerate ai_context**: `regenerate_ai_context()` generates fresh ai_context.md on every run
4. **Materialize resume.tex**: Template is copied/preserved/overwritten based on force flag
5. **Compile PDF**: LaTeX compilation produces resume.pdf

The ai_context.md file is regenerated on **every successful item run**, ensuring it always reflects the current tracker data (Requirement 4.5).

## Testing

### Unit Tests (`tests/test_ai_context_renderer.py`)

**15 tests covering:**

1. **TestRenderAiContext** (7 tests):
   - Basic rendering without file write
   - Rendering with atomic write to file
   - Error handling for missing full resume
   - Parent directory creation
   - Overwriting existing files
   - Multiline job descriptions
   - Special characters in company/position

2. **TestRegenerateAiContext** (5 tests):
   - Basic regeneration from tracker data
   - Error handling for missing tracker fields
   - Resume directory creation
   - Overwriting existing ai_context.md
   - Custom full resume path

3. **TestAtomicWrites** (1 test):
   - Verifying no partial content on write

4. **TestRequirementsCoverage** (2 tests):
   - Requirement 4.5: Regenerate every run
   - Requirement 4.6: Atomic writes

### Integration Tests (`tests/test_ai_context_renderer_integration.py`)

**6 tests covering:**

1. **TestAiContextRendererIntegration** (4 tests):
   - End-to-end tracker parsing to ai_context generation
   - Overwriting existing ai_context on regeneration
   - Multiple trackers in different workspaces (batch simulation)
   - Complex job descriptions with special formatting

2. **TestErrorHandling** (2 tests):
   - Missing job description section in tracker
   - Missing required frontmatter fields

### Test Results

All 21 tests pass successfully:
```
tests/test_ai_context_renderer.py: 15 passed
tests/test_ai_context_renderer_integration.py: 6 passed
Total: 21 passed in 0.10s
```

## Usage Example

```python
from utils.tracker_parser import parse_tracker_for_career_tailor
from utils.ai_context_renderer import regenerate_ai_context
from utils.file_ops import ensure_workspace_directories

# Parse tracker
tracker_data = parse_tracker_for_career_tailor("trackers/2026-02-07-amazon-4000.md")

# Create workspace
workspace_dir = "data/applications/amazon-4000"
ensure_workspace_directories("amazon-4000")

# Regenerate ai_context.md
ai_context_path = regenerate_ai_context(
    tracker_data=tracker_data,
    workspace_dir=workspace_dir,
    full_resume_path="data/templates/full_resume_example.md"
)

print(f"Generated: {ai_context_path}")
# Output: Generated: data/applications/amazon-4000/resume/ai_context.md
```

## Dependencies

- `utils.file_ops`: Provides `atomic_write()` for atomic file operations
- `utils.tracker_parser`: Provides `parse_tracker_for_career_tailor()` for tracker parsing
- `pathlib.Path`: For path manipulation
- `typing.Optional`: For type hints

## Next Steps

This implementation completes task 3.4. The next tasks in the career-tailor spec are:

- **Task 4.1**: Placeholder scan before compile
- **Task 4.2**: Run pdflatex and verify non-empty resume.pdf
- **Task 4.3**: Add compile tests
- **Task 5.1**: Create tools/career_tailor.py batch orchestration
- **Task 5.2**: Build structured response
- **Task 5.3**: Build successful_items handoff payload
- **Task 5.4**: Enforce boundary behavior in handler

The ai_context_renderer module is now ready to be integrated into the career_tailor tool handler.
