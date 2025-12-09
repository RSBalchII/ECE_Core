"""Compatibility shim for src.maintenance.repair.

This module re-exports `run_repair` from `src.maintenance.repair_wrapper` for
backwards compatibility. Keep it minimal to avoid duplication and errors.
"""
from __future__ import annotations

from src.maintenance.repair_wrapper import run_repair

__all__ = ['run_repair']
"""Compatibility shim for src.maintenance.repair.

This module re-exports `run_repair` from `src.maintenance.repair_wrapper` for
backwards compatibility.
"""
from __future__ import annotations

from src.maintenance.repair_wrapper import run_repair

__all__ = ['run_repair']
"""src.maintenance.repair

Lightweight wrapper that exposes `run_repair` from the scripts-based implementation while
providing a stable `src`-side import path for packaging.

This does not copy the heavy repair logic; it simply delegates to the implementation in
`scripts/neo4j/repair/repair_missing_links_similarity_embeddings.py` (or the legacy
`scripts/repair_missing_links_similarity_embeddings.py`). This keeps maintenance code in
one place, while enabling packaged builds to import `run_repair` from `src`.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _find_run_repair():
    candidates = (
        'scripts.neo4j.repair.repair_missing_links_similarity_embeddings',
        'scripts.repair_missing_links_similarity_embeddings',
    )
    last_exc = None
    for c in candidates:
        try:
            mod = importlib.import_module(c)
            if hasattr(mod, 'run_repair'):
                return getattr(mod, 'run_repair')
        except Exception as e:
            last_exc = e
            logger.debug('repair wrapper: import failed for %s: %s', c, e)
    raise ModuleNotFoundError('run_repair not importable; tried: %s' % ','.join(candidates)) from last_exc


# resolve eagerly at import time; if unavailable, callers will get a ModuleNotFoundError
try:
    _run_repair = _find_run_repair()
except ModuleNotFoundError:
    _run_repair = None


def run_repair(*args: Any, **kwargs: Any):
    """Proxy to the real `run_repair` implementation.

    Returns the coroutine produced by the underlying implementation (do not await here).
    """
    if not _run_repair:
        raise ModuleNotFoundError('run_repair not available; ensure scripts package exists and is importable')
    return _run_repair(*args, **kwargs)


__all__ = ['run_repair']
"""
Repair wrapper for run_repair.

This module provides a stable import for MemoryWeaver and other src code to call
`run_repair` without relying on dynamic imports of the `scripts` package.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _import_candidate() -> Any:
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
            logger.debug('repair wrapper: failed to import %s', cand, exc_info=True)
    raise ModuleNotFoundError('Could not import run_repair from candidates: %s' % (', '.join(candidates),))


_run_repair = None
try:
    _run_repair = _import_candidate()
except ModuleNotFoundError:
    _run_repair = None


def run_repair(*args: Any, **kwargs: Any):
    """Delegate to the underlying repair script's `run_repair`.

    Raises ModuleNotFoundError if the underlying script isn't available.
    """
    if not _run_repair:
        raise ModuleNotFoundError('run_repair not available; ensure scripts package is present')
    return _run_repair(*args, **kwargs)


__all__ = ['run_repair']
"""
Repair wrapper that exposes `run_repair` to be imported as a src module.

This wrapper imports the implementation that currently resides under
`scripts.neo4j.repair.repair_missing_links_similarity_embeddings` and
re-exports `run_repair` so that code under `src` can import it reliably.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _import_run_repair():
    """Attempt to import run_repair from known candidate module paths.

    Returns the callable if found, otherwise raises ModuleNotFoundError.
    """
    candidates = [
        'scripts.neo4j.repair.repair_missing_links_similarity_embeddings',
        'scripts.repair_missing_links_similarity_embeddings',
    ]
    for cand in candidates:
        try:
            mod = importlib.import_module(cand)
            if hasattr(mod, 'run_repair'):
                return getattr(mod, 'run_repair')
        except Exception:
            logger.debug('repair wrapper could not import %s', cand, exc_info=True)
    raise ModuleNotFoundError("Could not import run_repair from scripts.* candidates: %s" % candidates)


# Try to import the repair function at import time so that callers can directly use it.
_run_repair = None
try:
    _run_repair = _import_run_repair()
except ModuleNotFoundError:
    _run_repair = None


def run_repair(*args: Any, **kwargs: Any):
    """Call the underlying `run_repair` implementation.

    This wrapper provides a stable import path under `src.maintenance.repair` and
    will raise a clear error if the underlying script is not available.
    """
    if not _run_repair:
        raise ModuleNotFoundError("run_repair is not available; ensure repair scripts package is installed or the project root contains the scripts/ package")
    # Delegate call to the real run_repair (async function). We return its coroutine.
    return _run_repair(*args, **kwargs)


__all__ = ['run_repair']
"""
Repair wrapper that exposes `run_repair` to be imported as a src module.

This wrapper imports the implementation that currently resides under
`scripts.neo4j.repair.repair_missing_links_similarity_embeddings` and
re-exports `run_repair` so that code under `src` can import it reliably.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _import_run_repair():
    candidates = [
        'scripts.neo4j.repair.repair_missing_links_similarity_embeddings',
        'scripts.repair_missing_links_similarity_embeddings',
    ]
    for cand in candidates:
        try:
            mod = importlib.import_module(cand)
            if hasattr(mod, 'run_repair'):
                return getattr(mod, 'run_repair')
        except Exception:
            logger.debug('repair wrapper could not import %s', cand, exc_info=True)
    raise ModuleNotFoundError("Could not import run_repair from scripts.* candidates: %s" % candidates)


_run_repair = None

try:
    _run_repair = _import_run_repair()
except ModuleNotFoundError:
    # Defer raising until a caller attempts to use run_repair
    _run_repair = None


def run_repair(*args: Any, **kwargs: Any):
    """Call the underlying `run_repair` implementation.

    This wrapper provides a stable import path under `src.maintenance.repair` and
    will raise a clear error if the underlying script is not available.
    """
    if not _run_repair:
        raise ModuleNotFoundError("run_repair is not available; ensure repair scripts package is installed or the project root contains the scripts/ package")
    # Delegate call to the real run_repair (async function). We return its coroutine.
    return _run_repair(*args, **kwargs)


__all__ = ['run_repair']
"""
Repair wrapper that exposes `run_repair` to be imported as a src module.

This wrapper imports the implementation that currently resides under
`scripts.neo4j.repair.repair_missing_links_similarity_embeddings` and
re-exports `run_repair` so that code under `src` can import it reliably.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _import_run_repair():
    candidates = [
        'scripts.neo4j.repair.repair_missing_links_similarity_embeddings',
        'scripts.repair_missing_links_similarity_embeddings',
    ]
    for cand in candidates:
        try:
            mod = importlib.import_module(cand)
            if hasattr(mod, 'run_repair'):
                return getattr(mod, 'run_repair')
        except Exception:
            logger.debug('repair wrapper could not import %s', cand, exc_info=True)
    raise ModuleNotFoundError("Could not import run_repair from scripts.* candidates: %s" % candidates)


_run_repair = None

try:
    _run_repair = _import_run_repair()
except ModuleNotFoundError:
    # Defer raising until a caller attempts to use run_repair
    _run_repair = None


def run_repair(*args: Any, **kwargs: Any):
    """Call the underlying `run_repair` implementation.

    This wrapper provides a stable import path under `src.maintenance.repair` and
    will raise a clear error if the underlying script is not available.
    """
    if not _run_repair:
        raise ModuleNotFoundError("run_repair is not available; ensure repair scripts package is installed or the project root contains the scripts/ package")
    # Delegate call to the real run_repair (async function). We return its coroutine.
    return _run_repair(*args, **kwargs)


__all__ = ['run_repair']
"""
Repair wrapper module
- Purpose: Export `run_repair` callable for MemoryWeaver and other internal callers.
- Implementation: Import the run_repair function from the existing scripts module path (scripts.neo4j.repair.repair_missing_links_similarity_embeddings)
  and re-export it. This keeps the heavy repair logic in the `scripts` area while ensuring a stable `src` import path that is bundled with the app.
"""
from __future__ import annotations

import importlib
import sys
import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Attempt to import the repair module from the canonical nested script path
_run_repair_callable = None

# Ensure repo root in sys.path (defensive)
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    _mod = importlib.import_module('scripts.neo4j.repair.repair_missing_links_similarity_embeddings')
    if hasattr(_mod, 'run_repair'):
        _run_repair_callable = getattr(_mod, 'run_repair')
except Exception:
    # Try legacy flattened path
    try:
        _mod = importlib.import_module('scripts.repair_missing_links_similarity_embeddings')
        if hasattr(_mod, 'run_repair'):
            _run_repair_callable = getattr(_mod, 'run_repair')
    except Exception:
        logger.exception('Repair wrapper could not import the repair module from scripts.* paths')


def run_repair(*args, **kwargs) -> Optional[Any]:
    """Call the underlying run_repair implementation.

    If the underlying script is not available, this function will raise ModuleNotFoundError.

    Returns whatever the underlying `run_repair` returns.
    """
    if not _run_repair_callable:
        raise ModuleNotFoundError("Could not import the repair script implementation (scripts.neo4j.repair.repair_missing_links_similarity_embeddings)")
    return _run_repair_callable(*args, **kwargs)

__all__ = ['run_repair']
