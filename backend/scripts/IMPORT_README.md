Import combined_text2 into Neo4j
===============================

This script imports the `ece-core/combined_text2.txt` JSON array into Neo4j as Memory nodes.

Usage
-----
Run a dry-run to preview how many items would be inserted and what tags/metadata will be set:

```pwsh
python ece-core/scripts/import_combined_text2.py --dry-run
```

Commit changes to Neo4j (make sure Neo4j is running and configured in `src/config`):

```pwsh
python ece-core/scripts/import_combined_text2.py --commit
```

Options
-------
- `--include-thinking` — Include `thinking_content` entries (skipped by default to avoid contamination)
- `--no-dedupe` — Disable deduplication by content hash (by default duplicates are avoided)
- `--session-id` — Set the session ID to attach to memory nodes
- `--file` — Path to the JSON file to import

Notes
-----
- The script marks `metadata.committed` when performing an insert with `--commit`.
- The script will attempt to detect Neo4j availability and run in dry-run mode if it can't connect.
- Always prefer to run as a dry-run first and inspect the results.
