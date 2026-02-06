# Deployment Guide - JobWorkFlow MCP Server

This guide covers deployment, configuration, and operational aspects of the JobWorkFlow MCP Server.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Server](#running-the-server)
5. [Deployment Scenarios](#deployment-scenarios)
6. [Logging and Debugging](#logging-and-debugging)
7. [Troubleshooting](#troubleshooting)
8. [Production Considerations](#production-considerations)

## Prerequisites

- Python 3.11 or higher
- SQLite database with jobs table
- Virtual environment (recommended)

## Installation

### 1. Clone or Navigate to Repository

```bash
cd /path/to/JobWorkFlow
```

### 2. Install Dependencies with uv

```bash
# From repository root
uv sync
```

This creates a virtual environment at `.venv/` in the repository root with all dependencies.

### 3. Verify Installation

```bash
source .venv/bin/activate
python -c "import mcp; print('MCP installed successfully')"
```

## Configuration

The server supports configuration via environment variables with sensible defaults.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JOBWORKFLOW_ROOT` | Root directory for JobWorkFlow data | Repository root |
| `JOBWORKFLOW_DB` | Database file path (absolute or relative) | `data/capture/jobs.db` |
| `JOBWORKFLOW_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `JOBWORKFLOW_LOG_FILE` | Log file path (enables file logging) | None (stderr only) |
| `JOBWORKFLOW_SERVER_NAME` | MCP server name | `jobworkflow-mcp-server` |

### Configuration Priority

The server resolves configuration in the following order (highest priority first):

1. **Explicit environment variables** (e.g., `JOBWORKFLOW_DB`)
2. **JOBWORKFLOW_ROOT-based paths** (e.g., `$JOBWORKFLOW_ROOT/data/capture/jobs.db`)
3. **Default paths** (relative to repository root)

### Database Path Resolution

The database path is resolved as follows:

1. If `JOBWORKFLOW_DB` is set:
   - Use as absolute path if it starts with `/`
   - Otherwise, resolve relative to repository root
2. If `JOBWORKFLOW_ROOT` is set:
   - Use `$JOBWORKFLOW_ROOT/data/capture/jobs.db`
3. Otherwise:
   - Use `<repo_root>/data/capture/jobs.db`

### Examples

#### Use Default Configuration

```bash
# Database at: <repo_root>/data/capture/jobs.db
# Logs to: stderr
# Log level: INFO
python server.py
```

#### Custom Database Path

```bash
# Absolute path
export JOBWORKFLOW_DB=/var/lib/jobworkflow/jobs.db
python server.py

# Relative path (from repo root)
export JOBWORKFLOW_DB=custom/path/jobs.db
python server.py
```

#### Enable Debug Logging to File

```bash
export JOBWORKFLOW_LOG_LEVEL=DEBUG
export JOBWORKFLOW_LOG_FILE=logs/server.log
python server.py
```

#### Use JOBWORKFLOW_ROOT

```bash
# All data under /opt/jobworkflow
export JOBWORKFLOW_ROOT=/opt/jobworkflow
# Database will be: /opt/jobworkflow/data/capture/jobs.db
python server.py
```

## Running the Server

### Method 1: Direct Python Execution

```bash
cd mcp-server-python
source ../.venv/bin/activate  # Activate root venv
python server.py
```

### Method 2: Startup Script (Recommended)

The startup script provides convenient configuration and validation:

```bash
cd mcp-server-python
./start_server.sh
```

#### Startup Script Options

```bash
# Show help
./start_server.sh --help

# Custom database path
./start_server.sh --db-path /path/to/jobs.db

# Debug logging to file
./start_server.sh --log-level DEBUG --log-file logs/server.log

# Combine options
./start_server.sh --db-path custom.db --log-level DEBUG --log-file debug.log
```

### Method 3: MCP Client Configuration

For use with MCP clients (e.g., Claude Desktop), add to your MCP configuration file.

**Location of MCP configuration:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Configuration example** (see `mcp-config-example.json`):

```json
{
  "mcpServers": {
    "jobworkflow": {
      "command": "/path/to/JobWorkFlow/.venv/bin/python",
      "args": ["/path/to/JobWorkFlow/mcp-server-python/server.py"],
      "env": {
        "JOBWORKFLOW_DB": "/path/to/jobs.db",
        "JOBWORKFLOW_LOG_LEVEL": "INFO",
        "JOBWORKFLOW_LOG_FILE": "/path/to/logs/server.log"
      }
    }
  }
}
```

**Important**: Use absolute paths in MCP client configurations.

## Deployment Scenarios

### Scenario 1: Development Environment

**Goal**: Quick setup for local development and testing.

```bash
# From repository root
uv sync

# Start server
cd mcp-server-python
./start_server.sh
```

### Scenario 2: Shared Development Server

**Goal**: Multiple developers accessing a shared database.

```bash
# Set shared database location
export JOBWORKFLOW_ROOT=/shared/jobworkflow
export JOBWORKFLOW_LOG_FILE=/shared/jobworkflow/logs/server-$(whoami).log

cd mcp-server-python
source ../.venv/bin/activate
./start_server.sh
```

### Scenario 3: Production Deployment

**Goal**: Stable production environment with logging and monitoring.

```bash
# Production configuration
export JOBWORKFLOW_ROOT=/opt/jobworkflow
export JOBWORKFLOW_LOG_LEVEL=WARNING
export JOBWORKFLOW_LOG_FILE=/var/log/jobworkflow/mcp-server.log

# Create necessary directories
mkdir -p /opt/jobworkflow/data/capture
mkdir -p /var/log/jobworkflow

# Install dependencies
cd /opt/jobworkflow
uv sync

# Start server (consider using systemd or supervisor)
cd mcp-server-python
source ../.venv/bin/activate
python server.py
```

### Scenario 4: Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY mcp-server-python/ ./mcp-server-python/

# Install dependencies
RUN uv sync --frozen

# Set default environment variables
ENV JOBWORKFLOW_DB=/data/jobs.db
ENV JOBWORKFLOW_LOG_LEVEL=INFO

# Run server
CMD [".venv/bin/python", "mcp-server-python/server.py"]
```

Build and run:

```bash
docker build -t jobworkflow-mcp-server .
docker run -v /path/to/data:/data jobworkflow-mcp-server
```

## Logging and Debugging

### Log Levels

- **DEBUG**: Detailed information for diagnosing problems
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages for potentially problematic situations
- **ERROR**: Error messages for serious problems

### Enable Debug Logging

```bash
export JOBWORKFLOW_LOG_LEVEL=DEBUG
./start_server.sh
```

### Log to File

```bash
export JOBWORKFLOW_LOG_FILE=logs/server.log
./start_server.sh
```

### Log Format

Logs include timestamp, logger name, level, and message:

```
2024-02-04 10:30:15 - __main__ - INFO - Starting JobWorkFlow MCP Server
2024-02-04 10:30:15 - __main__ - INFO - Database path: /path/to/jobs.db
2024-02-04 10:30:15 - __main__ - INFO - Server starting in stdio mode
```

### Debugging Tips

1. **Enable DEBUG logging** to see detailed operation flow
2. **Check database path** in startup logs to verify correct location
3. **Review validation warnings** for configuration issues
4. **Monitor log file** for errors during operation
5. **Test database access** independently before starting server

## Troubleshooting

### Database Not Found

**Symptom**: Error message "Database file not found"

**Solutions**:
1. Verify database path: `echo $JOBWORKFLOW_DB`
2. Check file exists: `ls -l $JOBWORKFLOW_DB`
3. Verify permissions: `ls -l $(dirname $JOBWORKFLOW_DB)`
4. Use absolute path: `export JOBWORKFLOW_DB=/absolute/path/to/jobs.db`

### Permission Denied

**Symptom**: Cannot read database or write logs

**Solutions**:
1. Check file permissions: `ls -l /path/to/jobs.db`
2. Verify user has read access to database
3. Verify user has write access to log directory
4. Use appropriate user/group: `chown user:group /path/to/jobs.db`

### Import Errors

**Symptom**: "ModuleNotFoundError" or "ImportError"

**Solutions**:
1. Activate virtual environment: `source .venv/bin/activate` (from repository root)
2. Reinstall dependencies: `uv sync`
3. Verify Python version: `python --version` (should be 3.11+)
4. Check PYTHONPATH if running from different directory

### Server Not Responding

**Symptom**: Server starts but doesn't respond to requests

**Solutions**:
1. Verify server is running in stdio mode (default)
2. Check logs for errors: `tail -f $JOBWORKFLOW_LOG_FILE`
3. Test database connection independently
4. Verify MCP client configuration
5. Check for port conflicts if using network transport

### Empty Results

**Symptom**: Tool returns empty job list when jobs exist

**Solutions**:
1. Verify jobs have `status='new'` in database
2. Check database path is correct
3. Query database directly: `sqlite3 jobs.db "SELECT COUNT(*) FROM jobs WHERE status='new'"`
4. Enable DEBUG logging to see query execution

## Production Considerations

### 1. Process Management

Use a process manager to keep the server running:

**systemd** (Linux):

```ini
[Unit]
Description=JobWorkFlow MCP Server
After=network.target

[Service]
Type=simple
User=jobworkflow
WorkingDirectory=/opt/jobworkflow/mcp-server-python
Environment="JOBWORKFLOW_ROOT=/opt/jobworkflow"
Environment="JOBWORKFLOW_LOG_LEVEL=WARNING"
Environment="JOBWORKFLOW_LOG_FILE=/var/log/jobworkflow/server.log"
ExecStart=/opt/jobworkflow/.venv/bin/python server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**supervisor** (Cross-platform):

```ini
[program:jobworkflow-mcp]
command=/opt/jobworkflow/.venv/bin/python server.py
directory=/opt/jobworkflow/mcp-server-python
environment=JOBWORKFLOW_ROOT="/opt/jobworkflow",JOBWORKFLOW_LOG_LEVEL="WARNING"
user=jobworkflow
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/jobworkflow/server.log
```

### 2. Log Rotation

Configure log rotation to prevent disk space issues:

```bash
# /etc/logrotate.d/jobworkflow
/var/log/jobworkflow/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 jobworkflow jobworkflow
}
```

### 3. Monitoring

Monitor server health:

1. **Process monitoring**: Ensure server process is running
2. **Log monitoring**: Watch for ERROR level messages
3. **Database monitoring**: Check database file size and accessibility
4. **Performance monitoring**: Track response times and memory usage

### 4. Security

1. **Read-only database access**: Server opens database in read-only mode
2. **File permissions**: Restrict database and log file access
3. **User isolation**: Run server as dedicated user with minimal privileges
4. **Network isolation**: Use stdio transport (no network exposure)
5. **Input validation**: All inputs are validated before processing

### 5. Backup and Recovery

1. **Database backups**: Regular backups of jobs.db
2. **Configuration backups**: Document environment variables
3. **Recovery procedures**: Test restoration process
4. **Disaster recovery**: Plan for database corruption or loss

### 6. Performance Tuning

1. **Batch size**: Default 50 jobs per page (configurable via tool parameter)
2. **Database optimization**: Ensure indexes on `status`, `captured_at`, `id`
3. **Connection pooling**: Not needed (read-only, short-lived connections)
4. **Memory limits**: Monitor memory usage with large result sets

## Testing Deployment

### 1. Verify Installation

```bash
cd mcp-server-python
source ../.venv/bin/activate
python -c "from tools.bulk_read_new_jobs import bulk_read_new_jobs; print('OK')"
```

### 2. Test Configuration

```bash
python -c "from config import get_config; c = get_config(); print(f'DB: {c.db_path}')"
```

### 3. Run Test Suite

```bash
# From repository root
uv run pytest mcp-server-python/tests/ -v

# Or from mcp-server-python/ with activated venv
source ../.venv/bin/activate
pytest tests/ -v
```

### 4. Test Server Startup

```bash
./start_server.sh &
sleep 2
kill %1  # Stop background server
```

### 5. Integration Test

Create a test script to invoke the tool through MCP protocol.

## Support and Maintenance

### Regular Maintenance Tasks

1. **Update dependencies**: `uv sync --upgrade`
2. **Review logs**: Check for warnings or errors
3. **Monitor disk space**: Ensure adequate space for database and logs
4. **Test backups**: Verify backup and restore procedures
5. **Update documentation**: Keep deployment docs current

### Getting Help

1. Check logs for error messages
2. Review troubleshooting section
3. Verify configuration with `config.validate()`
4. Test database access independently
5. Consult project documentation

## Summary

The JobWorkFlow MCP Server is designed for easy deployment with:

- **Flexible configuration** via environment variables
- **Sensible defaults** for quick setup
- **Comprehensive logging** for debugging
- **Production-ready** error handling and validation
- **Multiple deployment options** (direct, script, Docker, systemd)

For most use cases, the startup script provides the easiest deployment method:

```bash
./start_server.sh --log-level INFO --log-file logs/server.log
```
