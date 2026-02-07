# Testing Guide - bulk_read_new_jobs MCP Server

This guide shows you how to test the MCP server in different ways.

## Prerequisites

Make sure you have installed dependencies:

```bash
uv sync
```

## 1. Run the Test Suite (Recommended)

The easiest way to verify everything works:

```bash
# Run all tests
uv run pytest mcp-server-python/tests/ -v

# Run specific test categories
uv run pytest mcp-server-python/tests/test_bulk_read_new_jobs.py -v  # Integration tests
uv run pytest mcp-server-python/tests/test_server_integration.py -v  # Server tests
uv run pytest mcp-server-python/tests/test_cursor.py -v              # Cursor tests

# Run with coverage report
uv run pytest mcp-server-python/tests/ --cov=mcp-server-python --cov-report=html
```

Expected output: `225 passed` ✅

## 2. Test the Tool Directly

Call the tool directly from a one-off script:

```bash
PYTHONPATH=mcp-server-python uv run python - <<'PY'
from tools.bulk_read_new_jobs import bulk_read_new_jobs

result = bulk_read_new_jobs({"limit": 10})
if "error" in result:
    print("Error:", result["error"])
else:
    print("Jobs returned:", result["count"])
    print("Has more pages:", result["has_more"])
    print("Next cursor:", result["next_cursor"])
    if result["jobs"]:
        first = result["jobs"][0]
        print("First job:", first["id"], first["title"], first["company"])
PY
```

This will:
- Fetch jobs with a custom page size (`limit=10`)
- Print pagination metadata
- Print a preview of the first job

Expected output:
```
Jobs returned: 10
Has more pages: True
Next cursor: eyJjYXB0dXJlZF9hdCI6...
First job: 467 Business Analytics & Operational Excellence Associate UCB
```

## 3. Start the MCP Server

Test the server startup:

```bash
cd mcp-server-python
./start_server.sh
```

Expected output:
```
==========================================
JobWorkFlow MCP Server
==========================================
Repository root: /path/to/JobWorkFlow
Server directory: /path/to/JobWorkFlow/mcp-server-python

Configuration:
  Database: /path/to/JobWorkFlow/data/capture/jobs.db
  Log level: INFO
  Log file: (stderr only)
==========================================

Activating virtual environment: /path/to/JobWorkFlow/.venv/
Starting MCP server...
Press Ctrl+C to stop
```

The server will wait for MCP protocol messages on stdin/stdout. Press `Ctrl+C` to stop.

## 4. Test with MCP Inspector (Advanced)

If you have the MCP Inspector installed, you can test the server interactively:

```bash
# Install MCP Inspector (if not already installed)
npm install -g @modelcontextprotocol/inspector

# Run the inspector
mcp-inspector mcp-server-python/server.py
```

This opens a web UI where you can:
- See available tools
- Call tools with different parameters
- Inspect responses
- Test error handling

## 5. Test with Claude Desktop (Production)

To test with Claude Desktop:

1. Copy `mcp-server-python/mcp-config-example.json` and update paths:

```json
{
  "mcpServers": {
    "jobworkflow": {
      "command": "/absolute/path/to/JobWorkFlow/.venv/bin/python",
      "args": ["/absolute/path/to/JobWorkFlow/mcp-server-python/server.py"],
      "env": {
        "JOBWORKFLOW_DB": "/absolute/path/to/JobWorkFlow/data/capture/jobs.db",
        "JOBWORKFLOW_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

2. Add this to your Claude Desktop config:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

3. Restart Claude Desktop

4. In Claude, you can now use the tool:
   ```
   Can you fetch the first 10 new jobs from the database?
   ```

## Common Test Scenarios

### Test Error Handling

```python
# Test with invalid limit
result = bulk_read_new_jobs({"limit": 9999})
# Should return validation error

# Test with invalid cursor
result = bulk_read_new_jobs({"cursor": "invalid"})
# Should return validation error

# Test with non-existent database
result = bulk_read_new_jobs({"db_path": "/nonexistent/path.db"})
# Should return DB_NOT_FOUND error
```

### Test Pagination

```python
# Fetch all jobs in batches
cursor = None
all_jobs = []

while True:
    args = {"limit": 50}
    if cursor:
        args["cursor"] = cursor

    result = bulk_read_new_jobs(args)

    if "error" in result:
        print(f"Error: {result['error']['message']}")
        break

    all_jobs.extend(result["jobs"])

    if not result["has_more"]:
        break

    cursor = result["next_cursor"]

print(f"Total jobs fetched: {len(all_jobs)}")
```

### Test with Debug Logging

```bash
export JOBWORKFLOW_LOG_LEVEL=DEBUG
cd mcp-server-python
./start_server.sh
```

This will show detailed logs including:
- Database queries
- Cursor encoding/decoding
- Pagination calculations
- Schema mapping

## Troubleshooting

### Database Not Found

If you see `DB_NOT_FOUND` error:

```bash
# Check if database exists
ls -l data/capture/jobs.db

# Check database has jobs with status='new'
sqlite3 data/capture/jobs.db "SELECT COUNT(*) FROM jobs WHERE status='new'"
```

### Import Errors

If you see `ModuleNotFoundError`:

```bash
# Make sure you're in the repository root
pwd

# Reinstall dependencies
uv sync

# Verify installation
uv run python -c "import mcp; print('MCP installed')"
```

### Tests Failing

If tests fail:

```bash
# Run tests with verbose output
uv run pytest mcp-server-python/tests/ -vv

# Run a single failing test
uv run pytest mcp-server-python/tests/test_bulk_read_new_jobs.py::TestBulkReadNewJobsIntegration::test_tool_with_default_parameters -vv

# Check for syntax errors
uv run python -m py_compile mcp-server-python/tools/bulk_read_new_jobs.py
```

## Performance Testing

To test with large datasets:

```bash
# Time a single request
time PYTHONPATH=mcp-server-python uv run python - <<'PY'
from tools.bulk_read_new_jobs import bulk_read_new_jobs
print(bulk_read_new_jobs({"limit": 50})["count"])
PY

# Test with different batch sizes
for limit in 10 50 100 500 1000; do
    echo "Testing with limit=$limit"
    time PYTHONPATH=mcp-server-python uv run python -c "
from tools.bulk_read_new_jobs import bulk_read_new_jobs
result = bulk_read_new_jobs({'limit': $limit})
print(f'Fetched {result[\"count\"]} jobs')
"
done
```

## Next Steps

- See [DEPLOYMENT.md](mcp-server-python/DEPLOYMENT.md) for production deployment
- See [README.md](mcp-server-python/README.md) for API documentation
- See [QUICKSTART.md](mcp-server-python/QUICKSTART.md) for quick setup guide
