"""
UTCP Filesystem Tool Service for ECE_Core
Simple file operations accessible via UTCP protocol
"""
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import os
from pathlib import Path
import json

app = FastAPI(title="UTCP Filesystem Service")

class FileReadRequest(BaseModel):
    path: str
    
class FileWriteRequest(BaseModel):
    path: str
    content: str
    
class DirectoryListRequest(BaseModel):
    path: str
    recursive: bool = False

@app.get("/")
async def root():
    return {"service": "UTCP Filesystem", "status": "running"}

@app.get("/utcp")
async def utcp_manual():
    """UTCP Manual - describes available tools"""
    return {
        "service": "filesystem",
        "version": "1.0.0",
        "tools": [
            {
                "name": "read_file",
                "description": "Read contents of a file",
                "parameters": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "endpoint": "/read_file"
            },
            {
                "name": "write_file",
                "description": "Write content to a file",
                "parameters": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "endpoint": "/write_file"
            },
            {
                "name": "list_directory",
                "description": "List files in a directory",
                "parameters": {
                    "path": {"type": "string", "description": "Directory path"},
                    "recursive": {"type": "boolean", "description": "List recursively", "default": False}
                },
                "endpoint": "/list_directory"
            },
            {
                "name": "run_command",
                "description": "Execute a whitelisted CLI command (safe-mode) on the server",
                "parameters": {
                    "command": {"type": "string", "description": "Command to run"},
                    "cwd": {"type": "string", "description": "Working directory (optional)"},
                    "timeout": {"type": "integer", "description": "Timeout seconds", "default": 5}
                },
                "endpoint": "/run_command"
            }
        ]
    }

@app.post("/read_file")
@app.get("/read_file")
async def read_file(path: str = None, request: Request = None):
    """Read file contents"""
    try:
        # Accept JSON body or query params
        if request is not None:
            try:
                payload = await request.json()
            except Exception:
                payload = None
            if payload:
                path = payload.get("path", path)
        file_path = Path(path).resolve()
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail=f"Not a file: {path}")
        
        content = file_path.read_text(encoding='utf-8')
        return {
            "success": True,
            "path": str(file_path),
            "content": content,
            "size": len(content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run_command")
async def run_command(request: Request, command: str = None, cwd: str = None, timeout: int = 5):
    """Execute a whitelisted CLI command in a safe manner.
    `command` should be a single command with optional arguments.
    `cwd` if provided must be under `UTCP_FILESYSTEM_ROOT` (if configured).
    Timeout in seconds applies to command execution.
    """
    from shlex import split as shlex_split
    import subprocess
    import platform
    try:
        # Accept both query params and JSON body payloads for compatibility with different clients
        try:
            payload = await request.json()
        except Exception:
            payload = None
        if payload:
            command = payload.get("command", command)
            cwd = payload.get("cwd", cwd)
            timeout = payload.get("timeout", timeout)
        # Security: Only allow simple commands from allowlist
        default_allowed = ["ls", "pwd", "cat", "dir", "echo", "type"]
        env_allow = os.environ.get("UTCP_RUN_COMMAND_ALLOWLIST")
        if env_allow:
            try:
                allowed_cmds = [s.strip() for s in env_allow.split(",") if s.strip()]
            except Exception:
                allowed_cmds = default_allowed
        else:
            allowed_cmds = default_allowed
        parts = shlex_split(command)
        if not parts:
            raise HTTPException(status_code=400, detail="Empty command")
        if parts[0] not in allowed_cmds:
            raise HTTPException(status_code=403, detail=f"Command not allowed: {parts[0]}")

        # Validate cwd under allowed root
        root_env = os.environ.get("UTCP_FILESYSTEM_ROOT")
        if cwd:
            wd = Path(cwd).resolve()
            if root_env:
                root = Path(root_env).resolve()
                try:
                    wd.relative_to(root)
                except Exception:
                    raise HTTPException(status_code=403, detail=f"CWD not allowed: {cwd}")
        else:
            wd = None

        # On Windows, some commands like 'dir', 'type', or 'pwd' are shell builtins.
        # Wrap them using `cmd.exe /c` so they execute correctly without shell=True.
        is_windows = platform.system().lower() == "windows"
        exec_parts = parts
        if is_windows and parts[0] in ("dir", "type", "pwd", "ls"):
            exec_parts = ["cmd", "/c"] + parts

        # Resource limiting: try to enforce CPU and memory limits on POSIX
        preexec_fn = None
        try:
            if os.name != 'nt':
                import resource
                mem_limit_mb = int(os.environ.get("UTCP_RUN_COMMAND_MEM_LIMIT_MB", "256"))
                mem_bytes = mem_limit_mb * 1024 * 1024
                def _preexec():
                    # CPU seconds limit slightly above timeout
                    try:
                        resource.setrlimit(resource.RLIMIT_CPU, (timeout + 1, timeout + 1))
                    except Exception:
                        pass
                    try:
                        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                    except Exception:
                        pass
                preexec_fn = _preexec
        except Exception:
            preexec_fn = None

        # Run the command with optional preexec limits
        proc = subprocess.run(exec_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(wd) if wd else None, timeout=timeout, preexec_fn=preexec_fn)
        # Audit logging: record the run in a log file under logs/utcp_run_command_audit.log
        try:
            # determine repo root by walking up until we find '.git' or 'package.json' or default to parents[3]
            candidate = Path(__file__).resolve().parent
            repo_root = candidate
            while repo_root and not (repo_root / 'package.json').exists():
                if repo_root.parent == repo_root:
                    break
                repo_root = repo_root.parent
            if not repo_root or not (repo_root / 'package.json').exists():
                repo_root = Path(__file__).resolve().parents[3]
            logs_dir = repo_root / 'logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            audit_file = logs_dir / 'utcp_run_command_audit.log'
            with open(audit_file, 'a', encoding='utf-8') as fh:
                audit_entry = {
                    'timestamp': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
                    'command': command,
                    'cwd': str(wd) if wd else None,
                    'exit_code': proc.returncode,
                    'stdout': proc.stdout.decode('utf-8', errors='ignore')[:5000],
                    'stderr': proc.stderr.decode('utf-8', errors='ignore')[:2000]
                }
                fh.write(json.dumps(audit_entry) + '\n')
        except Exception:
            pass

        return {
            "success": True,
            "command": command,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", errors="ignore"),
            "stderr": proc.stderr.decode("utf-8", errors="ignore"),
        }
    except subprocess.TimeoutExpired as e:
        raise HTTPException(status_code=504, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/write_file")
async def write_file(request: FileWriteRequest):
    """Write content to file"""
    try:
        file_path = Path(request.path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_path.write_text(request.content, encoding='utf-8')
        return {
            "success": True,
            "path": str(file_path),
            "size": len(request.content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/list_directory")
@app.get("/list_directory")
async def list_directory(path: str = None, recursive: bool = False, request: Request = None):
    """List directory contents"""
    try:
        if request is not None:
            try:
                payload = await request.json()
            except Exception:
                payload = None
            if payload:
                path = payload.get("path", path)
                recursive = payload.get("recursive", recursive)
        dir_path = Path(path).resolve()
        if not dir_path.exists():
            raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
        
        if not dir_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {path}")
        
        files = []
        if recursive:
            for item in dir_path.rglob("*"):
                files.append({
                    "path": str(item),
                    "name": item.name,
                    "type": "file" if item.is_file() else "directory",
                    "size": item.stat().st_size if item.is_file() else None
                })
        else:
            for item in dir_path.iterdir():
                files.append({
                    "path": str(item),
                    "name": item.name,
                    "type": "file" if item.is_file() else "directory",
                    "size": item.stat().st_size if item.is_file() else None
                })
        
        return {
            "success": True,
            "path": str(dir_path),
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search_files")
@app.get("/search_files")
async def search_files(
    path: str,
    pattern: str = "*",
    content_query: str = None,
    max_results: int = 50,
    recursive: bool = True
    , request: Request = None
):
    """Search for files under `path` by name or content.

    - `pattern` is a glob-like filename pattern (default '*').
    - `content_query` if provided, will search inside files and return line-snippets.
    - `max_results` limits the number of files returned.
    - `recursive` toggles recursive search.
    """
    try:
        from os import environ
        root_env = environ.get("UTCP_FILESYSTEM_ROOT")
        # Ensure paths are resolved and not outside root (if configured)
        # Accept JSON body payloads if request is provided by FastAPI.
        # When called directly in unit tests, request will be None and path param will be used.
        if request is not None:
            try:
                payload = await request.json()
            except Exception:
                payload = None
            if payload:
                path = payload.get("path", path)
                pattern = payload.get("pattern", pattern)
                content_query = payload.get("content_query", content_query)
                max_results = payload.get("max_results", max_results)
                recursive = payload.get("recursive", recursive)
        base = Path(path).resolve()
        if root_env:
            root = Path(root_env).resolve()
            try:
                base.relative_to(root)
            except Exception:
                raise HTTPException(status_code=403, detail=f"Path not allowed: {path}")

        if not base.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")
        if not base.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

        results = []
        count = 0
        iter_fn = base.rglob if recursive else base.glob
        for p in iter_fn(pattern):
            if count >= max_results:
                break
            if p.is_dir():
                continue
            item = {"path": str(p), "name": p.name}
            matches = []
            if content_query:
                try:
                    with p.open('r', encoding='utf-8', errors='ignore') as fh:
                        for lineno, line in enumerate(fh, start=1):
                            if content_query in line:
                                snippet = line.strip()
                                matches.append({"line": lineno, "snippet": snippet[:300]})
                                if len(matches) >= 10:
                                    break
                except Exception:
                    # Could not read file; skip content check but include file
                    matches = []
            item["matches"] = matches
            # If content_query is present, include only files with matches
            if content_query and not matches:
                continue
            results.append(item)
            count += 1

        return {"success": True, "root": str(base), "count": count, "files": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8006)
