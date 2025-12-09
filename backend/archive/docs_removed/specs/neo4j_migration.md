ARCHIVED: This migration guide has been archived at the project's request. The canonical migration details and active retrieval strategy now rely on Neo4j + Redis and are documented in `specs/spec.md` and `specs/TROUBLESHOOTING.md`.

If you need to review migration steps for historical purposes, see this archived file in `ece-core/archive/docs_removed/specs/neo4j_migration.md`.
<!-- ARCHIVED: This document was moved as part of documentation consolidation. See specs/doc_policy.md for active doc list. -->

<!-- Original content preserved for historical reference -->

````markdown
<!-- ARCHIVED: Full content moved to archive/docs_removed/neo4j_migration.md -->
[](archive/docs_removed/neo4j_migration.md)

---

## Current State

**Memory Architecture:**
```
Redis (hot cache) → SQLite (warm storage) → Neo4j (graph database)
```

<!-- Content preserved, trimmed for archival reference -->

---

**Last Updated:** 2025-11-12

<!-- End archived content -->
````
