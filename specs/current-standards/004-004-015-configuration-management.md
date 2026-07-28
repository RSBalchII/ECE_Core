# Standard 015: Configuration Management

**Status:** Active
**Date:** 2026-03-22
**Supersedes:** Standard 102 (Centralized Configuration Management)

## Context
Anchor Engine configuration was scattered across multiple files with duplicate definitions, hardcoded paths, and unclear settings hierarchy. This caused confusion and bugs.

## Pain Points Fixed
- Commit `a1b1a3f`: Duplicate `MIRRORED_BRAIN_DIR` definition caused inconsistency
- Commit `a1b1a3f`: `process.cwd()` usage broke when running from different directories
- Commit `dc072f9`: MCP server didn't read `user_settings.json`
- Commit `dc072f9`: Watchdog disabled by default required manual enabling

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

### CONF-002: Settings Hierarchy
1. Single `user_settings.json` for all configuration
2. Environment variables override settings file
3. Document settings file location clearly

```
Priority (highest to lowest):
1. Environment variables (ANCHOR_API_KEY, PORT, etc.)
2. user_settings.json
3. Default values in config/index.ts
```

### CONF-003: Auto-Enable Logic
1. If `watcher.extra_paths` is non-empty → Watchdog starts automatically
2. Log: "Watchdog auto-enabled: watching N paths"
3. No manual enable/disable flag needed

```typescript
// Auto-enable watchdog when paths configured
const extraPaths = config.WATCHER?.EXTRA_PATHS || [];
if (extraPaths.length > 0) {
  console.log(`[Watchdog] Auto-enabled: watching ${extraPaths.length} paths`);
  watchdog.start();
}
```

### CONF-004: No Duplicate Definitions
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

## Implementation Notes
- Path constants in `engine/src/config/paths.ts`
- Configuration loading in `engine/src/config/index.ts`
- Settings schema documented in `user_settings.json` comments
- MCP reads settings in `engine/src/mcp/server.ts`