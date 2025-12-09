#!/usr/bin/env python3
"""
Audit Neo4j memory nodes for problematic provenance sources.

Usage:
  python scripts/audit_memory_sources.py --output polluted_memories.csv [--delete]

This script scans Neo4j memory nodes and writes those that appear to be sourced
from local file artifacts (e.g., combined_text, prompt-logs, calibration_run) or
contain developer/test content (e.g., thinking_content). It provides a CSV of
found nodes with ID, created_at, content (truncated), and metadata for manual review.

By default it only reports findings. Use --delete with caution to remove them.
"""
import argparse
import csv
import os
import json
import sys
from pathlib import Path
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.memory.neo4j_store import Neo4jStore
from src.config import settings

async def main(output: str, delete: bool = False):
    ns = Neo4jStore()
    await ns.initialize()
    bad_nodes = []
    # Match nodes by content or metadata containing dev/test markers or thinking_content
    markers = ['combined_text', 'combined_text2', 'prompt-logs', 'prompt_logs', 'calibration_run', 'thinking_content', 'dry-run', 'dry_run', '[planner]']
    q = """
    MATCH (m:Memory)
    WHERE toLower(m.content) CONTAINS $marker OR toLower(m.metadata) CONTAINS $marker
    RETURN elementId(m) as id, m.content as content, m.metadata as metadata, m.created_at as created_at, m.session_id as session_id, m.category as category LIMIT 10000
    """
    try:
        async with ns.neo4j_driver.session() as session:
            for marker in markers:
                result = await session.run(q, {'marker': marker})
                rows = await result.data()
                for r in rows:
                    mid = r.get('id')
                    content = r.get('content') or ''
                    meta = r.get('metadata') or ''
                    created_at = r.get('created_at') or ''
                    session_id = r.get('session_id') or ''
                    category = r.get('category') or ''
                    bad_nodes.append({'id': mid, 'marker': marker, 'content': content[:400], 'metadata': meta, 'created_at': created_at, 'session_id': session_id, 'category': category})
    except Exception as e:
        print(f"Neo4j query failed: {e}")
        await ns.close()
        return

    # De-duplicate by id
    seen = {}
    unique = []
    for n in bad_nodes:
        if n['id'] not in seen:
            seen[n['id']] = True
            unique.append(n)

    # Write CSV output
    with open(output, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['id', 'marker', 'created_at', 'session_id', 'category', 'content', 'metadata'])
        for row in unique:
            w.writerow([row['id'], row['marker'], row['created_at'], row['session_id'], row['category'], row['content'], row['metadata']])

    print(f"Wrote {len(unique)} suspicious nodes to {output}")

    if delete:
        confirm = input(f"WARNING: delete {len(unique)} nodes? Type 'yes' to confirm: ")
        if confirm.strip().lower() == 'yes':
            async with ns.neo4j_driver.session() as session:
                for row in unique:
                    try:
                        await session.run('MATCH (m:Memory) WHERE elementId(m) = $id DETACH DELETE m', {'id': row['id']})
                    except Exception as e:
                        print(f"Failed to delete {row['id']}: {e}")
            print("Deleted nodes.")
        else:
            print("Aborted deletion.")
    await ns.close()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', '-o', default='polluted_memories.csv')
    p.add_argument('--delete', action='store_true', help='Delete found nodes after confirmation')
    args = p.parse_args()
    asyncio.run(main(args.output, args.delete))
