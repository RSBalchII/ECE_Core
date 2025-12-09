# Legacy SQLite Tools (Archived)

This folder contains archived legacy tools and importers that reference SQLite (e.g., `aiosqlite`). These scripts are maintained for historical reference and for migration purposes only. They are not part of the active ECE_Core runtime and should not be used for production workloads.

Why retain these files?
- Migration: They help migrate older `ece_memory.db` SQLite content into the new Neo4j knowledge graph.
- Debugging / Repro: They provide a historical trace if we need to re-run or re-evaluate previous import behavior.

Safety guidelines
1. ALWAYS backup production data before running legacy scripts.
2. These scripts frequently use `aiosqlite` (install via `pip install aiosqlite`).
3. In order to avoid accidental execution in active deployments: set the environment variable `ECE_ALLOW_LEGACY_SQLITE=1` before running these utilities.
4. Run in a staging or local environment, not on production DBs.
5. Prefer Neo4j importers and CSV/JSONL imports where possible; these are present outside the legacy folder and are the recommended path.

How to re-enable legacy SQLite scripts
1. Set up a Python virtual environment.
2. Install the optional dependency: `pip install aiosqlite`.
3. Set environment variable: `setx ECE_ALLOW_LEGACY_SQLITE 1` (Windows) or `export ECE_ALLOW_LEGACY_SQLITE=1` (POSIX).
4. Run the script in a staging environment only and follow migration steps.

Typical scripts in this folder
- `extract_entities.py` - Extract entity table rows and optionally link to Neo4j.
- `import_combined_context.py` - Import combined_text into SQLite for legacy imports.

Migration note
- Most data has already been migrated to Neo4j (2025-11-13). These scripts remain to re-run or verify the migration steps.
- Where possible use `migrate_to_neo4j_phase1.py` and the Neo4j importers in `src/data_pipeline` for current usage.

Contact/Support
If you require assistance with running a migration or dealing with legacy SQLite content, please file an issue and provide the exact path of the file you want to re-run and a short description of your goal.