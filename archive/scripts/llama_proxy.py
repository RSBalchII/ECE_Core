#!/usr/bin/env python3
"""
Simple FastAPI reverse proxy that enforces a static API key for local OpenAI-compatible LLaMa server.

Usage:
  LLAMA_PROXY_KEY=yourkey python scripts/llama_proxy.py
  or run via the `start_all_safe_simple.bat` script.

This forwards calls to http://localhost:8080 and validates ``Authorization: Bearer <key>``.
It supports GET/POST and streams the response content directly back.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
import os
import httpx
import asyncio
import uvicorn
from typing import AsyncGenerator

UPSTREAM = os.getenv("LLAMA_UPSTREAM", "http://localhost:8080")
PORT = int(os.getenv("LLAMA_PROXY_PORT", "8089"))
API_KEY = os.getenv("LLAMA_PROXY_KEY", "local-proxy-key")

app = FastAPI(title="LLaMa OpenAI Proxy (local key)")


def _check_auth(request: Request):
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")
    token = auth.split(None, 1)[1].strip()
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_v1(path: str, request: Request):
    # Validate auth
    _check_auth(request)

    # Build upstream URL
    url = f"{UPSTREAM}/v1/{path}"

    # Copy headers, but remove host and authorization
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "authorization")}

    async with httpx.AsyncClient(timeout=None) as client:
        if request.method == "GET":
            upstream_resp = await client.get(url, headers=headers, params=dict(request.query_params))
        else:
            body = await request.body()
            upstream_resp = await client.request(request.method, url, headers=headers, content=body)

        # If streaming, forward raw iter_bytes
        if upstream_resp.headers.get("content-type", "").startswith("text/event-stream"):
            async def ag():
                async for chunk in client.stream(request.method, url, headers=headers, content=await request.body()):
                    yield chunk.iter_bytes()
            return StreamingResponse(upstream_resp.aiter_bytes(), status_code=upstream_resp.status_code)

        return Response(content=upstream_resp.content, status_code=upstream_resp.status_code, headers=upstream_resp.headers)


if __name__ == "__main__":
    print(f"Starting LLaMa proxy on http://127.0.0.1:{PORT}, upstream={UPSTREAM}")
    if API_KEY:
        print("Using API key from LLAMA_PROXY_KEY environment variable")
    else:
        print("WARNING: No API key set; the proxy will require a blank key.")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
