Archived startup scripts
=======================

This directory contains historical or redundant startup scripts moved from the repository root as part of the canonicalization effort. The canonical, supported copies live under `scripts/dev/`.

When moving a script here, include a short note in the commit message stating the reason (e.g., "archived root wrapper, now calls scripts/dev/start-llama-server.bat").

If a script here is still needed for compatibility, add a README snippet explaining how to recreate its behavior using `scripts/dev/` or why it was retained.
Archived startup scripts & notes

This folder holds older or deprecated startup scripts that are no longer part of the canonical `scripts/dev` set. We keep them for historical purposes and to make it easier to restore a script if needed.

Policy:
- Migrate canonical scripts to `scripts/dev/` and keep minimal compatibility wrappers in the repo root.
- When a script is deprecated, move its full logic to `archive/startup-scripts/` and replace the root script with a wrapper to the canonical copy (if applicable).

Files here:
- None currently — all active startup scripts have been moved into `scripts/dev/` and the root contains wrappers for backward compatibility.

If you'd like files to be archived here, follow the pattern:
1) Copy the current script to `archive/startup-scripts/` with a timestamp in the filename
2) Replace the root script with a wrapper pointing to `scripts/dev/` (if a canonical version exists)
3) Update `scripts/README.md` and `README.md` to document the change
