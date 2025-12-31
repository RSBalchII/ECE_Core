# Standard 010: Bridge Redirect Implementation - Smart Model Loading

## What Happened?
The Anchor Core system had inconsistent model loading behavior where some models worked and others didn't. The issue was that the bridge was only serving local files and returning 404 errors when files were missing, instead of providing fallback to online sources.

The browser components (like chat.html) were requesting model files from the local bridge (localhost:8000), but if the model hadn't been downloaded locally, they would fail with 404 errors instead of falling back to online loading.

## The Cost
- Models failing to load when not downloaded locally
- Inconsistent behavior across different model requests
- User frustration when models appear unavailable
- Complex debugging to understand the local vs online loading pathway

## The Rule
1. **Smart Redirect Pattern**: Implement the following pattern for model file requests:
   - **Check Local First**: When receiving a request for `/models/{file_path}`, first check if the file exists in the local models directory
   - **Serve Local**: If found locally, serve the file with proper no-cache headers to prevent browser caching issues
   - **Redirect Online**: If not found locally, redirect to the corresponding HuggingFace URL with HTTP 302 status

2. **NoCache Headers**: When serving local files, ensure proper cache-control headers are applied:
   ```python
   # Headers to apply to local file responses
   Cache-Control: no-store, no-cache, must-revalidate
   Pragma: no-cache
   Expires: 0
   ```

3. **Request Method Handling**: Handle both GET and HEAD requests appropriately:
   - **GET**: Return the file content or redirect
   - **HEAD**: Return headers with file size if local file exists, or redirect if missing

4. **Logging**: Log when files are not found locally and redirected to HuggingFace for debugging purposes

5. **Resilience**: The system must never fail to provide model files when they exist online, regardless of local download status

## Implementation Example
```python
@app.get("/models/{file_path:path}")
async def models_redirect(file_path: str):
    """Smart redirect: Check for local file first, redirect to HuggingFace if missing"""
    import os
    from fastapi.responses import FileResponse, RedirectResponse
    
    # Construct path to local model file
    models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
    local_path = os.path.join(models_dir, file_path)
    
    # Check if the file exists locally
    if os.path.exists(local_path) and os.path.isfile(local_path):
        # Serve the local file with no-cache headers
        return NoCacheFileResponse(local_path)
    else:
        # File doesn't exist locally, redirect to HuggingFace
        print(f"⚠️ File not found locally, redirecting to HuggingFace: {file_path}")
        hf_url = f"https://huggingface.co/{file_path}"
        return RedirectResponse(url=hf_url, status_code=302)
```

This ensures the system provides maximum resilience by falling back to online sources when local files are missing.