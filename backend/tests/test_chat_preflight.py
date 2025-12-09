import os
import pytest
from fastapi.testclient import TestClient
from src.app_factory import create_app_with_routers
from src import config


headers = {"Authorization": "Bearer testkey"}


def test_chat_prompt_exceeds_ubatch(monkeypatch):
    # Set ubatch to a small number so our long prompt triggers the pre-flight check
    monkeypatch.setattr(config.settings, 'llama_server_ubatch_size', 16)

    long_text = 'a' * 1000  # ~250 tokens (rough estimate); should exceed UBATCH 16
    payload = {
        "model": "ece-core",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": long_text}
        ]
    }

    app = create_app_with_routers()
    with TestClient(app) as client:
        resp = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 400
    data = resp.json()
    assert 'exceed' in data.get('detail', '').lower()
