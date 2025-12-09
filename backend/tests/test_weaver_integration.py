import asyncio
import os
import sys
import uuid
import pytest
from unittest.mock import AsyncMock

# Ensure project root is in sys.path for 'src' imports in test harness
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.maintenance.weaver import MemoryWeaver
from src.agents.archivist import ArchivistAgent


def test_weaver_run_returns_run_id(monkeypatch, tmp_path):
    """Test that MemoryWeaver runs and returns a run_id when run_repair is patched."""

    # Patch run_repair so no real DB calls occur
    async def fake_run_repair(*args, **kwargs):
        # confirm run_id present
        assert 'run_id' in kwargs or 'run_id' in kwargs
        return None
    # monkeypatch the run_repair function used by the weaver via the repair_wrapper reference
    # The repair_wrapper resolves the concrete implementation at import time; patching
    # the wrapper's `_run_repair_fn` is robust against which candidate module is chosen.
    import src.maintenance.repair_wrapper as rw
    monkeypatch.setattr(rw, '_run_repair_fn', AsyncMock(side_effect=fake_run_repair))

    weaver = MemoryWeaver()
    result = asyncio.run(weaver.weave_recent(hours=1, dry_run=True, csv_out=str(tmp_path/'weaver_test.csv')))
    assert isinstance(result, dict)
    assert 'run_id' in result
    # verify UUID format
    assert isinstance(uuid.UUID(result['run_id']), uuid.UUID)


def test_weaver_commit_flag_respected(monkeypatch, tmp_path):
    """Test that MemoryWeaver respects the master switch setting and sets commit=True when enabled."""
    recorded = {}

    async def fake_run_repair(*args, **kwargs):
        recorded.update(kwargs)
        return None

    # Patch _run_repair_fn in the wrapper for stability across module candidates
    import src.maintenance.repair_wrapper as rw
    monkeypatch.setattr(rw, '_run_repair_fn', AsyncMock(side_effect=fake_run_repair))
    weaver = MemoryWeaver()
    # Toggle global settings to commit mode
    from src.config import settings as s
    s.weaver_commit_enabled = True
    # run
    asyncio.run(weaver.weave_recent(hours=1, dry_run=None, csv_out=str(tmp_path/'weaver_test_commit.csv')))
    # We expect commit=True in kwargs passed into run_repair
    assert recorded.get('commit') is True
    # restore
    s.weaver_commit_enabled = False


def test_archivist_integration_runs_weaver(monkeypatch):
    """Test that ArchivistAgent exposes run_weaving_cycle and delegates to MemoryWeaver."""

    # simple dummy memory & verifier so the Archivist can be constructed
    class DummyMemory:
        pass
    class DummyVerifier:
        async def verify_claim(self, content, context):
            return {'score': 1.0, 'verified': True}

    # patch the run_repair used by the weaver
    async def fake_run_repair(*args, **kwargs):
        return None
    # patch the wrapper's internal _run_repair_fn to our fake
    import src.maintenance.repair_wrapper as rw
    monkeypatch.setattr(rw, '_run_repair_fn', AsyncMock(side_effect=fake_run_repair))

    archivist = ArchivistAgent(DummyMemory(), DummyVerifier())
    # run a weave cycle (dry-run expected by default)
    result = asyncio.run(archivist.run_weaving_cycle(hours=1, dry_run=True))
    assert isinstance(result, dict)
    assert 'run_id' in result
    # check that archivist created a weaver successfully
    assert hasattr(archivist, 'weaver')


def test_archivist_commit_flag(monkeypatch, tmp_path):
    """Ensure Archivist's run_weaving_cycle honors the global weaver_commit_enabled setting when run."""
    # Patch the run_repair call
    recorded = {}

    async def fake_run_repair(*args, **kwargs):
        recorded.update(kwargs)
        return None

    import src.maintenance.repair_wrapper as rw
    monkeypatch.setattr(rw, '_run_repair_fn', AsyncMock(side_effect=fake_run_repair))
    # setup Archivist with Dummy Memory & Verifier
    class DummyMemory: pass
    class DummyVerifier:
        async def verify_claim(self, content, context):
            return {'score': 1.0, 'verified': True}

    from src.config import settings as s
    s.weaver_commit_enabled = True
    archivist = ArchivistAgent(DummyMemory(), DummyVerifier())
    result = asyncio.run(archivist.run_weaving_cycle(hours=1, dry_run=None))
    assert isinstance(result, dict)
    assert 'run_id' in result
    assert recorded.get('commit') is True
    s.weaver_commit_enabled = False
    # The Archivist's run_weaving_cycle delegates to the Weaver and returns a run_id.
    # We simply verify that it returns a run_id and that the weaver attribute exists.
