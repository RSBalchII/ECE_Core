import json
import sys
import importlib.util
from pathlib import Path
import pytest

import src.config as cfg


def load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "import_prompt_logs.py"
    spec = importlib.util.spec_from_file_location("import_prompt_logs", str(script_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeNeo4jStore:
    def __init__(self, *args, **kwargs):
        self.neo4j_driver = object()
        self.calls = []

    async def initialize(self):
        return

    async def close(self):
        return

    async def add_memory(self, **kwargs):
        self.calls.append(kwargs)
        return 999


def write_sample(prompt_path: Path):
    content = """
You: Good afternoon!
Assistant: I'm doing well, thank you for asking.
You: I am testing out your memory harness. what do you recall?
Assistant: <memory> We had a good morning greeting. </memory>
"""
    prompt_path.write_text(content)
    return content


@pytest.mark.asyncio
async def test_prompt_logs_parsing(monkeypatch, tmp_path):
    module = load_script_module()
    prompt_path = tmp_path / "prompt-logs.txt"
    sample = write_sample(prompt_path)
    # monkeypatch store
    import src.memory.neo4j_store as nstore
    monkeypatch.setattr(nstore, 'Neo4jStore', FakeNeo4jStore)
    cfg.settings.anchor_session_id = 'test-session'

    results = await module.import_file(prompt_path, commit=True, include_thinking=False, dedupe=True, session_id_override='test-session')
    assert len(results) > 0
    assert all('index' in r for r in results)


def test_cli_dryrun(tmp_path):
    # Ensure the script runs in dry-run mode and outputs JSON
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'import_prompt_logs.py'
    prompt_path = tmp_path / 'prompt-logs.txt'
    write_sample(prompt_path)
    import subprocess, sys
    res = subprocess.run([sys.executable, str(script), '--file', str(prompt_path), '--dry-run'], capture_output=True, text=True)
    assert res.returncode == 0
    assert res.stdout.strip().startswith('[')
