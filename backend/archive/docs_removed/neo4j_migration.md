````markdown
# Neo4j Integration & Migration (Archived)

This document describes the Neo4j migration and embedded setup used during development. The migration process and scripts were preserved here for historical reference. Current guidance is consolidated in `specs/spec.md` and operation/debug info is in `specs/TROUBLESHOOTING.md`.

Key artifacts archived:
- `migrate_to_neo4j_phase1.py` (SQLite → Neo4j)
- `migrate_to_neo4j_phase2.py` (Entity extraction)
- `migrate_to_neo4j_phase3.py` (Entity relationships)
- `initialize_neo4j_schema.py` - Schema initialization script
- `migrate_sqlite_to_neo4j.py` - Full migration script

For operational queries and Cypher references, still consult `specs/TROUBLESHOOTING.md` and `specs/spec.md`.
````
