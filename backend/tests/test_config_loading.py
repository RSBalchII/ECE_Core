import os
from urllib.parse import urlparse

from src.config import Settings


def test_yaml_config_parsed_from_repo_root(tmp_path, monkeypatch):
    # The repository already has a `configs/config.yaml`; Settings should pick it up
    monkeypatch.delenv('SERVER_HOST', raising=False)
    monkeypatch.delenv('SERVER_PORT', raising=False)
    monkeypatch.delenv('MCP_URL', raising=False)
    from importlib import reload, import_module
    reload(import_module('src.config'))
    # Recreate settings from the freshly reloaded module
    from importlib import import_module as _import
    settings_module = _import('src.config')
    s = settings_module.Settings()
    # The default config in repo `configs/config.yaml` sets mcp.url to http://localhost:8008
    assert s.mcp_url is None or s.mcp_host in ("localhost", "127.0.0.1")
    # Ensure that mcp_host and mcp_port are populated, and that server.host set from YAML maps to ece_host
    assert isinstance(s.mcp_host, str)
    assert isinstance(int(s.mcp_port), int)
    # To be robust, compare with the YAML directly if present
    import yaml
    cfg_path = 'configs/config.yaml'
    if os.path.exists(cfg_path):
        raw = yaml.safe_load(open(cfg_path).read()) or {}
        server_host_from_yaml = raw.get('server', {}).get('host')
        if server_host_from_yaml is not None:
            assert s.ece_host == server_host_from_yaml


def test_env_override_for_mcp_url(monkeypatch):
    monkeypatch.setenv("MCP_URL", "http://127.0.0.1:9000")
    s = Settings()
    # Parsed host / port should reflect the override
    assert s.mcp_host == "127.0.0.1"
    assert int(s.mcp_port) == 9000


def test_server_host_port_override(monkeypatch):
    monkeypatch.setenv("SERVER_HOST", "0.0.0.0")
    monkeypatch.setenv("SERVER_PORT", "8000")
    s = Settings()
    assert s.ece_host == "0.0.0.0"
    assert int(s.ece_port) == 8000


def test_mcp_runner_invokes_uvicorn(monkeypatch):
    # Ensure we don't actually start the server; monkeypatch uvicorn.run
    monkeypatch.setenv('MCP_URL', 'http://127.0.0.1:9876')
    monkeypatch.setenv('MCP_ENABLED', 'true')
    # Reload Settings and the module under test; ensure environment var is actually read
    from importlib import reload, import_module
    import src
    reload(import_module('src.config'))
    reload(import_module('src.mcp_runner'))
    import src.mcp_runner as runner
    import uvicorn

    called = {}

    def fake_run(app, host, port, log_level):
        called['host'] = host
        called['port'] = port
        called['app'] = app

    monkeypatch.setattr(uvicorn, 'run', fake_run)
    # Call main; it should invoke fake_run and return immediately
    runner.main()
    assert called.get('host') in ('127.0.0.1', 'localhost')
    assert int(called.get('port')) in (9876,)


def test_mcp_runner_respects_disabled(monkeypatch):
    monkeypatch.setenv('MCP_ENABLED', 'false')
    from importlib import reload, import_module
    reload(import_module('src.config'))
    runner = import_module('src.mcp_runner')
    reload(runner)
    import uvicorn

    invoked = {'called': False}

    def fake_run(app, host, port, log_level):
        invoked['called'] = True

    monkeypatch.setattr(uvicorn, 'run', fake_run)
    # Should not call uvicorn.run when MCP is disabled
    runner.main()
    assert invoked['called'] is False
