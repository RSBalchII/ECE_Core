import asyncio
import uvicorn
import json
import uuid
import os
import time
from collections import deque
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
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
    if request.method == "OPTIONS" or request.url.path in ["/mobile", "/favicon.ico", "/logs"]:
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

from fastapi.responses import HTMLResponse

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
    print(f"🔒 SECURE BRIDGE STARTING")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   🔑 TOKEN: {AUTH_TOKEN}")
    print(f"   📱 Mobile URL: http://{host}:{port}/mobile")
    print("="*60 + "\n")
    
    uvicorn.run(app, host=host, port=port)
