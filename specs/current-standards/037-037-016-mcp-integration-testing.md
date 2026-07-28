# Standard 016: MCP Integration Testing

**Status:** Active  
**Created:** 2026-03-22  
**Pain Point:** MCP server broke repeatedly (port mismatches, env vars, path resolution) with no automated detection.

## Problem

The MCP (Model Context Protocol) server is a critical integration point, but had no automated tests. Issues discovered in production included:

1. Port mismatch between engine default (3160) and MCP default (3161)
2. Environment variables not being passed from wrapper script
3. Path resolution failing when running from npm install vs local dev
4. MCP server disabling itself when engine not running at startup
5. No visibility into API call failures

Each fix addressed a symptom rather than the root cause.

## Requirements

### 1. Integration Test Coverage

MCP integration tests MUST cover:

```typescript
// tests/integration/mcp-integration.vitest.ts

describe('MCP Integration', () => {
  it('should connect to engine on correct port', async () => {
    // Test that MCP uses engine port from user_settings.json
  });

  it('should handle engine not running gracefully', async () => {
    // MCP should not crash, should retry or operate in degraded mode
  });

  it('should resolve paths correctly in npm context', async () => {
    // Test path resolution when installed via npm
  });

  it('should pass environment variables from wrapper', async () => {
    // Test that ANCHOR_API_URL and ANCHOR_API_KEY are used
  });

  it('should report API call failures with context', async () => {
    // Test error messages include URL and reason
  });
});
```

### 2. MCP Server Health Check

MCP server MUST expose a health/status mechanism:

```typescript
// In mcp-server/index.ts

// Log startup configuration
console.error('🔌 MCP Server Configuration:');
console.error(`   Engine URL: ${ANCHOR_API_URL}`);
console.error(`   API Key: ${ANCHOR_API_KEY ? 'set' : 'not set'}`);
console.error(`   MCP Enabled: ${securitySettings.enabled ? '✅' : '❌'}`);

// Test engine connectivity on startup
async function testEngineConnection(): Promise<boolean> {
  try {
    const response = await fetch(`${ANCHOR_API_URL}/health`, {
      signal: AbortSignal.timeout(5000)
    });
    return response.ok;
  } catch {
    return false;
  }
}
```

### 3. Graceful Degradation

MCP server MUST NOT crash when engine is unavailable:

```typescript
// Before tool execution
const engineReady = await testEngineConnection();
if (!engineReady) {
  return {
    content: [{
      type: 'text',
      text: '⚠️ Engine not responding. Please ensure Anchor Engine is running on ' + ANCHOR_API_URL
    }],
    isError: true
  };
}
```

### 4. Retry Logic

MCP server SHOULD retry transient failures:

```typescript
async function callAnchorAPIWithRetry(endpoint: string, retries = 3): Promise<any> {
  for (let i = 0; i < retries; i++) {
    try {
      return await callAnchorAPI(endpoint);
    } catch (error) {
      if (i === retries - 1) throw error;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}
```

## Validation

- [ ] Integration tests exist for MCP ↔ Engine communication
- [ ] MCP server logs configuration on startup
- [ ] MCP server handles engine unavailability gracefully
- [ ] Error messages include actionable context (URL, expected config)

## Related Standards

- Standard 011: Security Hardening (API key validation)
- Standard 014: Operational Visibility (logging)
- Standard 015: Configuration Management (settings loading)