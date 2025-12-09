#!/usr/bin/env python3
import sys
import asyncio
import os
import json
from typing import List

sys.path.insert(0, r'C:\Users\rsbiiw\Projects\ECE_Core')
from src.memory.manager import TieredMemory
import uuid
from src.memory.neo4j_store import Neo4jStore


def chunk_text_by_chars(text: str, chunk_chars: int) -> List[str]:
    if not text:
        return []
    res = []
    i = 0
    while i < len(text):
        res.append(text[i:i+chunk_chars])
        i += chunk_chars
    return res


async def import_to_neo4j(file_path: str, chunk_chars: int = 10000, resume: bool = True):
    store = TieredMemory()
    await store.initialize()
    if not store.neo4j_driver:
        print('Neo4j not connected, aborting direct import')
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text_by_chars(text, chunk_chars)
    print(f'Found {len(chunks)} chunks')
    state_file = os.path.join(os.path.dirname(__file__), 'import_direct_state.json')
    last = -1
    if resume and os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as sf:
                last = int(json.load(sf).get('last_completed_chunk', -1))
                print(f'Resuming direct import from chunk {last + 1}')
        except Exception:
            last = -1

    for i, chunk in enumerate(chunks):
        if resume and i <= last:
            continue
        # Skip empty
        if not chunk.strip():
            continue
        # Check existing by matching metadata string in node
        # metadata stored as JSON string in Neo4j; use CONTAINS match
        q = "MATCH (m:Memory) WHERE m.metadata CONTAINS $idx RETURN count(m) as cnt"
        result = await store.neo4j.execute_cypher(q, {'idx': f'"chunk_index": {i}'})
        cnt = 0
        if result and isinstance(result, list) and len(result) > 0:
            row = result[0]
            cnt = int(row.get('cnt', 0)) if row.get('cnt') is not None else 0
        if cnt > 0:
            print(f'Chunk {i} already exists, skipping')
            try:
                with open(state_file, 'w', encoding='utf-8') as sf:
                    json.dump({'last_completed_chunk': i}, sf)
            except Exception:
                pass
            continue

        # Compute a deterministic app_id based on file path and chunk index to ensure idempotent imports
        try:
            ns = uuid.UUID('f8bd0f6e-0c4c-4654-9201-12c4f2b4b5ef')
            app_id = str(uuid.uuid5(ns, f"{file_path}:{i}"))
        except Exception:
            app_id = str(uuid.uuid4())
        metadata = {'source': 'direct_import', 'chunk_index': i, 'app_id': app_id}
        await store.add_memory(session_id='import', content=chunk, category='import', tags=['imported'], importance=5, metadata=metadata)
        print(f'Imported chunk {i}')
        try:
            with open(state_file, 'w', encoding='utf-8') as sf:
                json.dump({'last_completed_chunk': i}, sf)
        except Exception:
            pass

    await store.close()
    print('Direct import completed')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--chunk-chars', type=int, default=10000)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    asyncio.run(import_to_neo4j(args.file, chunk_chars=args.chunk_chars, resume=args.resume))
