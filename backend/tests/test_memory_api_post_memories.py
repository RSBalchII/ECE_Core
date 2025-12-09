import pytest
from fastapi.testclient import TestClient
from src.app_factory import create_app_with_routers


def test_add_memory_fails_when_neo4j_unavailable(monkeypatch):
    app = create_app_with_routers()
    # Ensure the memory store exists
    memory = app.state.memory
    # Force Neo4j to be unavailable
    if getattr(memory, 'neo4j', None):
        memory.neo4j.neo4j_driver = None
    client = TestClient(app)
    payload = {"category": "note", "content": "Test memory from API", "tags": ["test"], "importance": 3}
    res = client.post('/memories', json=payload)
    assert res.status_code == 503
    assert "Neo4j unavailable" in res.json().get("detail", "")
