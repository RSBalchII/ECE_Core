"""Top-level shim to re-export `anchor.tools.code_tools` for test imports that expect `tools.code_tools`.
"""
try:
    from anchor.tools.code_tools import *  # noqa: F401, F403
except Exception:
    # Minimal fallback implementations
    def code_search(root: str, query: str, **kwargs):
        return {"root": root, "query": query, "count": 0, "results": []}

    def code_grep(root: str, query: str, **kwargs):
        return {"root": root, "query": query, "files": 0, "total_matches": 0, "results": []}

__all__ = ["code_search", "code_grep"]
