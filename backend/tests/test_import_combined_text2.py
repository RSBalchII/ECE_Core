import json
import importlib.util
import sys
import asyncio
from pathlib import Path
import pytest

import src.config as cfg


class FakeNeo4jStore:
    def __init__(self, *args, **kwargs):
        # presence of neo4j_driver used by script to detect connectivity
        self.neo4j_driver = object()
        self.calls = []

    async def initialize(self):
        return

    async def close(self):
        return

    async def add_memory(self, **kwargs):
        self.calls.append(kwargs)
        # Simulate create and return a fake id
        return 12345


def load_script_module(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "import_combined_text2.py"
    spec = importlib.util.spec_from_file_location("import_combined_text2", str(script_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_import_skips_thinking_and_inserts_others(monkeypatch, tmp_path):
    module = load_script_module(tmp_path)

    # Create a sample JSON file
    sample = [
        {"response_content": "Hello from response", "tags": ["test"]},
        {"thinking_content": "Internal thought log"},
        {"content": "Regular content", "thinking_content": "internal"},
    ]
    fpath = tmp_path / "ct_sample.json"
    fpath.write_text(json.dumps(sample, ensure_ascii=False))

    # Monkeypatch Neo4jStore in src.memory.neo4j_store to our fake
    import src.memory.neo4j_store as nstore
    monkeypatch.setattr(nstore, "Neo4jStore", FakeNeo4jStore)

    # Also set a predictable session id in settings
    cfg.settings.anchor_session_id = "test-import"

    # Run import: commit mode so it tries to call add_memory
    results = await module.import_file(fpath, commit=True, include_thinking=False, dedupe=True, session_id_override='test-import')

    # Ensure we have results for all entries
    assert len(results) == 3

    # Retrieve fake store instance via calling location - we created it per module import
    mock_store = FakeNeo4jStore()

    # The module created its own Neo4jStore instance; monkeypatching only replaces the constructor.
    # Validate that output indicates two insert attempts (first and third) and one skipped.
    inserted_count = len([r for r in results if r.get("inserted")])
    assert inserted_count == 2
    # Ensure the second entry was skipped as thinking_content
    assert results[1]["reason"] == "thinking_content_skipped"


@pytest.mark.asyncio
async def test_import_respects_dedupe_flag(monkeypatch, tmp_path):
    module = load_script_module(tmp_path)

    sample = [
        {"response_content": "Unique content"},
    ]
    fpath = tmp_path / "ct_sample2.json"
    fpath.write_text(json.dumps(sample))

    calls = []

    class TrackStore(FakeNeo4jStore):
        async def add_memory(self, **kwargs):
            calls.append(kwargs)
            return 6789

    import src.memory.neo4j_store as nstore
    monkeypatch.setattr(nstore, "Neo4jStore", TrackStore)

    cfg.settings.anchor_session_id = "test-import"

    # Dedupe enabled (default) => content_hash should be present
    results = await module.import_file(fpath, commit=True, include_thinking=False, dedupe=True, session_id_override='test-import')
    assert len(calls) == 1
    assert calls[0].get("content_hash") is not None
    assert calls[0].get("session_id") == 'test-import'

    calls.clear()
    # Dedupe disabled -> no content_hash param passed
    results = await module.import_file(fpath, commit=True, include_thinking=False, dedupe=False, session_id_override='test-import')
    assert len(calls) == 1
    assert calls[0].get("content_hash") is None
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "ece-core" / "scripts" / "import_combined_text2.py"


def test_import_combined_text2_dryrun():
    # Run script with dry-run and file path set to combined_text2.txt
    file_path = REPO_ROOT / "ece-core" / "combined_text2.txt"
    assert file_path.exists(), "combined_text2.txt not found in ece-core"

    args = [sys.executable, str(SCRIPT), "--file", str(file_path), "--dry-run"]
    res = subprocess.run(args, capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    assert res.returncode == 0
    # expecting JSON result array in stdout
    assert res.stdout.strip().startswith('[')
