# Standard 005: Model Loading Configuration

## What Happened?
Model loading failed due to various configuration issues including "Cannot find model record" errors, 404 errors for specific model types (OpenHermes, NeuralHermes), and improper model ID to URL mapping. The bridge also had issues accepting model names during embedding requests, causing 503 errors.

## The Cost
- Failed model initialization preventing AI functionality
- Multiple 404 errors for specific model types
- 503 errors during embedding requests
- Hours spent debugging model configuration issues
- Unreliable model loading across different model types

## The Rule
1. **Model ID Mapping:** Always map alternative model names to verified WASM libraries:
   ```python
   # Example mapping for problematic models
   MODEL_MAPPINGS = {
       'OpenHermes': 'Mistral-v0.3',
       'NeuralHermes': 'Mistral-v0.3',
       # Add other mappings as needed
   }
   ```

2. **Bridge Configuration:** Configure the bridge to accept any model name to prevent 503 errors:
   ```python
   # In webgpu_bridge.py - ensure flexible model name handling
   # Don't validate model names strictly on the bridge side
   ```

3. **Decouple Internal IDs:** Separate internal model IDs from HuggingFace URLs to prevent configuration mismatches:
   ```javascript
   // In frontend code
   const internalModelId = getModelInternalId(userModelName);
   const modelUrl = getModelUrl(internalModelId);
   ```

4. **Verification Registry:** Maintain `specs/mlc-urls.md` as a registry for verified WASM binaries to ensure compatibility.

5. **Bridge-Based URLs:** Use bridge-based model URLs (`http://localhost:8080/models/`) with comprehensive cache-disabling configuration to prevent Cache API errors.