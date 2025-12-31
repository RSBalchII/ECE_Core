import os
import sys
import subprocess
import asyncio
import time
import uvicorn
import json
import uuid
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

# --- CONFIGURATION ---
PORT = 8000  # The One Port
HOST = "0.0.0.0"

# Fix Windows Encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI(title="Anchor Core")

# --- CORS (Open Internal Borders) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STATE ---
workers: Dict[str, WebSocket] = {"chat": None}
active_requests: Dict[str, asyncio.Queue] = {}

# --- MODEL RESOLVE REDIRECT (for MLC-LLM compatibility) ---
# Handle the /resolve/main/ pattern that MLC-LLM expects for local models
@app.get("/models/{model_name}/resolve/main/{file_path}")
@app.head("/models/{model_name}/resolve/main/{file_path}")
@app.options("/models/{model_name}/resolve/main/{file_path}")
async def model_resolve_redirect(model_name: str, file_path: str, request: Request):
    """Redirect MLC-LLM /resolve/main/ requests to actual local model files"""
    import os
    from fastapi.responses import FileResponse, JSONResponse
    from starlette.responses import Response

    # Construct path to actual model file
    models_base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
    actual_path = os.path.join(models_base, model_name, file_path)

    # Check if the file exists in the actual model directory
    if os.path.exists(actual_path) and os.path.isfile(actual_path):
        # For HEAD requests, return a minimal response with correct headers
        if request.method == "HEAD":
            # Get file size for Content-Length header
            file_size = os.path.getsize(actual_path)
            return Response(
                status_code=200,
                headers={
                    "content-type": "application/json" if actual_path.endswith(('.json', '.config')) else "application/octet-stream",
                    "content-length": str(file_size)
                }
            )
        # For OPTIONS requests (CORS preflight), return appropriate headers
        elif request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "access-control-allow-origin": "*",
                    "access-control-allow-methods": "GET, HEAD, OPTIONS",
                    "access-control-allow-headers": "*",
                    "access-control-max-age": "86400"
                }
            )
        else:
            return FileResponse(actual_path)
    else:
        # If file doesn't exist, return 404
        return JSONResponse(status_code=404, content={"error": f"File {file_path} not found for model {model_name}"})


# --- STATIC ASSETS (No-Cache for Models) ---
class NoCacheStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    async def __call__(self, scope, receive, send):
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = message.get('headers', [])
                # Force browser to keep models in RAM, not Disk
                headers.extend([
                    (b"Cache-Control", b"no-store, no-cache, must-revalidate"),
                    (b"Pragma", b"no-cache"),
                    (b"Expires", b"0"),
                ])
                message['headers'] = headers
            await send(message)
        await super().__call__(scope, receive, send_wrapper)

# 1. Smart Model Redirect (Special No-Cache Handling)
# Look for models directory in the parent directory (project root)
models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
if not os.path.exists(models_dir):
    # If models directory doesn't exist, create it
    os.makedirs(models_dir, exist_ok=True)

# Create a custom route for models that checks locally first, then redirects to HuggingFace
@app.get("/models/{file_path:path}")
async def models_redirect(file_path: str):
    """Smart redirect: Check for local file first, redirect to HuggingFace if missing"""
    import os
    from fastapi.responses import FileResponse, RedirectResponse

    # Construct path to local model file
    local_path = os.path.join(models_dir, file_path)

    # Check if the file exists locally
    if os.path.exists(local_path) and os.path.isfile(local_path):
        # Serve the local file with no-cache headers (Standard 002)
        return NoCacheFileResponse(local_path)
    else:
        # File doesn't exist locally, redirect to HuggingFace
        print(f"⚠️ File not found locally, redirecting to HuggingFace: {file_path}")
        hf_url = f"https://huggingface.co/{file_path}"
        return RedirectResponse(url=hf_url, status_code=302)

# Also need to handle HEAD requests for the same path
@app.head("/models/{file_path:path}")
async def models_redirect_head(file_path: str):
    """Handle HEAD requests for model files with same redirect logic"""
    import os
    from starlette.responses import Response

    # Construct path to local model file
    local_path = os.path.join(models_dir, file_path)

    # Check if the file exists locally
    if os.path.exists(local_path) and os.path.isfile(local_path):
        # Return response with file size for HEAD request
        file_size = os.path.getsize(local_path)
        return Response(
            status_code=200,
            headers={
                "content-length": str(file_size),
                "content-type": "application/octet-stream",
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    else:
        # File doesn't exist locally, redirect to HuggingFace
        print(f"⚠️ HEAD request: File not found locally, redirecting to HuggingFace: {file_path}")
        hf_url = f"https://huggingface.co/{file_path}"
        return RedirectResponse(url=hf_url, status_code=302)

# Custom FileResponse class to apply NoCache headers (Standard 002)
class NoCacheFileResponse(FileResponse):
    async def __call__(self, scope, receive, send):
        # Apply the same cache control headers as NoCacheStaticFiles
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = message.get('headers', [])
                headers.extend([
                    (b"Cache-Control", b"no-store, no-cache, must-revalidate"),
                    (b"Pragma", b"no-cache"),
                    (b"Expires", b"0"),
                ])
                message['headers'] = headers
            await send(message)
        await super().__call__(scope, receive, send_wrapper)

# --- API ENDPOINTS (The Brain) ---
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxies chat requests to the Browser Engine (Ghost)"""
    if not workers["chat"]:
        return JSONResponse(status_code=503, content={"error": "Anchor Engine not connected. Open chat.html."})
    
    try:
        body = await request.json()
        req_id = str(uuid.uuid4())
        active_requests[req_id] = asyncio.Queue()
        
        await workers["chat"].send_json({
            "id": req_id,
            "type": "chat",
            "data": body
        })
        
        # Wait for response (Simple non-streaming for now, or stream handling could be added)
        # For simplicity in this unified view, we assume non-streaming or handle the first chunk
        response = await asyncio.wait_for(active_requests[req_id].get(), timeout=60.0)
        del active_requests[req_id]
        
        return response
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/shell/exec")
async def shell_exec(request: Request):
    """Executes system commands requested by the Engine"""
    try:
        body = await request.json()
        cmd = body.get("cmd") or body.get("command")
        if not cmd:
            return JSONResponse(status_code=400, content={"error": "No command provided"})
            
        print(f"⚓ EXEC: {cmd}")
        # Execute in native shell
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "code": proc.returncode
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/system/spawn_shell")
async def spawn_shell(request: Request):
    """Spawns a new PowerShell window running the Anchor terminal client"""
    try:
        print("⚓ SPAWN: Launching Anchor Shell")

        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Path to the anchor.py script
        anchor_script = os.path.join(script_dir, "anchor.py")

        # Command to start a new PowerShell window running the anchor client
        cmd = f'start "Anchor Terminal" powershell -NoExit -Command "cd {script_dir}; python anchor.py"'

        # Try to run the command to spawn a new window (non-blocking)
        subprocess.Popen(cmd, shell=True)

        return {"status": "spawned", "message": "Anchor terminal launched in new PowerShell window"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})




# --- MODEL DOWNLOAD ENDPOINTS ---
# Track model download status
model_download_status = {}

@app.post("/v1/models/pull")
async def pull_model(request: Request):
    """Download a model from HuggingFace to local storage"""
    try:
        body = await request.json()
        model_id = body.get("model_id")
        model_url = body.get("url")

        if not model_id:
            return JSONResponse(status_code=400, content={"error": "model_id is required"})

        print(f"📥 DOWNLOAD: Requested to pull model {model_id}")

        # Check if download is already in progress
        if model_id in model_download_status:
            if model_download_status[model_id]["status"] == "downloading":
                return JSONResponse(status_code=409, content={"error": "Download already in progress"})

        # For now, return a simulated response since full implementation would require complex download logic
        return {
            "status": "simulated",
            "model_id": model_id,
            "message": "Model download simulated - check if model exists locally"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/v1/models/pull/status")
async def get_pull_status(request: Request):
    """Get the status of a model download"""
    model_id = request.query_params.get("id")

    if not model_id:
        return JSONResponse(status_code=400, content={"error": "id parameter is required"})

    # Return simulated status for now
    return {
        "status": "done",  # Simulated as completed
        "progress": "100%",
        "file": "Download completed (simulated)"
    }


# --- GPU MANAGEMENT ENDPOINTS ---
# Track GPU state
gpu_state = {
    "locked": False,
    "owner": None,
    "queue_depth": 0,
    "queued": [],
    "hasPendingLoad": False,
    "activeLoaders": []
}

@app.post("/v1/gpu/lock")
async def gpu_lock(request: Request):
    """Acquire GPU lock for model loading"""
    try:
        body = await request.json()
        agent_id = body.get("id", "unknown")

        # For now, just return a token to simulate lock acquisition
        gpu_state["locked"] = True
        gpu_state["owner"] = agent_id
        gpu_state["queue_depth"] = 0  # Simplified

        return {"status": "acquired", "token": f"token_{agent_id}_{time.time()}"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/v1/gpu/unlock")
async def gpu_unlock(request: Request):
    """Release GPU lock"""
    try:
        body = await request.json()
        agent_id = body.get("id", "unknown")

        # Release the lock
        gpu_state["locked"] = False
        gpu_state["owner"] = None

        return {"status": "released"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/v1/gpu/status")
async def gpu_status(request: Request):
    """Get GPU status"""
    return {
        "locked": gpu_state["locked"],
        "owner": gpu_state["owner"],
        "queue_depth": gpu_state["queue_depth"],
        "queued": gpu_state["queued"],
        "hasPendingLoad": gpu_state["hasPendingLoad"],
        "activeLoaders": gpu_state["activeLoaders"]
    }


@app.post("/v1/gpu/reset")
async def gpu_reset(request: Request):
    """Reset GPU state"""
    try:
        gpu_state["locked"] = False
        gpu_state["owner"] = None
        gpu_state["queue_depth"] = 0
        gpu_state["queued"] = []

        return {"status": "reset"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/v1/gpu/force-release-all")
async def gpu_force_release_all(request: Request):
    """Force release all GPU locks"""
    try:
        gpu_state["locked"] = False
        gpu_state["owner"] = None
        gpu_state["queue_depth"] = 0
        gpu_state["queued"] = []
        gpu_state["hasPendingLoad"] = False
        gpu_state["activeLoaders"] = []

        return {"status": "all_released"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# --- WEBSOCKETS (The Nervous System) ---
@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    workers["chat"] = websocket
    print("✅ Anchor Engine Connected")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if "id" in msg and msg["id"] in active_requests:
                await active_requests[msg["id"]].put(msg)
    except:
        workers["chat"] = None
        print("❌ Anchor Engine Disconnected")

@app.get("/health")
async def health():
    return {"status": "nominal", "engine": "connected" if workers["chat"] else "waiting"}

# 2. Mount UI (The Face) - Must be last to catch all other routes
# Serves the current directory (tools/) as the root website
app.mount("/", StaticFiles(directory=".", html=True), name="ui")

if __name__ == "__main__":
    print(f"⚓ ANCHOR CORE RUNNING on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")