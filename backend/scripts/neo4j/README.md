# Neo4j-related Scripts

This folder contains Neo4j migration, repair, verification and indexing tools organized by concept.

Structure:
- `migrate/` - Data migration scripts that modify existing Memory nodes or the schema (assign `app_id`, seeding, post-import verification)
- `repair/` - Repair and heuristic fixes (timestamp heuristics, similarity heuristics, rollback/undo utilities)
- `verify/` - Verification scripts to ensure auditability and correctness (verify commits, DB health checks)
- `maintenance/` - One-time fixup utilities and maintenance tools (index creation, metadata fixes)
- `indexing/` - Scripts for indexing Neo4j content into vector DBs (bulk indexing)

Compatibility:
To preserve backwards compatibility with older scripts that used `scripts/<name>.py`, the top level `scripts/` directory contains small shims that re-export functions or act as passthrough to the organized locations. This keeps existing CI, docs, and developer habits functional while we move to a cleaner structure.

Examples:
- Migration (dry-run):
```pwsh
python .\scripts\neo4j\migrate\assign_app_id_to_nodes.py --limit 100
```
- Repair (dry-run):
```pwsh
python .\scripts\neo4j\repair\repair_missing_links_similarity_embeddings.py --dry-run --csv-out weaver_dry_run.csv --limit 100
```
- Verify & Rollback (dry-run):
```pwsh
python .\scripts\neo4j\verify\verify_committed_relationships.py --run-id <RUN_ID>
python .\scripts\neo4j\repair\rollback_commits_by_run.py --run-id <RUN_ID> --confirm
```

If you'd like, I can:
- Move remaining Neo4j-related scripts into these folders
- Add a 'scripts/neo4j/safe_admin.sh' wrapper to orchestrate dry-run > audit > stage > commit flows
- Add a 'scripts/neo4j/diagnostics' subfolder to hold CSV analysis and auditing helpers
