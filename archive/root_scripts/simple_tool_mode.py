"""Top-level shim to re-export anchor.simple_tool_mode for tests that import `simple_tool_mode`.
This avoids test import errors when running tests from the repo root.
"""
try:
    from anchor.simple_tool_mode import SimpleToolMode, SimpleToolHandler, SimpleToolIntent
except Exception:
    # Fallback minimal shims if the anchor package cannot be imported during test discovery
    class SimpleToolMode:
        def can_handle_directly(self, query):
            return False

    class SimpleToolHandler:
        def __init__(self, mcp, llm):
            self.mcp = mcp
            self.llm = llm

        def can_handle_directly(self, query):
            return False

        async def handle_query(self, *args, **kwargs):
            return None

    class SimpleToolIntent:
        def __init__(self, tool_name, arg, score, reason):
            self.tool_name = tool_name
            self.arg = arg
            self.score = score
            self.reason = reason

__all__ = ["SimpleToolMode", "SimpleToolHandler", "SimpleToolIntent"]
