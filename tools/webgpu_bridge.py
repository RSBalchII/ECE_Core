import os
import sys
import asyncio
import uuid
import json
import time
import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

# --- CONFIGURATION ---
PORT = 8000
HOST = "0.0.0.0"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# --- LOG COLLECTION ---
import datetime
import asyncio
from collections import deque
import os
from datetime import datetime as dt

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(logs_dir, exist_ok=True)

# Global log buffer for collecting system logs
MAX_LOG_ENTRIES = 5000
log_buffer = deque(maxlen=MAX_LOG_ENTRIES)
log_buffer_lock = asyncio.Lock()

async def add_log_entry(source: str, log_type: str, message: str):
    """Add a log entry to the global log buffer and save to file"""
    global log_buffer
    async with log_buffer_lock:
        log_entry = {
            "timestamp": dt.now().isoformat(),
            "source": source,
            "type": log_type,
            "message": message
        }
        log_buffer.append(log_entry)

        # Also write to individual log file with truncation
        try:
            log_file_path = os.path.join(logs_dir, f"{source.lower().replace('-', '_').replace(' ', '_')}.log")

            # Read existing content and truncate if needed
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Keep only last 5000 lines
                if len(lines) >= 5000:
                    lines = lines[-4500:]  # Keep last 4500 to have room for new entries

                # Write back truncated content plus new entry
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                # Append the new log entry
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    f.write(f"[{dt.now().strftime('%Y-%m-%d %H:%M:%S')}] [{log_type.upper()}] {message}\n")
            else:
                # File doesn't exist, create it with the new entry
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    f.write(f"[{dt.now().strftime('%Y-%m-%d %H:%M:%S')}] [{log_type.upper()}] {message}\n")
        except Exception:
            # If file writing fails, just continue
            pass

async def get_recent_logs(limit: int = 100):
    """Get recent log entries"""
    async with log_buffer_lock:
        recent_logs = list(log_buffer)[-limit:]
        return recent_logs

# Initialize with startup message - defer until after event loop starts
def initialize_logging():
    # This will be called when the app starts up
    pass

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await add_log_entry("System", "info", f"Anchor Core started on port {PORT}")
    await add_log_entry("Resurrection", "info", "Launching Ghost Engine (headless browser)...")
    asyncio.create_task(resurrection_manager.launch_browser())
    
    yield
    
    # Shutdown
    await add_log_entry("System", "info", "Shutting down Anchor Core...")
    await resurrection_manager.terminate_browser()

app = FastAPI(title="Anchor Core (Text-Only)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STATE ---
workers: Dict[str, WebSocket] = {"chat": None}
active_requests: Dict[str, asyncio.Queue] = {}

# --- AUTO-RESURRECTION STATE ---
class ResurrectionManager:
    """Manages automatic restart of Ghost Engine (headless browser)."""
    def __init__(self):
        self.browser_process = None
        self.resurrection_task = None
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.launch_command = self._get_launch_command()

    def _get_launch_command(self) -> list:
        """Get the appropriate launch command for the headless browser."""
        import tempfile
        temp_dir = tempfile.gettempdir()

        if sys.platform == "win32":
            # Detect Edge Path
            edge_path = "msedge" # Fallback
            possible_paths = [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    edge_path = path
                    break
            
            # Base Windows Command
            base_cmd = [
                edge_path,
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-extensions",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-ipc-flooding-protection",
                "--disable-background-media-suspend",
                "--remote-debugging-port=9222",
                f"--user-data-dir={temp_dir}/anchor_ghost_{int(time.time())}"
            ]

            # Append mode-specific flags
            if os.environ.get("LOW_RESOURCE_MODE") == "true":
                base_cmd.extend([
                    "--max-active-webgl-contexts=1",
                    "--max-webgl-contexts-per-group=1",
                    "--disable-gpu-memory-buffer-compositor-resources",
                    "--force-gpu-mem-available-mb=64",
                    "--force-low-power-gpu"
                ])
            elif os.environ.get("CPU_ONLY_MODE") == "true":
                base_cmd.extend([
                    "--force-low-power-gpu",
                    "--disable-gpu-sandbox",
                    "--disable-features=VizDisplayCompositor"
                ])

            # Append Target URL
            base_cmd.append(f"http://localhost:{PORT}/ghost.html?headless=true")
            return base_cmd

        else:
            # Linux/Mac: Use Chrome
            return [
                "google-chrome",
                "--headless",
                "--no-first-run",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-ipc-flooding-protection",
                "--disable-background-media-suspend",
                "--remote-debugging-port=9222",  # Explicitly set port to avoid conflicts
                f"--user-data-dir={temp_dir}/anchor_ghost_{int(time.time())}",  # Unique temp profile
                f"http://localhost:{PORT}/ghost.html?headless=true"
            ]

    async def kill_existing_browsers(self):
        """Kill any existing browser processes to prevent port conflicts."""
        import psutil
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() in ['msedge.exe', 'chrome.exe', 'chromium-browser']:
                        await add_log_entry("Resurrection", "info", f"Killing existing browser process: {proc.info['name']} (PID: {proc.info['pid']})")
                        proc.kill()
                        proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    continue
        except Exception as e:
            await add_log_entry("Resurrection", "warning", f"Error killing existing browsers: {str(e)}")

        # Clean up old temporary browser profiles
        await self._cleanup_old_profiles()

    async def _cleanup_old_profiles(self):
        """Clean up old temporary browser profiles to prevent disk space issues."""
        import tempfile
        import shutil
        import glob
        from datetime import datetime, timedelta

        try:
            temp_dir = tempfile.gettempdir()
            # Find all anchor_ghost temporary directories
            pattern = os.path.join(temp_dir, "anchor_ghost_*")
            temp_dirs = glob.glob(pattern)

            # Remove directories older than 1 day
            cutoff_time = datetime.now() - timedelta(days=1)
            for temp_dir_path in temp_dirs:
                try:
                    # Extract timestamp from directory name
                    dir_name = os.path.basename(temp_dir_path)
                    if '_' in dir_name:
                        timestamp_str = dir_name.split('_')[-1]
                        try:
                            dir_time = datetime.fromtimestamp(int(timestamp_str))
                            if dir_time < cutoff_time:
                                shutil.rmtree(temp_dir_path, ignore_errors=True)
                                await add_log_entry("Resurrection", "info", f"Cleaned up old browser profile: {temp_dir_path}")
                        except ValueError:
                            # If timestamp parsing fails, just remove old directories
                            shutil.rmtree(temp_dir_path, ignore_errors=True)
                            await add_log_entry("Resurrection", "info", f"Cleaned up browser profile: {temp_dir_path}")
                except Exception as e:
                    await add_log_entry("Resurrection", "warning", f"Error cleaning up profile {temp_dir_path}: {str(e)}")
        except Exception as e:
            await add_log_entry("Resurrection", "warning", f"Error during profile cleanup: {str(e)}")

    async def launch_browser(self):
        """Launch the headless browser process."""
        import subprocess
        # Kill any existing browser processes first to prevent port conflicts
        await self.kill_existing_browsers()

        try:
            self.browser_process = subprocess.Popen(
                self.launch_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            await add_log_entry("Resurrection", "success", f"Browser launched with PID {self.browser_process.pid}")
            return True
        except Exception as e:
            await add_log_entry("Resurrection", "error", f"Failed to launch browser: {str(e)}")
            return False

    async def terminate_browser(self):
        """Terminate the browser process."""
        if self.browser_process:
            try:
                self.browser_process.terminate()
                self.browser_process.wait(timeout=5)
                await add_log_entry("Resurrection", "info", "Browser process terminated")
            except Exception as e:
                await add_log_entry("Resurrection", "warning", f"Error terminating browser: {str(e)}")
                if self.browser_process.poll() is None:
                    self.browser_process.kill()
            self.browser_process = None
    
    async def resurrect_with_retry(self):
        """Attempt to resurrect the browser with retry logic."""
        global workers
        for attempt in range(self.max_retries):
            try:
                # Kill any existing browser processes before attempting resurrection
                await self.kill_existing_browsers()
                await asyncio.sleep(self.retry_delay)

                if await self.launch_browser():
                    # Wait for browser to connect
                    await asyncio.sleep(5)  # Increased wait time to allow for full initialization
                    if workers["chat"] is not None:
                        await add_log_entry("Resurrection", "success", f"Ghost Engine resurrected on attempt {attempt + 1}")
                        return True
                else:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                await add_log_entry("Resurrection", "error", f"Resurrection attempt {attempt + 1} failed: {str(e)}")

        await add_log_entry("Resurrection", "error", f"Failed to resurrect browser after {self.max_retries} attempts")
        return False

resurrection_manager = ResurrectionManager()

# --- GPU RESOURCE MANAGEMENT ---
import asyncio
from collections import deque

# GPU state management
gpu_state = {
    "locked": False,
    "owner": None,
    "queue": deque(),  # Queue for pending GPU requests
    "queue_lock": asyncio.Lock()  # Lock for queue operations
}

# --- STATIC & MODELS ---
import mimetypes
from pathlib import Path
from urllib.parse import unquote

class BinaryFileResponse(FileResponse):
    """Stream large binary files with proper headers and no caching."""
    def __init__(self, path, **kwargs):
        super().__init__(path, **kwargs)
        self.media_type = self._get_mime_type(path)

    @staticmethod
    def _get_mime_type(path: str) -> str:
        """Determine MIME type for model files."""
        _, ext = os.path.splitext(path.lower())
        mime_map = {
            '.wasm': 'application/wasm',
            '.json': 'application/json',
            '.bin': 'application/octet-stream',
            '.safetensors': 'application/octet-stream',
            '.txt': 'text/plain',
            '.md': 'text/markdown'
        }
        return mime_map.get(ext, 'application/octet-stream')

    async def __call__(self, scope, receive, send):
        # Add no-cache headers for model files
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                # Remove any existing cache-control headers
                headers = [(k, v) for k, v in headers if k.lower() != b'cache-control']
                # Add proper headers for large files
                headers.extend([
                    (b"Cache-Control", b"public, max-age=604800"),  # Cache 1 week for immutable files
                    (b"Accept-Ranges", b"bytes"),
                    (b"X-Content-Type-Options", b"nosniff")
                ])
                message['headers'] = headers
            await send(message)
        await super().__call__(scope, receive, send_wrapper)

models_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "models"))

@app.get("/models/{file_path:path}")
async def serve_model_file(file_path: str):
    """Serve model files from local directory with fallback to HuggingFace.
    
    Expected structure:
      models/Qwen2.5-7B-Instruct-q4f16_1-MLC/resolve/main/model.safetensors
    """
    try:
        # Decode URL-encoded path
        file_path = unquote(file_path)
        
        # Prevent directory traversal
        requested_path = os.path.abspath(os.path.join(models_dir, file_path))
        if not requested_path.startswith(models_dir):
            await add_log_entry("Model-Server", "warning", f"Directory traversal attempt blocked: {file_path}")
            return JSONResponse(status_code=403, content={"error": "Access denied"})
        
        # Serve from local directory if file exists
        if os.path.exists(requested_path) and os.path.isfile(requested_path):
            file_size = os.path.getsize(requested_path)
            await add_log_entry("Model-Server", "info", f"Serving local model file: {file_path} ({file_size} bytes)")
            return BinaryFileResponse(requested_path, media_type=BinaryFileResponse._get_mime_type(requested_path))
        
        # Fall back to HuggingFace for missing files
        hf_url = f"https://huggingface.co/{file_path.replace('/resolve/main/', '/resolve/main/')}"
        await add_log_entry("Model-Server", "info", f"File not found locally, redirecting to: {hf_url}")
        return RedirectResponse(url=hf_url, status_code=307)
        
    except Exception as e:
        await add_log_entry("Model-Server", "error", f"Error serving model file {file_path}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.head("/models/{file_path:path}")
async def check_model_file(file_path: str):
    """Check model file availability and return headers."""
    from starlette.responses import Response
    try:
        file_path = unquote(file_path)
        requested_path = os.path.abspath(os.path.join(models_dir, file_path))

        # Prevent directory traversal
        if not requested_path.startswith(models_dir):
            return Response(status_code=403)

        # Return headers for local file
        if os.path.exists(requested_path) and os.path.isfile(requested_path):
            file_size = os.path.getsize(requested_path)
            return Response(
                status_code=200,
                headers={
                    "content-length": str(file_size),
                    "content-type": BinaryFileResponse._get_mime_type(requested_path),
                    "accept-ranges": "bytes"
                }
            )

        # Check upstream
        hf_url = f"https://huggingface.co/{file_path}"
        return Response(status_code=307, headers={"location": hf_url})

    except Exception as e:
        return Response(status_code=500)

# --- MODEL RESOLVE REDIRECT (for MLC-LLM compatibility) ---
# Handle the /resolve/main/ pattern that MLC-LLM expects for local models
@app.get("/models/{model_name}/resolve/main/{file_path:path}")
async def model_resolve_redirect_get(model_name: str, file_path: str):
    """Handle GET requests for MLC-LLM /resolve/main/ requests"""
    from fastapi.responses import FileResponse, RedirectResponse

    # Construct path to actual model file
    actual_path = os.path.join(models_dir, model_name, file_path)

    # Check if the file exists in the actual model directory
    if os.path.exists(actual_path) and os.path.isfile(actual_path):
        await add_log_entry("Model-Resolve", "info", f"Serving local model file: {model_name}/{file_path}")
        return BinaryFileResponse(actual_path)
    else:
        # If file doesn't exist locally, redirect to HuggingFace (Standard 009 Bridge Redirect Logic)
        await add_log_entry("Model-Resolve", "info", f"File not found locally, redirecting to HuggingFace: {model_name}/resolve/main/{file_path}")
        hf_url = f"https://huggingface.co/mlc-ai/{model_name}/resolve/main/{file_path}"
        return RedirectResponse(url=hf_url, status_code=307)

@app.head("/models/{model_name}/resolve/main/{file_path:path}")
async def model_resolve_redirect_head(model_name: str, file_path: str):
    """Handle HEAD requests for MLC-LLM /resolve/main/ requests"""
    from starlette.responses import Response

    # Construct path to actual model file
    actual_path = os.path.join(models_dir, model_name, file_path)

    # Check if the file exists in the actual model directory
    if os.path.exists(actual_path) and os.path.isfile(actual_path):
        # Get file size for Content-Length header
        file_size = os.path.getsize(actual_path)
        await add_log_entry("Model-Resolve", "info", f"Model file exists locally: {model_name}/{file_path} ({file_size} bytes)")
        return Response(
            status_code=200,
            headers={
                "content-length": str(file_size),
                "content-type": BinaryFileResponse._get_mime_type(actual_path),
                "accept-ranges": "bytes"
            }
        )
    else:
        # If file doesn't exist locally, redirect to HuggingFace (Standard 009 Bridge Redirect Logic)
        await add_log_entry("Model-Resolve", "info", f"HEAD request: File not found locally, redirecting to HuggingFace: {model_name}/resolve/main/{file_path}")
        hf_url = f"https://huggingface.co/mlc-ai/{model_name}/resolve/main/{file_path}"
        return Response(status_code=307, headers={"location": hf_url})

@app.options("/models/{model_name}/resolve/main/{file_path:path}")
async def model_resolve_redirect_options(model_name: str, file_path: str):
    """Handle OPTIONS requests for MLC-LLM /resolve/main/ requests"""
    # For OPTIONS requests (CORS preflight), return appropriate headers
    return Response(
        status_code=200,
        headers={
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET, HEAD, OPTIONS",
            "access-control-allow-headers": "*",
            "access-control-max-age": "86400"
        }
    )

# --- GPU MANAGEMENT ENDPOINTS ---
@app.post("/v1/gpu/lock")
async def gpu_lock(request: Request):
    """Acquire GPU lock with queuing mechanism"""
    try:
        body = await request.json()
        agent_id = body.get("id", "unknown")

        # Add to queue and wait for turn
        async with gpu_state["queue_lock"]:
            request_id = str(uuid.uuid4())
            queue_item = {
                "id": request_id,
                "agent_id": agent_id,
                "acquired": asyncio.Event()
            }

            # If GPU is not locked, acquire immediately without queuing
            if not gpu_state["locked"]:
                gpu_state["locked"] = True
                gpu_state["owner"] = agent_id
                queue_item["acquired"].set()
            else:
                # Otherwise, add to queue and wait for turn
                gpu_state["queue"].append(queue_item)

        # Wait for GPU to be available
        await queue_item["acquired"].wait()

        # Return a token to represent the lock
        token = f"gpu_token_{agent_id}_{request_id}_{int(time.time())}"
        await add_log_entry("GPU-Manager", "info", f"GPU lock acquired by {agent_id} (token: {token[:20]}...)")
        return {"status": "acquired", "token": token, "queue_position": 0}
    except Exception as e:
        await add_log_entry("GPU-Manager", "error", f"GPU lock failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/gpu/unlock")
async def gpu_unlock(request: Request):
    """Release GPU lock and process next in queue"""
    try:
        body = await request.json()
        agent_id = body.get("id", "unknown")

        # Release the lock for this agent
        if gpu_state["owner"] == agent_id and gpu_state["locked"]:
            gpu_state["locked"] = False
            gpu_state["owner"] = None

            # Process next item in queue if available
            async with gpu_state["queue_lock"]:
                if gpu_state["queue"]:
                    next_item = gpu_state["queue"].popleft()
                    gpu_state["locked"] = True
                    gpu_state["owner"] = next_item["agent_id"]
                    next_item["acquired"].set()

                    await add_log_entry("GPU-Manager", "info", f"GPU lock transferred to next in queue: {next_item['agent_id']}")
                # If no items in queue, state remains unlocked with no owner

        await add_log_entry("GPU-Manager", "info", f"GPU lock released by {agent_id}")
        return {"status": "released"}
    except Exception as e:
        await add_log_entry("GPU-Manager", "error", f"GPU unlock failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/v1/gpu/status")
async def gpu_status(request: Request):
    """Get GPU status"""
    status = {
        "locked": gpu_state["locked"],
        "owner": gpu_state["owner"],
        "queue_length": len(gpu_state["queue"]),
        "queue_depth": len(gpu_state["queue"])  # For compatibility
    }
    return status

@app.post("/v1/gpu/reset")
async def gpu_reset(request: Request):
    """Reset GPU state"""
    gpu_state["locked"] = False
    gpu_state["owner"] = None
    async with gpu_state["queue_lock"]:
        gpu_state["queue"].clear()
    await add_log_entry("GPU-Manager", "info", "GPU state reset")
    return {"status": "reset"}

@app.post("/v1/gpu/force-release-all")
async def gpu_force_release_all(request: Request):
    """Force release all GPU locks"""
    gpu_state["locked"] = False
    gpu_state["owner"] = None
    async with gpu_state["queue_lock"]:
        # Notify all queued items that they can't acquire the lock
        while gpu_state["queue"]:
            item = gpu_state["queue"].popleft()
            # Don't set acquired event since we're cancelling
        gpu_state["queue"].clear()
@app.post("/v1/system/spawn_shell")
async def spawn_shell():
    """Launch the native PowerShell Anchor Terminal."""
    import subprocess
    try:
        # Determine the correct path to anchor.py
        anchor_script = os.path.join(os.path.dirname(__file__), "anchor.py")
        
        if sys.platform == "win32":
            # Launch in a new command window
            subprocess.Popen(
                f'start "Anchor Terminal" cmd /k python "{anchor_script}"', 
                shell=True,
                cwd=os.path.dirname(__file__)
            )
        else:
            # Linux/Mac fallback (attempt to use xterm or similar, though strictly Windows OS env for this user)
            subprocess.Popen(
                ["x-terminal-emulator", "-e", f"python3 {anchor_script}"],
                cwd=os.path.dirname(__file__)
            )
            
        await add_log_entry("System-API", "success", "Spawned Anchor Shell")
        return {"status": "success", "message": "Terminal spawned"}
    except Exception as e:
        await add_log_entry("System-API", "error", f"Failed to spawn shell: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/shell/exec")
async def shell_exec(request: Request):
    """Execute a system command and return output."""
    import subprocess
    
    try:
        body = await request.json()
        
        # Handle "Neural Mode" where terminal asks for "prompt" instead of "cmd"
        if "prompt" in body:
             # Just a placeholder for now as the logic for "Brain" connection isn't fully migrated 
             # to the bridge yet, but we need to prevent 500 error.
             # In a full implementation, this would query the LLM to get a command.
             return JSONResponse(content={"error": "Neural Shell requires an active LLM session. Feature pending migration."})

        cmd = body.get("cmd", "").strip()
        if not cmd:
            return JSONResponse(status_code=400, content={"error": "Command required"})

        await add_log_entry("Shell-API", "info", f"Executing: {cmd}")
        
        # Execute command
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd() 
        )
        
        stdout, stderr = process.communicate(timeout=30)
        
        return {
            "cmd": cmd,
            "stdout": stdout,
            "stderr": stderr,
            "code": process.returncode
        }

    except subprocess.TimeoutExpired:
        process.kill()
        return JSONResponse(status_code=408, content={"error": "Command timed out","stdout": "", "stderr": "Timeout"})
    except Exception as e:
        await add_log_entry("Shell-API", "error", f"Shell execution failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- CHAT COMPLETION WITH GPU QUEUING ---
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxies chat to Ghost Engine and accumulates the stream."""
    if not workers["chat"]:
        await add_log_entry("Chat-API", "error", "Ghost Engine Disconnected - The headless browser is not connected.")
        return JSONResponse(status_code=503, content={"error": "Ghost Engine Disconnected", "message": "The headless browser is not connected."})

    try:
        body = await request.json()
        req_id = str(uuid.uuid4())
        active_requests[req_id] = asyncio.Queue()

        # Forward request to Ghost Engine
        await workers["chat"].send_json({"id": req_id, "type": "chat", "data": body})
        await add_log_entry("Chat-API", "info", f"Forwarded chat request {req_id} to Ghost Engine")

        # Accumulate the stream from the browser into one big response
        full_content = ""
        while True:
            # Wait 60s max per chunk
            msg = await asyncio.wait_for(active_requests[req_id].get(), timeout=60.0)

            # Check for stream end or error
            if isinstance(msg, dict):
                if msg.get("done"):
                    await add_log_entry("Chat-API", "info", f"Chat request {req_id} completed successfully")
                    break
                if msg.get("error"):
                    # Check if it's a WebGPU adapter error and provide helpful message
                    error_msg = msg.get("error", "")
                    await add_log_entry("Chat-API", "error", f"Chat request {req_id} error: {str(error_msg)}")
                    if "No WebGPU Adapter found" in str(error_msg) or "GPU crash" in str(error_msg):
                        del active_requests[req_id]
                        return {
                            "id": req_id,
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "choices": [{
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "⚠️ WebGPU Adapter not found. This device may not support WebGPU acceleration. Try using a CPU-based model or check GPU drivers. Error: " + str(error_msg)
                                },
                                "finish_reason": "stop"
                            }]
                        }
                    return JSONResponse(status_code=500, content=msg)
                # Handle direct object response (non-streaming)
                if msg.get("choices"):
                    await add_log_entry("Chat-API", "info", f"Received direct response for request {req_id}")
                    return msg

            # Append chunk content
            if isinstance(msg, dict) and "chunk" in msg:
                chunk = msg["chunk"]
                # Parse OpenAI chunk format
                if isinstance(chunk, dict):
                    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    full_content += content

        del active_requests[req_id]

        # Return standard OpenAI non-streaming response
        await add_log_entry("Chat-API", "info", f"Returning completed response for request {req_id}")
        return {
            "id": req_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": full_content}, "finish_reason": "stop"}]
        }

    except asyncio.TimeoutError:
        await add_log_entry("Chat-API", "error", f"Chat request {req_id} timed out after 60 seconds")
        if req_id in active_requests: del active_requests[req_id]
        return {
            "id": req_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "⚠️ Request timed out. The model may not be loaded or WebGPU adapter is unavailable. Please check that the Ghost Engine is running and has access to GPU resources."
                },
                "finish_reason": "stop"
            }]
        }
    except Exception as e:
        await add_log_entry("Chat-API", "error", f"Chat request {req_id} failed with exception: {str(e)}")
        if req_id in active_requests: del active_requests[req_id]
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/memory/search")
async def memory_search(request: Request):
    if not workers["chat"]:
        await add_log_entry("Memory-API", "error", "Memory search requested but Ghost Engine is disconnected")
        return JSONResponse(status_code=503, content={"error": "Ghost Engine Disconnected"})

    try:
        body = await request.json()
        query = body.get("query", "")
        req_id = str(uuid.uuid4())
        active_requests[req_id] = asyncio.Queue()

        await add_log_entry("Memory-API", "info", f"Forwarding memory search request '{query}' (ID: {req_id}) to Ghost Engine")
        await workers["chat"].send_json({"type": "direct_search_request", "id": req_id, "query": query})

        result = await asyncio.wait_for(active_requests[req_id].get(), timeout=15.0)
        del active_requests[req_id]

        await add_log_entry("Memory-API", "info", f"Memory search completed successfully for query '{query}'")
        return {"status": "success", "context": result}
    except asyncio.TimeoutError:
        await add_log_entry("Memory-API", "error", f"Memory search timed out for query '{body.get('query', '')}'")
        if req_id in active_requests: del active_requests[req_id]
        return JSONResponse(status_code=504, content={"error": "Search request timed out"})
    except Exception as e:
        await add_log_entry("Memory-API", "error", f"Memory search failed with error: {str(e)}")
        if req_id in active_requests: del active_requests[req_id]
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/memory/ingest")
async def memory_ingest(request: Request):
    """Ingest context files from the watchdog service.
    
    Accepts files from the context/ folder and forwards them to the Ghost Engine
    for processing and memory storage.
    """
    if not workers["chat"]:
        await add_log_entry("Memory-API", "error", "Memory ingest requested but Ghost Engine is disconnected")
        return JSONResponse(status_code=503, content={"error": "Ghost Engine Disconnected"})

    try:
        body = await request.json()
        source = body.get("source", "unknown")
        content = body.get("content", "")
        timestamp = body.get("timestamp", datetime.datetime.now().isoformat())
        file_type = body.get("file_type", ".txt")
        
        req_id = str(uuid.uuid4())
        active_requests[req_id] = asyncio.Queue()

        await add_log_entry("Memory-API", "info", f"Forwarding memory ingest request from '{source}' (ID: {req_id}) to Ghost Engine")
        
        # Send to Ghost Engine for processing
        await workers["chat"].send_json({
            "type": "memory_ingest",
            "id": req_id,
            "source": source,
            "content": content,
            "timestamp": timestamp,
            "file_type": file_type
        })

        # Wait for acknowledgment (with shorter timeout)
        result = await asyncio.wait_for(active_requests[req_id].get(), timeout=10.0)
        del active_requests[req_id]

        await add_log_entry("Memory-API", "info", f"Memory ingest completed successfully for '{source}'")
        return {"status": "success", "source": source, "result": result}
    
    except asyncio.TimeoutError:
        await add_log_entry("Memory-API", "error", f"Memory ingest timed out for source '{body.get('source', '')}'")
        if req_id in active_requests: del active_requests[req_id]
        return JSONResponse(status_code=504, content={"error": "Ingest request timed out"})
    except Exception as e:
        await add_log_entry("Memory-API", "error", f"Memory ingest failed with error: {str(e)}")
        if req_id in active_requests: del active_requests[req_id]
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/context", response_class=HTMLResponse)
async def get_context():
    import os
    file_path = os.path.join(os.path.dirname(__file__), "context.html")
    return FileResponse(file_path)

@app.get("/sidecar", response_class=HTMLResponse)
async def get_sidecar():
    import os
    file_path = os.path.join(os.path.dirname(__file__), "sidecar.html")
    return FileResponse(file_path)

# --- LOGGING ENDPOINTS ---
@app.get("/logs/recent")
async def get_recent_logs_endpoint():
    """API endpoint to get recent system logs"""
    logs = await get_recent_logs(50)
    return {"logs": logs}

@app.post("/logs/collect")
async def collect_log(request: Request):
    """API endpoint to collect logs from various system components"""
    try:
        body = await request.json()
        source = body.get("source", "unknown")
        log_type = body.get("type", "info")
        message = body.get("message", "")

        await add_log_entry(source, log_type, message)

        return {"status": "success", "message": "Log entry added"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "nominal", "engine": "connected" if workers["chat"] else "waiting", "timestamp": datetime.datetime.now().isoformat()}

# --- WEBSOCKETS ---
@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    workers["chat"] = websocket
    await add_log_entry("WebGPU-Bridge", "success", "Ghost Engine Connected")
    print("🟢 Ghost Engine Connected")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            # Route messages to waiting requests
            # Special case for memory search results
            if msg.get("type") == "direct_search_result":
                rid = msg.get("id")
                if rid in active_requests:
                    await active_requests[rid].put(msg.get("result"))
            
            # Route other response messages to waiting requests
            elif "id" in msg and msg["id"] in active_requests:
                await active_requests[msg["id"]].put(msg)
            # Handle other message types that might come from the Ghost Engine
            elif msg.get("type") == "engine_ready":
                await add_log_entry("Ghost-Engine", "success", "Ghost Engine Ready - Model loaded and ready for requests")
                print("🔧 Ghost Engine Ready - Model loaded and ready for requests")
            elif msg.get("type") == "model_loading":
                status = msg.get('status', 'Loading...')
                await add_log_entry("Ghost-Engine", "info", f"Ghost Engine Loading: {status}")
                print(f"⚙️ Ghost Engine Loading: {status}")
            elif msg.get("type") == "log":
                log_msg = msg.get('message', '')
                await add_log_entry("Ghost-Engine", "info", f"{log_msg}")
            elif msg.get("type") == "error":
                error_msg = msg.get('message', 'Unknown error')
                await add_log_entry("Ghost-Engine", "error", f"Ghost Engine Error: {error_msg}")
                print(f"❌ Ghost Engine Error: {error_msg}")
    except Exception as e:
        workers["chat"] = None
        error_msg = f"Ghost Engine Disconnected: {str(e)}"
        await add_log_entry("WebGPU-Bridge", "error", error_msg)
        print(error_msg)
        
        # Attempt to clear any pending requests
        for req_id in list(active_requests.keys()):
            try:
                # Put an error message in the queue to unblock waiting requests
                await active_requests[req_id].put({"error": "Ghost Engine disconnected", "done": True})
            except:
                pass
        
        # Trigger auto-resurrection of the Ghost Engine
        await add_log_entry("Resurrection", "info", "Triggering auto-resurrection of Ghost Engine...")
        asyncio.create_task(resurrection_manager.resurrect_with_retry())

app.mount("/", StaticFiles(directory=".", html=True), name="ui")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(os.path.dirname(__file__), "favicon.ico")) if os.path.exists("favicon.ico") else JSONResponse({"status": "ok"})

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="error")