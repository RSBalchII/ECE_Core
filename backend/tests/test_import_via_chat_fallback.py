import importlib.util
import sys
import os
import json
import types
from types import SimpleNamespace

import pytest


def load_script():
    path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'import_via_chat.py')
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location("import_via_chat", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code=200, text='ok', json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data or {"status": "ok"}

    def json(self):
        return self._json


def test_chat_failure_auto_fallback(monkeypatch, tmp_path, capsys):
    module = load_script()
    # Write a small file to import
    p = tmp_path / "small.txt"
    p.write_text("One line about Sybil")

    calls = []

    def fake_get(url, timeout=None):
        calls.append(("get", url))
        # Health check says API is up
        return FakeResponse(status_code=200)

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(("post", url, json))
        if url.endswith('/chat'):
            raise Exception("connection refused")
        if url.endswith('/memories'):
            return FakeResponse(status_code=200, json_data={"status": "success"})
        return FakeResponse()

    monkeypatch.setattr('requests.get', fake_get)
    monkeypatch.setattr('requests.post', fake_post)

    # Call script main with args
    sys_argv = ["import_via_chat.py", "--file", str(p), "--api", "http://127.0.0.1:8001", "--limit", "1", "--auto-fallback", "--session", "import_test", "--chunk-size", "100"]
    monkeypatch.setattr(sys, 'argv', sys_argv)

    # Run
    module.main()

    # Expect that POST /memories was attempted (after chat failure)
    assert any(call[0] == 'post' and call[1].endswith('/memories') for call in calls)
    # Check output indicates success
    captured = capsys.readouterr()
    assert "Import finished" in captured.out
