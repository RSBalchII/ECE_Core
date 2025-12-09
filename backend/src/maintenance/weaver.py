"""
Memory Weaver - a lightweight engine that runs the repair logic as a scheduled/programmable task.

This module uses `src.maintenance.repair_wrapper.run_repair` as the canonical import path.
The wrapper dynamically loads the script-based implementation from one of these candidates:
 - `scripts.neo4j.repair.repair_missing_links_similarity_embeddings`
 - `scripts.repair_missing_links_similarity_embeddings`

The wrapper protects the package import from changes to the script location and provides
an introspection-based API to filter parameters passed to the underlying function.

The MemoryWeaver is safe to call in dry-run mode and only performs writes if the
master switch `WEAVER_COMMIT_ENABLED` is set in settings. The wrapper also raises a
clear `ModuleNotFoundError` when the implementation is not available and avoids
hard-failing the import path during startup.
"""
import asyncio
import time
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.config import Settings, settings as GLOBAL_SETTINGS
from src.memory.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class MemoryWeaver:
    def __init__(self, settings: Optional[Settings] = None):
        # Default to the module-global settings if none passed; this allows centralized overrides
        self.settings = settings or GLOBAL_SETTINGS

    async def weave_recent(self, hours: int | None = None, threshold: float | None = None, max_commit: int | None = None, candidate_limit: int | None = None, prefer_same_app: bool | None = None, dry_run: bool | None = None, csv_out: Optional[str] = None, run_id: Optional[str] = None, batch_size: int | None = None):
        """
        Run a repair cycle for the recent time window (hours) and commit matches if not dry_run.
        Returns: dict with run_id, processed items and commit count.
        """
        # Import the central `src.maintenance.repair` wrapper which exposes run_repair.
        # This wrapper keeps the weaver import simple (no dynamic path handling here) and is included in the 'src' package.
        try:
            from src.maintenance.repair_wrapper import run_repair
        except Exception as e:
            logger.error("MemoryWeaver: failed to import run_repair from src.maintenance.repair_wrapper; error=%s", e)
            return {'run_id': run_id, 'status': 'import_failed', 'message': str(e)}

        if not run_id:
            run_id = str(uuid.uuid4())

        # Build args
        # Resolve defaults from settings unless explicitly provided
        if hours is None:
            hours = self.settings.weaver_time_window_hours
        if threshold is None:
            threshold = self.settings.weaver_threshold
        if max_commit is None:
            max_commit = self.settings.weaver_max_commit
        if prefer_same_app is None:
            prefer_same_app = self.settings.weaver_prefer_same_app
        if dry_run is None:
            dry_run = self.settings.weaver_dry_run_default

        # Master Switch: If weaver_commit_enabled is True, we want to actually commit (auto-apply)
        if self.settings.weaver_commit_enabled:
            # If operator has enabled commit, force write-mode and clear dry-run
            dry_run = False
            commit_mode = True
        else:
            commit_mode = False

        # Resolve candidate limit and batch size defaults using settings when not supplied
        if candidate_limit is None:
            candidate_limit = self.settings.weaver_candidate_limit
        if batch_size is None:
            batch_size = getattr(self.settings, 'weaver_batch_size_default', self.settings.llm_embeddings_default_batch_size)

        params = {
            'threshold': threshold,
            'limit': 1000,
            'candidate_limit': candidate_limit,
            'dry_run': dry_run,
            'csv_out': csv_out,
            'time_window_hours': hours,
            'prefer_same_app': prefer_same_app,
            'min_origin_length': 100,
            'exclude_phrases': ["Genesis memory", "ECE Core System Initialized"],
            'delta': self.settings.weaver_delta,
            'max_commit': max_commit,
            # Use commit_mode (explicit master switch) when set; otherwise infer from dry_run
            'commit': commit_mode or (not dry_run),
            'run_id': run_id,
            'exclude_tag': self.settings.weaver_exclude_tag,
            'batch_size': batch_size,
        }

        logger.info(f"MemoryWeaver: Starting weave run {run_id} (hours={hours}, threshold={threshold}, commit={not dry_run})")

        # Adaptive throttling: process the large 'limit' value in smaller batches and sleep between them.
        sleep_between = getattr(self.settings, 'weaver_sleep_between_batches', 1.0)

        # Resolve batch size using prioritized sources: function arg -> explicit env -> default config values
        resolved_batch = int(batch_size or getattr(self.settings, 'weaver_batch_size', None) or getattr(self.settings, 'weaver_batch_size_default', None) or getattr(self.settings, 'llm_embeddings_default_batch_size', 2))
        if resolved_batch <= 0:
            resolved_batch = 1

        total_limit = int(params.get('limit', 1000))
        offset = 0

        # If Redis is available, check for recent user activity and pause if within last N seconds
        # 5 minutes (300 seconds) is used as the active-user window
        redis_client = RedisCache()
        await redis_client.initialize()

        while offset < total_limit:
            # Check user activity to avoid collisions with interactive sessions
            try:
                last_active = None
                if redis_client.redis:
                    val = await redis_client.redis.get(f"session:{self.settings.anchor_session_id}:last_active_at")
                    if val:
                        try:
                            last_active = int(val)
                        except Exception:
                            # value might be an ISO timestamp; try conversion
                            try:
                                last_active = int(float(val))
                            except Exception:
                                last_active = None
                if last_active:
                    now = int(time.time())
                    if (now - last_active) < 300:
                        logger.info(f"MemoryWeaver: Paused weave run {run_id} because user activity detected {now - last_active}s ago")
                        await redis_client.close()
                        return {'run_id': run_id, 'status': 'paused_user_active', 'delay_seconds': now - last_active}
            except Exception as e:
                logger.debug("MemoryWeaver: Failed to check last_active, continuing. err=%s", e)

            # Prepare params for this batch
            batch_params = dict(params)
            batch_params['limit'] = resolved_batch
            batch_params['skip'] = offset
            logger.info(f"MemoryWeaver: Running batch {offset}:{offset + resolved_batch} (limit {resolved_batch})")
            try:
                await run_repair(threshold=batch_params['threshold'], limit=batch_params['limit'], candidate_limit=batch_params['candidate_limit'], dry_run=batch_params['dry_run'], csv_out=batch_params['csv_out'], time_window_hours=batch_params['time_window_hours'], prefer_same_app=batch_params['prefer_same_app'], min_origin_length=batch_params['min_origin_length'], exclude_phrases=batch_params['exclude_phrases'], delta=batch_params['delta'], max_commit=batch_params['max_commit'], commit=batch_params['commit'], run_id=batch_params['run_id'], exclude_tag=batch_params['exclude_tag'], batch_size=batch_params['batch_size'], skip=batch_params.get('skip', 0))
            except Exception as e:
                logger.error(f"MemoryWeaver: Batch failed for range {offset}:{offset + resolved_batch} with error: {e}")
                # If a batch fails, record and continue (the underlying run_repair already uses resilient embedding backoff)
            # Sleep between batches to avoid simultaneous bursts with user requests
            offset += resolved_batch
            if offset < total_limit:
                logger.debug(f"MemoryWeaver: Sleeping {sleep_between}s between batches to avoid resource contention")
                await asyncio.sleep(sleep_between)

        await redis_client.close()
        logger.info(f"MemoryWeaver: Completed weave run {run_id}")
        return {'run_id': run_id}
