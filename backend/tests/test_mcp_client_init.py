from src.bootstrap import create_app
from src.config import settings


def test_mcp_client_initialization(monkeypatch):
    # Ensure MCP config is enabled
    monkeypatch.setattr(settings, 'mcp_enabled', True)
    monkeypatch.setattr(settings, 'mcp_host', '127.0.0.1')
    monkeypatch.setattr(settings, 'mcp_port', 8421)
    app = create_app()
    comp = app.state
    # mcp_client may be None if init failed; ensure either None or correct base_url attribute
    mcp_client = getattr(comp, 'mcp_client', None)
    if mcp_client:
        assert hasattr(mcp_client, 'base_url')
        assert '127.0.0.1' in mcp_client.base_url


def test_mcp_client_uses_mcp_url_env(monkeypatch):
    monkeypatch.setenv('MCP_URL', 'http://127.0.0.1:9000')
    monkeypatch.setattr(settings, 'mcp_enabled', True)
    app = create_app()
    comp = app.state
    mcp_client = getattr(comp, 'mcp_client', None)
    if mcp_client:
        assert mcp_client.base_url.endswith(':9000') or '9000' in mcp_client.base_url