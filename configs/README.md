# Configs directory

This folder contains consolidated configuration defaults for the repository.

- `config.yaml` — canonical YAML defaults used by the app when no environment variable overrides are present.
- `.env.example` — example env variables to copy into `configs/.env` for local setup.

Prefer `configs/.env` for local/developer overrides. The loader looks for `configs/.env` and then root `.env`.

When updating defaults, update `configs/config.yaml` and `configs/.env.example`.
