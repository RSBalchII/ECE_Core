"""Safe wrapper for the repair script implementation.

This helper exposes `run_repair` while delegating to the scripts-based implementation.
It avoids editing or duplicating heavy logic and ensures a stable `src` import path.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _load_run_repair():
    candidates = (
        'scripts.neo4j.repair.repair_missing_links_similarity_embeddings',
        'scripts.repair_missing_links_similarity_embeddings',
    )
    for cand in candidates:
        try:
            mod = importlib.import_module(cand)
            if hasattr(mod, 'run_repair'):
                return getattr(mod, 'run_repair')
        except Exception:
            logger.debug('repair_wrapper: failed to import %s', cand, exc_info=True)
    raise ModuleNotFoundError('repair_wrapper: could not find run_repair on candidates: %s' % ','.join(candidates))


try:
    _run_repair_fn = _load_run_repair()
except ModuleNotFoundError:
    _run_repair_fn = None


def run_repair(*args: Any, **kwargs: Any):
    if not _run_repair_fn:
        raise ModuleNotFoundError('repair_wrapper: run_repair not available; ensure scripts package is present and importable')
    # Filter kwargs to only those accepted by the underlying implementation to maintain compatibility
    try:
        import inspect
        sig = inspect.signature(_run_repair_fn)
        accepted = set(sig.parameters.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in accepted}
    except Exception:
        # If introspection fails for any reason, fall back to passing all kwargs
        filtered_kwargs = kwargs
    return _run_repair_fn(*args, **filtered_kwargs)


__all__ = ['run_repair']
