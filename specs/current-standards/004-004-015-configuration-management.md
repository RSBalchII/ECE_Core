# Standard 015: Configuration Management

**Status:** Active  
**Date:** 2026-03-22 (Updated: 2026-08-10)  
**Supersedes:** Standard 102 (Centralized Configuration Management)  
**Version:** v5.2.0+ (Dynamic DB-backed config)

## Context
Anchor Engine configuration was scattered across multiple files with duplicate definitions, hardcoded paths, and unclear settings hierarchy. This caused confusion and bugs. Starting in v5.2.0, all runtime configuration is stored as key-value pairs in the `app_settings` database table, enabling zero-downtime changes without restarting the engine.

## Pain Points Fixed
- Commit `a1b1a3f`: Duplicate `MIRRORED_BRAIN_DIR` definition caused inconsistency
- Commit `a1b1a3f`: `process.cwd()` usage broke when running from different directories
- Commit `dc072f9`: MCP server didn't read `user_settings.json`
- Commit `dc072f9`: Watchdog disabled by default required manual enabling
- **v5.2.0:** Static config files prevented runtime changes — now all settings live in DB

## Requirements

### CONF-001: Path Constants
1. All paths must use `PATHS` from `config/paths.ts`
2. Never use `process.cwd()` or relative paths
3. Single source of truth for all file system locations

```typescript
// ✅ CORRECT: Use PATHS constant
import { PATHS } from '../config/paths.js';
const dbPath = PATHS.DATABASE_DIR;

// ❌ WRONG: process.cwd() is unreliable
const dbPath = path.join(process.cwd(), 'local-data', 'db');

// ❌ WRONG: Relative path breaks in node_modules
const dbPath = './local-data/db';
```

### CONF-002: Settings Hierarchy (v5.2.0+)
1. **Database (`app_settings` table)** — live runtime settings (highest priority)
2. **Environment variables** — override database values for critical settings like API keys
3. **File defaults (`user_settings.json`)** — fallback defaults imported on first startup

```
Priority (highest to lowest):
1. Database (app_settings table) — queried at request time, changes take effect immediately
2. Environment variables (ANCHOR_API_KEY, PORT, etc.)
3. user_settings.json — only used for initial DB import; not read at runtime after v5.2.0
```

### CONF-003: Dynamic Config via Database
1. All settings stored in `app_settings` table with key-value pairs
2. Settings queried live from database on every request (no frozen config objects)
3. Changes take effect immediately — no restart needed
4. Audit trail via `updated_at` and `source` columns

```typescript
// ✅ CORRECT: Read settings live from DB
async function getSetting(key: string): Promise<any> {
    const result = await db.run(
        'SELECT value FROM app_settings WHERE key = ?', [key]
    );
    return result.rows?.[0]?.value;  // Returns JSON-parsed value
}

// Usage — no restart needed, change in DB takes effect instantly
const autoStart = await getSetting('watchdog.auto_start');
if (autoStart) startWatchdog();

// ❌ WRONG: Reading from frozen config object at startup
const autoStart = config.WATCHER.AUTO_START;  // Frozen forever after startup
```

### CONF-004: Auto-Enable Logic (v5.2.0+)
1. Watchdog checks `app_settings.watchdog.auto_start` on every request
2. Settings can be toggled via API without restart
3. Log changes with audit trail

```typescript
// ✅ CORRECT: Dynamic watchdog auto-start from DB
const autoStart = await getSetting('watchdog.auto_start');
if (autoStart) {
    console.log('[Watchdog] Auto-enabled from database config');
    watchdog.start();
}

// ❌ WRONG: Static check at startup only
if (config.WATCHER.AUTO_START === true) {
    startWatchdog();  // Can't be changed without restart
}
```

### CONF-005: No Duplicate Definitions
1. Each path/constant defined exactly once
2. Import from single source
3. Use TypeScript to catch duplicates

```typescript
// ✅ CORRECT: Single definition
// config/paths.ts
export const MIRRORED_BRAIN_DIR = path.join(PROJECT_ROOT, 'local-data', 'mirrored_brain');

// Other files import it
import { MIRRORED_BRAIN_DIR } from '../config/paths.js';

// ❌ WRONG: Duplicate definition
// file1.ts
const MIRRORED_BRAIN = path.join(process.cwd(), 'mirrored_brain');

// file2.ts  
const MIRRORED_BRAIN_DIR = path.join(__dirname, '../../mirrored_brain');
```

### CONF-006: Settings Migration from user_settings.json (v5.2.0+)
1. On first startup, flatten nested `user_settings.json` into flat key-value pairs
2. Insert all settings into `app_settings` table
3. After import, database becomes source of truth; file can remain as backup/defaults

```typescript
// During server init (once)
const settingsFile = fs.readFileSync('~/.anchor/user_settings.json', 'utf-8');
const fileSettings = JSON.parse(settingsFile);

// Convert nested object to flat key-value pairs and insert into DB
function flatten(obj, prefix = '') {
    for (const [key, value] of Object.entries(obj)) {
        const fullKey = prefix ? `${prefix}.${key}` : key;
        if (typeof value === 'object' && !Array.isArray(value)) {
            flatten(value, fullKey);
        } else {
            await db.run(
                `INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)`,
                [fullKey, JSON.stringify(value)]
            );
        }
    }
}

flatten(fileSettings);
```

### CONF-007: Settings Validation & Schema Definition (v5.2.0+)
1. All known settings have schema definitions with type constraints and validation rules
2. `validateSetting(key, value)` checks type compatibility and custom validators before accepting changes
3. Unknown keys are allowed (extensible) but known keys enforce strict typing

```typescript
// Schema definition example
const SETTINGS_SCHEMA = {
  'server.port': { 
    key: 'server.port', 
    type: 'number', 
    defaultValue: 3160, 
    validate: (v) => v >= 1 && v <= 65535,
    description: 'Server port number' 
  },
  // ... more settings
};

// Validation before setting
const validation = validateSetting('server.port', 99999);
if (!validation.valid) {
  throw new Error(`Validation failed: ${validation.error}`);
}
```

### CONF-008: Audit Logging for Setting Changes (v5.2.0+)
1. Every `setSetting()` call logs an audit event with timestamp, action, key, old value, and new value
2. In-memory circular buffer keeps last 1000 entries
3. Audit trail accessible via `getAuditTrail(key?)` for debugging and compliance

```typescript
// Automatic audit logging on every setting change
await setSetting('search.max_chars_default', 1048576);
// Logs: [Audit] SET "search.max_chars_default" from=524288 to=1048576

// Retrieve full audit trail
const trail = await getAuditTrail(); // All events
const keyTrail = await getAuditTrail('server.port'); // Events for specific key
```

## Database Schema: `app_settings` Table (v5.2.0+)

```sql
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,           -- e.g., "watchdog.auto_start", "server.port"
    value TEXT NOT NULL,            -- JSON-stringified value (stored as text for PGlite)
    type TEXT DEFAULT 'string',     -- Coerced type: 'string' | 'number' | 'boolean'
    description TEXT,               -- human-readable explanation
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by key prefix (e.g., all "watchdog.*" settings)
CREATE INDEX idx_app_settings_key ON app_settings(key);
```

## Implementation Notes (v5.2.0+ — 70% Complete)
- **Settings Service:** `engine/src/services/settings.ts` — full implementation with DB CRUD, file sync, validation schema, and audit logging ✅
- **API Routes:** `engine/src/routes/v1/settings.ts` — GET/PUT /v1/settings/:key endpoints using DB-backed service ✅
- **Search Module Migration:** `engine/src/services/search/search.ts` — migrated to use `getMemoryThresholds()` from settings service (async) ✅
- **Config Export:** `DEFAULT_SETTINGS` exported from `engine/src/config/index.ts` for API defaults endpoint ✅
- **Validation Schema:** 25+ known settings with type constraints and custom validators defined in `SETTINGS_SCHEMA` ✅
- **Audit Trail:** In-memory circular buffer (1000 entries) tracking all SET/DELETE/IMPORT operations ✅
- **File Sync:** Bidirectional sync — API writes update both DB and `user_settings.json` for persistence across restarts ✅

## Benefits of DB-Based Configuration (v5.2.0+)
1. **Zero-downtime changes** — toggle watchdog, change search limits, add watched directories instantly
2. **Centralized configuration** — all settings in one place (the database)
3. **Audit trail** — `updated_at` and source tracking via audit logging service
4. **Consistent access pattern** — same way we read data from DB pointers for search/distill, now config too
5. **Type flexibility** — JSONB stores any type (boolean, string, number, array) without schema changes
6. **Per-tenant settings** — could extend to `key = "tenant1.watchdog.auto_start"` for multi-tenancy
7. **Validation safety** — schema definitions prevent invalid values from being persisted

## Trade-offs & Considerations
| Aspect | Current File-Based | Proposed DB-Based |
|--------|-------------------|-------------------|
| Performance | Fast (in-memory) | Slightly slower (DB query), but negligible for rarely-changing settings |
| Persistence | Survives restarts automatically | Must ensure DB is available; can fallback to file if needed |
| Type safety | TypeScript config objects | JSONB — need runtime type validation (✅ now implemented via schema) |
| Default values | Hardcoded in code | Need explicit defaults in application logic (✅ now exported from config) |
