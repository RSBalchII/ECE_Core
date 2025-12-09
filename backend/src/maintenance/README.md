# Maintenance & Weaver

This folder contains maintenance workflows and utilities for the ECE_Core knowledge graph and memory repairs.

Key files:
- `weaver.py` — MemoryWeaver class which schedules and runs repair cycles using `run_repair`.
- `repair_wrapper.py` — Import wrapper for the script-based implementation. The wrapper tries multiple import candidates and provides `run_repair(*args, **kwargs)`.

Import notes:
- The preferred import path is `from src.maintenance.repair_wrapper import run_repair`.
- The wrapper will dynamically import one of the script-based implementations from the `scripts/neo4j/repair` folder. This helps avoid package import breakage if the script is moved.

Running weaver:
- MemoryWeaver runs in dry-run by default. It respects `WEAVER_COMMIT_ENABLED` and other settings in `src/config.py`.
- Example (dry-run):
```pwsh
cd ece-core
python -c "from src.maintenance.weaver import MemoryWeaver; import asyncio; mw = MemoryWeaver(); asyncio.run(mw.weave_recent(hours=24, dry_run=True, csv_out='weaver_dry.csv'))"
```

Troubleshooting:
- If `ModuleNotFoundError` arises from `repair_wrapper`, verify the script file `ece-core/scripts/neo4j/repair/repair_missing_links_similarity_embeddings.py` exists and defines `run_repair`.
- If repair scripts change signatures, `repair_wrapper.run_repair` does introspection and will filter kwargs to match the current signature.
