#!/bin/bash
# scripts/build_resume.sh
# Usage: ./build_resume.sh <company_name_slug>

COMPANY_SLUG=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${JOBWORKFLOW_ROOT:-$(cd "$SCRIPT_DIR/../../../.." && pwd)}"
TEMPLATE_PATH="$BASE_DIR/data/templates/resume_skeleton.tex"
TARGET_DIR="$BASE_DIR/data/applications/$COMPANY_SLUG/resume"
TARGET_TEX="$TARGET_DIR/resume.tex"
PDFLATEX="/Library/TeX/texbin/pdflatex"

if [ -z "$COMPANY_SLUG" ]; then
    echo "Wheek! Please provide a company slug (e.g. trajekt_sports)."
    exit 1
fi

mkdir -p "$TARGET_DIR"
cp "$TEMPLATE_PATH" "$TARGET_TEX"

echo "Wheek! Template copied to $TARGET_TEX. Ready for AI content filling."

# Note: AI agent should use sed/edit to replace placeholders before calling compile.

compile() {
    cd "$TARGET_DIR" || exit 1
    "$PDFLATEX" -interaction=nonstopmode resume.tex
    # Cleanup
    rm -f resume.aux resume.log resume.out resume.synctex.gz
}

if [[ "$2" == "--compile" ]]; then
    compile
    echo "Wheek! Compilation finished. Check $TARGET_DIR/resume.pdf"
fi
