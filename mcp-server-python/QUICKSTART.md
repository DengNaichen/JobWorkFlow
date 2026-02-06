# Quick Start Guide

Get the JobWorkFlow MCP Server running in 5 minutes.

## 1. Install Dependencies

```bash
# From repository root
uv sync
```

This will install all dependencies (MCP server + jobspy) into `.venv/` at the repository root.

## 2. Start the Server

### Option A: Use the Startup Script (Recommended)

```bash
cd mcp-server-python
./start_server.sh
```

### Option B: Direct Python Execution

```bash
cd mcp-server-python
source ../.venv/bin/activate  # Activate root venv
python server.py
```

## 3. Verify It's Working

The server will display startup information:

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

Starting MCP server...
Press Ctrl+C to stop
```

## Common Configurations

### Development with Debug Logging

```bash
./start_server.sh --log-level DEBUG --log-file logs/dev.log
```

### Custom Database Location

```bash
./start_server.sh --db-path /path/to/custom/jobs.db
```

### Using Environment Variables

```bash
export JOBWORKFLOW_DB=/path/to/jobs.db
export JOBWORKFLOW_LOG_LEVEL=DEBUG
./start_server.sh
```

## Testing the Installation

Run the test suite to verify everything works:

```bash
# From repository root
uv run pytest mcp-server-python/tests/ -v

# Or activate venv first
source .venv/bin/activate
cd mcp-server-python
pytest tests/ -v
```

## Next Steps

- **Configuration**: See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed configuration options
- **Usage**: See [README.md](README.md) for tool usage examples
- **Troubleshooting**: See [DEPLOYMENT.md](DEPLOYMENT.md#troubleshooting) for common issues

## Need Help?

1. Check that the database file exists at the configured path
2. Verify Python version is 3.11 or higher: `python --version`
3. Ensure virtual environment is activated
4. Review logs for error messages
5. See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed troubleshooting

## Stopping the Server

Press `Ctrl+C` to stop the server gracefully.
