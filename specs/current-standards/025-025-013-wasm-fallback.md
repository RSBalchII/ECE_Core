# Standard 013: WASM Module Fallbacks

**Status:** Active
**Date:** 2026-03-22
**Supersedes:** Standard 074 (Native Module Acceleration)

## Context
Anchor Engine uses Rust-compiled WASM modules for performance-critical operations (fingerprinting, atomization, keyword extraction, graph search). These modules may fail to load due to platform incompatibility, missing dependencies, or npm resolution issues.

## Pain Points Fixed
- Commit `f4c9cc3`: WASM modules failed to load when installed as npm package
- Commit `080c347`, `20da329`: Missing runtime dependencies caused crashes
- Commit `b2cdb89`: Engine crashed when WASM modules unavailable

## Requirements

### DEPS-001: Runtime Dependencies
1. All packages required at runtime must be in `dependencies`, not `devDependencies`
2. WASM packages must be in `dependencies`
3. Verify with `npm ls --prod` before publishing

```json
// ✅ CORRECT: WASM in dependencies
{
  "dependencies": {
    "@rbalchii/anchor-fingerprint-wasm": "^1.0.0",
    "@rbalchii/anchor-atomizer-wasm": "^1.0.0"
  }
}

// ❌ WRONG: WASM in devDependencies
{
  "devDependencies": {
    "@rbalchii/anchor-fingerprint-wasm": "^1.0.0"
  }
}
```

### DEPS-002: WASM Fallbacks
1. Every WASM module must have a pure JavaScript fallback implementation
2. Engine must continue running if WASM fails to load
3. Log warning instead of crashing
4. Track module status with fallback detection

```typescript
// ✅ CORRECT: Fallback implementation
try {
  const wasmModule = await import(import.meta.resolve('@rbalchii/anchor-fingerprint-wasm'));
  fingerprint_fn = wasmModule.fingerprint;
  console.log('[WasmModuleLoader] ✓ anchor-fingerprint-wasm loaded');
} catch (e) {
  console.warn('[WasmModuleLoader] ⚠ anchor-fingerprint-wasm unavailable, using fallback');
  fingerprint_fn = fallbackFingerprint;  // Pure JS implementation
}

// ❌ WRONG: Crash on failure
const wasmModule = await import('@rbalchii/anchor-fingerprint-wasm');  // throws if unavailable
```

### DEPS-003: ESM Resolution
1. Use `import.meta.resolve()` for WASM module paths
2. Ensures correct resolution when installed as npm package
3. Works with both local development and published packages

```typescript
// ✅ CORRECT: ESM resolution
const wasmPath = import.meta.resolve('@rbalchii/anchor-fingerprint-wasm');
const module = await import(wasmPath);

// ❌ WRONG: Relative path fails in node_modules
const module = await import('../node_modules/@rbalchii/anchor-fingerprint-wasm');
```

## Fallback Implementations

| Module | WASM Function | JS Fallback |
|--------|---------------|-------------|
| `anchor-fingerprint-wasm` | `fingerprint(text)` | SHA-256 hash, take first 8 bytes as bigint |
| `anchor-fingerprint-wasm` | `distance(a, b)` | XOR + popcount for Hamming distance |
| `anchor-atomizer-wasm` | `sanitize(text)` | Regex to remove control characters |
| `anchor-atomizer-wasm` | `atomize(text, strategy)` | Split by paragraphs/sentences |
| `anchor-keyextract-wasm` | `extract_keywords(text, max)` | Word frequency analysis |
| `anchor-tagwalker-wasm` | `search_graph(query, data, config)` | Simple text matching |

## Implementation Notes
- WASM loader in `engine/src/utils/wasm-module-loader.ts`
- Fallback implementations are pure JavaScript, no external dependencies
- Module status available via `wasmModuleLoader.getSummary()`
- Health check endpoint returns fallback status