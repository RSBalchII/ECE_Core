#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
ARCHIVE_DIR="$REPO_ROOT/archive/startup-scripts"
mkdir -p "$ARCHIVE_DIR"
echo "Scanning for root-level wrappers that should be archived..."
COUNT=0
for f in "$REPO_ROOT"/start-*.* ; do
  [ -e "$f" ] || continue
  fname="$(basename "$f")"
  # Check if the wrapper calls a canonical script in scripts/dev
  if grep -q "scripts/dev/start-" "$f" 2>/dev/null; then
    echo " - Will archive: $fname (calls canonical scripts)"
    ((COUNT++))
  else
    echo " - Skipping (likely not a thin wrapper): $fname"
  fi
done
if [ $COUNT -eq 0 ]; then
  echo "No root wrappers identified to archive."
  exit 0
fi
read -p "Archive $COUNT files to $ARCHIVE_DIR? [y/N] " answer
if [[ "$answer" =~ ^[Yy] ]]; then
  for f in "$REPO_ROOT"/start-*.* ; do
    [ -e "$f" ] || continue
    if grep -q "scripts/dev/start-" "$f" 2>/dev/null; then
      echo "Archiving $(basename "$f") -> $ARCHIVE_DIR"
      mv "$f" "$ARCHIVE_DIR/"
    fi
  done
  echo "Archived $COUNT wrappers to $ARCHIVE_DIR"
else
  echo "No files moved. Exiting."
fi
exit 0
