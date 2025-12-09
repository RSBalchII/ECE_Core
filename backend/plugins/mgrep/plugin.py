import os
import re
import glob
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MgrepPlugin:
    """
    Plugin for 'mgrep' (Semantic/Smart Grep).
    Provides tools for searching the codebase.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.root_dir = config.get("PROJECT_ROOT", os.getcwd())

    def discover_tools(self) -> List[Dict[str, Any]]:
        return [{
            "name": "mgrep",
            "description": "Search for a pattern in files recursively. Supports regex.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "Directory to search in (default: root)"},
                    "include": {"type": "string", "description": "Glob pattern for files to include (e.g. *.py)"}
                },
                "required": ["pattern"]
            }
        }]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None, **kwargs) -> Any:
        if tool_name != "mgrep":
            return {"error": f"Unknown tool: {tool_name}"}
            
        args = arguments or {}
        if kwargs:
            args.update(kwargs)
            
        pattern = args.get("pattern")
        search_path = args.get("path", ".")
        include = args.get("include", "**/*")
        
        if not pattern:
            return {"error": "Pattern is required"}
            
        return self._mgrep(pattern, search_path, include)

    def _mgrep(self, pattern: str, search_path: str, include: str) -> List[Dict[str, Any]]:
        results = []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

        # Sanitize and validate paths to prevent malformed paths like .->.->.-> patterns
        # Check for suspicious patterns that could cause errors
        if '..->' in search_path or '->' in search_path.replace('.', ''):
            return {"error": f"Invalid path format: {search_path}"}

        # Prevent directory traversal attempts beyond project boundary
        search_path = search_path.strip()
        if search_path.startswith('../') or '../' in search_path:
            return {"error": f"Directory traversal not allowed: {search_path}"}

        # Resolve absolute path
        abs_search_path = os.path.abspath(os.path.join(self.root_dir, search_path))

        # Validate that resolved path is within project directory
        try:
            # This will raise ValueError if path is outside the project root
            Path(abs_search_path).relative_to(self.root_dir)
        except ValueError:
            return {"error": f"Path is outside project directory: {abs_search_path}"}

        # Walk and search
        # Note: This is a simple implementation. For large codebases, use `ripgrep` via subprocess if available.
        # Here we use python for portability as requested.

        # Construct glob pattern
        glob_pattern = os.path.join(abs_search_path, include) if not os.path.isabs(include) else include

        # If include is just extension like "*.py", we need to walk
        if "**" in include:
             files = glob.glob(os.path.join(abs_search_path, include), recursive=True)
        else:
             # If simple glob, just use it
             files = glob.glob(os.path.join(abs_search_path, include))
             if not files:
                 # Try recursive if no matches and user didn't specify recursive
                 files = glob.glob(os.path.join(abs_search_path, "**", include), recursive=True)

        count = 0
        MAX_RESULTS = 50
        
        for file_path in files:
            if os.path.isdir(file_path):
                continue
            if count >= MAX_RESULTS:
                break
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            results.append({
                                "file": os.path.relpath(file_path, self.root_dir),
                                "line": i + 1,
                                "content": line.strip()
                            })
                            count += 1
                            if count >= MAX_RESULTS:
                                break
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
                
        return {
            "results": results,
            "count": len(results),
            "truncated": count >= MAX_RESULTS
        }
