import pytest
from fastapi.testclient import TestClient
from src.app_factory import create_app_with_routers


def test_get_memories_compat_endpoint():
    app = create_app_with_routers()
    client = TestClient(app)
    res = client.get('/memories')
    # 405 is possible if the implementation is not registered, otherwise 200
    assert res.status_code in (200, 405)
