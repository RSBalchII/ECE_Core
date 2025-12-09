import os
import json
import pytest
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.parent
BENCH = HERE / "benchmarks"

@pytest.mark.integration
@pytest.mark.skipif(not (BENCH / "compare_memlayer_vs_ece.py").exists(), reason="No benchmark script found")
def test_run_benchmark_ece_only():
    # Run with ECE only
    env = os.environ.copy()
    # Skip if ECE isn't listening on 127.0.0.1:8000
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            pass
    except Exception:
        pytest.skip("ECE server not up on 127.0.0.1:8000 - skipping benchmark")
    # Use ECE running on default local port
    cmd = [sys.executable, str(BENCH / "compare_memlayer_vs_ece.py"), "--ece-url", "http://localhost:8000"]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
    print(res.stdout)
    assert res.returncode == 0, f"Benchmark failed: {res.stderr}"
    # Expect results json to exist
    rjson = BENCH / "results" / "ece_results.json"
    assert rjson.exists(), "ece results file not found"
    data = json.loads(rjson.read_text(encoding='utf-8'))
    # We expect there to be entries for each query
    assert len(data) >= 3
    # sanity: check keys exist
    for entry in data:
        assert "id" in entry and "system" in entry and "found" in entry


@pytest.mark.integration
def test_salience_saves_expected_facts():
    # Run a small sequence of chat messages to simulate salience
    import requests
    from benchmarks.compare_memlayer_vs_ece import run_ece_salience_test

    ece_url = "http://localhost:8000"
    # Skip if ECE doesn't respond on default port
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            pass
    except Exception:
        pytest.skip("ECE server not up on 127.0.0.1:8000 - skipping integration benchmark")
    session = requests.Session()
    results = run_ece_salience_test(ece_url, session)
    # Expect at least 1 salient fact (Alice at TechCorp) to be stored in ECE
    assert any("alice" in (m.get("content", "").lower()) for m in results), f"ECE salience did not store expected fact: {results}"
