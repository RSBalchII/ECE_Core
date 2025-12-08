Cleanup & Archival Plan for Startup Scripts
==========================================

This document provides a conservative, step-by-step plan to clean up legacy startup scripts and consolidate canonical scripts under `scripts/dev/`.

Principles
----------
- Keep one canonical copy of each script under `scripts/dev/`.
- Root-level wrappers should remain thin and only call `scripts/dev/*` scripts.
- Archive (move, but preserve) any historical or redundant root-level scripts to `archive/startup-scripts/`.
- Update docs and README before removing anything from root to avoid breaking developer workflows.

Checklist (manual)
------------------
1. Audit root-level `start-*.*` files and confirm whether they are thin wrappers calling `scripts/dev/start-*`.
2. If a wrapper is a thin wrapper, add a short mention to `archive/startup-scripts/README.md` and move it to `archive/startup-scripts/` (use `scripts/dev/archive-old-wrappers.*` script).
3. If a wrapper contains unique behavior not present in `scripts/dev/`, either:
   - Move the unique logic into the canonical script and convert the root script to a wrapper; or
   - Keep it but add a clear README comment explaining why it's special.
4. Update `scripts/README.md` and `README.md` to add references to new helpers and archive policies.
5. Run `scripts/dev/validate-scripts.*` and consider adding to CI to ensure canonical scripts and wrappers are consistent.

Checklist (automated)
---------------------
1. Run `scripts/dev/validate-scripts.sh` to enumerate canonical scripts.
2. Run `scripts/dev/archive-old-wrappers.sh` or `scripts/dev/archive-old-wrappers.ps1` to move thin wrappers to archive.
3. Add a commit message for the archival step indicating the new canonical script (e.g., "archive: moved start-llama-server.bat (thin wrapper) to archive/startup-scripts/ – now calls scripts/dev/start-llama-server.bat").
4. Create a PR with these changes and request review from a maintainer to ensure nothing breaks CI or tooling.

Post-cleanup validation
------------------------
- Run `scripts/dev/validate-scripts.*` in CI.
- Run `select_model.py` and `scripts/dev/verify-models.*` locally and ensure interactive selection still works.
- Run `start-all-safe` locally and confirm it starts LLaMa, ECE core, and optionally proxy/mcp as expected.

Safe revert plan
----------------
- If a removed wrapper is needed, move it back from `archive/startup-scripts/` and include a unit test in CI to prevent accidental removal in the future.

Notes
-----
 - If a wrapper is popular and used externally (e.g. scripts called by automation or onboarding guides), keep the wrapper and add a note that it is a thin wrapper referencing the canonical script.
 - Communicate any breaking changes in the release notes and docs.

---
This plan is designed to be conservative and avoid breaking developer workflows. For automation, use the provided archiver scripts and validate results via `validate-scripts.*` and CI checks.
