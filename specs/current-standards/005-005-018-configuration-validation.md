# Standard 018: Configuration Validation at Startup

**Status:** Active  
**Created:** 2026-03-22  
**Pain Point:** Hardcoded defaults, missing API key, and path issues caused startup failures with unclear error messages.

## Problem

Configuration issues discovered at runtime:

1. Default API key `"bolt-memory-secret"` hardcoded in multiple places
2. Port mismatch between engine (3161) and MCP (3160) defaults
3. Missing `user_settings.json` caused silent failures
4. Invalid paths caused database errors after startup
5. No clear indication of what was misconfigured

## Requirements

### CONF-001: Fail Fast on Missing Required Configuration

Engine MUST fail immediately on startup if required configuration is missing:

```typescript
// config/validation.ts

interface RequiredConfig {
  key: string;
  value: any;
  source: string;
  required: boolean;
}

function validateRequiredConfig(): void {
  const required: RequiredConfig[] = [
    { key: 'server.port', value: config.PORT, source: 'user_settings.json', required: true },
    { key: 'server.api_key', value: config.API_KEY, source: 'user_settings.json', required: true },
    { key: 'database.path', value: PATHS.database, source: 'config/paths.ts', required: true },
  ];

  const missing = required.filter(r => r.required && !r.value);

  if (missing.length > 0) {
    console.error('\n❌ Configuration validation failed:\n');
    missing.forEach(m => {
      console.error(`   ✗ ${m.key}: not set (expected in ${m.source})`);
    });
    console.error('\nPlease update user_settings.json or set environment variables.\n');
    process.exit(1);
  }
}
```

### CONF-002: Startup Banner Shows Configuration Status

Engine MUST display configuration status on startup:

```
╔═══════════════════════════════════════════════════════════════╗
║                    Anchor Engine v4.9.5                       ║
╠═══════════════════════════════════════════════════════════════╣
║ Configuration:                                                ║
║   ✓ Port: 3160                                                ║
║   ✓ API Key: bolt-mem...                                      ║
║   ✓ Database: /path/to/pglite                                 ║
║   ✓ WASM Modules: 4/4 loaded                                  ║
║   ✓ MCP Server: enabled                                       ║
║                                                               ║
║ Warnings:                                                     ║
║   ⚠ API Key uses default value (change for production)        ║
╚═══════════════════════════════════════════════════════════════╝
```

### CONF-003: No Hardcoded Defaults for Security-Critical Values

Security-critical values MUST NOT have hardcoded defaults:

```typescript
// ❌ WRONG: Hardcoded default
const API_KEY = process.env.ANCHOR_API_KEY || 'bolt-memory-secret';

// ✅ CORRECT: Require explicit configuration
const API_KEY = process.env.ANCHOR_API_KEY || settings.server?.api_key;
if (!API_KEY) {
  console.error('✗ API_KEY not configured. Set ANCHOR_API_KEY or server.api_key in user_settings.json');
  process.exit(1);
}
```

### CONF-004: Validate Paths Are Writable

Engine MUST verify paths are accessible before starting:

```typescript
function validatePaths(): void {
  const paths = [
    { name: 'Database', path: PATHS.database },
    { name: 'Inbox', path: PATHS.INBOX_DIR },
    { name: 'External Inbox', path: PATHS.EXTERNAL_INBOX_DIR },
    { name: 'Mirrored Brain', path: PATHS.CONTEXT_DIR },
  ];

  for (const { name, path } of paths) {
    try {
      // Try to create directory if it doesn't exist
      if (!fs.existsSync(path)) {
        fs.mkdirSync(path, { recursive: true });
      }
      // Try to write a test file
      const testFile = join(path, '.write-test');
      fs.writeFileSync(testFile, 'test');
      fs.unlinkSync(testFile);
      console.log(`  ✓ ${name}: ${path}`);
    } catch (error) {
      console.error(`  ✗ ${name}: ${path} (not writable)`);
      process.exit(1);
    }
  }
}
```

### CONF-005: Validate Port Availability

Engine MUST check if port is available before binding:

```typescript
import { createServer } from 'net';

async function isPortAvailable(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close();
      resolve(true);
    });
    server.listen(port);
  });
}

// Before starting Express
if (!(await isPortAvailable(config.PORT))) {
  console.error(`✗ Port ${config.PORT} is already in use`);
  console.error('  Kill the existing process or change server.port in user_settings.json');
  process.exit(1);
}
```

### CONF-006: Warn on Insecure Defaults

Engine MUST warn when using insecure default values:

```typescript
const INSECURE_DEFAULTS = [
  { key: 'server.api_key', value: 'bolt-memory-secret', message: 'Change API key for production' },
  { key: 'mcp.require_api_key', value: false, message: 'MCP API key validation disabled' },
];

function checkInsecureDefaults(): void {
  const warnings: string[] = [];

  for (const { key, value, message } of INSECURE_DEFAULTS) {
    if (getNestedValue(config, key) === value) {
      warnings.push(`⚠ ${key}: ${message}`);
    }
  }

  if (warnings.length > 0) {
    console.log('\nSecurity Warnings:');
    warnings.forEach(w => console.log(`  ${w}`));
    console.log('');
  }
}
```

## Validation Checklist

- [ ] Required configuration validated at startup
- [ ] Startup banner shows configuration status
- [ ] No hardcoded defaults for security-critical values
- [ ] Paths validated as writable
- [ ] Port availability checked
- [ ] Warnings shown for insecure defaults

## Implementation

```typescript
// In engine/src/core/startup.ts

export async function validateStartup(): Promise<void> {
  console.log('\n📋 Validating configuration...\n');

  // 1. Check required config
  validateRequiredConfig();

  // 2. Check paths
  await validatePaths();

  // 3. Check port
  if (!(await isPortAvailable(config.PORT))) {
    console.error(`✗ Port ${config.PORT} already in use`);
    process.exit(1);
  }

  // 4. Check insecure defaults
  checkInsecureDefaults();

  console.log('\n✅ Configuration valid\n');
}
```

## Related Standards

- Standard 011: Security Hardening (API key handling)
- Standard 014: Operational Visibility (startup logging)
- Standard 015: Configuration Management (settings loading)