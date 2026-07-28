# Standard 002: Reproducible Benchmarking

**Status:** Active  
**Date:** 2026-03-13  
**Supersedes:** Standard 005 (original), `benchmarks/run_benchmark.js` and `test-search-live.js` conventions

## Context
To maintain predictable performance and detect regressions, all benchmarks must be reproducible. This includes search latency, ingestion throughput, and memory usage.

## Requirements
1. **Seeded Randomness:** All benchmarks must accept a `--seed` parameter to initialize random number generators, ensuring identical runs produce identical results.
2. **Comparison Mode:** Benchmarks must support a `--compare` flag that compares current results against a known good baseline and exits with an error if results deviate beyond a defined threshold.
3. **Concurrency Testing:** When testing concurrency (e.g., multiple simultaneous searches), the benchmark must respect the adaptive concurrency settings defined in Standard 005 and log the effective concurrency used.
4. **Standardized Output:** Benchmark scripts must output results in a machine‑readable format (JSON) with timestamps and system information (platform, free memory, CPU).

## Implementation Notes
- The script `benchmarks/run_benchmark.js` already implements seed and comparison logic; it should be updated to output JSON.
- `test-search-live.js` should be extended to log concurrency mode and results in the same format.