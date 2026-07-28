# Standard 011: Security Hardening

**Status:** Active
**Date:** 2026-03-22
**Supersedes:** N/A

## Context
Anchor Engine exposes HTTP APIs and MCP tools that may contain sensitive data. Security vulnerabilities were discovered including hardcoded default credentials and path traversal risks.

## Pain Points Fixed
- Commit `035ce82`: Hardcoded default API key `ece-secret-key` allowed unauthorized access
- Commit `7ef1bd1`: Path traversal vulnerability in `/v1/system/paths`
- Commit `7ef1bd1`: No rate limiting on ingestion endpoints

## Requirements

### SEC-001: No Default Credentials
1. Never ship hardcoded API keys, passwords, or secrets in source code
2. Engine must fail to start with clear error message if authentication is not configured
3. Example error: `Error: API key required. Set server.api_key in user_settings.json`

```typescript
// ✅ CORRECT: Fail fast with clear message
if (!config.server.api_key) {
  console.error('API key required. Set server.api_key in user_settings.json');
  process.exit(1);
}

// ❌ WRONG: Silent fallback to insecure default
const apiKey = config.server.api_key || 'default-key';
```

### SEC-002: Path Validation
1. All path inputs must be validated as absolute paths
2. Check path exists and is readable before accepting
3. Warn when adding paths outside PROJECT_ROOT
4. Return `within_project_root` boolean flag in responses

```typescript
// ✅ CORRECT: Validate before accepting
const resolvedPath = path.resolve(inputPath);
if (!path.isAbsolute(resolvedPath)) {
  return res.status(400).json({ error: 'Absolute path required' });
}
if (!fs.existsSync(resolvedPath)) {
  return res.status(400).json({ error: 'Path does not exist' });
}

// ❌ WRONG: Accept any input (path traversal vulnerability)
const watchPath = req.body.path;
```

### SEC-003: Rate Limiting
1. Ingestion endpoints must have rate limiting
2. Default: 10 requests/minute for ingest (mobile-friendly)
3. Skip rate limiting for localhost in development mode
4. Return `retry-after` header on rate limit exceeded

## Implementation Notes
- Auth middleware in `engine/src/middleware/auth.ts`
- Path validation in `engine/src/routes/v1/settings.ts`
- Rate limiting via `express-rate-limit` package