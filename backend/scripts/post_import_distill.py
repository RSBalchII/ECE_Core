#!/usr/bin/env python3
"""
Post-import distillation script.

This script searches Neo4j for Memories imported by `import_via_chat.py` (tags include 'imported' or metadata contains 'import_via_chat')
and runs the Distiller on each memory content to create a summarized 'summary' memory and link it back to the original memory.

Usage:
  python scripts/post_import_distill.py [--dry-run] [--batch-size 10] [--limit 100] [--resume]

"""

import argparse
import uuid
import logging
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from src.memory.manager import TieredMemory
from src.llm import LLMClient
from src.distiller import distill_moment
from src.config import settings

STATE_FILE = os.path.join(os.path.dirname(__file__), 'post_import_distill_state.json')
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'post_import_distill_cache.json')


async def _run_batch(tmem: TieredMemory, llm_client: LLMClient, batch: List[Dict[str, Any]], dry_run=False, allow_fallback=False, max_retries: int = 3, retry_backoff: float = 2.0, cache: Dict[str, Any] = None, force_retry: bool = False, logger: logging.Logger = None):
    results = []
    for rec in batch:
        node_id = rec.get('id')
        content = rec.get('content')
        print(f"Processing node {node_id}... len={len(content or '')}")
        if not content or not content.strip():
            print("  Skipping empty content")
            continue
        try:
            # If we have a cache and this node is marked as skipped due to prior LLM failures,
            # and we are not forcing a retry, skip it to avoid repeated LLM hits.
            if cache is not None and cache.get(str(node_id), {}).get('status') == 'skipped' and not cache.get(str(node_id), {}).get('retry', False) and not force_retry:
                if logger:
                    logger.debug(f"Skipping node {node_id} as marked skipped in cache")
                continue

            attempt = 0
            moment = None
            lerr = None
            while attempt < max_retries:
                attempt += 1
                try:
                    moment = await distill_moment(content, llm_client=llm_client)
                    lerr = None
                    break
                except Exception as e:
                    lerr = e
                    if logger:
                        logger.warning(f"Distill error for node {node_id} (attempt {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        backoff = retry_backoff * (2 ** (attempt - 1))
                        if logger:
                            logger.debug(f"Sleeping {backoff}s before retrying...")
                        await asyncio.sleep(backoff)
            if moment is None and lerr is not None:
                # LLM failed after retries
                if allow_fallback:
                    summary = (content[:400] + '...') if content else ''
                    entities = []
                    if logger:
                        logger.info(f"Using fallback summary for node {node_id} after LLM failures")
                else:
                    if logger:
                        logger.error(f"Failed to distill node {node_id} after {max_retries} attempts: {lerr}")
                    # mark in cache and skip
                    if cache is not None:
                        cache[str(node_id)] = {'status': 'skipped', 'error': str(lerr), 'retry': False}
                    continue
            else:
                # We have a valid moment
                if moment:
                    summary = moment.get('summary') or (content[:400] + '...')
                    entities = moment.get('entities', [])
                else:
                    summary = (content[:400] + '...') if content else ''
                    entities = []
            # Save summary as a new Memory node in Neo4j and link
            if dry_run:
                print(f"  DRY RUN: would save summary for node {node_id}: summary_len={len(summary)} entities={len(entities)}")
                continue
            # Create summary node and get elementId(s); create deterministic or random app_id for summary node
                cypher_create = """
                    CREATE (s:Memory {session_id: $session_id, content: $content, category: 'summary', tags: ['distilled','summary'], importance: 5, app_id: $app_id, metadata: $metadata, created_at: datetime()})
                    RETURN elementId(s) as id
                    """
            new_app_id = str(uuid.uuid4())
            orig_app_id = rec.get('app_id') or node_id
            metadata = {"distilled_from_app_id": orig_app_id, "distilled_method": 'llm' if moment else 'fallback', 'app_id': new_app_id}
            res = await tmem.neo4j.execute_cypher(cypher_create, {"session_id": 'import', "content": summary, "app_id": new_app_id, "metadata": json.dumps(metadata)})
            if not res:
                print(f"  Warning: failed to create summary node for {node_id}")
                continue
            new_id = res[0].get('id')
            # Create link using app_id so it survives internal id changes
            cypher_link = """
            MATCH (orig:Memory {app_id: $orig_app_id}), (s:Memory {app_id: $s_app_id})
            MERGE (s)-[:DISTILLED_FROM]->(orig)
            RETURN 1
            """
            await tmem.neo4j.execute_cypher(cypher_link, {"orig_app_id": orig_app_id, "s_app_id": new_app_id})
            print(f"  Created summary node {new_id} and linked to {node_id}")
            results.append((node_id, new_id))
            # Write success to cache
            if cache is not None:
                cache[str(node_id)] = {'status': 'distilled', 'summary_id': new_id}
        except Exception as e:
            print(f"  Error distilling node {node_id}: {e}")
            continue
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--batch-size', type=int, default=None)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--resume', action='store_true')

    parser.add_argument('--allow-fallback', action='store_true', help='When set, use a simple content fallback summary if LLM fails')
    parser.add_argument('--max-retries', type=int, default=3, help='Max retries for LLM calls')
    parser.add_argument('--retry-backoff', type=float, default=2.0, help='Base backoff seconds for LLM retry; exponential backoff applied')
    parser.add_argument('--log-file', type=str, default=None, help='Optional path to write logs')
    parser.add_argument('--force-retry', action='store_true', help='Force retry of nodes previously marked as skipped due to LLM errors')
    parser.add_argument('--reprocess-failed', action='store_true', help='After full run, reprocess nodes marked as skipped due to LLM errors')
    parser.add_argument('--force-remote', action='store_true', help='Force usage of the configured remote API (skip local GGUF fallback)')
    parser.add_argument('--llm-chunk-tokens', type=int, default=None, help='Override archivist chunk token size when splitting large prompts for the LLM')
    parser.add_argument('--llm-chunk-overlap', type=int, default=None, help='Override archivist chunk overlap (tokens) used when splitting for the LLM')
    args = parser.parse_args()

    print("Connecting to Neo4j and LLM... this may take a moment.")
    # Setup logger
    logger = logging.getLogger('post_import_distill')
    logger.setLevel(logging.INFO)
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(ch)
    # Optional file handler
    if args.log_file:
        fh = logging.FileHandler(args.log_file)
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    tmem = TieredMemory(llm_client=None)
    # Ensure Python sees the project imports (scripts executed directly)
    try:
        await tmem.initialize()
    except Exception as e:
        print(f"Failed to initialize TieredMemory: {e}")
        return

    llm_client = LLMClient()
    if args.force_remote:
        llm_client.force_remote_api = True
    # Optionally override chunk sizes
    if args.llm_chunk_tokens is not None:
        settings.archivist_chunk_size = int(args.llm_chunk_tokens)
    if args.llm_chunk_overlap is not None:
        settings.archivist_overlap = int(args.llm_chunk_overlap)
    await llm_client.detect_model()

    # Find imported memory nodes to distill; ignore those that already have summaries
    find_query = """
        MATCH (m:Memory)
        WHERE ((m.tags IS NOT NULL AND 'imported' IN m.tags) OR (m.metadata IS NOT NULL AND m.metadata CONTAINS 'import_via_chat'))
            AND NOT ( ()-[:DISTILLED_FROM]->(m) )
        RETURN elementId(m) as id, m.app_id as app_id, m.content as content
        ORDER BY m.created_at
        """

    # Query all candidates
    candidates = await tmem.neo4j.execute_cypher(find_query)
    print(f"Found {len(candidates)} imported memories to distill")

    start_index = 0
    if args.resume and os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as sf:
                state = json.load(sf)
                start_index = int(state.get('last_index', 0))
                print(f"Resuming from index {start_index}")
        except Exception as e:
            print(f"Failed to read state file: {e}")
    # If the current list of candidates is shorter than the recorded state index,
    # we were resuming from a different candidate set; clamp to zero.
    if start_index >= len(candidates):
        print(f"Resume index {start_index} >= candidate count {len(candidates)}; resetting start_index to 0")
        start_index = 0

    total = len(candidates)
    idx = start_index
    # Load cache
    cache = {}
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as cf:
                cache = json.load(cf) or {}
    except Exception as e:
        if logger:
            logger.warning(f"Failed to load cache file: {e}")
    batch_size = args.batch_size if args.batch_size is not None else getattr(settings, 'weaver_batch_size_default', 10)
    while idx < total:
        batch = candidates[idx: idx + batch_size]
        if not batch:
            break
                results = await _run_batch(tmem, llm_client, batch, dry_run=args.dry_run, allow_fallback=args.allow_fallback, max_retries=args.max_retries, retry_backoff=args.retry_backoff, cache=cache, force_retry=args.force_retry, logger=logger)
        idx += len(batch)
        # Save state
        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as sf:
                json.dump({"last_index": idx}, sf)
        except Exception:
            pass
        # Save cache after each batch
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as cf:
                json.dump(cache, cf)
        except Exception:
            if logger:
                logger.warning('Failed to save cache file')
        if args.limit and idx >= args.limit:
            print(f"Reached limit {args.limit}; stopping")
            break
        time.sleep(0.1)

    print(f"Done; processed {idx}/{total} memories")
    # Optionally reprocess failed/skipped nodes from cache
    if args.reprocess_failed:
        skipped_ids = [nid for nid, v in cache.items() if v.get('status') == 'skipped']
        if skipped_ids:
            print(f"Reprocessing {len(skipped_ids)} previously skipped nodes (will force retries)")
            # Build candidates for skipped nodes by matching from initial candidates list
            skipped_candidates = [c for c in candidates if str(c.get('id')) in skipped_ids]
            # Re-run in batches
            sidx = 0
            total_skipped = len(skipped_candidates)
            while sidx < total_skipped:
                sbatch = skipped_candidates[sidx:sidx + batch_size]
                await _run_batch(tmem, llm_client, sbatch, dry_run=args.dry_run, allow_fallback=args.allow_fallback, max_retries=args.max_retries, retry_backoff=args.retry_backoff, cache=cache, force_retry=True, logger=logger)
                sidx += len(sbatch)
                # Save cache periodically
                try:
                    with open(CACHE_FILE, 'w', encoding='utf-8') as cf:
                        json.dump(cache, cf)
                except Exception:
                    if logger:
                        logger.warning('Failed to save cache file after reprocess')
    await tmem.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
