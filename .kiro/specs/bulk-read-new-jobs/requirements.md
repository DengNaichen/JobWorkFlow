# Requirements Document

## Introduction

The `bulk_read_new_jobs` MCP tool provides read-only batch retrieval of job records from a SQLite database for downstream LLM triage processing. This tool is part of the JobWorkFlow pipeline, specifically handling step 2: fetching newly imported jobs that require evaluation.

## Glossary

- **MCP_Tool**: A Model Context Protocol tool that can be invoked by an LLM agent
- **Job_Database**: SQLite database located at `data/capture/jobs.db` containing job records
- **New_Job**: A job record with status field set to `new`
- **Batch**: A collection of job records retrieved in a single operation
- **Triage_Agent**: The downstream LLM agent that evaluates job records

## Requirements

### Requirement 1: Batch Job Retrieval

**User Story:** As an LLM agent, I want to retrieve new jobs in configurable batches, so that I can process them efficiently without overwhelming memory or API limits.

#### Acceptance Criteria

1. WHEN the tool is invoked with a batch size parameter, THE MCP_Tool SHALL return up to that number of jobs with status `new`
2. WHEN the tool is invoked without a batch size parameter, THE MCP_Tool SHALL return up to 50 jobs with status `new`
3. WHEN the batch size parameter is less than 1, THE MCP_Tool SHALL return an error indicating invalid batch size
4. WHEN the batch size parameter exceeds 1000, THE MCP_Tool SHALL return an error indicating batch size too large
5. WHEN fewer new jobs exist than the requested batch size, THE MCP_Tool SHALL return all available new jobs

### Requirement 2: Database Query

**User Story:** As the MCP tool, I want to query the SQLite database for jobs with status `new`, so that I can provide the correct subset of jobs to the triage agent.

#### Acceptance Criteria

1. WHEN querying the database, THE MCP_Tool SHALL connect to the SQLite database at `data/capture/jobs.db` by default
2. WHEN querying the database, THE MCP_Tool SHALL accept an optional `db_path` parameter to override the default database location
3. WHEN querying the database, THE MCP_Tool SHALL filter records where status equals `new`
4. WHEN querying the database, THE MCP_Tool SHALL order results by `captured_at DESC, id DESC` to ensure deterministic batch retrieval
5. WHEN the database file does not exist, THE MCP_Tool SHALL return an error indicating the database is not found
6. WHEN the database connection fails, THE MCP_Tool SHALL return an error with connection details

### Requirement 3: Job Data Structure

**User Story:** As a triage agent, I want to receive complete job information, so that I can evaluate each job effectively.

#### Acceptance Criteria

1. WHEN returning job records, THE MCP_Tool SHALL include the following fixed fields: `id`, `job_id`, `title`, `company`, `description`, `url`, `location`, `source`, `status`, `captured_at`
2. WHEN returning job records, THE MCP_Tool SHALL NOT include arbitrary additional database columns beyond the fixed schema
3. WHEN a field value is missing in the database, THE MCP_Tool SHALL return `null` or empty string consistently
4. WHEN returning job records, THE MCP_Tool SHALL format all fields as JSON-serializable types
5. WHEN returning job records, THE MCP_Tool SHALL maintain a stable schema contract across all responses

### Requirement 4: Read-Only Operations

**User Story:** As a system administrator, I want the tool to perform only read operations, so that the database integrity is maintained and job status updates are handled by dedicated components.

#### Acceptance Criteria

1. THE MCP_Tool SHALL NOT modify any job records in the database
2. THE MCP_Tool SHALL NOT update job status fields
3. THE MCP_Tool SHALL NOT delete any job records
4. THE MCP_Tool SHALL NOT create any new job records
5. WHEN database operations complete, THE MCP_Tool SHALL close the database connection properly

### Requirement 5: Error Handling

**User Story:** As an LLM agent, I want clear error messages when operations fail, so that I can understand what went wrong and take appropriate action.

#### Acceptance Criteria

1. WHEN the database file is not accessible, THE MCP_Tool SHALL return an error message indicating the file path and access issue
2. WHEN a database query fails, THE MCP_Tool SHALL return an error message with the query failure reason
3. WHEN invalid parameters are provided, THE MCP_Tool SHALL return an error message describing the parameter validation failure
4. WHEN no jobs with status `new` exist, THE MCP_Tool SHALL return an empty result set without error
5. WHEN an unexpected error occurs, THE MCP_Tool SHALL return a descriptive error message without exposing sensitive system details

### Requirement 6: MCP Tool Interface

**User Story:** As an MCP server, I want the tool to conform to MCP protocol standards, so that it can be invoked correctly by LLM agents.

#### Acceptance Criteria

1. THE MCP_Tool SHALL accept parameters as a structured input following MCP conventions
2. THE MCP_Tool SHALL return results as structured output following MCP conventions
3. WHEN invoked, THE MCP_Tool SHALL validate all input parameters before executing database operations
4. WHEN returning results, THE MCP_Tool SHALL format job data as JSON-serializable structures
5. THE MCP_Tool SHALL include metadata in responses indicating the number of jobs returned (`count`)
6. THE MCP_Tool SHALL include pagination metadata (`has_more`, `next_cursor`) to support multi-page retrieval

### Requirement 7: Cursor-Based Pagination

**User Story:** As an LLM agent, I want to paginate through large result sets using cursors, so that I can retrieve all new jobs without loading them all into memory at once.

#### Acceptance Criteria

1. WHEN the tool returns results, THE MCP_Tool SHALL include a `has_more` boolean indicating if additional pages exist
2. WHEN additional pages exist, THE MCP_Tool SHALL include a `next_cursor` string that can be used to retrieve the next page
3. WHEN the tool is invoked with a `cursor` parameter, THE MCP_Tool SHALL return the next page of results after that cursor position
4. WHEN the cursor is malformed or invalid, THE MCP_Tool SHALL return a validation error
5. THE cursor SHALL be opaque to clients and encode the pagination state (`captured_at`, `id`)
6. WHEN paginating through results, THE MCP_Tool SHALL ensure no duplicate records across pages
7. WHEN paginating through results, THE MCP_Tool SHALL maintain deterministic ordering across all pages
