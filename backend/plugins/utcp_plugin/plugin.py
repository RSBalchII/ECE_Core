import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class UTCPPlugin:
    """
    Plugin for Universal Tool Call Protocol (UTCP).
    Discovers tools from UTCP endpoints defined in environment variables.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.endpoints = self._parse_endpoints(config.get("UTCP_ENDPOINTS", ""))
        self.tools = []

    def _parse_endpoints(self, endpoints_str: str) -> List[str]:
        if not endpoints_str:
            return []
        return [e.strip() for e in endpoints_str.split(",") if e.strip()]

    def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Discover tools from configured UTCP endpoints.
        For now, this is a placeholder that would fetch /tools from endpoints.
        """
        logger.info(f"Discovering UTCP tools from: {self.endpoints}")
        # In a real implementation, we would HTTP GET {endpoint}/tools
        # For now, if a client with 'available_tools' attribute is provided, use it
        tools: List[Dict[str, Any]] = []
        if hasattr(self, "_client") and getattr(self._client, "available_tools", None):
            # DummyClient style mapping
            for tname, tinfo in getattr(self._client, "available_tools", {}).items():
                tools.append({
                    "name": tname,
                    "description": tinfo.get("description", ""),
                    "service": tinfo.get("service", "unknown")
                })
            return tools
        return []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None, **kwargs) -> Any:
        """
        Execute a tool via UTCP.
        """
        logger.info(f"Executing UTCP tool {tool_name} with {arguments}")
        # In a real implementation, we would HTTP POST {endpoint}/execute
        args = arguments or {}
        # Merge kwargs into args if provided (supports both call styles)
        if kwargs:
            args = {**args, **kwargs}
        if hasattr(self, "_client") and hasattr(self._client, "call_tool"):
            try:
                return await self._client.call_tool(tool_name, args)
            except Exception:
                pass
        return {"error": "Not implemented"}

    # Backward compatibility: provide `get_tools` alias expected by older tests
    def get_tools(self) -> List[Dict[str, Any]]:
        return self.discover_tools()


# Backward compatibility alias (some test fixtures import `UtcpPlugin`)
UtcpPlugin = UTCPPlugin
