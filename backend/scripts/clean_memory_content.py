#!/usr/bin/env python3
"""
Clean Memory node 'content' and write a `content_cleaned` property for cleaned content.
This script is conservative: default is --dry-run; use --write to update Neo4j.

Usage:
  python scripts/clean_memory_content.py --limit 100 --dry-run
"""
import argparse
import datetime
import csv
import sys
import os
# Ensure repo root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from neo4j import GraphDatabase
from src.config import Settings
from src.content_utils import clean_content, is_json_like, is_html_like, has_technical_signal


def main(limit: int = 0, batch: int = 100, write: bool = False, skip_json: bool = True, skip_html: bool = True, min_clean_length: int = 30, output: str = 'temp_clean_report.csv'):
    settings = Settings()
    if not settings.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    processed = 0
    changed = 0
    suspect_skipped = 0
    rows = []
    with driver.session() as session:
        if limit and limit > 0:
            q = "MATCH (m:Memory) RETURN elementId(m) as eid, m.app_id as app_id, m.created_at as created_at, m.content as content LIMIT $limit"
            res = session.run(q, {'limit': limit})
        else:
            q = "MATCH (m:Memory) RETURN elementId(m) as eid, m.app_id as app_id, m.created_at as created_at, m.content as content"
            res = session.run(q)
        for r in res:
            processed += 1
            eid = r['eid']
            app_id = r.get('app_id')
            created_at = r.get('created_at')
            raw = r.get('content') or ''
            # skip heuristics
            if skip_json and is_json_like(raw) and not has_technical_signal(raw):
                suspect_skipped += 1
                rows.append([eid, app_id, 'skipped_json', len(raw)])
                continue
            if skip_html and is_html_like(raw) and not has_technical_signal(raw):
                suspect_skipped += 1
                rows.append([eid, app_id, 'skipped_html', len(raw)])
                continue
            tech_signal = has_technical_signal(raw)
            cleaned = clean_content(raw, remove_emojis=not tech_signal, remove_non_ascii=False, annotate_technical=tech_signal)
            if not cleaned or len(cleaned) < min_clean_length:
                rows.append([eid, app_id, 'skipped_short', len(cleaned)])
                continue
            # If cleaned equals raw, skip
            if cleaned.strip() == raw.strip():
                rows.append([eid, app_id, 'unchanged', len(raw)])
                continue
            # Optionally write cleaned content
            if write:
                try:
                    session.run("MATCH (m:Memory) WHERE elementId(m) = $eid SET m.content_cleaned = $cleaned, m.content_cleaned_at = $ts", {'eid': str(eid), 'cleaned': cleaned, 'ts': str(datetime.datetime.utcnow().isoformat())})
                    changed += 1
                    rows.append([eid, app_id, 'updated', len(cleaned)])
                except Exception as e:
                    rows.append([eid, app_id, 'update_failed', str(e)])
            else:
                rows.append([eid, app_id, 'dry_run', len(cleaned)])

    # Write CSV
    with open(output, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['eid', 'app_id', 'status', 'len'])
        for r in rows:
            w.writerow(r)

    print(f"Processed {processed} memory nodes; changed={changed}; suspect_skipped={suspect_skipped}; report={output}")
    driver.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--batch', type=int, default=100)
    p.add_argument('--write', action='store_true')
    p.add_argument('--skip-json', action='store_true')
    p.add_argument('--skip-html', action='store_true')
    p.add_argument('--min-clean-length', type=int, default=30)
    p.add_argument('--output', type=str, default='temp_clean_report.csv')
    args = p.parse_args()
    main(limit=args.limit, batch=args.batch, write=args.write, skip_json=args.skip_json, skip_html=args.skip_html, min_clean_length=args.min_clean_length, output=args.output)
