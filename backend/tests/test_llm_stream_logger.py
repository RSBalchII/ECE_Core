import pytest
import asyncio
import httpx

from src.llm import LLMClient


@pytest.mark.asyncio
async def test_stream_generate_handles_http_503_with_logger(caplog):
    # Create an LLM client and patch the internal client to use a MockTransport that returns 503
    client = LLMClient()
    async def handler(request):
        return httpx.Response(status_code=503, content=b"Service Unavailable")

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    client.client = async_client
    client._detected_model = "test-model"
    client._model_detection_attempted = True
    # Call stream_generate and expect it to raise an HTTPStatusError but not NameError
    with pytest.raises(httpx.HTTPStatusError):
        async for _ in client.stream_generate(prompt="hello"):
            pass
    # Ensure the logs captured an error message (logger used without NameError)
    assert any("LLM server" in rec.message or "Service Unavailable" in rec.message for rec in caplog.records)
