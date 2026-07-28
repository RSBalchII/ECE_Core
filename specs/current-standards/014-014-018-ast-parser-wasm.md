# Standard 018: AST Parser WASM Implementation

**Status:** Active  
**Date:** 2026-05-18  
**Category:** Dependencies / Tooling  

## Problem

The Code AST Parser needed to parse TypeScript and JavaScript files for semantic atomization. Initial attempts using the `tree-sitter-wasms` package failed because:

1. **Native Build Requirement**: The package required native compilation with specific toolchains (cmake, python, etc.)
2. **Platform Incompatibility**: Failed on Windows ARM64 where prebuilt binaries weren't available
3. **Build Complexity**: Cascading build failures made the dependency chain fragile

## Solution

Switched to `web-tree-sitter` package which uses pure WASM modules with no native compilation requirements.

### Dependency Selection Process

**DO:**
- Prefer WASM-based packages over native builds for cross-platform compatibility
- Verify bundled assets (`.wasm` files) are included in the npm package
- Test on target architecture before committing to a dependency

**DON'T:**
- Assume a package works across all platforms just because it works locally
- Ignore build toolchain requirements when selecting dependencies

### Required Dependencies

```json
{
  "dependencies": {
    "web-tree-sitter": "^0.23.x",
    "tree-sitter-typescript": "^0.21.x",
    "tree-sitter-javascript": "^0.21.x"
  }
}
```

### Path Resolution Pattern

**Standard pattern for resolving WASM asset paths:**

```typescript
// Get the directory of the web-tree-sitter package
const webTreeSitterDir = path.dirname(require.resolve('web-tree-sitter'));

// Resolve individual WASM files relative to package directory
const treeSitterWasm = path.join(webTreeSitterDir, 'node_modules/web-tree-sitter/web-tree-sitter.wasm');
const treeSitterTypescriptWasm = path.join(webTreeSitterDir, 'node_modules/tree-sitter-typescript/tree-sitter-typescript.wasm');
const treeSitterJavascriptWasm = path.join(webTreeSitterDir, 'node_modules/tree-sitter-javascript/tree-sitter-javascript.wasm');

// Alternative: use bundled directory directly
const wasmDir = path.join(webTreeSitterDir, 'node_modules/web-tree-sitter');
```

**Never rely solely on `import.meta.url` for asset paths - it doesn't work in all contexts.**

### Language Parser Fallbacks

Know the limitations of available parsers and implement sensible fallbacks:

| File Extension | Primary Parser | Fallback | Notes |
|----------------|----------------|----------|-------|
| `.ts` | TypeScript | N/A | Full TypeScript support |
| `.tsx` | TypeScript | N/A | No separate TSX WASM - uses TypeScript parser |
| `.js` | JavaScript | N/A | Full JavaScript support |
| `.jsx` | JavaScript | N/A | No separate JSX WASM - uses JavaScript parser |

**Implementation:**

```typescript
const extToLanguage = new Map([
  ['.ts', 'typescript'],
  ['.tsx', 'typescript'], // Fallback to TypeScript parser
  ['.js', 'javascript'],
  ['.jsx', 'javascript'], // Fallback to JavaScript parser
]);

function getParserForFile(ext: string): Parser | null {
  const language = extToLanguage.get(ext);
  if (!language) return null;
  
  // TSX/JSX use TypeScript/JavaScript parsers respectively
  if (ext === 'tsx' || ext === 'jsx') {
    console.log(`[${ext.toUpperCase()}] Using ${language} parser (no separate WASM)`);
  }
  
  return getParser(language);
}
```

### Parse Error Handling

**DO:**
- Return `null` or empty result on parse errors, don't crash
- Log parse failures for debugging
- Document known limitations (e.g., "TSX uses TypeScript parser fallback")

**DON'T:**
- Crash the engine when encountering syntax errors in source files
- Assume all code will be valid TypeScript/JavaScript

```typescript
try {
  const tree = parser.parse(code, offset, length);
  blocks = extractBlocks(tree.rootNode);
} catch (error) {
  console.error(`[astParser] Parse failed: ${error.message}`);
  return null; // Or throw with specific error type
}
```

## Implementation Checklist

### Pre-Implementation
- [ ] Verify package uses WASM (not native builds)
- [ ] Check bundled assets are included in npm package
- [ ] Test on target architecture (Windows ARM64, macOS, Linux)

### Implementation
- [ ] Implement `extToLanguage()` mapping function
- [ ] Add fallback logic for TSX/JSX → TypeScript/JavaScript
- [ ] Handle parse errors gracefully (return null, don't crash)
- [ ] Document parser limitations in code comments

### Testing
- [ ] Test with valid TypeScript files
- [ ] Test with valid JavaScript files
- [ ] Test with TSX files (verify fallback works)
- [ ] Test with JSX files (verify fallback works)
- [ ] Test edge cases: empty files, parse errors, deeply nested code

### Post-Implementation
- [ ] Run full build (`pnpm run build`) to catch cascading errors
- [ ] Verify no new compiler errors in unrelated files
- [ ] Update documentation with known limitations

## Known Limitations

1. **TSX/JSX Syntax**: The TypeScript/JavaScript parsers don't understand JSX syntax natively. Files with JSX will parse as JavaScript/TypeScript, which may miss JSX-specific features.

2. **No Decorator Support**: Standard ESTree format doesn't include decorator metadata.

3. **Type Inference**: AST doesn't include inferred types - only declared types are available.

4. **Macro Expansion**: TypeScript macros are not expanded (pre-processed by compiler).

## Related Standards

- Standard 017: Dependency Validation
- Standard 013: WASM Module Fallbacks  
- Standard 022: Documentation Hygiene

---

*Created: 2026-05-18*  
*Author: RS Balch II*