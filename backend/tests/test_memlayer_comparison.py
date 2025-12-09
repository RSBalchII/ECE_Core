def test_run_benchmark_ece_only():
    # This test is deprecated - see tests/test_benchmarks.py
    import pytest
    pytest.skip("Deprecated - benchmark tests now in tests/test_benchmarks.py")
    env = os.environ.copy()
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


def test_salience_saves_expected_facts():
    import pytest
    pytest.skip("Deprecated - see tests/test_benchmarks.py")
