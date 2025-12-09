Benchmarks: ECE_Core memory & retrieval
=================================

This folder contains a small benchmark and test harness to compare ECE_Core's memory & retrieval components and to measure RAG-relevant metrics.

Goals:
- Measure recall (does the system surface the expected memory?)
- Measure retrieval latency
- Measure ranking (position of expected memory)
- Measure salience (what is stored) and graph traversal for entity-connected queries

Requirements:
- ECE_Core running (default: http://localhost:8000)

Quick start (PowerShell):
```pwsh
# Run ECE_Core services in one terminal (Neo4j + Redis + ECE_Core)
cd C:\Users\rsbiiw\Projects\ECE_Core
# start services or ensure they are running
python -m uvicorn main:app --reload

# In a separate terminal, run the benchmark
cd C:\Users\rsbiiw\Projects\ECE_Core\benchmarks
python compare_memlayer_vs_ece.py --ece-url http://localhost:8000
```

Notes:
- Results are printed as JSON summary and as CSV files saved under `benchmarks/results/` (e.g., `ece_results.json` / `ece_results.csv`).
