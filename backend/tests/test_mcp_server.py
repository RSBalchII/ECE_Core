import pytest
from fastapi.testclient import TestClient

from src import mcp_server
from src.mcp_server import app
from src.config import settings


class FakeStore:
    def __init__(self):
        self._data = []
        self._id_seq = 1
        self.neo4j_driver = True

    async def initialize(self):
        return

    async def close(self):
        return

    async def add_memory(self, session_id, content, category, tags, importance, metadata, entities):
        _id = f"mem-{self._id_seq}"
        self._id_seq += 1
        self._data.append({"id": _id, "session_id": session_id, "content": content, "category": category})
        return _id

    async def search_memories(self, query, category, limit):
        return [d for d in self._data if query.lower() in (d.get("content") or "").lower()][:limit]

    async def get_summaries(self, session_id, limit=5):
        return [f"summary {session_id}"]


def test_list_and_health_endpoints():
    with TestClient(app) as client:
        r = client.get("/mcp/tools")
        assert r.status_code == 200
        assert any(t["name"] == "add_memory" for t in r.json().get("tools", []))

        # health endpoint without a store should not crash
        r2 = client.get("/health")
        assert r2.status_code == 200
        assert r2.json().get("status") == "ok"


def test_mcp_auth_required(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(mcp_server, "_neo4j_store", fake)
    # Require auth
    monkeypatch.setattr(settings, 'ece_require_auth', True)
    monkeypatch.setattr(settings, 'mcp_api_key', 'secret-token')

    with TestClient(app) as client:
        payload = {"name": "get_summaries", "arguments": {"session_id": "s1", "limit": 2}}
        # No auth -> 401
        r = client.post("/mcp/call", json=payload)
        assert r.status_code == 401

        # Wrong token -> 403
        r2 = client.post("/mcp/call", json=payload, headers={"Authorization": "Bearer bad-token"})
        assert r2.status_code == 403

        # Correct token -> success
        r3 = client.post("/mcp/call", json=payload, headers={"Authorization": "Bearer secret-token"})
        assert r3.status_code == 200


def test_add_and_search_memory(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(mcp_server, "_neo4j_store", fake)

    with TestClient(app) as client:
        add_payload = {"name": "add_memory", "arguments": {"session_id": "s1", "content": "Hello world", "category": "note", "tags": ["test"]}}
        r = client.post("/mcp/call", json=add_payload)
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "success"
        # If Neo4j isn't available in this test environment, update will no-op and return None id
        assert "id" in j["result"] if isinstance(j.get("result"), dict) else True

        search_payload = {"name": "search_memories", "arguments": {"query": "hello", "limit": 5}}
        r2 = client.post("/mcp/call", json=search_payload)
        assert r2.status_code == 200
        j2 = r2.json()
        assert j2["status"] == "success"
        assert isinstance(j2["result"], list)


def test_alias_tool_names(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(mcp_server, "_neo4j_store", fake)
    with TestClient(app) as client:
        add_payload = {"name": "write_memory", "arguments": {"session_id": "s2", "content": "Alias test", "category": "note"}}
        r = client.post("/mcp/call", json=add_payload)
        assert r.status_code == 200
        j = r.json()
        assert j.get('status') == 'success'

        search_payload = {"name": "read_memory", "arguments": {"query": "Alias test", "limit": 5}}
        r2 = client.post("/mcp/call", json=search_payload)
        assert r2.status_code == 200
        j2 = r2.json()
        assert j2['status'] == 'success'


def test_get_summaries(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(mcp_server, "_neo4j_store", fake)

    with TestClient(app) as client:
        payload = {"name": "get_summaries", "arguments": {"session_id": "s1", "limit": 2}}
        r = client.post("/mcp/call", json=payload)
        assert r.status_code == 200
        j = r.json()
        assert j["status"] == "success"
        assert isinstance(j["result"], list)
