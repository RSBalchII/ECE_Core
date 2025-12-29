import os
import sys
import subprocess
import asyncio
import uvicorn
import json
import uuid
import time
import random
import secrets
from collections import deque
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

# --- CRITICAL FIX: Force UTF-8 Output on Windows ---
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI(title="WebGPU Bridge")

# --- AUTH & CORS ---
AUTH_TOKEN = os.getenv("BRIDGE_TOKEN", "sovereign-secret")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def verify_token(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in ["/mobile", "/favicon.ico", "/logs", "/health", "/audit/server-logs", "/file-mod-time"]:
        return await call_next(request)
    if request.url.path.startswith("/models") or request.url.path.startswith("/v1/models"):
        return await call_next(request)
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer ") or auth_header.split(" ")[1] != AUTH_TOKEN:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return await call_next(request)

# --- STATE ---
workers: Dict[str, WebSocket] = { "chat": None, "embed": None }
active_requests: Dict[str, asyncio.Queue] = {}

# --- MODEL MANAGEMENT (No-Cache Serving) ---
class NoCacheStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    async def __call__(self, scope, receive, send):
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = message.get('headers', [])
                headers.extend([
                    (b"Cache-Control", b"no-store, no-cache, must-revalidate, proxy-revalidate"),
                    (b"Pragma", b"no-cache"),
                    (b"Expires", b"0"),
                ])
                message['headers'] = headers
            await send(message)
        await super().__call__(scope, receive, send_wrapper)

app.mount("/models", NoCacheStaticFiles(directory="models"), name="models")

# --- ANCHOR PROTOCOL: Spawn Native Shell ---
@app.post("/v1/system/spawn_shell")
async def spawn_shell(request: Request):
    """Launches anchor.py in a new visible PowerShell window."""
    try:
        print("🚀 Spawning Anchor Terminal...")
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        anchor_script = os.path.join(tools_dir, "anchor.py")
        
        # Windows-specific spawn
        if os.name == 'nt':
            cmd = f'Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd \'{tools_dir}\'; python anchor.py" -WindowStyle Normal'
            subprocess.Popen(["powershell", "-Command", cmd], shell=True)
        else:
            # Linux/Mac fallback (xterm)
            subprocess.Popen(["xterm", "-e", f"python3 {anchor_script}"], shell=False)

        return {"status": "spawned", "message": "Anchor Shell Launched"}
    except Exception as e:
        print(f"❌ Spawn Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- NEURAL SHELL PROTOCOL ---
@app.post("/v1/shell/exec")
async def shell_exec(request: Request):
    """
    Handles NL->Command translation via the connected Ghost (Chat Worker).
    Returns the suggested command to the client (Anchor) for local execution.
    """
    try:
        body = await request.json()
        prompt = body.get("prompt", "")
        
        if not workers["chat"]:
             return JSONResponse(status_code=503, content={"error": "Ghost Engine not connected. Launch the Headless Browser."})

        # Ask Ghost to translate
        req_id = str(uuid.uuid4())
        active_requests[req_id] = asyncio.Queue()
        
        system_prompt = "You are a Windows PowerShell expert. Output a JSON object with keys: 'command' (the exact powershell command) and 'explanation' (brief reasoning). Do not use markdown."
        
        await workers["chat"].send_json({
            "id": req_id,
            "type": "chat",
            "data": {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "stream": False
            }
        })
        
        # Wait for Ghost response
        raw_response = await asyncio.wait_for(active_requests[req_id].get(), timeout=30.0)
        del active_requests[req_id]
        
        # Parse Ghost response
        content = raw_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Clean markdown if present
        content = content.replace("```json", "").replace("```", "").strip()
        
        try:
            data = json.loads(content)
            return data # {command, explanation}
        except:
            # Fallback if model didn't output JSON
            return {"command": content, "explanation": "Raw model output"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# --- WEBSOCKET HANDLERS (Ghost Connection) ---
@app.websocket("/ws/{worker_type}")
async def websocket_endpoint(websocket: WebSocket, worker_type: str):
    await websocket.accept()
    workers[worker_type] = websocket
    print(f"✅ {worker_type.upper()} Ghost Connected")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            # Route responses to waiting HTTP requests
            if "id" in msg and msg["id"] in active_requests:
                await active_requests[msg["id"]].put(msg)
    except:
        workers[worker_type] = None
        print(f"❌ {worker_type.upper()} Ghost Disconnected")


@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    host = os.getenv("BRIDGE_HOST", "0.0.0.0")
    port = int(os.getenv("BRIDGE_PORT", "8080"))
    print(f"🔒 BRIDGE STARTED on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="error")
