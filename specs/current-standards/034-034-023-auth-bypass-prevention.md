# Standard 131: Authentication Bypass Prevention

**Status:** ✅ Implemented  
**Date:** March 2026  
**Priority:** P0 (Security Critical)  
**Branch:** `dev/security/auth-bypass-audit`

---

## Problem Statement

Test endpoints under `/v1/test/*` were configured to bypass authentication entirely for "development convenience." This created a critical vulnerability where:

1. **Arbitrary file execution** - `/v1/test/run-file` could execute any test file
2. **Filesystem write access** - `/v1/test/snapshot` could write arbitrary JSON to `logs/`
3. **Path traversal** - `/v1/test/snapshot/:name` could read files outside intended directory via `../../../etc/passwd`
4. **Data exposure** - `/v1/test/snapshots` could list all snapshot files

### Attack Vector

An attacker with network access (but no API key) could:
```bash
# Read arbitrary files via path traversal
curl http://target:3000/v1/test/snapshot/../../../etc/passwd

# Write malicious data to filesystem
curl -X POST http://target:3000/v1/test/snapshot \
  -H "Content-Type: application/json" \
  -d '{"name":"malicious","type":"backdoor","data":"..."}'

# Execute arbitrary test scripts
curl -X POST http://target:3000/v1/test/run-file \
  -H "Content-Type: application/json" \
  -d '{"file":"../../../malicious.test.ts"}'
```

---

## Solution

### 1. Remove Blanket Auth Bypass

**File:** `engine/src/middleware/auth.ts`

**Before:**
```typescript
if (req.path === '/health' ||
    req.path.startsWith('/health/') ||
    req.path.startsWith('/v1/test/')) {  // ❌ DANGEROUS
  return next();
}
```

**After:**
```typescript
// Allow health endpoints without auth (public monitoring)
// SECURITY FIX (Standard 131): Remove /v1/test/* bypass
if (req.path === '/health' || req.path.startsWith('/health/')) {
  return next();
}
```

### 2. Validate Path Parameters

**File:** `engine/src/routes/test-ui.ts`

**Before:**
```typescript
app.get('/v1/test/snapshot/:name', async (req: Request, res: Response) => {
  const { name } = req.params;
  const snapshotPath = path.join(process.cwd(), 'logs', `snapshot-${name}.json`);
  // ❌ No validation - allows ../../../etc/passwd
```

**After:**
```typescript
app.get('/v1/test/snapshot/:name', async (req: Request, res: Response) => {
  const { name } = req.params;
  
  // SECURITY FIX (Standard 131): Validate snapshot name to prevent path traversal
  // Only allow alphanumeric, hyphens, and underscores
  if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
    return res.status(400).json({ 
      error: 'Invalid snapshot name. Only alphanumeric, hyphens, and underscores allowed.' 
    });
  }
  
  const snapshotPath = path.join(process.cwd(), 'logs', `snapshot-${name}.json`);
```

---

## Implementation Checklist

- [x] Remove `/v1/test/*` from auth bypass whitelist in `auth.ts`
- [x] Add regex validation for `:name` parameter in snapshot endpoints
- [x] Verify all test endpoints now require API key authentication
- [x] Document the vulnerability pattern and fix
- [ ] Add test cases for auth bypass prevention
- [ ] Audit other potential auth bypass patterns in codebase

---

## Testing

### Manual Testing

```bash
# Should FAIL without API key (401/403)
curl http://localhost:3000/v1/test/run-file
curl http://localhost:3000/v1/test/snapshot

# Should FAIL with invalid name pattern (400)
curl http://localhost:3000/v1/test/snapshot/../../../etc/passwd

# Should SUCCEED with valid API key
curl -H "Authorization: Bearer <valid-key>" \
  http://localhost:3000/v1/test/snapshot/test-snapshot
```

### Unit Test Coverage

Create tests in `engine/tests/unit/auth-bypass.test.ts`:
- Verify `/v1/test/*` endpoints reject requests without API key
- Verify path traversal patterns are rejected (400)
- Verify valid requests with API key succeed (200)

---

## Related Standards

- **Standard 129:** Path Traversal Prevention (filesystem access validation)
- **Standard 130:** SQL Injection Prevention (parameterized queries)
- **Standard 131:** Authentication Bypass Prevention (this standard)

---

## Security Review Notes

**Vulnerability Class:** Authentication Bypass + Path Traversal  
**CVSS Score:** ~8.6 (High)  
**CWE:** 
- CWE-287 (Improper Authentication)
- CWE-22 (Path Traversal)
- CWE-284 (Improper Access Control)

**Discovery Method:** Code audit of middleware exemptions  
**Impact:** Full filesystem read/write access without authentication

---

## Future Hardening

1. **Deprecate test endpoints in production** - Add environment check
2. **Audit logging** - Log all test endpoint access
3. **Rate limiting** - Apply stricter limits to test endpoints
4. **Input sanitization** - Use validation library (Zod) for all params

---

**Approved by:** Security Review  
**Implemented by:** Automated Security Hardening (March 2026)
