# Standard 020: Ephemeral Database Architecture

**Status:** Active  
**Date:** 2026-03-23  
**Supersedes:** Standard 012 (partial - DATA-001)  
**Related:** Standard 007 (PGlite Memory Optimization), Standard 012 (Data Integrity)

## Context

Anchor Engine uses PGlite (WASM PostgreSQL) as an **ephemeral index database**. Unlike traditional databases that persist state across restarts, the Anchor Engine database is designed to be wiped and rebuilt on every startup. This is an intentional architectural decision, not a limitation.

### The Problem: PGlite Corruption

PGlite runs PostgreSQL inside a WebAssembly (WASM) module. While this provides excellent portability, it has specific failure modes:

1. **Unclean Shutdown Corruption**: If the process is killed (SIGKILL, crash, power loss) during a write operation, the database files can become corrupted
2. **WASM Heap Corruption**: Under memory pressure or with large result sets, the WASM heap can become corrupted, causing all subsequent queries to fail
3. **Silent Write Failures**: Database writes may appear to succeed but fail silently, leaving the index in an inconsistent state
4. **Hanging Ingestion**: A corrupted database can cause ingestion to hang indefinitely without error messages

### The Solution: Source of Truth Pattern

The Anchor Engine uses a **source of truth** architecture:

| Component | Role | Persistence |
|-----------|------|-------------|
| `inbox/` | **Source of Truth** | Permanent - never deleted |
| `external-inbox/` | **Source of Truth** | Permanent - never deleted |
| `mirrored_brain/` | Rebuildable Cache | Wiped on startup |
| PGlite Database | Ephemeral Index | Wiped on startup |

**Key Principle:** The database is a disposable cache. The filesystem (`inbox/`, `external-inbox/`) is the only source of truth.

---

## Requirements

### EPH-001: Always Wipe Database on Startup

**Default Configuration:**
```json
{
  "database": {
    "wipe_on_startup": true
  }
}
```

**Implementation in `engine/src/core/db.ts`:**
```typescript
// Wipe and recreate the database directory on every startup
const shouldWipe = config.DATABASE?.WIPE_ON_STARTUP !== false;

if (shouldWipe) {
  // Remove existing database directory to prevent corruption from unclean shutdowns
  if (fs.existsSync(dbPath)) {
    console.log(`[DB] Removing existing database directory: ${dbPath}`);
    fs.rmSync(dbPath, { recursive: true, force: true });
  }
}
```

**Why this matters:**
- Prevents corruption accumulation from previous crashes
- Ensures a clean, consistent state on every startup
- Eliminates "ghost" data from failed transactions
- Prevents the "hanging ingestion" bug where the engine appears healthy but can't ingest

### EPH-002: Always Wipe mirrored_brain on Startup

The `mirrored_brain/` directory is a **rebuildable cache** of cleaned content, not a source of truth.

**Implementation:**
```typescript
// Also wipe mirrored_brain to prevent corrupted files from accumulating
const mirroredBrainPath = path.join(path.dirname(dbPath), 'mirrored_brain');
if (fs.existsSync(mirroredBrainPath)) {
  console.log('[DB] Clearing mirrored_brain directory (regenerated from inbox on start)');
  const entries = fs.readdirSync(mirroredBrainPath);
  for (const entry of entries) {
    fs.rmSync(path.join(mirroredBrainPath, entry), { recursive: true, force: true });
  }
}
```

**Why this matters:**
- `mirrored_brain/` can accumulate corrupted files from crashes
- It is regenerated from `inbox/` on every startup anyway
- Wiping prevents "stale cache" issues

### EPH-003: Rebuild from inbox/ on Every Restart

After wiping, the database must be rebuilt from the source of truth:

```
Startup Sequence:
1. Wipe PGlite database directory
2. Wipe mirrored_brain/ directory  
3. Initialize fresh PGlite instance
4. Run Mirror Protocol to populate mirrored_brain/ from inbox/ + external-inbox/
5. Ingest mirrored_brain/ contents into PGlite index
6. Start accepting queries
```

**Console output on startup:**
```
[DB] Removing existing database directory (preventing corruption): /path/to/db
[DB] Old database directory removed successfully
[DB] Clearing mirrored_brain directory (regenerated from inbox on start)
[DB] mirrored_brain cleared (42 entries removed)
[Startup] Regenerating mirrored_brain/ from inbox/ (Standard 110)...
[Mirror] Processed 150 files from inbox/
[Ingest] Indexed 12,847 atoms from mirrored_brain/
```

### EPH-004: inbox/ is the Source of Truth

**Critical Rule:** Never delete or modify `inbox/` or `external-inbox/` files directly.

These directories contain:
- Raw ingested content (JSONL format)
- Chat history exports
- External data imports
- Git repository snapshots

**To "delete" data:**
1. Remove the file from `inbox/` or `external-inbox/`
2. Restart the engine
3. The database will rebuild without that content

**To "update" data:**
1. Add the updated file to `inbox/` with a new timestamp
2. Restart the engine
3. Both versions will exist; use search filters to distinguish

### EPH-005: Proper Shutdown Procedure

To ensure clean shutdown and prevent corruption:

**Preferred: Graceful Shutdown**
```bash
# Send SIGTERM (graceful shutdown)
pkill -TERM -f "anchor-engine"

# Or use the shutdown endpoint
curl -X POST http://localhost:3160/v1/system/shutdown
```

**If Graceful Shutdown Fails:**
```bash
# Check if engine is responsive
curl http://localhost:3160/health

# If unresponsive, check for hanging ingestion
curl http://localhost:3160/v1/ingest/status

# Force kill only as last resort
pkill -9 -f "anchor-engine"
```

**After Force Kill:**
1. The database will be wiped on next startup (automatic)
2. The engine will rebuild from `inbox/` (automatic)
3. No data loss occurs (source of truth is preserved)

---

## Anti-Patterns

### ❌ NEVER: Set `wipe_on_startup: false` for "Performance"

```json
// DON'T DO THIS
{
  "database": {
    "wipe_on_startup": false  // ❌ Risks corruption
  }
}
```

**Why this fails:**
- Corruption from previous crashes accumulates
- Silent write failures go undetected
- Eventually the database becomes unusable
- "Hanging ingestion" bug appears
- Requires manual intervention to fix

### ❌ NEVER: Treat mirrored_brain/ as Source of Truth

```bash
# DON'T DO THIS
cp important-file.txt mirrored_brain/  # ❌ Will be deleted on startup
```

**Correct approach:**
```bash
# DO THIS
cp important-file.txt inbox/  # ✅ Permanent storage
```

### ❌ NEVER: Manually Delete Database Files

```bash
# DON'T DO THIS
rm -rf engine/context_data/*.db  # ❌ Unnecessary - engine handles this
```

**Correct approach:**
```bash
# DO THIS
# Just restart the engine - it will wipe and rebuild automatically
pnpm restart
```

---

## Operational Guidelines

### Startup Checklist

```bash
# 1. Verify wipe_on_startup is true (default)
grep "wipe_on_startup" user_settings.json
# Expected: "wipe_on_startup": true

# 2. Start the engine
pnpm start

# 3. Watch for startup messages:
# [DB] Removing existing database directory...
# [DB] Clearing mirrored_brain directory...
# [Startup] Regenerating mirrored_brain/ from inbox/...

# 4. Verify health
curl http://localhost:3160/health
```

### Recovery from Corruption

**Symptoms of Database Corruption:**
- Ingestion hangs indefinitely
- Search returns empty results despite data existing
- `/health` shows healthy but operations fail
- Error messages about "database not initialized"
- WASM heap errors in logs

**Recovery Steps:**
```bash
# 1. Force kill if hanging
pkill -9 -f "anchor-engine"

# 2. Verify inbox/ is intact (source of truth)
ls -la local-data/inbox/
ls -la local-data/external-inbox/

# 3. Restart (automatic wipe and rebuild)
pnpm start

# 4. Monitor rebuild progress
curl http://localhost:3160/v1/ingest/status
tail -f engine/logs/server.log
```

### Backup Strategy

**What to Back Up:**
```bash
# Source of truth - BACKUP THESE
local-data/inbox/
local-data/external-inbox/
user_settings.json

# Optional - can be regenerated
mirrored_brain/  # Rebuilt from inbox/
distills/        # Can be regenerated
```

**Backup Script:**
```bash
#!/bin/bash
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

cp -r local-data/inbox "$BACKUP_DIR/"
cp -r local-data/external-inbox "$BACKUP_DIR/"
cp user_settings.json "$BACKUP_DIR/"

echo "Backup complete: $BACKUP_DIR"
```

**Restore from Backup:**
```bash
# 1. Stop engine
pnpm stop

# 2. Restore source of truth
rm -rf local-data/inbox/*
cp -r backups/20260323_120000/inbox/* local-data/inbox/

# 3. Restart (automatic rebuild)
pnpm start
```

---

## Configuration Reference

### user_settings.json

```json
{
  "database": {
    "wipe_on_startup": true
  }
}
```

| Value | Behavior | Use Case |
|-------|----------|----------|
| `true` | Wipe and rebuild on every startup | **Default - always use this** |
| `false` | Retain database across restarts | ⚠️ Only for debugging - not recommended |

### Environment Variables

```bash
# Override database path (optional)
export PGLITE_DB_PATH=/custom/path/to/db

# Force wipe regardless of settings (emergency)
export ANCHOR_FORCE_WIPE=true
```

---

## Troubleshooting

### Issue: "Ingestion Hangs Indefinitely"

**Cause:** Database corruption from previous unclean shutdown

**Solution:**
```bash
# Force kill and restart
pkill -9 -f "anchor-engine"
pnpm start
```

### Issue: "Database Not Initialized" Error

**Cause:** PGlite failed to initialize due to corrupted files

**Solution:**
```bash
# Manual wipe (engine will recreate)
rm -rf local-data/context_data
cp -r local-data/inbox local-data/inbox.backup  # Safety
cp -r local-data/external-inbox local-data/external-inbox.backup  # Safety
pnpm start
```

### Issue: "WASM Heap Corruption" Error

**Cause:** Memory pressure or large query results corrupted WASM heap

**Solution:**
```bash
# Restart with lower memory limits
export NODE_OPTIONS="--max-old-space-size=2048"
pnpm start
```

### Issue: "Missing Data After Restart"

**Cause:** Files were placed in mirrored_brain/ instead of inbox/

**Solution:**
```bash
# Move files to correct location
mv local-data/mirrored_brain/@inbox/myfile.jsonl local-data/inbox/
pnpm restart
```

---

## Decision Record

**Problem:** PGlite database corruption causes ingestion hangs, silent failures, and requires manual intervention.

**Solution:** Treat the database as ephemeral - wipe and rebuild from filesystem source of truth on every startup.

**Rationale:**
1. **Reliability over Performance**: A slow, reliable startup is better than a fast, corrupted one
2. **Simplicity over Complexity**: Rebuilding is simpler than corruption detection and repair
3. **Filesystem is Trustworthy**: File operations are more reliable than WASM database operations
4. **Deterministic State**: Every startup begins from a known good state

**Trade-offs:**
- ✅ Eliminates corruption-related bugs
- ✅ Simplifies operational model
- ✅ Makes crashes non-destructive
- ⚠️ Slower startup for large corpora (mitigated by parallel ingestion)
- ⚠️ Higher disk I/O on startup (acceptable for most use cases)

**Related Incidents:**
- 2026-03-23: Database corruption caused ingestion to hang indefinitely. Solution was force-kill and wipe.
- 2026-03-12: WASM heap corruption after large search query. Required restart.
- 2026-02-28: Silent write failures accumulated over multiple restarts. Required manual database deletion.

---

## References

- Standard 007: PGlite Memory Optimization
- Standard 012: Data Integrity (Operation State Machine)
- Standard 110: Mirror Protocol (referenced in code comments)
- `engine/src/core/db.ts`: Database initialization and wipe logic
- `engine/src/services/mirror/mirror.ts`: Mirror Protocol implementation
- `docs/TROUBLESHOOTING.md`: Operational troubleshooting guide
