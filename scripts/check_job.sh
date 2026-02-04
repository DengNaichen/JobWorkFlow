#!/bin/bash

# check_job.sh: Check if a job URL or Company+Position has already been tracked.
# Usage: ./check_job.sh "https://linkedin.com/jobs/view/12345" "Company Name" "Position Name"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TRACKERS_DIR="${TRACKERS_DIR:-$REPO_ROOT/trackers}"
URL=$1
COMPANY=$2
POSITION=$3

# 1. Check by URL (most reliable)
if grep -rl "$URL" "$TRACKERS_DIR" > /dev/null; then
    echo "EXISTS: Job URL already found in trackers."
    exit 0
fi

# 2. Check by Company + Position (case insensitive)
# We search for lines like 'company: Company Name' and 'position: Position Name' in the same file
FILES=$(grep -il "company: $COMPANY" "$TRACKERS_DIR"/*.md 2>/dev/null)

for FILE in $FILES; do
    if grep -iq "position: $POSITION" "$FILE"; then
        echo "EXISTS: Company and Position combination already found in $FILE."
        exit 0
    fi
done

echo "NEW: No matching job found."
exit 1
