#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export JOBWORKFLOW_ROOT="${JOBWORKFLOW_ROOT:-$REPO_ROOT}"
exec "$REPO_ROOT/mcp-server-python/start_server.sh" "$@"
