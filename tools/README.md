## Requirements

*   **Browser**: Chrome 113+, Edge 113+ (WebGPU required)
*   **GPU**: WebGPU-compatible (most modern GPUs)
*   **RAM**: 4GB+ for 7B models, 2GB+ for 1.5B models
*   **Storage**: IndexedDB for persistent memory (browser-managed)

## Corruption Recovery

If you see "Failed to convert Uint8Array to Vec<u8>" or WASM panics:
1. Click **🚨 Recover from Crash** button (appears automatically)
2. Or use **Nuke Database** for complete reset
3. Data export available before recovery for backup

## Quick Start: Zero Dependencies

### Option 1: Direct HTML (Recommended)
1. Open `tools/index.html` in Chrome/Edge
2. Click **Model Server Chat** → Select model → Start chatting
3. Click **Memory Builder** → Ingest your data
4. All processing happens in-browser via WebGPU/WASM

### Option 2: Extension Integration (Optional)
Install Chrome extension for automatic page context injection