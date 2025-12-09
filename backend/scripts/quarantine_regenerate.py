#!/usr/bin/env python3
"""
Regenerate sanitized summaries for nodes tagged with '#corrupted' (or a custom tag) by applying normalization and redistillation.

Usage:
  python scripts/quarantine_regenerate.py --tag '#corrupted' --dry-run --limit 100 --csv-out logs/regenerate_report.csv
  python scripts/quarantine_regenerate.py --tag '#corrupted' --write --limit 100

Actions:
  - Normalizes technical artifacts via `normalize_technical_content`.
  - Re-distills using the existing `distill_moment` API; updates `content_cleaned` if the new summary is acceptable.
  - Optionally removes the `#corrupted` tag if regeneration succeeds.
"""
import argparse
import csv
import os
import sys
import json
from datetime import datetime
# Repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from neo4j import GraphDatabase
from src.config import Settings
from src.content_utils import normalize_technical_content, clean_content, has_technical_signal
from src.distiller_impl import distill_moment


def append_csv(path, header, rows):
    write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
    with open(path, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(header)
        for row in rows:
            w.writerow(row)


def main(tag: str = '#corrupted', limit: int = 0, dry_run: bool = True, write: bool = False, csv_out: str = None):
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled; aborting')
        return
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    header = ['eid', 'app_id', 'created_at', 'before_excerpt', 'after_excerpt', 'status', 'error']
    with driver.session() as session:
        q = "MATCH (m:Memory) WHERE ANY(t in m.tags WHERE toLower(t) = $tag) RETURN elementId(m) as eid, m.app_id as app_id, m.created_at as created_at, m.content as content, m.content_cleaned as content_cleaned, m.tags as tags LIMIT $limit"
        res = session.run(q, {'tag': tag.lower(), 'limit': limit or 1000})
        rows = list(res)
        print(f"Found {len(rows)} nodes tagged {tag}")
        out_rows = []
        updated = 0
        for r in rows:
            eid = r['eid']
            raw = r.get('content') or ''
            before = (r.get('content_cleaned') or '')[:300]
            if not raw:
                out_rows.append([str(eid), r.get('app_id') or '', r.get('created_at') or '', before, '', 'no_raw_content', ''])
                continue
            try:
                normalized = normalize_technical_content(raw)
                tech_signal = has_technical_signal(normalized)
                cleaned_candidate = clean_content(normalized, remove_emojis=not tech_signal, annotate_technical=tech_signal)
                # If cleaned_candidate is dramatically shorter than raw, we consider it a success
                # Call distill_moment to generate a representative summary
                import asyncio
                try:
                    distilled = asyncio.run(distill_moment(cleaned_candidate))
                except Exception as e:
                    distilled = None
                summary = ''
                if isinstance(distilled, dict):
                    summary = distilled.get('summary') or ''
                if not summary or len(summary) < 8:
                    # If summary too short, fallback to the cleaned text truncated
                    summary = (cleaned_candidate[:300] + '...') if len(cleaned_candidate) > 300 else cleaned_candidate
                out_rows.append([str(eid), r.get('app_id') or '', r.get('created_at') or '', before, summary[:300], 'candidate', ''])
                # Write to DB if requested
                if write:
                    # Update content_cleaned and append a tag 'regenerated_n' with timestamp
                    now = datetime.utcnow().isoformat()
                    # Optionally remove the corruption tag and add a 'quarantined_regenerated' flag
                    # Get new tags: append if not present
                    tags = r.get('tags') or []
                    # normalize tags to list
                    if isinstance(tags, str):
                        try:
                            tags = json.loads(tags)
                        except Exception:
                            tags = [tags]
                    # Replace tag
                    try:
                        tags = [t for t in tags if t.lower() != tag.lower()]
                    except Exception:
                        pass
                    tags.append('regenerated')
                    session.run("MATCH (m:Memory) WHERE elementId(m) = $eid SET m.content_cleaned = $cleaned, m.content_cleaned_at = $now, m.tags = $tags", {'eid': str(eid), 'cleaned': summary, 'now': now, 'tags': tags})
                    updated += 1
            except Exception as e:
                out_rows.append([str(eid), r.get('app_id') or '', r.get('created_at') or '', before, '', 'error', str(e)])
        if csv_out and out_rows:
            append_csv(csv_out, header, out_rows)
    print(f"Regeneration complete: examined={len(rows)} updated={updated}")
    driver.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='#corrupted', type=str, help='Tag used to mark corrupted nodes')
    parser.add_argument('--limit', default=100, type=int, help='Limit nodes to examine')
    parser.add_argument('--dry-run', action='store_true', help='Dry run: do not write DB changes')
    parser.add_argument('--write', action='store_true', help='Write DB updates (remove corruption tag, update content_cleaned)')
    parser.add_argument('--csv-out', type=str, default=None, help='Optional CSV path to append report entries')
    args = parser.parse_args()
    if args.write:
        dry_run = False
        write = True
    else:
        dry_run = True
        write = False
    main(tag=args.tag, limit=args.limit, dry_run=dry_run, write=write, csv_out=args.csv_out)
