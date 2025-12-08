"""Top-level shim for `tool_safety` used by anchor tests.
This provides a minimal, test-friendly ToolSafetyManager and helpers.
If the real `anchor.tool_safety` is importable, prefer it.
"""
from enum import Enum
import os

try:
    from anchor.tool_safety import (
        ToolSafetyManager,
        ToolSafety,
        get_safety_manager,
        is_tool_safe,
        requires_confirmation,
        sanitize_command,
    )
except Exception:
    class ToolSafety(Enum):
        SAFE = 1
        DANGEROUS = 2

    class ToolSafetyManager:
        _instance = None

        def __init__(self):
            safe = os.getenv("SAFE_TOOLS", "filesystem_read,web_search").split(',')
            dangerous = os.getenv("DANGEROUS_TOOLS", "shell_execute,filesystem_write").split(',')
            self.safe = set([s.strip() for s in safe if s.strip()])
            self.dangerous = set([d.strip() for d in dangerous if d.strip()])

        def categorize_tool(self, name: str):
            if name in self.safe:
                return ToolSafety.SAFE
            if name in self.dangerous:
                return ToolSafety.DANGEROUS
            return ToolSafety.DANGEROUS

        def sanitize_shell_command(self, cmd: str):
            # Basic heuristics
            lower = cmd.lower()
            dangerous_patterns = ["rm -rf", "dd ", "| sh", "| bash", "nc -e", "nc -l", "wget http", "curl http"]
            if any(p in lower for p in dangerous_patterns):
                return False, "Dangerous command detected"
            if "`" in cmd or "$(" in cmd:
                return False, "Command substitution detected"
            if ">" in cmd:
                return True, "Redirection detected"
            return True, None

        def requires_confirmation(self, name: str):
            return self.categorize_tool(name) == ToolSafety.DANGEROUS

        def should_auto_execute(self, name: str, params: dict):
            # Only auto execute safe tools
            return self.categorize_tool(name) == ToolSafety.SAFE

        def get_confirmation_prompt(self, name: str, params: dict):
            return f"Execute {name} with {params}? (y/n)"

    def get_safety_manager():
        if ToolSafetyManager._instance is None:
            ToolSafetyManager._instance = ToolSafetyManager()
        return ToolSafetyManager._instance

    def is_tool_safe(name: str):
        return get_safety_manager().categorize_tool(name) == ToolSafety.SAFE

    def requires_confirmation(name: str):
        return get_safety_manager().requires_confirmation(name)

    def sanitize_command(cmd: str):
        return get_safety_manager().sanitize_shell_command(cmd)

__all__ = [
    "ToolSafety",
    "ToolSafetyManager",
    "get_safety_manager",
    "is_tool_safe",
    "requires_confirmation",
    "sanitize_command",
]
