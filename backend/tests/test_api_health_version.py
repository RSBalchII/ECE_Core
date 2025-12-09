import pytest
import sys
import os
from fastapi.testclient import TestClient
# Ensure project root is on sys.path so `src` package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.app_factory import create_app_with_routers
from src.config import settings


def test_health_includes_version():
    app = create_app_with_routers()
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert 'status' in data and data['status'] == 'healthy'
    # Ensure version is present and matches settings
    assert 'version' in data
    assert data['version'] == getattr(settings, 'ece_version', 'dev')
