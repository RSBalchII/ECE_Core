import asyncio
import uvicorn
import json
import uuid
import os
import time
from collections import deque
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

app = FastAPI(title="WebGPU Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections
# We use a simple single-worker model for now (one browser tab per role)
workers: Dict[str, WebSocket] = {
    "chat": None,
    "embed": None
}

# Store pending response futures
# Map: request_id -> asyncio.Queue
active_requests: Dict[str, asyncio.Queue] = {}

import heapq

# --- GPU Priority Manager (The Traffic Cop) ---
class PriorityGPUManager:
    def __init__(self):
        self.current_owner: str = None
        self.locked_at: float = 0
        self.lock_token: str = None
        # Queue stores: (priority, timestamp, event, requester_id)
        # Using a list + sort is sufficient for small N (waiters < 10)
        self.queue = []
        # Track request start times to prevent starvation
        self.request_start_times = {}

    def _get_priority(self, requester_id: str) -> int:
        rid = requester_id.lower()
        if "mic" in rid: return 0        # 🚨 PRIORITY 1: Voice
        if "console" in rid: return 10   # 💬 PRIORITY 2: Chat
        if "chat" in rid: return 10
        if "dream" in rid: return 20     # 💤 PRIORITY 3: Dreaming
        return 15                        # Default

    async def acquire(self, requester_id: str, timeout: float = 120.0) -> tuple[bool, str]:
        """
        Waits for the lock based on PRIORITY with improved timeout handling.
        """
        priority = self._get_priority(requester_id)

        # Track when this request started to prevent starvation
        self.request_start_times[requester_id] = time.time()

        # 1. Fast Path: If free, take it immediately
        if self.current_owner is None:
            self._take_lock(requester_id)
            if requester_id in self.request_start_times:
                del self.request_start_times[requester_id]
            return True, self.lock_token

        # 2. Slow Path: Queue up
        event = asyncio.Event()
        # Tuple: (Priority, Time, Event, ID) -> Sorts by Priority asc, then Time asc
        entry = (priority, time.time(), event, requester_id)
        self.queue.append(entry)
        self.queue.sort(key=lambda x: (x[0], x[1])) # Strict sorting

        log(f"⏳ {requester_id} QUEUED (Priority {priority}). Pos: {self.queue.index(entry)+1}/{len(self.queue)}")

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            if requester_id in self.request_start_times:
                del self.request_start_times[requester_id]
            return True, self.lock_token
        except asyncio.TimeoutError:
            if entry in self.queue:
                self.queue.remove(entry)
                if requester_id in self.request_start_times:
                    del self.request_start_times[requester_id]
            log(f"💀 Timeout dropping {requester_id}")
            return False, None

    def release(self, requester_id: str, force: bool = False):
        if self.current_owner != requester_id and not force:
            return False

        duration = int(time.time() - self.locked_at)
        log(f"🔓 RELEASED by {requester_id} (Held {duration}s)")

        self.current_owner = None
        self.locked_at = 0
        self.lock_token = None

        # 3. Wake the Next Highest Priority
        if self.queue:
            # Pop index 0 (Lowest Priority Number = Highest Importance)
            prio, ts, event, next_id = self.queue.pop(0)
            if next_id in self.request_start_times:
                del self.request_start_times[next_id]
            self._take_lock(next_id)
            event.set() # Wake up the waiting coroutine
        else:
            # Clear any remaining request start times if queue is empty
            self.request_start_times.clear()

        return True

    def _take_lock(self, requester_id):
        self.current_owner = requester_id
        self.locked_at = time.time()
        self.lock_token = str(uuid.uuid4())
        log(f"🔒 LOCKED by {requester_id}")

    def get_status(self):
        return {
            "locked": self.current_owner is not None,
            "owner": self.current_owner,
            "queue_depth": len(self.queue),
            "queued": [x[3] for x in self.queue], # List queued IDs
            "request_start_times": {req_id: start_time for req_id, start_time in self.request_start_times.items()}
        }

    def force_release_all(self):
        """Emergency method to clear all locks and queues"""
        self.current_owner = None
        self.locked_at = 0
        self.lock_token = None
        # Cancel all waiting events
        for _, _, event, req_id in self.queue:
            event.set()  # Wake up all waiting coroutines
        self.queue.clear()
        self.request_start_times.clear()
        log("⚠️  ALL GPU LOCKS FORCE RELEASED")

gpu_lock = PriorityGPUManager()

@app.post("/v1/gpu/lock")
async def acquire_gpu_lock(request: Request):
    body = await request.json()
    requester = body.get("id", "unknown")
    # FIX: Increase timeout to match the Manager's capability (120s)
    success, token = await gpu_lock.acquire(requester, timeout=120.0)

    if success:
        return {"status": "acquired", "token": token}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "timeout", "msg": "GPU Queue Timeout"}
        )

@app.post("/v1/gpu/unlock")
async def release_gpu_lock(request: Request):
    body = await request.json()
    requester = body.get("id", "unknown")
    gpu_lock.release(requester)
    return {"status": "released"}

# Auto-release watchdog (Optional, for now handled by timeouts)
@app.post("/v1/gpu/reset")
async def reset_gpu_lock():
    gpu_lock.release("admin", force=True)
    return {"status": "reset"}

@app.post("/v1/gpu/force-release-all")
async def force_release_all_gpu_locks():
    """Emergency endpoint to clear all GPU locks and queues"""
    gpu_lock.force_release_all()
    return {"status": "all_gpu_locks_force_released"}

@app.get("/v1/gpu/status")
async def gpu_status():
    return gpu_lock.get_status()

# --- Logging / observability ---
# Keep a ring buffer of recent bridge logs for the HTML log viewer.
_LOG_MAX_LINES = int(os.getenv("BRIDGE_LOG_MAX_LINES", "5000"))
_LOG_MAX_CHARS_PER_LINE = int(os.getenv("BRIDGE_LOG_MAX_CHARS_PER_LINE", "400"))
# If enabled, log streamed content deltas (can be noisy but is what you want for prompt-pipeline debugging)
_LOG_STREAM_DELTAS = os.getenv("BRIDGE_LOG_STREAM_DELTAS", "true").strip().lower() in ("1", "true", "yes", "on")

_bridge_logs: deque[tuple[int, str]] = deque(maxlen=_LOG_MAX_LINES)
_bridge_log_seq: int = 0

# Per-request telemetry (timing/throughput)
_req_meta: Dict[str, Dict[str, Any]] = {}


def _clip(s: str, max_chars: int) -> str:
    if s is None:
        return ""
    s = str(s)
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"

def log(msg: str):
    import datetime
    from pathlib import Path
    
    timestamp = datetime.datetime.now().isoformat()
    entry = f"{timestamp} - {msg}"
    print(entry)
    global _bridge_log_seq
    _bridge_log_seq += 1
    _bridge_logs.append((_bridge_log_seq, entry))
        
    # Write to file
    try:
        log_path = Path("../backend/logs/webgpu_bridge.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}")

@app.get("/logs")
async def get_logs(limit: int = 200, since: int = 0):
    """Return recent bridge logs.

    Query params:
    - limit: max number of log lines to return
    - since: return only entries with seq > since

    Response:
    - logs: [{seq, line}, ...]
    - last_seq: latest sequence number currently available
    """
    # Snapshot to avoid holding references while iterating
    items = list(_bridge_logs)
    if since and since > 0:
        items = [it for it in items if it[0] > since]
    if limit and limit > 0:
        items = items[-limit:]
    last_seq = items[-1][0] if items else _bridge_log_seq
    return {
        "logs": [{"seq": seq, "line": line} for seq, line in items],
        "last_seq": last_seq,
    }


@app.post("/logs/clear")
async def clear_logs():
    _bridge_logs.clear()
    return {"ok": True}

@app.get("/v1/models")
async def list_models():
    """
    Return a list of available models.
    Since this is a bridge, we return the models currently loaded in the connected workers.
    """
    models = []
    
    if workers["chat"]:
        # We could query the worker for the actual model name, but for now we'll use a placeholder
        # or assume the client knows what it's doing.
        # Ideally, the worker should send its loaded model ID on connection.
        models.append({
            "id": "webgpu-chat",
            "object": "model",
            "created": 1677610602,
            "owned_by": "webgpu-bridge"
        })
        
    if workers["embed"]:
        models.append({
            "id": "webgpu-embedding",
            "object": "model",
            "created": 1677610602,
            "owned_by": "webgpu-bridge"
        })
        
    return {"object": "list", "data": models}


# --- Compatibility endpoint: audit/server-logs ---
# Some UI pages (log-viewer.html) expect '/audit/server-logs' provided by the full backend (ECE_Core).
# If that backend isn't running, provide a graceful fallback here that returns bridge logs so UI doesn't see 404s.
from pathlib import Path

@app.get('/audit/server-logs')
async def get_audit_server_logs(limit: int = 50):
    try:
        # Try known workspace locations for the backend server log (same heuristic used elsewhere)
        log_file = Path("logs/server.log")
        if not log_file.exists():
            log_file = Path("../logs/server.log")

        if log_file.exists():
            with log_file.open('r', encoding='utf-8', errors='ignore') as f:
                lines = f.read().splitlines()
            tail = lines[-int(limit):] if limit and len(lines) > 0 else lines
            return {"logs": tail, "count": len(tail)}

        # Fallback: serve bridge internal logs if backend log file not present
        items = list(_bridge_logs)[-int(limit):]
        tail = [line for (_seq, line) in items]
        return {"logs": tail, "count": len(tail)}
    except Exception as e:
        return {"logs": [f"Bridge audit logs error: {str(e)}"], "count": 0}

@app.websocket("/ws/{worker_type}")
async def websocket_endpoint(websocket: WebSocket, worker_type: str):
    if worker_type not in workers:
        await websocket.close(code=4000)
        return
    
    await websocket.accept()
    workers[worker_type] = websocket
    log(f"✅ {worker_type.upper()} Worker Connected")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Log token usage if present
            if "usage" in message:
                log(f"📊 Token Usage: {json.dumps(message['usage'])}")
            elif "chunk" in message and "usage" in message["chunk"]:
                 # Sometimes usage is inside the chunk
                 log(f"📊 Token Usage (Chunk): {json.dumps(message['chunk']['usage'])}")

            req_id = message.get("id")

            # Capture streamed token/chunk content for debugging.
            # The worker typically sends OpenAI-compatible SSE chunks under `chunk`.
            if req_id and isinstance(message, dict):
                # Handle chunk deltas
                if _LOG_STREAM_DELTAS and "chunk" in message:
                    try:
                        ch = message.get("chunk")
                        # Try chat-completions delta
                        if isinstance(ch, dict) and isinstance(ch.get("choices"), list) and ch["choices"]:
                            choice0 = ch["choices"][0] if isinstance(ch["choices"][0], dict) else {}
                            delta = choice0.get("delta") if isinstance(choice0, dict) else None
                            if isinstance(delta, dict) and "content" in delta:
                                piece = delta.get("content") or ""
                                if piece:
                                    log(f"Δ {req_id}: {_clip(piece, _LOG_MAX_CHARS_PER_LINE)}")
                                    meta = _req_meta.get(req_id)
                                    if meta is not None:
                                        meta["chars"] = int(meta.get("chars", 0)) + len(piece)
                                        meta["chunks"] = int(meta.get("chunks", 0)) + 1
                    except Exception:
                        pass

                # Handle token_events emitted by the browser worker
                if "token_events" in message and isinstance(message.get("token_events"), list):
                    try:
                        events = message.get("token_events")
                        meta = _req_meta.get(req_id)
                        for ev in events:
                            # Normalize fields
                            tidx = ev.get("idx")
                            ttext = _clip(ev.get("text", ""), _LOG_MAX_CHARS_PER_LINE)
                            tdt = float(ev.get("dt_ms") or ev.get("dt") or 0.0)
                            tlogp = ev.get("logprob")
                            # Log a compact token-line for the viewer to parse
                            log(f"TOK {req_id} IDX={tidx} DTms={tdt:.2f} TOK=" + ttext + (" LOGP=" + str(tlogp) if tlogp is not None else ""))
                            if meta is not None:
                                meta["chars"] = int(meta.get("chars", 0)) + len(ttext)
                                meta["chunks"] = int(meta.get("chunks", 0)) + 1
                    except Exception:
                        pass
            if req_id in active_requests:
                # Put the chunk/result into the queue for the HTTP handler to consume
                await active_requests[req_id].put(message)
                
    except Exception as e:
        log(f"❌ {worker_type.upper()} Worker Disconnected: {e}")
    finally:
        workers[worker_type] = None

async def stream_generator(req_id: str):
    queue = active_requests[req_id]
    try:
        while True:
            message = await queue.get()
            
            if message.get("error"):
                yield f"data: {json.dumps({'error': message['error']})}\n\n"
                break
                
            if message.get("done"):
                # Emit summary telemetry if available
                meta = _req_meta.pop(req_id, None)
                if meta is not None:
                    dt = max(1e-6, time.perf_counter() - float(meta.get("t0", time.perf_counter())))
                    chars = int(meta.get("chars", 0))
                    chunks = int(meta.get("chunks", 0))
                    log(f"✅ Done {req_id}: {chars} chars in {dt:.2f}s across {chunks} chunks (~{(chars / dt):.1f} chars/s)")
                yield "data: [DONE]\n\n"
                break
            
            # Forward the chunk exactly as received (OpenAI format)
            if "chunk" in message:
                yield f"data: {json.dumps(message['chunk'])}\n\n"
            
    finally:
        if req_id in active_requests:
            del active_requests[req_id]

async def collect_full_response(req_id: str):
    """
    Collects the full response for non-streaming requests.
    Aggregates chunks if the worker sends them as a stream.
    """
    queue = active_requests[req_id]
    
    # Initialize accumulator
    accumulated_content = ""
    first_chunk = None
    finish_reason = None
    
    try:
        while True:
            message = await queue.get()
            
            if message.get("error"):
                raise HTTPException(status_code=500, detail=message['error'])
                
            if message.get("done"):
                break
            
            if "chunk" in message:
                chunk = message["chunk"]
                
                # If it's a full response object (not a delta), just use it
                if "choices" in chunk and "message" in chunk["choices"][0]:
                    return chunk
                
                # Otherwise, accumulate deltas
                if not first_chunk:
                    first_chunk = chunk
                
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        accumulated_content += content
                    
                    if chunk["choices"][0].get("finish_reason"):
                        finish_reason = chunk["choices"][0]["finish_reason"]
                
    finally:
        if req_id in active_requests:
            del active_requests[req_id]

        meta = _req_meta.pop(req_id, None)
        if meta is not None:
            dt = max(1e-6, time.perf_counter() - float(meta.get("t0", time.perf_counter())))
            chars = int(meta.get("chars", 0))
            chunks = int(meta.get("chunks", 0))
            log(f"✅ Done {req_id}: {chars} chars in {dt:.2f}s across {chunks} chunks (~{(chars / dt):.1f} chars/s)")
            
    if not first_chunk:
        raise HTTPException(status_code=500, detail="No response received from WebGPU worker")
        
    # Construct final response object from accumulated chunks
    final_response = first_chunk.copy()
    final_response["object"] = "chat.completion"
    final_response["choices"] = [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": accumulated_content
        },
        "finish_reason": finish_reason or "stop"
    }]
        
    return final_response

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request):
    if not workers["chat"]:
        raise HTTPException(status_code=503, detail="WebGPU Chat Worker not connected. Open tools/webgpu-server-chat.html")
    
    body = await request.json()
    req_id = str(uuid.uuid4())
    active_requests[req_id] = asyncio.Queue()
    
    stream = body.get("stream", False)
    log(f"Chat Request: {req_id} - Model: {body.get('model')} - Stream: {stream}")
    # Track request timing/throughput
    _req_meta[req_id] = {"t0": time.perf_counter(), "chars": 0, "chunks": 0}

    # Forward request to browser
    await workers["chat"].send_json({
        "id": req_id,
        "type": "chat",
        "data": body
    })
    
    if stream:
        # Return streaming response
        return StreamingResponse(stream_generator(req_id), media_type="text/event-stream")
    else:
        # Return standard JSON response
        response_data = await collect_full_response(req_id)
        # Log a concise summary of the chat response for UI/bridge observability
        try:
            summary = None
            if isinstance(response_data, dict):
                # Try to extract assistant content if present
                choices = response_data.get('choices')
                if choices and isinstance(choices, list) and len(choices) > 0:
                    msg = choices[0].get('message') if isinstance(choices[0], dict) else None
                    if msg and isinstance(msg, dict):
                        content = msg.get('content') or ''
                        summary = content[:200]
            if summary is None:
                summary = str(response_data)[:200]
            log(f"[WEBGPU-CHAT] RESP {req_id}: {summary}")
        except Exception:
            pass
        return JSONResponse(content=response_data)

@app.post("/v1/embeddings")
async def embeddings(request: Request):
    if not workers["embed"]:
        raise HTTPException(status_code=503, detail="WebGPU Embed Worker not connected. Open tools/webgpu-server-embed.html")
    
    body = await request.json()
    
    # Override model name to match what the worker expects/has loaded
    # The worker is strict about the model name matching its loaded model
    # body["model"] = "snowflake-arctic-embed-m-q0f32-MLC-b32" 
    
    req_id = str(uuid.uuid4())
    active_requests[req_id] = asyncio.Queue()
    
    log(f"Embed Request: {req_id} - Input length: {len(str(body.get('input')))}")

    # Forward request to browser
    await workers["embed"].send_json({
        "id": req_id,
        "type": "embedding",
        "data": body
    })
    
    # Wait for the single response (Embeddings are usually not streamed, but we use the queue for async wait)
    response_msg = await active_requests[req_id].get()
    del active_requests[req_id]
    
    if response_msg.get("error"):
        raise HTTPException(status_code=500, detail=response_msg["error"])
        
    # Log a concise summary of embedding result for visibility
    try:
        res = response_msg.get('result')
        if res:
            summary = str(res)
            log(f"[WEBGPU-EMBED] RESP {req_id}: {summary[:200]}")
    except Exception:
        pass

    return JSONResponse(content=response_msg["result"])

import secrets
import random
import mimetypes

# --- Authentication & Config ---
AUTH_TOKEN = os.getenv("BRIDGE_TOKEN")
if not AUTH_TOKEN:
    AUTH_TOKEN = secrets.token_urlsafe(16) # Generate secure token if not set

# Middleware for Auth
@app.middleware("http")
async def verify_token(request: Request, call_next):
    # Allow OPTIONS (CORS preflight) and the mobile UI page itself
    if request.method == "OPTIONS" or request.url.path in ["/mobile", "/favicon.ico", "/logs", "/health", "/audit/server-logs"]:
        return await call_next(request)
    
    # Allow local loopback without token (optional, but convenient for localhost dev)
    # client_host = request.client.host
    # if client_host == "127.0.0.1" or client_host == "localhost":
    #     return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer ") or auth_header.split(" ")[1] != AUTH_TOKEN:
        # Return 401 but allows 403 for specific logic. 
        # Using JSON response to keep it clean.
        return JSONResponse(status_code=401, content={"error": "Unauthorized. Invalid Token."})

    return await call_next(request)

@app.get("/health")
async def health_check():
    """
    Simple health check for extensions and external tools.
    """
    return {"status": "ok", "service": "webgpu-bridge"}

@app.get("/mobile")
async def serve_mobile_app():
    """Serves the lightweight mobile chat interface."""
    file_path = "mobile-chat.html"
    # If not in current dir, check tools/
    if not os.path.exists(file_path):
        file_path = "tools/mobile-chat.html"
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Mobile App Not Found</h1><p>Ensure mobile-chat.html exists.</p>", status_code=404)

@app.post("/memories/search")
async def search_memories(request: Request):
    """
    Bridge endpoint for the Chrome Extension.
    Input: { "query": "User is typing about..." }
    Output: JSON array of relevant local memories.
    """
    # 1. Check if the Brain is connected
    if not workers["chat"]:
        raise HTTPException(status_code=503, detail="WebGPU Chat Worker not connected. Open tools/model-server-chat.html")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse(content=[])

    # 2. Create a Request ID to track this specific query
    req_id = str(uuid.uuid4())
    active_requests[req_id] = asyncio.Queue()
    
    # 3. Log the "Thought"
    log(f"🔎 Bridge Memory Search: {req_id} - '{_clip(query, 50)}'")

    try:
        # 4. Forward the signal to the Browser (Root Console) via WebSocket
        await workers["chat"].send_json({
            "id": req_id,
            "type": "memory_query", 
            "data": {"query": query}
        })
        
        # 5. Wait for the Brain to return the Context (Timeout: 3s for speed)
        response_msg = await asyncio.wait_for(active_requests[req_id].get(), timeout=3.0)
        
        if response_msg.get("error"):
            log(f"❌ Search Error {req_id}: {response_msg['error']}")
            raise HTTPException(status_code=500, detail=response_msg["error"])
        
        results = response_msg.get("result", [])
        log(f"✅ Served {len(results)} memories to Extension")
        return JSONResponse(content=results)

    except asyncio.TimeoutError:
        log(f"⏰ Search Timeout {req_id} - Browser didn't respond in 3s")
        del active_requests[req_id]
        raise HTTPException(status_code=504, detail="Query timed out")
    except Exception as e:
        if req_id in active_requests:
            del active_requests[req_id]
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import HTMLResponse


# --- NEURAL SHELL PROTOCOL (The Hands) ---
import subprocess

@app.post("/v1/shell/exec")
async def shell_exec(request: Request):
    """
    Executes a shell command on the host machine.
    Security: Protected by Bearer Token.
    """
    # 1. Verify Auth (Handled by Middleware)

    try:
        body = await request.json()
        cmd = body.get("cmd", "")

        if not cmd:
            return JSONResponse(status_code=400, content={"error": "No command provided"})

        log(f"💻 SHELL EXEC: {cmd}")

        # 2. Execute via Subprocess (PowerShell/CMD compatible)
        # timeout=30 prevents hanging processes
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            input="", # EOF to stdin: prevents hanging on interactive commands like 'powershell'
            timeout=30
        )

        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "code": proc.returncode,
            "cmd": cmd
        }

    except subprocess.TimeoutExpired:
        return JSONResponse(status_code=408, content={"error": "Command timed out (30s limit)"})
    except Exception as e:
        log(f"❌ Shell Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# --- SYSTEM SPAWN PROTOCOL (Fire-and-Forget) ---
@app.post("/v1/system/spawn_shell")
async def spawn_shell(request: Request):
    """
    Spawns a new PowerShell window running the Anchor terminal.
    This is a fire-and-forget operation that doesn't wait for output.
    """
    try:
        log("🚀 Spawning Anchor Terminal in new PowerShell window")

        # Determine the command to run the anchor script
        # Use absolute path to avoid issues with current working directory
        project_root = os.path.dirname(os.path.abspath(__file__))  # This gets the tools directory
        anchor_script_path = os.path.join(project_root, "anchor.py")

        cmd = f'start "Anchor Terminal" powershell -NoExit -Command "cd {project_root} && python anchor.py"'

        # Execute the command to spawn a new window (non-blocking)
        subprocess.Popen(
            cmd,
            shell=True
        )

        return {"status": "spawned", "message": "Anchor terminal launched in new PowerShell window"}

    except Exception as e:
        log(f"❌ Spawn Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    host = os.getenv("BRIDGE_HOST", "0.0.0.0")
    
    # Obfuscated / Random Port Logic
    default_port = os.getenv("BRIDGE_PORT")
    if default_port:
        port = int(default_port)
    else:
        # Pick a random port in the dynamic/private range to obscure services
        port = random.randint(9000, 9999)

    print("\n" + "="*60)
    print(f"SECURE BRIDGE STARTING")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   TOKEN: {AUTH_TOKEN}")
    print(f"   Mobile URL: http://{host}:{port}/mobile")
    print("="*60 + "\n")
    
    uvicorn.run(app, host=host, port=port)
