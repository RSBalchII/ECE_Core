from typing import List, Dict, Any
from pathlib import Path
import os


class ExampleToolsPlugin:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def discover_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "filesystem_read",
                "description": "Read a file or list a directory",
                "signature": "filesystem_read(path)"
            }
        ]

    def execute_tool(self, tool_name: str, params: Dict[str, Any]):
        if tool_name == "filesystem_read":
            path = params.get('path')
            if not path:
                return {"error": "missing path"}
            p = Path(path)
            if p.is_dir():
                items = [f.name for f in p.iterdir() if f.is_file()]
                return {"type": "directory", "items": items}
            elif p.is_file():
                try:
                    content = p.read_text(encoding='utf-8', errors='ignore')
                    return {"type": "file", "content": content}
                except Exception as e:
                    return {"error": str(e)}
            else:
                return {"error": "path not found"}
        return {"error": "unknown tool"}
