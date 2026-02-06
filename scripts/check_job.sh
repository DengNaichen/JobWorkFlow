#!/bin/bash
set -euo pipefail

# check_job.sh: Check if a job URL or Company+Position has already been tracked.
# Usage: ./check_job.sh "https://linkedin.com/jobs/view/12345" "Company Name" "Position Name"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TRACKERS_DIR="${TRACKERS_DIR:-$REPO_ROOT/trackers}"

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 \"<url>\" \"<company>\" \"<position>\"" >&2
    exit 2
fi

URL=$1
COMPANY=$2
POSITION=$3

# 1. Check by URL (most reliable)
if grep -rFl -- "$URL" "$TRACKERS_DIR" > /dev/null; then
    echo "EXISTS: Job URL already found in trackers."
    exit 0
fi

# 2. Check by Company + Position (case insensitive)
# We scan markdown files safely with null-delimited paths to support spaces.
while IFS= read -r -d '' FILE; do
    if grep -qiF -- "company: $COMPANY" "$FILE" && grep -qiF -- "position: $POSITION" "$FILE"; then
        echo "EXISTS: Company and Position combination already found in $FILE."
        exit 0
    fi
done < <(find "$TRACKERS_DIR" -type f -name '*.md' -print0 2>/dev/null)

echo "NEW: No matching job found."
exit 1
