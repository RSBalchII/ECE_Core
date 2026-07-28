# Standard 017: Dependency Validation

**Status:** Active  
**Created:** 2026-03-22  
**Pain Point:** Dependencies incorrectly placed in `devDependencies`, WASM packages not declared, npm consumers got missing module errors.

## Problem

Multiple commits fixed dependency issues:

1. `js-yaml`, `undici`, `commander` were in `devDependencies` but used at runtime
2. WASM packages (`@rbalchii/anchor-*-wasm`) not declared as dependencies
3. ESM module resolution differed between local dev and npm install
4. No automated check to catch these issues before publish

## Requirements

### 1. Dependency Classification

Dependencies MUST be correctly classified:

| Type | Location | Examples |
|------|----------|----------|
| **Runtime** | `dependencies` | express, js-yaml, undici, commander, WASM packages |
| **Build-time** | `devDependencies` | typescript, vitest, @types/* |
| **Optional** | `optionalDependencies` | Platform-specific native modules |

### 2. Validation Script

A pre-publish validation script MUST verify dependencies:

```javascript
// scripts/validate-deps.js

import { readFileSync } from 'fs';
import { glob } from 'glob';

const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
const deps = new Set(Object.keys(pkg.dependencies || {}));

// Find all imports in src/
const srcFiles = glob.sync('src/**/*.ts');
const imports = new Set();

for (const file of srcFiles) {
  const content = readFileSync(file, 'utf8');
  const importMatches = content.matchAll(/from ['"]([^'"]+)['"]/g);
  for (const match of importMatches) {
    const mod = match[1];
    // Only check external packages (not relative imports)
    if (!mod.startsWith('.') && !mod.startsWith('#')) {
      imports.add(mod.split('/')[0]); // Handle scoped packages
    }
  }
}

// Check all imports are in dependencies
const missing = [...imports].filter(imp => !deps.has(imp));

if (missing.length > 0) {
  console.error('❌ Missing dependencies:');
  missing.forEach(m => console.error(`   - ${m}`));
  console.error('\nAdd to package.json dependencies or use conditional import.');
  process.exit(1);
}

console.log('✅ All runtime imports have declared dependencies');
```

### 3. Package.json Scripts

```json
{
  "scripts": {
    "validate:deps": "node scripts/validate-deps.js",
    "prepublishOnly": "npm run validate:deps && npm run build && npm test"
  }
}
```

### 4. WASM Package Declaration

WASM packages MUST be declared as runtime dependencies:

```json
{
  "dependencies": {
    "@rbalchii/anchor-fingerprint-wasm": "^1.0.0",
    "@rbalchii/anchor-atomizer-wasm": "^1.0.0",
    "@rbalchii/anchor-keyextract-wasm": "^1.0.0",
    "@rbalchii/anchor-tagwalker-wasm": "^1.0.0"
  }
}
```

### 5. Conditional Imports for Optional Dependencies

For packages that may not be available in all environments:

```typescript
// Use dynamic import with fallback
let wasmModule;
try {
  wasmModule = await import('@rbalchii/anchor-fingerprint-wasm');
} catch {
  console.warn('WASM module not available, using JS fallback');
  wasmModule = await import('./fallbacks/fingerprint-fallback.js');
}
```

## Validation Checklist

- [ ] All imports in `src/` have corresponding entries in `dependencies`
- [ ] WASM packages declared in `dependencies`
- [ ] No `require()` of dev-only packages in runtime code
- [ ] `npm run validate:deps` passes
- [ ] `npm pack` produces installable package

## CI Integration

```yaml
# .github/workflows/ci.yml
- name: Validate Dependencies
  run: npm run validate:deps

- name: Test npm pack
  run: |
    npm pack
    tar -xzf anchor-engine-*.tgz
    cd package
    npm install --production
    node -e "require('./dist/index.js')" # Smoke test
```

## Related Standards

- Standard 013: WASM Fallback (graceful degradation)
- Standard 011: Security Hardening (no hardcoded secrets in deps)