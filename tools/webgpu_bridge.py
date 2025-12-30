import os
import sys
import subprocess
import asyncio
import uvicorn
import json
import uuid
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse, FileResponse
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

# 1. Mount Models (Special No-Cache Handling)
# Look for models directory in the parent directory (project root)
models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
if os.path.exists(models_dir):
    app.mount("/models", NoCacheStaticFiles(directory=models_dir), name="models")
else:
    # If models directory doesn't exist, mount an empty directory or skip
    # For now, let's mount the models directory from the tools directory as fallback
    fallback_models_dir = os.path.join(os.path.dirname(__file__), "models")
    if os.path.exists(fallback_models_dir):
        app.mount("/models", NoCacheStaticFiles(directory=fallback_models_dir), name="models")
    else:
        # Create a temporary empty directory for models if none exists
        os.makedirs(fallback_models_dir, exist_ok=True)
        app.mount("/models", NoCacheStaticFiles(directory=fallback_models_dir), name="models")

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