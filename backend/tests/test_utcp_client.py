import importlib
import importlib.util
import pytest


def test_utcp_filesystem_importable():
    """Ensure the UTCP filesystem module is importable."""
    spec = importlib.util.find_spec('src.utils.utcp_filesystem')
    assert spec is not None, "src.utils.utcp_filesystem not importable"


def test_utcp_plugin_discovery_and_simple_call(monkeypatch):
    try:
        from plugins.manager import PluginManager
    except Exception:
        pytest.skip('plugins.manager not available; skipping UTCP plugin discovery test')
    pm = PluginManager({})
    discovered = pm.discover()
    assert isinstance(discovered, list)
    # if UTCP plugin is present, it should be discoverable
    if 'utcp' in discovered:
        # test that plugin manager can list tools and the method returns a list
        tools = pm.list_tools()
        assert isinstance(tools, list)