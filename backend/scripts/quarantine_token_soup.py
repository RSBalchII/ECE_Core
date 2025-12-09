#!/usr/bin/env python3
"""
Scan Neo4j for nodes that are "token soup" using src.content_utils.is_token_soup and optionally tag them as '#corrupted'.

Usage:
  python scripts/quarantine_token_soup.py --dry-run --category summary --limit 100 --sample 5 --csv-out logs/token_soup_scan.csv
  python scripts/quarantine_token_soup.py --write --category summary --limit 100

Notes:
  - This script will not delete or change 'content' or 'content_cleaned' properties by default; it only tags nodes (optional write mode) and writes a CSV audit if supplied.
  - To be safe, it defaults to dry-run unless --write is passed.
"""
import argparse
import csv
import os
import json
import sys
from pathlib import Path
# Repo root insertion
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime
from neo4j import GraphDatabase
from src.config import Settings
from src.content_utils import is_token_soup, sanitize_token_soup, clean_content


def append_csv(path, header, rows):
    write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
    with open(path, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(header)
        for row in rows:
            w.writerow(row)


def main(category: str | None = None, limit: int = 0, dry_run: bool = True, write: bool = False, csv_out: str = None, sample_count: int = 5, use_cleaned: bool = True):
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings; aborting')
        return
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

    total = 0
    found = 0
    sampled = []
    to_tag = []
    header = ['eid', 'app_id', 'created_at', 'category', 'field', 'is_token_soup', 'original_excerpt']

    with driver.session() as session:
        q = "MATCH (m:Memory)"
        if category:
            q += " WHERE m.category = $category"
            q += " RETURN elementId(m) as eid, m.app_id as app_id, m.created_at as created_at, m.category as category, m.content as content, m.content_cleaned as content_cleaned, m.tags as tags LIMIT $limit"
            res = session.run(q, {'category': category, 'limit': limit or 1000})
        else:
            q += " RETURN elementId(m) as eid, m.app_id as app_id, m.created_at as created_at, m.category as category, m.content as content, m.content_cleaned as content_cleaned, m.tags as tags LIMIT $limit"
            res = session.run(q, {'limit': limit or 1000})

        rows = list(res)
        total = len(rows)
        print(f"Scanning {total} nodes (category={category or 'ALL'})")

        for r in rows:
            eid = r['eid']
            cat = r.get('category')
            app_id = r.get('app_id')
            created_at = r.get('created_at')
            # Prefer content_cleaned if requested
            text_field = 'content_cleaned' if use_cleaned else 'content'
            candidate_text = r.get('content_cleaned') if use_cleaned else r.get('content')
            if not candidate_text:
                candidate_text = r.get('content_cleaned') or r.get('content') or ''

            # Run token-soup detection
            try:
                if candidate_text and is_token_soup(candidate_text):
                    found += 1
                    excerpt = (candidate_text or '')[:200]
                    sampled.append((eid, app_id, created_at, cat, text_field, True, excerpt))
                    # If write mode, we will tag later
                    to_tag.append({'eid': eid, 'tags': r.get('tags') or [], 'excerpt': excerpt, 'category': cat, 'existing_tags_raw': r.get('tags')})
                else:
                    # Not token soup; skip
                    pass
            except Exception as e:
                print(f"Error detecting token soup for eid={eid}: {e}")
                continue

    print(f"Scan complete: examined={total}; token_soup_found={found}")

    # Write CSV if requested
    if csv_out:
        rows_out = [(str(x[0]), str(x[1] or ''), str(x[2] or ''), x[3] or '', x[4] or '', str(x[5] or ''), x[6] or '') for x in sampled]
        append_csv(csv_out, header, rows_out)
        print(f"Wrote report to {csv_out}")

    # Sample output
    if sample_count and sampled:
        print(f"Sample {min(sample_count, len(sampled))} examples:")
        for i, srow in enumerate(sampled[:sample_count]):
            print(f"{i+1}. eid={srow[0]} app_id={srow[1]} cat={srow[3]} field={srow[4]} excerpt={srow[6][:140]}")

    # Write mode: tag nodes as '#corrupted'
    if write and to_tag:
        added_count = 0
        with driver.session() as session:
            for t in to_tag:
                eid = t['eid']
                tags_raw = t['tags']
                try:
                    # Normalize tags to a python list
                    if isinstance(tags_raw, str):
                        try:
                            tags = json.loads(tags_raw)
                            if not isinstance(tags, list):
                                tags = [tags]
                        except Exception:
                            tags = [tags_raw]
                    elif isinstance(tags_raw, list):
                        tags = tags_raw
                    else:
                        tags = []
                    # Ensure we don't duplicate tag
                    if '#corrupted' in tags or 'corrupted' in tags:
                        continue
                    tags.append('#corrupted')
                    # Persist tags on node
                    session.run("MATCH (m:Memory) WHERE elementId(m) = $eid SET m.tags = $tags", {'eid': str(eid), 'tags': tags})
                    added_count += 1
                except Exception as e:
                    print(f"Failed to tag eid={eid}: {e}")
                    continue
        print(f"Wrote {added_count} tags to nodes as #corrupted")

    driver.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', default='summary', type=str, help='If set, only scan Memory nodes with this category. Defaults to summary.')
    parser.add_argument('--limit', default=100, type=int, help='Max nodes to examine')
    parser.add_argument('--dry-run', action='store_true', help='Dry-run: do not write tags (default)')
    parser.add_argument('--write', action='store_true', help='If set, write tags to the DB. Requires write permission.')
    parser.add_argument('--csv-out', type=str, default=None, help='Optional CSV path to append report entries')
    parser.add_argument('--sample', type=int, default=5, help='Number of samples to show')
    parser.add_argument('--use-cleaned', action='store_true', help='Use content_cleaned field to detect token soup; otherwise use original content')
    args = parser.parse_args()
    # If the user passes --write, then dry-run is forced to False
    if args.write:
        dry_run = False
        write = True
    else:
        dry_run = True
        write = False
    main(category=args.category if args.category else None, limit=args.limit, dry_run=dry_run, write=write, csv_out=args.csv_out, sample_count=args.sample, use_cleaned=args.use_cleaned)
