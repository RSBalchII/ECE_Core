#!/usr/bin/env python3
"""
Repair Missing DISTILLED_FROM relationships using timestamps (v2).

This is an improved version that handles multiple timestamp formats and provides CLI flags
such as `--dry-run` and `--csv-out` for manual review.

Usage:
  python scripts/repair_missing_links_by_timestamp_v2.py --window 86400 --dry-run --csv-out candidates.csv
"""

from neo4j import GraphDatabase
from src.config import Settings
from datetime import datetime, timedelta, timezone
import dateutil.parser
import argparse
import csv
import os
import sys

CONFIDENCE_WINDOW_SECONDS = 7200


def parse_maybe_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
        try:
            n = int(s)
            if n > 1_000_000_000_000:
                return datetime.fromtimestamp(n / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(n, tz=timezone.utc)
        except Exception:
            pass
    try:
        f = float(s)
        if f > 1_000_000_000_000:
            return datetime.fromtimestamp(f / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(f, tz=timezone.utc)
    except Exception:
        pass
    try:
        dt = dateutil.parser.isoparse(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        dt = dateutil.parser.parse(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def append_csv(path, row):
    write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
    with open(path, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if write_header:
            w.writerow(['s_eid', 's_app_id', 's_created_at', 'orig_eid', 'orig_app_id', 'orig_created_at'])
        w.writerow(row)


def run_repair(window_seconds: int = CONFIDENCE_WINDOW_SECONDS, dry_run: bool = False, limit: int = 1000, csv_out: str = None):
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    created = 0
    processed = 0
    with driver.session() as session:
        results = session.run(
            """
            MATCH (s:Memory)
            WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->()
            RETURN elementId(s) as s_eid, s.app_id as s_app_id, s.created_at as created_at, s.content as content
            ORDER BY s.created_at DESC
            LIMIT $limit
            """,
            {'limit': limit}
        )
        rows = list(results)
        print(f"Processing {len(rows)} summary candidates (window={window_seconds}s); dry_run={dry_run}")
        for r in rows:
            processed += 1
            s_eid = r['s_eid']
            s_app_id = r.get('s_app_id')
            created_at = r['created_at']
            if not created_at:
                continue
            s_dt = parse_maybe_datetime(created_at)
            if not s_dt:
                print(f"Could not parse created_at for summary {s_eid}: {created_at}")
                continue
            cutoff = s_dt - timedelta(seconds=window_seconds)
            q = """
                MATCH (orig:Memory)
                WHERE ((orig.tags IS NOT NULL AND 'imported' IN orig.tags) OR (orig.metadata IS NOT NULL AND orig.metadata CONTAINS 'import_via_chat'))
                  AND NOT (() -[:DISTILLED_FROM]->(orig))
                  AND orig.created_at <= $s_dt
                  AND orig.created_at >= $cutoff_dt
                RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at
                ORDER BY orig.created_at DESC
                LIMIT 1
            """
            try:
                cand = session.run(q, {'s_dt': s_dt.isoformat(), 'cutoff_dt': cutoff.isoformat()}).single()
            except Exception as e:
                print(f"Query failed for {s_eid}: {e}")
                continue
            if cand:
                orig_eid = cand['orig_eid']
                orig_app_id = cand.get('orig_app_id')
                if dry_run:
                    if csv_out:
                        append_csv(csv_out, [str(s_eid), str(s_app_id) if s_app_id else '', s_dt.isoformat(), str(orig_eid), str(orig_app_id) if orig_app_id else '', str(cand.get('o_created_at'))])
                    else:
                        print(f"DRY: s={s_eid} (app_id={s_app_id}) -> orig={orig_eid} (app_id={orig_app_id}) orig_created_at={cand.get('o_created_at')}")
                else:
                    try:
                        if orig_app_id and s_app_id:
                            session.run("MATCH (s:Memory{app_id: $s_app}), (orig:Memory{app_id: $orig_app}) MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_app': str(s_app_id), 'orig_app': str(orig_app_id)})
                        elif orig_app_id and not s_app_id:
                            session.run("MATCH (s),(orig:Memory{app_id: $orig_app}) WHERE elementId(s) = $s_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_app': str(orig_app_id)})
                        else:
                            session.run("MATCH (s),(orig) WHERE elementId(s) = $s_eid AND elementId(orig) = $orig_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_eid': str(orig_eid)})
                    except Exception as e:
                        print(f"Failed to MERGE relationship for s={s_eid} -> orig={orig_eid}: {e}")
                        continue
                created += 1
        print(f"Done: processed={processed}, created={created} (dry_run={dry_run})")
    driver.close()


def main():
    parser = argparse.ArgumentParser(description='Repair missing DISTILLED_FROM links using timestamp heuristics')
    parser.add_argument('--window', type=int, default=CONFIDENCE_WINDOW_SECONDS, help='Confidence window in seconds to search for original memory created before summary (default 7200)')
    parser.add_argument('--dry-run', action='store_true', help='Do not write DB changes; instead emit candidate pairs or write CSV')
    parser.add_argument('--limit', type=int, default=1000, help='Limit number of summary candidates to process')
    parser.add_argument('--csv-out', type=str, default=None, help='If set, append dry-run candidate pairs to this CSV file')
    args = parser.parse_args()
    run_repair(window_seconds=args.window, dry_run=args.dry_run, limit=args.limit, csv_out=args.csv_out)


if __name__ == '__main__':
    main()
