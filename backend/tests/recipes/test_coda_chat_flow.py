from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import pytest
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.recipes.coda_chat import router
from src.security import verify_api_key

# Mock verify_api_key to always pass
async def mock_verify_api_key(request: Request):
    return True

def test_coda_chat_flow():
    app = FastAPI()
    # Mount the router. In the real app it is mounted at /chat, but here we can mount at root or /chat.
    # The router itself defines "/" and "/stream".
    # If we mount at root, endpoints are "/" and "/stream".
    app.include_router(router)
    app.dependency_overrides[verify_api_key] = mock_verify_api_key

    # Mock Components
    mock_memory = MagicMock()
    mock_memory.touch_session = AsyncMock()
    mock_memory.count_tokens = MagicMock(return_value=10)

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="Hello from Coda")
    
    # For streaming, we need an async generator
    async def async_gen(*args, **kwargs):
        yield "Hello "
        yield "from "
        yield "Coda"
    mock_llm.stream_generate = async_gen

    mock_audit = MagicMock()
    mock_audit.log = MagicMock()

    mock_context_mgr = MagicMock()
    mock_context_mgr.build_context = AsyncMock(return_value="Context")
    mock_context_mgr.update_context = AsyncMock()

    mock_chunker = MagicMock()
    mock_chunker.process_large_input = AsyncMock(return_value="Processed message")

    mock_tool_parser = MagicMock()
    mock_tool_parser.parse_response = MagicMock(return_value=None) # No tools for simple test

    # Inject into state
    app.state.memory = mock_memory
    app.state.llm = mock_llm
    app.state.audit_logger = mock_audit
    app.state.context_mgr = mock_context_mgr
    app.state.chunker = mock_chunker
    app.state.tool_parser = mock_tool_parser
    app.state.tool_validator = MagicMock()
    app.state.plugin_manager = MagicMock()
    app.state.mcp_client = MagicMock()

    client = TestClient(app)

    # Test 1: Standard Chat (POST /)
    payload = {
        "session_id": "test-session",
        "message": "Hello"
    }
    response = client.post("/", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "thinking: Hello from Coda" in data["response"]
    
    # Test 2: Streaming Chat (POST /stream)
    response_stream = client.post("/stream", json=payload)
    assert response_stream.status_code == 200
    
    # Verify content in stream
    # The stream format is SSE: data: {"chunk": "..."}
    assert "Hello" in response_stream.text
    assert "Coda" in response_stream.text
    
    # Verify Audit Log for Stream
    # We expect "chat_stream_start" and "chat_stream_end"
    calls = [call.args[0] for call in mock_audit.log.call_args_list]
    assert "chat_stream_start" in calls
    assert "chat_stream_end" in calls
