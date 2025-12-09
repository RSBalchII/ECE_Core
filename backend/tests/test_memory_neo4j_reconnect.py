import asyncio
import pytest

from src.memory import TieredMemory
from neo4j import AsyncGraphDatabase


class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run(self, query, params=None):
        class DummyResult:
            async def data(self):
                return []
        return DummyResult()


class DummyDriver:
    def session(self):
        return DummySession()
    async def close(self):
        return None


@pytest.mark.asyncio
async def test_neo4j_reconnect(monkeypatch):
    # Replace driver to raise on first two calls and succeed on third
    calls = {'count': 0}

    def fake_driver_factory(uri, auth=None, max_connection_lifetime=None):
        calls['count'] += 1
        if calls['count'] < 3:
            raise Exception('Simulated Neo4j critical failure')
        return DummyDriver()

    monkeypatch.setattr(AsyncGraphDatabase, 'driver', fake_driver_factory)
    # Reduce delays and attempts for fast test
    from src.config import settings
    monkeypatch.setattr(settings, 'neo4j_reconnect_initial_delay', 0.1)
    monkeypatch.setattr(settings, 'neo4j_reconnect_max_attempts', 5)
    monkeypatch.setattr(settings, 'neo4j_reconnect_backoff_factor', 1.0)

    mem = TieredMemory()
    await mem.initialize()
    # Wait a few seconds for reconnect attempts
    await asyncio.sleep(0.5)
    # After some attempts, either driver is set or reconnect task exists
    assert mem._neo4j_reconnect_task is not None
    # Wait a little longer for success if possible
    await asyncio.sleep(0.5)
    assert mem.neo4j_driver is not None
    # Clean up
    await mem.close()
