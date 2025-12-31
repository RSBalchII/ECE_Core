# Standard 007: Model Loading Transition - Online-Only Implementation

## What Happened?
The Anchor Console (`chat.html`) was experiencing hangs during model loading after GPU configuration, while the Anchor Mic (`anchor-mic.html`) worked perfectly with the same models. The issue was in the complex model loading approach in `chat.html` that attempted to use local model files with bridge downloads, creating a problematic flow that caused the loading process to stall after GPU initialization.

The old implementation in `chat.html` was trying to:
1. Check for local model files using the `/models/{model}/resolve/main/` pattern
2. Download models through the bridge if not found locally
3. Use a complex configuration with multiple model entries and local file resolution

This approach was causing the loading process to hang after the GPU configuration step, preventing models from loading properly.

## The Cost
- Hours spent debugging model loading failures in `chat.html`
- Confusion between working and failing components (anchor-mic.html vs chat.html)
- Inconsistent model loading across different UI components
- User frustration with non-functional chat interface
- Time wasted on attempting to fix complex local model resolution logic
- Delayed development due to complex debugging of the local file + bridge download approach

## The Rule
1. **Online-Only Model Loading**: For reliable model loading, use direct online URLs instead of complex local file resolution:
   ```javascript
   // Use direct HuggingFace URLs like anchor-mic.html
   const appConfig = {
       model_list: [{
           model: "https://huggingface.co/" + selectedModelId + "/resolve/main/",
           model_id: selectedModelId,
           model_lib: modelLib,  // WASM library URL
           // ... other config
       }],
       useIndexedDBCache: false, // Disable caching to prevent issues
   };
   ```

2. **Simplified Configuration**: Use the same straightforward approach as `anchor-mic.html` instead of complex multi-model configurations with local file resolution.

3. **Archive Complex Logic**: When a complex model loading approach fails, archive it for future reference while implementing a working solution:
   ```javascript
   // Archive the old function with a descriptive name
   async function loadModel_archived() {
       // Original complex implementation
   }
   
   // Implement the working online-only approach
   async function loadModel() {
       // Simplified online-only implementation
   }
   ```

4. **Fallback to Working Patterns**: When debugging model loading issues, compare with known working implementations (like `anchor-mic.html`) and adopt their patterns.

5. **Progressive Enhancement**: Start with a working online-only solution, then add local model loading capabilities in a separate iteration after the basic functionality is stable.

6. **Model Loading Verification**: Always test model loading with the same models across different UI components to ensure consistency.

## Implementation Pattern

### Working Online-Only Format (Recommended):
```javascript
// Based on the working anchor-mic.html implementation
async function loadModel() {
    // ... setup code ...
    
    const appConfig = {
        model_list: [{
            model: "https://huggingface.co/" + selectedModelId + "/resolve/main/",
            model_id: selectedModelId,
            model_lib: modelLib,  // WASM library URL from mapper
            vram_required_MB: 2000,
            low_resource_required: true,
            buffer_size_required_bytes: gpuConfig.maxBufferSize,
            overrides: {
                context_window_size: gpuConfig.isConstrained ? 2048 : 4096
            }
        }],
        useIndexedDBCache: false, // Disable caching to prevent issues
    };

    engine = await CreateWebWorkerMLCEngine(
        new Worker('./modules/llm-worker.js', { type: 'module' }),
        selectedModelId,
        {
            initProgressCallback: (report) => {
                // Progress reporting
            },
            appConfig: appConfig,
            logLevel: "INFO",
            useIndexedDBCache: false, // Force disable cache
        }
    );
}
```

### Complex Local Resolution (Problematic - Avoid):
```javascript
// DO NOT USE - This causes hangs after GPU configuration
// Complex local file checking and bridge download logic
const localModelUrl = `${window.location.origin}/models/${safeStrippedId}/ndarray-cache.json`;
const check = await fetch(localModelUrl, { method: 'HEAD' });
// ... complex download and resolution logic that causes hangs
```

## Transition Protocol

When transitioning model loading implementations:

1. **Identify Working Component**: Find a UI component that successfully loads models (e.g., `anchor-mic.html`)
2. **Analyze Working Pattern**: Study the model loading approach in the working component
3. **Archive Complex Logic**: Preserve the old implementation for future reference
4. **Implement Simple Approach**: Adopt the working pattern from the successful component
5. **Test Thoroughly**: Verify the new implementation works with multiple models
6. **Document Changes**: Record the transition in standards documentation

## Future Considerations

The archived local model loading approach should be revisited after further prototyping and debugging. The online-only approach provides immediate functionality while the more complex local approach can be refined separately without blocking development progress.