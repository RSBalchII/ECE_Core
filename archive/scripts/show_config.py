"""Utility to print the resolved configuration used by the app.

This helps debugging: it will show config that comes from env -> YAML -> defaults.
"""
import os
import json
from importlib import reload
from pathlib import Path

import dotenv

# Load .env from configs/ or root
repo_root = Path(__file__).resolve().parents[1]
configs_dir = repo_root / 'configs'
for p in (configs_dir / '.env', repo_root / '.env'):
    if p.exists():
        dotenv.load_dotenv(str(p), override=False)
        break

# Ensure the src package path
from src import config as cfg
# reload to pick up env changes
reload(cfg)

settings = cfg.settings
# Only display a subset of settings for debugging
keys = [k for k in dir(settings) if not k.startswith('_') and k.islower()]

out = {k: getattr(settings, k) for k in keys if not callable(getattr(settings, k))}
print(json.dumps(out, indent=2, default=str))
