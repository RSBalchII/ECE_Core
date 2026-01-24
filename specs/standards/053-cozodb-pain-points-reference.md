# Standard 053: CozoDB Pain Points & OS Compatibility

**Status:** Active | **Category:** Architecture / Database

## 1. Native Binary Desync (Critical)
The `cozo-node` package relies on a native C++ binding (`.node` file). On Windows systems, `pnpm install` may fail to correctly link or place the prebuilt binary in the expected path, especially when moving between different Node.js context (e.g., global vs workspace).

### Symptoms
- `Error: Cannot find module '.../cozo_node_prebuilt.node'`
- `MODULE_NOT_FOUND` during engine startup.

### Resolution
#### Windows-Specific Binary Location
On Windows (and other platforms), the engine now implements a **Fallback Loading Strategy**. It checks for the binary in this order:
1. Standard `require('cozo-node')` (Node Resolution)
2. `engine/cozo_node_win32.node` (Windows Fallback)
3. `engine/cozo_node_darwin.node` (macOS Fallback)
4. `engine/cozo_node_linux.node` (Linux Fallback)

If the standard load fails (common on Windows due to pathing issues), you must manually copy the native binary from `node_modules` to the `engine/` root and rename it accordingly.

## 2. API Inconsistency (v0.7.6+)
The official `cozo-node` library exports a `CozoDb` class, but the ECE_Core architecture expects individual function exports. Furthermore, the **Native Binary Interface** is stricter than the JS wrapper.

### Native Interface Contract
If you bypass the `cozo-node` JS wrapper (e.g., loading the `.node` binary directly in a fallback scenario), you **MUST** strictly adhere to the C++ signature:

| Function | Argument | Type | Requirement |
| :--- | :--- | :--- | :--- |
| `open_db` | `options` | `String` (JSON) | **CRITICAL:** Must be `JSON.stringify(options)`. Passing a JS Object causes `TypeError: failed to downcast any to string`. |
| `query_db` | `params` | `Object` | Passed as standard JS Object (handled by N-API). |

### The Patch (Standard Loading)
We maintain a manual patch in `node_modules/cozo-node/index.js` to expose native methods directly.
### The Shim (Fallback Loading)
In `db.ts`, when loading the binary directly, we implement a **Shim** that replicates the checking logic:
```typescript
open_db: (engine, path, options) => native.open_db(engine, path, JSON.stringify(options || {})) // <--- CRITICAL
```

## 3. CozoDB Parser Fragility
The CozoDB Datalog parser is sensitive to:
- **Multiline Strings**: Newlines in template literals can cause desync.
- **Empty Params**: Always pass `{}` if no params are used.
- **Type Downcasting**: Passing `null` to `path` in `open_db` can cause `failed to downcast any to string`. Use a string path or a descriptive constant.

## 4. Hardware/OS Constraints
- **Windows**: Requires VS Build Tools for native compilation if prebuilts fail.
- **VRAM**: CozoDB is disk-native (RocksDB); it does not compete for VRAM, but large FTS indices can bloat RAM. Limit file sizes to <500KB (Standard 053: FTS Poisoning).

> [!IMPORTANT]
> When updating dependencies, ALWAYS verify the `cozo-node/index.js` patch is still active. Automated builds may overwrite this file.
