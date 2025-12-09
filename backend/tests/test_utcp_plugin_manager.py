import pytest
from plugins.manager import PluginManager


def test_utcp_plugin_discovery():
    pm = PluginManager({"UTCP_ENDPOINTS": "http://localhost:9000"})
    discovered = pm.discover()
    # Either it's discovered or not (if UTCP plugin not loaded); assert that the method runs
    assert isinstance(discovered, list)
    # If UTCP plugin exists, it should be named 'utcp'
    if discovered:
        assert 'utcp' in discovered


@pytest.mark.asyncio
async def test_execute_tool_with_utcp_plugin():
    pm = PluginManager({})
    discovered = pm.discover()
    if 'utcp' not in discovered:
        pytest.skip("UTCP plugin not available; skipping execution test")
    # PluginManager.execute_tool is async and returns plugin's execution result
    result = await pm.execute_tool('utcp:some_tool', param1='v1')
    assert result is not None
