#!/usr/bin/env bash
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.nd.jobworkflow.jobspy.plist"
LOG_DIR="/Users/nd/Developer/JobWorkFlow/logs"

if [ -f "$PLIST" ]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  echo "Removed launchd job: $PLIST"
else
  echo "No launchd job found at: $PLIST"
fi

if [ -d "$LOG_DIR" ]; then
  rm -f "$LOG_DIR/jobspy_batch_run.out.log" "$LOG_DIR/jobspy_batch_run.err.log"
  echo "Removed logs in: $LOG_DIR"
fi
