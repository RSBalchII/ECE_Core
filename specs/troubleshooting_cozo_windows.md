# Troubleshooting: CozoDB Native Module Loading

## Issue Description
The `cozo-node` native module fails to load on Windows systems with the following error:
```
Cannot find module '.../node_modules/cozo-node/native/6/cozo_node_prebuilt.node'
```

## Root Cause
This is a known issue with native Node.js modules on Windows systems. The `cozo-node` package relies on prebuilt binaries that may not be available for all Windows/Node.js combinations. This is documented in Standard 053: CozoDB Pain Points & OS Compatibility.

## Windows Binary Location
On Windows systems, the cozo-node binary may need to be placed at:
```
C:\Users\ECE_Core\engine\cozo_node_prebuilt.node
```

The binary can typically be found in the pnpm store at:
```
C:\Users\ECE_Core\node_modules\.pnpm\cozo-node@0.7.6\node_modules\cozo-node\native\6\cozo_node_prebuilt.node
```

## Current Behavior
- System runs in "Stateless Mode" using MockDB
- All native modules (Key Assassin, Atomizer, Fingerprint) continue to function
- File ingestion and processing work normally
- Data is not persisted between sessions

## Solutions

### Option 1: Use Alternative Platform
- CozoDB native modules work reliably on Linux/macOS
- Consider using WSL2 for development on Windows

### Option 2: Docker Deployment
- Use the official CozoDB Docker image for reliable deployment
- Mount volumes for persistent storage

### Option 3: Wait for Prebuilt Binaries
- Check for newer versions of cozo-node that include Windows prebuilt binaries
- Monitor releases for your specific Node.js version

### Option 4: Build from Source (Advanced)
- Install Rust toolchain (required for CozoDB compilation)
- Set up Windows build tools (Visual Studio Build Tools)
- Follow CozoDB compilation instructions

## Temporary Workaround
The system currently operates in stateless mode which is sufficient for:
- Testing native module functionality
- Validating the "Iron Lung" architecture
- Processing and refining files
- Running the core ECE pipeline

## Verification
To verify native modules are working (regardless of DB status):
- Look for: `[Atomizer] Loaded Native Accelerator (C++17) 🚀`
- Look for: `[Refiner] Loaded Native Accelerator (C++17) 🚀`
- Check Key Assassin reports: `Removed X Metadata Keys, Y Wrappers, and processed Z escape chars`

## Status
- Native modules: ✅ Working
- Database persistence: ❌ Not available on this platform
- Core functionality: ✅ Available in stateless mode

## Next Steps
1. For production deployment, consider Linux server
2. For development, use WSL2 or Docker
3. Monitor cozo-node releases for Windows compatibility updates