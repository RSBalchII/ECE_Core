#!/usr/bin/env python3
"""A small proxy that accepts OpenAI-compatible chat requests and forwards them to
the local llama.cpp server, preserving streaming semantics and converting to SSE where required.

This is intended to make Cline or other OpenAI-compatible clients work with local servers
that implement slightly different streaming semantics.

Usage: python openai_stream_proxy.py --target http://127.0.0.1:8080 --port 9000
Then point Cline's LLM Base to http://127.0.0.1:9000/v1
"""
from __future__ import annotations

import argparse
import logging
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import httpx
import json
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="OpenAI Stream Proxy")


def openai_stream_event_to_sse(line: str):
    # expecting lines like: "data: {json}\n\n" or chunked json
    line = line.strip()
    if line.startswith("data: "):
        data = line[6:]
    else:
        data = line
    if data == "[DONE]":
        return None
    try:
        return json.loads(data)
    except Exception:
        return data


@app.post("/v1/chat/completions")
async def proxy_chat(request: Request):
    body = await request.json()
    args = dict(body)
    # Remove streaming flags the client may set; always forward stream flag if present
    stream = args.get("stream", True)

    target_host = app.state.target
    target_url = f"{target_host.rstrip('/')}/v1/chat/completions"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host",)}

    async def generator():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", target_url, json=args, headers=headers) as resp:
                # If not streaming, just forward the JSON body
                if not stream:
                    text = await resp.aread()
                    yield text
                    return

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    # Convert to sse payload
                    ev = openai_stream_event_to_sse(line)
                    if ev is None:
                        yield "event: done\ndata: [DONE]\n\n"
                        break
                    # If event is dict, we forward as JSON
                    payload = json.dumps(ev) if not isinstance(ev, str) else ev
                    yield f"data: {payload}\n\n"

    # Return as SSE stream so client can parse the events
    return EventSourceResponse(generator())


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="OpenAI to local model streaming proxy")
    parser.add_argument("--target", default="http://127.0.0.1:8080", help="Target local model server base URL")
    parser.add_argument("--port", default=9000, type=int, help="Port to run the proxy on")
    args = parser.parse_args()
    app.state.target = args.target
    logger.info(f"Starting proxy on http://127.0.0.1:{args.port} -> {args.target}")
    uvicorn.run(app, host="127.0.0.1", port=args.port)
