#!/usr/bin/env python3
"""Small runner that uses `src.config.settings` to start uvicorn with configured host/port.

This avoids hardcoding in start scripts and allows values from config.yaml or env vars to drive MCP server startup.
"""
from __future__ import annotations

from src.config import settings
import uvicorn


def main():
    if not settings.mcp_enabled:
        print("MCP server is disabled in configuration. Set MCP_ENABLED to true in env or configs/config.yaml to start the MCP server.")
        # Print a hint showing the current derived settings so users can debug quickly
        try:
            print(f"Current settings: mcp_url={settings.mcp_url}, mcp_host={settings.mcp_host}, mcp_port={settings.mcp_port}")
        except Exception:
            pass
        return
    host = settings.mcp_host
    port = int(settings.mcp_port)
    # Print a friendly startup message containing config-derived values
    try:
        src = settings.mcp_url or f"{settings.mcp_host}:{settings.mcp_port}"
        print(f"Starting MCP server using settings derived from YAML/env: {src} (enabled={settings.mcp_enabled})")
    except Exception:
        print(f"Starting MCP server on {host}:{port}")
    uvicorn.run("src.mcp_server:app", host=host, port=port, log_level=settings.ece_log_level.lower())


if __name__ == "__main__":
    main()
