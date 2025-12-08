#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Validating canonical startup scripts under $ROOT_DIR"
COUNTER=0
for f in $(ls "$ROOT_DIR"); do
  if [[ "$f" =~ ^start-.*\.(sh|bat)$ ]]; then
    COUNTER=$((COUNTER+1))
    echo " - Found canonical script: $f"
  fi
done
if [ $COUNTER -eq 0 ]; then
  echo "No startup scripts found under $ROOT_DIR"
  exit 2
fi
echo "Checked $COUNTER scripts; those are canonical startup scripts."

# Validate that root wrappers (if present) are thin wrappers pointing to canonical scripts
ROOT_WRAPPER_COUNT=0
for f in "$REPO_ROOT"/start-*.* ; do
  [ -e "$f" ] || continue
  fname="$(basename "$f")"
  if grep -q "scripts/dev/start-" "$f" 2>/dev/null; then
    echo " - Root wrapper calls canonical script: $fname"
    ROOT_WRAPPER_COUNT=$((ROOT_WRAPPER_COUNT+1))
  else
    echo " - Root wrapper (NOT pointing to canonical script): $fname (please re-evaluate)"
  fi
done
echo "Root wrapper summary: $ROOT_WRAPPER_COUNT wrappers call canonical scripts in scripts/dev/"
echo "Checked $COUNTER scripts; those are canonical startup scripts."
echo "Run these from the repo root or use the root wrappers in the repo root."
exit 0
