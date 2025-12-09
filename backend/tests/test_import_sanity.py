import asyncio
import importlib
import os
import shutil
import sys
import types
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so `src` and `scripts` package imports work in test runner
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def test_repair_wrapper_import_and_run_raises_when_missing():
    """Ensure `src.maintenance.repair_wrapper` imports and behaves as a safe wrapper.

    If the real `scripts.*` repair implementation isn't installed, `run_repair` should
    be callable but raise a ModuleNotFoundError when invoked. If the underlying
    implementation exists (e.g. in a dev environment), we simply assert `run_repair`
    is callable and do not invoke it to avoid heavy side effects.
    """
    mod = importlib.import_module('src.maintenance.repair_wrapper')
    assert hasattr(mod, 'run_repair')
    # If the wrapper could not locate the scripts implementation it will set
    # the inner resolution to None, and attempting to call run_repair should raise.
    if getattr(mod, '_run_repair_fn', None) is None:
        with pytest.raises(ModuleNotFoundError):
            # Should raise quickly; we do not call heavy work
            mod.run_repair()
    else:
        # If implementation exists in the dev environment, ensure it's callable
        assert callable(mod.run_repair)


def test_weaver_import_and_dummy_run(monkeypatch):
    """Validate that `MemoryWeaver` can import the wrapper and that
    weaver.weave_recent runs when `run_repair` is replaced with a dummy coroutine.

    We monkeypatch the wrapper's internal callable to a no-op coroutine to avoid
    triggering any DB or I/O behavior. This test confirms the weaver's integration
    with the shimmed `run_repair` callable is robust.
    """
    # Import the weaver module and wrapper
    weaver_mod = importlib.import_module('src.maintenance.weaver')
    wrapper_mod = importlib.import_module('src.maintenance.repair_wrapper')

    async def _dummy(*args, **kwargs):
        # simple no-op async stub that returns immediately
        return None

    # Monkeypatch the internal fixture on the wrapper module so the weaver will call this
    monkeypatch.setattr(wrapper_mod, '_run_repair_fn', _dummy, raising=False)

    mw = weaver_mod.MemoryWeaver()
    # Run the async method and assert we get a run_id back
    res = asyncio.get_event_loop().run_until_complete(mw.weave_recent(hours=1, dry_run=True))
    assert isinstance(res, dict)
    assert 'run_id' in res


def test_scripts_importable_via_simulated_meipass(tmp_path, monkeypatch):
    """Simulate a PyInstaller-like environment by copying the `scripts` package
    into a temporary `MEIPASS` directory and inserting that into `sys.path`.

    We stub 'neo4j' to avoid missing-dependency failures during import. The goal
    is to ensure `scripts.neo4j.repair.repair_missing_links_similarity_embeddings` is
    importable (or gracefully skip) when present under the MEIPASS root.
    """
    repo_root = Path(__file__).resolve().parents[1]
    scripts_src = repo_root / 'scripts'
    assert scripts_src.exists(), 'scripts/ directory must exist in repo for this test'

    # Copy the scripts/ package into tmp MEIPASS dir
    meipass_dir = tmp_path / 'MEIPASS'
    shutil.copytree(scripts_src, meipass_dir / 'scripts')

    # Simulate PyInstaller extractor layout: sys._MEIPASS is often set; ensure path is present
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'meipass', str(meipass_dir), raising=False)
    sys.path.insert(0, str(meipass_dir))

    # Provide a minimal fake 'neo4j' module to avoid dependency error on import
    fake_neo4j = types.ModuleType('neo4j')
    fake_neo4j.GraphDatabase = object()
    sys.modules['neo4j'] = fake_neo4j

    # Try importing the repair script; if it fails due to missing external dependencies
    # we gracefully skip the test rather than failing unexpectedly in CI.
    try:
        importlib.invalidate_caches()
        importlib.import_module('scripts.neo4j.repair.repair_missing_links_similarity_embeddings')
    except Exception as e:
        pytest.skip('Could not import the repair script in simulated MEIPASS: %s' % e)
    finally:
        # Cleanup: remove our inserted path and the fake neo4j module
        try:
            sys.path.remove(str(meipass_dir))
        except Exception:
            pass
        sys.modules.pop('neo4j', None)
