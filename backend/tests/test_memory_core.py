import pytest
from src.memory import TieredMemory


@pytest.mark.asyncio
async def test_tieredmemory_save_and_get_active_context():
    tm = TieredMemory()
    await tm.initialize()
    await tm.save_active_context('s1', 'User: hello')
    got = await tm.get_active_context('s1')
    assert 'User: hello' in got


@pytest.mark.asyncio
async def test_tieredmemory_count_tokens():
    tm = TieredMemory()
    assert tm.count_tokens('hello world') > 0
