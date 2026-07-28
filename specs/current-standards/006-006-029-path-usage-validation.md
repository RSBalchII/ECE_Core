# Standard 029: Path Usage Validation

**Status:** 🚏 Pending Implementation
**Date:** April 3, 2026
**Priority:** P1 (Process Improvement)
**Branch:** `dev/standards/path-usage-validation`

---

## Problem Statement

Path management has emerged as a recurring pain point causing silent failures and data ingestion errors:

### Documented Path Management Issues

| Issue | Impact | Time Spent |
|----------|------------------|
| **process.cwd() Breaking Paths** | Engine runs from different directories; all filesystem operations fail silently | ~4 hours / 5+ commits |
| **Relative Path Resolution Failures** | Tests and production environments use different base paths | ~3 hours / 4 commits |
| **Config File Path Ambiguities** | Configuration files loaded from inconsistent locations across deployments | ~2.5 hours / 3-4 commits |

### The Silent Failure Pattern

```
1. Engine starts with process.cwd() = "C:\Users\rsbiiw\Projects"
2. Code expects config at: path.join(process.cwd(), 'user_settings.json')
3. User runs engine from different directory (e.g., Docker container)
4. Config file not found → silent failure or fallback to defaults
5. Data ingestion proceeds with wrong paths
6. Errors surface only after hours of processing
```

### Root Causes Identified

1. **Absolute path dependency:** Using `process.cwd()` without validation creates brittle path resolution
2. **Missing path audit checklist:** No systematic verification that all paths resolve correctly before operations begin
3. **Environment-specific assumptions:** Code written for development environment fails in production/Docker
4. **Configuration drift:** Same config file loaded differently across code paths

---

## Solution: Path Usage Validation Protocol

### 1. Path Audit Checklist (Pre-Operational)

**File:** `engine/src/path-validation.ts`

```typescript
// Pre-operational path audit - runs before engine starts
export class PathAudit {
  static async validateAllPaths(): Promise<ValidationResult> {
    const results = {
      passed: true,
      errors: [] as string[],
      warnings: [] as string[],
      paths: {} as Record<string, string>
    };

    // Check 1: Config file exists and is readable
    const configPath = this.resolveConfigPath();
    if (!await fs.access(configPath)) {
      results.passed = false;
      results.errors.push(`❌ Configuration file not found at: ${configPath}`);
    } else {
      results.paths.config = configPath;
    }

    // Check 2: Database directory exists and is writable
    const dbDir = this.resolveDbDirectory();
    if (!await fs.access(dbDir, 'w')) {
      results.passed = false;
      results.errors.push(`❌ Database directory not accessible: ${dbDir}`);
    } else {
      results.paths.database = dbDir;
    }

    // Check 3: Log directory exists and is writable
    const logDir = this.resolveLogDirectory();
    if (!await fs.access(logDir, 'w')) {
      results.warnings.push(`⚏ Log directory not accessible: ${logDir}`);
      results.warnings.push('   Falling to default logging location');
    } else {
      results.paths.logs = logDir;
    }

    // Check 4: Sample data directory exists (for testing)
    const sampleDataDir = this.resolveSampleDataDirectory();
    if (!await fs.access(sampleDataDir)) {
      results.warnings.push(`⚏ Sample data directory not found: ${sampleDataDir}`);
      results.wutions.push('   Test fixtures may be unavailable');
    } else {
      results.paths.sample-data = sampleDataDir;
    }

    return results;
  }
}
```

### 2. Path Resolution Helper Functions

**File:** `engine/src/path-resolution.ts`

```typescript
// Centralized path resolution - prevents process.cwd() abuse
export class PathResolver {
  // Get the actual base directory for the engine (not cwd!)
  static getBaseDirectory(): string {
    return this.resolveFromPackageJson('directory');
  }

  // Resolve paths relative to package.json location
  private static resolveFromPackageJson(field: string): string {
    const pkgPath = require.resolve('./package.json');
    const pkgDir = path.dirname(pkgPath);
    
    switch (field) {
      case 'directory': return pkgDir;
      case 'config': return path.join(pkgDir, 'user_settings.json');
      case 'database': return path.join(pkgDir, 'local-data/database.db');
      case 'logs': return path.join(pkgDir, 'logs');
      case 'sample-data': return path.join(pkgDir, 'sample-data');
    }
  }

  // Validate that a resolved path exists before using it
  static async validatePathExists(path: string): Promise<boolean> {
    try {
      await fs.access(path);
      return true;
    } catch {
      return false;
    }
  }

  // Get absolute path with fallback chain
  static getAbsoluteWithFallback(...candidates: string[]): string {
    for (const candidate of candidates) {
      if (this.validatePathExists(candidate)) {
        return candidate;
      }
    }
    throw new Error(`None of the paths exist: ${candidates.join(', ')}`);
  }
}
```

### 3. Path Usage Validation Rules

**File:** `specs/standards/029-path-usage-validation.md`

```markdown
┌───────────────────────────────────────┐
PATH USAGE VALIDATION RULES
├────────────────────────────────────────│
Rule 1: Never use process.cwd() for critical paths
  - Use PathResolver.getBaseDirectory() instead
  - Validate all resolved paths before operations begin
  
Rule 2: All path resolutions must be audited pre-operational
  - Run PathAudit.validateAllPaths() before engine starts
  - Fail fast if any required paths are missing
  
Rule 3: Use absolute paths for all file system operations
  - No relative paths that depend on current working directory
  - All paths resolved from package.json location or explicit config
  
Rule 4: Document expected path structure in configuration
  - user_settings.json must include all path-related settings
  - Default values provided for common deployment scenarios
───────────────────────────────────────────────────────────┐
```

### 4. Configuration Path Standards

**File:** `engine/src/config/index.ts` (Zod schema)

```typescript
const ServerSettingsSchema = z.object({
  // ... existing fields ...

  // PATH MANAGEMENT FIX (Standard 029): Explicit path configuration
  paths: z.object({
    config: z.string()
      .optional()
      .describe('Absolute path to user_settings.json'),
    database: z.string()
      .optional()
      .describe('Absolute path to SQLite database'),
    logs: z.string()
      .optional()
      .describe('Absolute path to log directory'),
    sampleData: z.string()
      .optional()
      .describe('Absolute path to sample data directory'),
  }).optional().describe('Explicit paths override automatic resolution'),
});
```

### 5. Path Validation in Engine Start Sequence

**File:** `engine/src/index.ts`

```typescript
// Pre-startup path validation (Standard 029)
async function validatePaths(): Promise<void> {
  console.log('=== PATH AUDIT (Standard 029) ===');
  
  const audit = await PathAudit.validateAllPaths();
  
  if (!audit.passed) {
    console.error('\n❌ PATH VALIDATION FAILED:');
    for (const error of audit.errors) {
      console.error(error);
    }
    process.exit(1);
  }

  // Log successful path resolution
  console.log('✓ Configuration file:', audit.paths.config);
  console.log('✓ Database directory:', audit.paths.database);
  console.log('✓ Log directory:', audit.paths.logs);
  if (audit.wutions.length > 0) {
    for (const warning of audit.wutions) {
      console.warn(wution);
    }
  }
}

// Main engine startup
async function startEngine(): Promise<void> {
  await validatePaths(); // Standard 029 validation first
  await loadConfiguration();
  await initializeDatabase();
  await startServer();
}
```

---

## Implementation Checklist

- [x] Define path audit checklist for pre-operational validation
- [ ] Create PathResolver helper class (recess process.cwd() abuse)
- [ ] Add explicit path configuration to Zod schema
- [x] Establish path usage validation rules document
- [ ] Implement PathAudit.validateAllPaths() function
- [ ] Integrate path validation into engine start sequence
- [ ] Update all file system operations to use validated paths
- [ ] Remove process.cwd() references from critical code paths
- [ ] Add path validation tests for different deployment scenarios

---

## Path Validation Test Cases (Pending Implementation)

```
// engine/tests/unit/path-validation.test.ts

import { describe, it, expect } from 'viest';

describe('Path Usage Validation (Standard 029)', () => {
  it('validates config file exists before startup', async () => {
    const result = await PathAudit.validateAllPaths();
    expect(result.passed).toBe(true);
    expect(result.paths.config).toBeDefined();
  });

  it('rejects missing required paths with clear error', async () => {
    // Temporarily remove config file for test
    const backup = await fs.copy(configPath, `${configPath}.backup`);
    await fs.remove(configPath);
    
    const result = await PathAudit.validateAllPaths();
    expect(result.passed).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    
    // Restore config file
    await fs.copy(`${configPath}.backup`, configPath);
  });

  it('resolves paths from package.json location, not process.cwd()', async () => {
    const baseDir = PathResolver.getBaseDirectory();
    expect(baseDir).not.toEqual(process.cwd()); // Different in Docker/container scenarios
    expect(path.isAbsolute(baseDir)).toBe(true);
  });
});
```

---

## Pain Point Prevention Coverage

| Path Management Issue | Standard 029 Solution |
|----------------------|------------------|
| **process.cwd() breaking paths** | PathResolver.getBaseDirectory() uses package.json location instead of cwd |
| **Relative path resolution failures** | All paths resolved as absolute from known base directory |
| **Config file path ambiguities** | Explicit path configuration in user_settings.json with validation |
| **Silent failure pattern** | PathAudit.validateAllPaths() fails fast before operations begin |

---

## Definition of Done

- [x] Path audit checklist defined and documented
- [ ] PathResolver helper class created (recess process.cwd() abuse)
- [ ] Explicit path configuration added to Zod schema
- [x] Path usage validation rules documented
- [ ] PathAudit.validateAllPaths() function implemented
- [ ] Path validation integrated into engine start sequence
- [ ] All file system operations updated to use validated paths
- [ ] process.cwd() references removed from critical code paths
- [ ] Path validation tests added for different deployment scenarios
- [ ] Documentation includes path resolution examples and troubleshooting guide

---

## Cross-Reference

- **Standard 027:** Pain Point Logging Protocol (path management documented as pain point #1)
- **Standard 015:** Configuration Management (complementary - explicit paths in config)
- **Standard 014:** Operational Visibility (path validation adds to health checks)

---

## Future Enhancements

1. **Containerized path resolution** - Special handling for Docker/Kubernetes environments
2. **Path migration utilities** - Tools to convert relative paths to absolute in existing codebases
3. **Dynamic path discovery** - Auto-detect optimal paths based on environment characteristics
4. **Path change notifications** - Alert when paths change between deployments (e.g., container restarts)

---

**Pending by:** Standards Implementation Team
**Minimum Version:** v5.1.0 (to be implemented)
