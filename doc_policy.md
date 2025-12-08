<!-- Doc & script policy for Context-Engine -->
# Scripting & Documentation Policy

This doc describes the approach we use for canonical scripts, archive rules, and how we evolve scripts across the repository.

1) Canonical Scripts Location
 - Canonical startup and dev scripts live under `scripts/dev/`.
 - Root-level scripts should be thin wrappers that `call` or `exec` the canonical scripts in `scripts/dev/` to keep logic centralized.

2) Naming & Behavior
 - All canonical startup scripts should be named `start-<component>-*.sh` or `start-<component>-*.bat`.
 - Each script should implement these features: preflight checks, readable debug traces, a `--noninteractive` or `CI` mode, and safe defaults where applicable.
 - Scripts that start long-running servers should write logs to `logs/<script-name>.log` when run from `start-all-safe`.
 - Provide helper scripts under `scripts/dev/` for common maintenance tasks such as `verify-models.*` and `archive-old-wrappers.*`.

3) Archiving Policy
 - Historical or redundant scripts in the repo root (or elsewhere) should be moved to `archive/startup-scripts/` with a short commit message describing the motivation.
 - Use `scripts/dev/archive-old-wrappers.*` (bash / PowerShell) to locate thin wrappers and move them into the archive safely. This will keep the repo root tidy and reduce confusion.
 - When moving a script to the archive, add a README entry into `archive/startup-scripts/README.md` indicating what canonical script replaces it and when/why it was archived.

4) Validation & CI
 - Add the `scripts/dev/validate-scripts.*` script to the CI pipeline to ensure canonical scripts exist and follow naming conventions.
 - Consider adding a CI step to verify that root wrappers call canonical scripts (grep for `scripts/dev/start-` inside) and that canonical scripts are referenced from the README(s).

5) Documentation Updates
 - `scripts/README.md` must be the single source of truth for dev-start scripts and describe how to run `start-all-safe`, `start-llama-server-safe`, and handle missing prerequisites.
 - Update `README.md` (project root) to describe the canonical script location and how to run the archive/cleanup operation.

6) Developer Workflow
 - When adding a new startup script, add it to `scripts/dev/`, then create or update the thin wrapper at the repo root that calls it.
 - Update `scripts/README.md` and `doc_policy.md` and consider adding a `scripts/dev/` test that verifies basic health checks succeed (e.g., `curl` to endpoints after starting in a guarded CI job when appropriate).

7) Safety Considerations
 - Avoid starting all services on a developer's machine by default; use `start-all-safe` to try to be conservative on memory usage.
 - Keep interactive model selection optional and provide a `--noninteractive` or `CI` mode that fails fast when resources aren't present.

---
Created by repository maintainers - modify with a PR following the repo contribution guidelines.
