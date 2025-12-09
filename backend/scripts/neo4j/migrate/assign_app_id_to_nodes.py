#!/usr/bin/env python3
"""
Assigns a stable and unique `app_id` to Memory nodes that are missing it.

Strategy:
- If a node has `metadata` with `app_id` already, set node property `app_id` to that value.
- Else, if metadata contains `source` and `chunk_index`, derive a deterministic UUIDv5 from that.
- Else, derive a deterministic UUIDv5 from content (normalized and trimmed) to make it deterministic.
- Update both node property `app_id` and add to `metadata` JSON so the next time we can rely on it.

This script runs in batches so it's safe to run on large DBs.
"""

import argparse
import asyncio
import json
import uuid
import math

from src.memory.neo4j_store import Neo4jStore

BATCH_SIZE = 500

# A static namespace for uuid5 generation (stable across runs)
NAMESPACE_UUID = uuid.UUID('f8bd0f6e-0c4c-4654-9201-12c4f2b4b5ef')


def compute_app_id_from_meta(meta: dict, content: str):
    if meta is None:
        meta = {}
    # If there's an explicit app_id, use it
    if 'app_id' in meta and meta['app_id']:
        return str(meta['app_id'])
    # If we have source and chunk_index, use that for deterministic id
    if 'source' in meta and 'chunk_index' in meta:
        ns_input = f"{meta.get('source')}:{meta.get('chunk_index')}"
        return str(uuid.uuid5(NAMESPACE_UUID, ns_input))
    # Fallback: use normalized content, trim and compute uuid5
    if content:
        normalized = content.strip()[:4096]  # limit length used to compute ID
        return str(uuid.uuid5(NAMESPACE_UUID, normalized))
    # Absolute fallback
    return str(uuid.uuid4())


async def migrate(limit: int = 0):
    store = Neo4jStore()
    await store.initialize()
    if not store.neo4j_driver:
        print('Neo4j not connected; aborting')
        return

    offset = 0
    total_processed = 0
    while True:
        q = (
            'MATCH (m:Memory) WHERE (m.app_id IS NULL OR m.app_id = "" ) '
            'RETURN elementId(m) as eid, m.metadata as metadata, m.content as content '
            'ORDER BY m.created_at '
            + ('LIMIT $limit' if limit > 0 else '')
        )
        params = {}
        if limit > 0:
            params['limit'] = min(limit, BATCH_SIZE)
        else:
            params['limit'] = BATCH_SIZE
        result = await store.execute_cypher(q, params)
        if not result:
            print('No more nodes to update (or query returned no rows).')
            break

        print(f'Processing batch with {len(result)} nodes')
        for rec in result:
            eid = rec.get('eid')
            meta_str = rec.get('metadata')
            content = rec.get('content')
            try:
                if isinstance(meta_str, str):
                    meta = json.loads(meta_str) if meta_str else {}
                else:
                    # driver may already return parsed JSON
                    meta = meta_str or {}
            except Exception:
                # Broken metadata; replace with basic structure
                meta = {}
            # Compute app_id
            app_id = compute_app_id_from_meta(meta, content)
            # Update both property and the metadata JSON (if not present)
            meta['app_id'] = app_id
            new_meta_json = json.dumps(meta, default=str)
            update_q = (
                'MATCH (m:Memory) WHERE elementId(m) = $eid '
                'SET m.app_id = $app_id, m.metadata = $metadata '
                'RETURN elementId(m) as eid'
            )
            ures = await store.execute_cypher(update_q, {'eid': eid, 'app_id': app_id, 'metadata': new_meta_json})
            if ures:
                total_processed += 1
        # If a limit was provided, process at most that many total
        if limit > 0:
            break

    print(f'Done: added app_id to {total_processed} nodes')
    await store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Limit processed nodes (useful for testing)')
    args = parser.parse_args()
    asyncio.run(migrate(limit=args.limit))
