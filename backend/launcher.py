from src.app_factory import create_app_with_routers
from src.config import settings
import logging
import os
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configure logging
log_file = os.path.join(log_dir, "server.log")
logging.basicConfig(
    level=getattr(logging, settings.ece_log_level),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(log_file, maxBytes=500*1024, backupCount=5, encoding='utf-8')
    ]
)


class _ConsoleNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        suppress_embeddings = bool(getattr(settings, "logging_suppress_embeddings_console", False))
        suppress_weaver = bool(getattr(settings, "logging_suppress_weaver_console", False))

        if not (suppress_embeddings or suppress_weaver):
            return True

        name = (getattr(record, "name", "") or "").lower()
        try:
            msg = record.getMessage().lower()
        except Exception:
            msg = ""

        if suppress_embeddings:
            # Keep this conservative: only filter obvious embedding/vector chatter.
            if (
                "embedding" in msg
                or "embeddings" in msg
                or ".vector_adapter" in name
                or ".vector_adapters" in name
                or "redis_vector" in name
            ):
                return False

        if suppress_weaver:
            if "weaver" in name or "weaver" in msg:
                return False

        return True


# Apply noise filter to console handler only (do not hide in file logs)
for _h in logging.getLogger().handlers:
    if isinstance(_h, logging.StreamHandler):
        _h.addFilter(_ConsoleNoiseFilter())

# Ensure Uvicorn logs also go to the file
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.handlers = logging.getLogger().handlers
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.handlers = logging.getLogger().handlers

# Test log
logging.info("✅ ECE Backend Launcher Initialized - Logging to file enabled")

# --- Start WebGPU Bridge (Sovereign Tools) ---
import subprocess
import sys
from pathlib import Path


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def _subprocess_stdio(mode: str, log_path: str):
    """Return (stdout, stderr, opened_file_handle_or_None) for subprocess.Popen."""
    mode = (mode or "inherit").strip().lower()
    if mode == "hide":
        return subprocess.DEVNULL, subprocess.DEVNULL, None
    if mode == "file":
        _ensure_parent_dir(log_path)
        fh = open(log_path, "a", encoding="utf-8")
        return fh, subprocess.STDOUT, fh
    # inherit
    return None, None, None

# Use absolute path resolution to find the tools directory relative to this script
# backend/launcher.py -> backend/ -> Context-Engine/ -> tools/webgpu_bridge.py
current_dir = Path(__file__).resolve().parent
bridge_script = current_dir.parent / "tools" / "webgpu_bridge.py"

_bridge_log_fh = None
_llama_log_fh = None

if bridge_script.exists():
    print(f"🚀 Starting WebGPU Bridge from {bridge_script}...")
    # Run in background, detached
    # Use the same python executable that is running this script
    _b_stdout, _b_stderr, _bridge_log_fh = _subprocess_stdio(
        getattr(settings, "launcher_bridge_stdout", "inherit"),
        getattr(settings, "launcher_bridge_log_path", "./logs/webgpu_bridge.log"),
    )
    subprocess.Popen(
        [sys.executable, str(bridge_script)],
        cwd=str(bridge_script.parent.parent),
        stdout=_b_stdout,
        stderr=_b_stderr,
    )
else:
    print(f"⚠️ WebGPU Bridge script not found at {bridge_script}")


# Optional: start llama-server (or wrapper) so its stdout is visible here
repo_root = current_dir.parent
llama_launcher = repo_root / "start_llm_server.py"
if bool(getattr(settings, "launcher_llama_server_enabled", False)):
    try:
        cmd = getattr(settings, "launcher_llama_server_command", None)
        if cmd and isinstance(cmd, list) and all(isinstance(x, str) for x in cmd):
            llama_cmd = cmd
        elif llama_launcher.exists():
            llama_cmd = [sys.executable, str(llama_launcher)]
        else:
            llama_cmd = None

        if llama_cmd:
            print(f"🚀 Starting llama-server via launcher: {llama_cmd}")
            _l_stdout, _l_stderr, _llama_log_fh = _subprocess_stdio(
                getattr(settings, "launcher_llama_server_stdout", "inherit"),
                getattr(settings, "launcher_llama_server_log_path", "./logs/llama_server.log"),
            )
            subprocess.Popen(
                llama_cmd,
                cwd=str(repo_root),
                stdout=_l_stdout,
                stderr=_l_stderr,
            )
        else:
            print("⚠️ llama-server enabled, but no command configured and start_llm_server.py not found.")
    except Exception as e:
        print(f"⚠️ Failed to start llama-server: {e}")
# ---------------------------------------------

app = create_app_with_routers()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=settings.ece_host, port=settings.ece_port, log_config=None)
