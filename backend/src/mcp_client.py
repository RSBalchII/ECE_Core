#!/usr/bin/env python3
"""
Minimal MCP client for ECE_Core to call external MCP servers.
This is used sparingly in ECE_Core when plugin manager isn't available, or when tools are offloaded.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import httpx
from src.config import settings


class MCPClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 10):
        if base_url:
            self.base_url = base_url.rstrip('/')
        elif getattr(settings, 'mcp_url', None):
            self.base_url = settings.mcp_url.rstrip('/')
        else:
            self.base_url = f"http://{settings.mcp_host}:{settings.mcp_port}"
        self.api_key = api_key or settings.mcp_api_key or settings.ece_api_key
        self._timeout = timeout

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def get_tools(self) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(f"{self.base_url}/mcp/tools", headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def call_tool(self, name: str, **arguments) -> Any:
        payload = {"name": name, "arguments": arguments}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(f"{self.base_url}/mcp/call", json=payload, headers=self._headers())
            if r.status_code >= 400:
                return {"status": "error", "status_code": r.status_code, "error": r.text}
            return r.json()
