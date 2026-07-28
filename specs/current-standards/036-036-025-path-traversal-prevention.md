# Standard 129: Path Traversal Prevention

**Status:** ✅ Active | **Date:** April 3, 2026 | **Priority:** P0 Security

---

## Problem

User-supplied file paths in API endpoints were vulnerable to path traversal attacks. An attacker with a valid API key could potentially access files outside allowed directories (e.g., `/etc/passwd`, `~/.ssh/id_rsa`).

### Vulnerable Pattern

```typescript
// ❌ DON'T: Direct path.join/resolve without validation
const fullPath = path.join(process.cwd(), filePath);
const resolvedPath = path.resolve(userPath);

// This allows: ../../../etc/passwd
```

### Affected Endpoints

1. `POST /v1/system/paths` - Add watch path
2. `POST /v1/system/explorer` - Open file explorer
3. `POST /v1/test/run-file` - Run test file

---

## Solution

### 1. Centralized Path Validation Utility

Created `engine/src/utils/security.ts` with validation functions:

```typescript
import { validatePathSafety } from '../utils/security.js';

// ✅ DO: Validate against allowed base directories
const result = validatePathSafety(userPath, [PROJECT_ROOT, allowedDir2]);

if (!result.isValid) {
  return res.status(403).json({
    error: 'Path traversal detected',
    message: result.error
  });
}

// Safe to use: result.resolvedPath
```

### 2. Validation Rules

All user-supplied paths MUST:

1. **Resolve to absolute path** within allowed base directories
2. **Reject empty/null** paths
3. **Normalize separators** (Windows `\` → Unix `/`)
4. **Verify existence** (when using `validatePathSafetyWithExistence`)

### 3. Allowed Base Directories

| Endpoint | Allowed Bases | Rationale |
|----------|---------------|-----------|
| `/v1/system/paths` | `PROJECT_ROOT` only | Watch paths must be within project |
| `/v1/system/explorer` | `PROJECT_ROOT` only | Explorer access limited to project |
| `/v1/test/run-file` | `PROJECT_ROOT`, `tests/` | Test files in tests directory |
| `/v1/files/read` | `PATHS.DISTILLS_DIR` | Distilled files only |

---

## Implementation

### Utility Functions

```typescript
// engine/src/utils/security.ts

export interface PathValidationResult {
  isValid: boolean;
  resolvedPath: string;
  error?: string;
  allowedBase?: string;
}

export function validatePathSafety(
  userPath: string,
  allowedBases: string[]
): PathValidationResult

export async function validatePathSafetyWithExistence(
  userPath: string,
  allowedBases: string[]
): Promise<PathValidationResult>

export async function getSafePath(
  userPath: string,
  allowedBases: string[]
): Promise<string>
```

### Example Usage

```typescript
// engine/src/routes/v1/system.ts

app.post('/v1/system/explorer', async (req: Request, res: Response) => {
  const { path } = req.body;
  
  // Validate path is within PROJECT_ROOT
  const pathValidation = await validatePathSafetyWithExistence(
    path, 
    [PROJECT_ROOT]
  );
  
  if (!pathValidation.isValid) {
    console.warn(`[System] Rejected path traversal attempt: ${path}`);
    return res.status(403).json({
      error: 'Path traversal detected',
      message: pathValidation.error,
    });
  }
  
  // Additional: verify it's a directory
  const stats = await fs.promises.stat(pathValidation.resolvedPath);
  if (!stats.isDirectory()) {
    return res.status(400).json({ error: 'Path must be a directory' });
  }
  
  // Safe to use
  await execFilePromise('explorer.exe', [pathValidation.resolvedPath]);
});
```

---

## Testing

### Unit Tests

Location: `engine/tests/unit/security.test.ts`

Test coverage includes:

- ✅ Valid paths within allowed directories
- ✅ Path traversal with `../`
- ✅ Path traversal with `..\` (Windows)
- ✅ Absolute paths outside allowed dirs
- ✅ Empty/null/undefined paths
- ✅ Mixed path separators
- ✅ URL-encoded traversal attempts
- ✅ Unicode paths
- ✅ Null byte injection attempts

### Attack Scenarios Tested

```typescript
// Classic traversal
validatePathSafety('../../etc/passwd', [PROJECT_ROOT]); 
// → isValid: false

// Windows UNC paths
validatePathSafety('\\\\evil\\share\\file.txt', [PROJECT_ROOT]);
// → isValid: false

// Hidden traversal
validatePathSafety('....//....//etc/passwd', [PROJECT_ROOT]);
// → isValid: false

// NTFS alternate data streams
validatePathSafety('file.txt:secret.txt', [PROJECT_ROOT]);
// → isValid: false
```

---

## Security Considerations

### Threat Model

**Assumption:** Attacker has valid API key (authenticated but malicious)

**Attack Vectors:**
1. Direct traversal: `../../../etc/passwd`
2. URL encoding: `%2e%2e%2f` 
3. Mixed separators: `..\\..//etc/passwd`
4. Null bytes: `file.txt\u0000.jpg`
5. Symlink exploitation (mitigated by realpath)

### Defense in Depth

1. **Validation layer:** `validatePathSafety()` checks path stays within bounds
2. **Existence check:** `validatePathSafetyWithExistence()` verifies file exists
3. **Type check:** Additional validation for file vs directory
4. **Logging:** All rejected attempts logged with `[Security]` prefix

### Limitations

- Does not protect against TOCTOU (time-of-check-time-of-use) races
- Relies on correct `PROJECT_ROOT` configuration
- Does not validate file permissions beyond readability

---

## Migration Guide

### For Existing Code

Search for these patterns and replace:

```typescript
// ❌ Old pattern
const fullPath = path.join(process.cwd(), userPath);

// ✅ New pattern
const { validatePathSafety } = await import('../utils/security.js');
const result = validatePathSafety(userPath, [PROJECT_ROOT]);
if (!result.isValid) {
  return res.status(403).json({ error: result.error });
}
const fullPath = result.resolvedPath;
```

### For New Code

Always import and use the security utility:

```typescript
import { validatePathSafety } from '../utils/security.js';
```

---

## Related Standards

- **Standard 001:** Security First Development
- **Standard 045:** Input Validation
- **Standard 067:** Error Handling

---

## References

- OWASP Path Traversal: https://owasp.org/www-community/attacks/Path_Traversal
- Node.js Security Best Practices: https://nodejs.org/en/docs/guides/security/
- CWE-22: Improper Limitation of a Pathname: https://cwe.mitre.org/data/definitions/22.html

---

**Maintained by:** Anchor Engine Team  
**Last Updated:** 2026-04-03  
**Next Review:** After Q2 2026 security audit
