"""
LEGACY: SQLite-dependent archival script.

This file is part of the archived/legacy SQLite toolset maintained for migration
and historical purposes. SQLite has been deprecated for active ECE_Core usage in
favor of Neo4j (graph backend). Do NOT use these scripts in a production context.

To re-enable or run legacy SQLite tooling:
 - Install the legacy dependency: `pip install aiosqlite`
 - Set the environment variable `ECE_ALLOW_LEGACY_SQLITE=1` if you must run these
 - Use in a safe, isolated environment only for migration or debugging

See `ece-core/archive/legacy_sqlite/README.md` for details.
"""

"""
Legacy: import_combined_context.py relying on SQLite; moved from TODO/ to archive/legacy_sqlite.
This file is kept for archival reasons only and is not part of the active code base.
"""

import aiosqlite

class LegacyImportCombinedContext:
    pass
