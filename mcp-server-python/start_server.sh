#!/bin/bash
#
# Startup script for JobWorkFlow MCP Server
#
# This script provides a convenient way to start the MCP server with
# proper environment configuration and error handling.
#
# Usage:
#   ./start_server.sh [options]
#
# Options:
#   --db-path PATH       Override database path
#   --log-level LEVEL    Set log level (DEBUG, INFO, WARNING, ERROR)
#   --log-file PATH      Enable file logging to specified path
#   --help               Show this help message
#

set -e  # Exit on error

# Script directory (mcp-server-python/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Repository root (parent of mcp-server-python/)
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
DEFAULT_DB_PATH="$REPO_ROOT/data/capture/jobs.db"
DEFAULT_LOG_LEVEL="INFO"

# Parse command line arguments
DB_PATH=""
LOG_LEVEL=""
LOG_FILE=""

show_help() {
    cat << EOF
JobWorkFlow MCP Server Startup Script

Usage: $0 [options]

Options:
  --db-path PATH       Override database path (default: data/capture/jobs.db)
  --log-level LEVEL    Set log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --log-file PATH      Enable file logging to specified path
  --help               Show this help message

Environment Variables:
  JOBWORKFLOW_ROOT     Root directory for JobWorkFlow data (overrides default paths)
  JOBWORKFLOW_DB       Database path (overrides --db-path and default)
  JOBWORKFLOW_LOG_LEVEL    Log level (overrides --log-level)
  JOBWORKFLOW_LOG_FILE     Log file path (overrides --log-file)

Examples:
  # Start with defaults
  $0

  # Start with custom database path
  $0 --db-path /path/to/jobs.db

  # Start with debug logging to file
  $0 --log-level DEBUG --log-file logs/server.log

  # Start with JOBWORKFLOW_ROOT environment variable
  JOBWORKFLOW_ROOT=/path/to/jobworkflow $0

EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --db-path)
            DB_PATH="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set environment variables from command line arguments (if not already set)
if [ -n "$DB_PATH" ] && [ -z "$JOBWORKFLOW_DB" ]; then
    export JOBWORKFLOW_DB="$DB_PATH"
fi

if [ -n "$LOG_LEVEL" ] && [ -z "$JOBWORKFLOW_LOG_LEVEL" ]; then
    export JOBWORKFLOW_LOG_LEVEL="$LOG_LEVEL"
fi

if [ -n "$LOG_FILE" ] && [ -z "$JOBWORKFLOW_LOG_FILE" ]; then
    export JOBWORKFLOW_LOG_FILE="$LOG_FILE"
fi

# Display configuration
echo "=========================================="
echo "JobWorkFlow MCP Server"
echo "=========================================="
echo "Repository root: $REPO_ROOT"
echo "Server directory: $SCRIPT_DIR"
echo ""
echo "Configuration:"
echo "  Database: ${JOBWORKFLOW_DB:-$DEFAULT_DB_PATH}"
echo "  Log level: ${JOBWORKFLOW_LOG_LEVEL:-$DEFAULT_LOG_LEVEL}"
if [ -n "$JOBWORKFLOW_LOG_FILE" ]; then
    echo "  Log file: $JOBWORKFLOW_LOG_FILE"
else
    echo "  Log file: (stderr only)"
fi
echo "=========================================="
echo ""

# Check if virtual environment exists at root
if [ ! -d "$REPO_ROOT/.venv" ]; then
    echo "Warning: Virtual environment not found at repository root."
    echo "Please run from repository root: uv sync"
    echo ""
fi

# Activate virtual environment if it exists at root
if [ -d "$REPO_ROOT/.venv" ]; then
    echo "Activating virtual environment: $REPO_ROOT/.venv/"
    source "$REPO_ROOT/.venv/bin/activate"
fi

# Check if database exists (warning only, not fatal)
DB_CHECK="${JOBWORKFLOW_DB:-$DEFAULT_DB_PATH}"
if [ ! -f "$DB_CHECK" ]; then
    echo "Warning: Database file not found: $DB_CHECK"
    echo "The server will start but tools will fail until the database is created."
    echo ""
fi

# Change to server directory
cd "$SCRIPT_DIR"

# Start the server
echo "Starting MCP server..."
echo "Press Ctrl+C to stop"
echo ""

exec python server.py
