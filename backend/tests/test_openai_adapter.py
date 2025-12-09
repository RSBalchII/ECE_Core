import pytest
from fastapi.testclient import TestClient
from src.app_factory import create_app_with_routers




def test_openai_adapter_basic(monkeypatch):
    # Mock verify_api_key dependency to bypass auth
    headers = {"Authorization": "Bearer testkey"}
    payload = {
        "model": "ece-core",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello."}
        ]
    }

    # Create the client inside the test to ensure autouse fixtures have run
    app = create_app_with_routers()
    with TestClient(app) as client:
        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code in (200, 202)
    data = resp.json()
    assert "choices" in data or "id" in data
