from scripts.neo4j.repair.repair_missing_links_by_timestamp import *

def parse_maybe_datetime(value):
    """Parse a variety of timestamp formats into a UTC datetime.
    Returns None if it cannot parse.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    # Numeric epoch detection
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
    main()#!/usr/bin/env python3
"""
Simplified and cleaned single-version script with robust datetime parsing.
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
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    s = str(value).strip()
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
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = dateutil.parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
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
#!/usr/bin/env python3
"""
Repair Missing DISTILLED_FROM relationships using timestamps.

Usage:
  python scripts/repair_missing_links_by_timestamp.py --window 86400 --dry-run --csv-out candidates.csv
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
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    s = str(value).strip()
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
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = dateutil.parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
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
#!/usr/bin/env python3
"""
Repair Missing DISTILLED_FROM relationships using timestamps.

This script attempts to link summary memories back to original imported memories
by searching for original memories that were created within a confidence window
prior to the summary's creation time.

It supports a number of timestamp formats and includes a `--dry-run` mode which
prints or writes candidate pairs to CSV for manual review.

Usage:
  python scripts/repair_missing_links_by_timestamp.py --window 86400 --dry-run --csv-out candidates.csv
"""

from neo4j import GraphDatabase
from src.config import Settings
from datetime import datetime, timedelta, timezone
import dateutil.parser
import argparse
import csv
import os
import sys

CONFIDENCE_WINDOW_SECONDS = 7200  # Two hours


def parse_maybe_datetime(value):
    """Try to parse a value into a timezone-aware datetime in UTC or return None.
    Accepts datetime instances, ISO strings, epoch ints/floats (sec or ms), and any
    string parseable by dateutil.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    s = str(value).strip()
    # Numeric epoch detection
    if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
        try:
            n = int(s)
            # Heuristic: if > 1e12 -> milliseconds
            if n > 1_000_000_000_000:
                return datetime.fromtimestamp(n / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(n, tz=timezone.utc)
        except Exception:
            pass
    try:
        f = float(s)
        # If greater than 1e12, assume ms
        if f > 1_000_000_000_000:
            return datetime.fromtimestamp(f / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(f, tz=timezone.utc)
    except Exception:
        pass
    # ISO / dateutil parse
    try:
        dt = dateutil.parser.isoparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = dateutil.parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
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
        # Fetch summary nodes missing the relationship and include app_id if present
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
                            # Link by orig.app_id when summary has no app_id
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
#!/usr/bin/env python3
"""
Repair Missing DISTILLED_FROM relationships using timestamps.

This script attempts to link summary memories back to original imported memories
by searching for original memories that were created within a confidence window
prior to the summary's creation time.

It supports a number of timestamp formats and includes a `--dry-run` mode which
prints or writes candidate pairs to CSV for manual review.

Usage:
  python scripts/repair_missing_links_by_timestamp.py --window 86400 --dry-run --csv-out candidates.csv
"""

from neo4j import GraphDatabase
from src.config import Settings
from datetime import datetime, timedelta, timezone
import dateutil.parser
import argparse
import csv
import os
import sys

CONFIDENCE_WINDOW_SECONDS = 7200  # Two hours


def parse_maybe_datetime(value):
    """Try to parse a value into a timezone-aware datetime in UTC or return None.
    Accepts datetime instances, ISO strings, epoch ints/floats (sec or ms), and any
    string parseable by dateutil.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    s = str(value).strip()
    # Numeric epoch detection
    if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
        try:
            n = int(s)
            # If > 1e12 assume milliseconds
            if n > 1_000_000_000_000:
                return datetime.fromtimestamp(n / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(n, tz=timezone.utc)
        except Exception:
            pass
    try:
        f = float(s)
        # If greater than 1e12, assume ms
        if f > 1_000_000_000_000:
            return datetime.fromtimestamp(f / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(f, tz=timezone.utc)
    except Exception:
        pass
    # ISO / dateutil parse
    try:
        dt = dateutil.parser.isoparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = dateutil.parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
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
        # Fetch summary nodes missing the relationship and include app_id if present
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
                            # Link by orig.app_id when summary has no app_id
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
from neo4j import GraphDatabase
from src.config import Settings
from datetime import datetime, timedelta
import dateutil.parser
import argparse
import csv
import os

CONFIDENCE_WINDOW_SECONDS = 7200  # Two hours
def parse_maybe_datetime(value):
    """Robust parser that accepts various timestamp formats and returns a timezone-aware datetime in UTC.
    Handles:
    - Neo4j's datetime string output (e.g., 2025-07-30T18:16:49.949Z)
    - ISO-8601 strings with or without timezone
    - epoch seconds (int/float) and milliseconds
    - bare date/time strings parseable by dateutil
    - None or non-parsable values returns None
    """
    if value is None:
        return None
    # If we get a neo4j datetime object, it's safe to str() it and parse
    try:
        # Check for direct datetime
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        s = str(value)
        s = s.strip()
        # Integers/floats -> epoch seconds or ms
        if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
            try:
                n = int(s)
                # Heuristic: if > 1e12 -> milliseconds
                if n > 1_000_000_000_000:
                    return datetime.fromtimestamp(n/1000, tz=timezone.utc)
                # If it's in the past and seems like seconds
                return datetime.fromtimestamp(n, tz=timezone.utc)
            except Exception:
                pass
        # decimal numbers
        try:
            f = float(s)
            if f > 0:
                # heuristics for ms vs s
                if f > 1e12:
                    return datetime.fromtimestamp(f/1000.0, tz=timezone.utc)
                return datetime.fromtimestamp(f, tz=timezone.utc)
        except Exception:
            pass
        # Use dateutil as a robust fallback
        try:
            dt = dateutil.parser.isoparse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
        try:
            dt = dateutil.parser.parse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

def run_repair():
    s = Settings()
    if not s.neo4j_enabled:
        print('Neo4j not enabled in settings')
        return
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    created = 0
    with driver.session() as session:
        # Fetch summary nodes missing the relationship
            # Fetch summary nodes missing the relationship and include app_id if present
            rows = session.run("MATCH (s:Memory) WHERE s.category='summary' AND NOT (s)-[:DISTILLED_FROM]->() RETURN elementId(s) as s_eid, s.app_id as s_app_id, s.created_at as created_at, s.content as content LIMIT $limit", {'limit': limit})
            s_eid = r['s_eid']
            s_app_id = r.get('s_app_id')
            created_at = r['created_at']
            if not created_at:
                continue
            # Parse created_at - neo4j datetime -> str e.g. 2025-07-30T18:16:49.949Z
            try:
                try:
                    s_dt = parse_maybe_datetime(created_at)
                continue
            # Find candidate original memory created prior to summary within the confidence window
            cutoff = s_dt - timedelta(seconds=CONFIDENCE_WINDOW_SECONDS)
                cutoff = s_dt - timedelta(seconds=window_seconds)
                MATCH (orig:Memory)
                WHERE ((orig.tags IS NOT NULL AND 'imported' IN orig.tags) OR (orig.metadata IS NOT NULL AND orig.metadata CONTAINS 'import_via_chat'))
                  AND NOT (() -[:DISTILLED_FROM]->(orig))
                  AND orig.created_at <= $s_dt
                  AND orig.created_at >= $cutoff_dt
                RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at
                    RETURN elementId(orig) as orig_eid, orig.app_id as orig_app_id, orig.created_at as o_created_at
                LIMIT 1
            """
            cand = session.run(q, {'s_dt': s_dt.isoformat(), 'cutoff_dt': cutoff.isoformat()}).single()
            if cand:
                orig_eid = cand['orig_eid']
                orig_app_id = cand.get('orig_app_id')
                    orig_app_id = cand.get('orig_app_id')
                    # If dry run, write match to CSV or print
                    if dry_run:
                        if csv_out:
                            # CSV fields: s_eid, s_app_id, s_created_at, orig_eid, orig_app_id, orig_created_at
                            append_csv(csv_out, [str(s_eid), str(s_app_id) if s_app_id else '', s_dt.isoformat(), str(orig_eid), str(orig_app_id) if orig_app_id else '', str(cand.get('o_created_at'))])
                        else:
                            print(f"DRY: s={s_eid} (app_id={s_app_id}) -> orig={orig_eid} (app_id={orig_app_id}) orig_created_at={cand.get('o_created_at')}")
                    else:
                        if orig_app_id and s_app_id:
                            session.run("MATCH (s:Memory{app_id: $s_app}), (orig:Memory{app_id: $orig_app}) MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_app': str(s_app_id), 'orig_app': str(orig_app_id)})
                        elif orig_app_id and not s_app_id:
                            # link by orig.app_id to the summary by elementId(s)
                            session.run("MATCH (s),(orig:Memory{app_id: $orig_app}) WHERE elementId(s) = $s_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_app': str(orig_app_id)})
                        else:
                            session.run("MATCH (s),(orig) WHERE elementId(s) = $s_eid AND elementId(orig) = $orig_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_eid': str(orig_eid)})
                    session.run("MATCH (s:Memory{app_id: $s_app}), (orig:Memory{app_id: $orig_app}) MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_app': str(s_app_id), 'orig_app': str(orig_app_id)})
        print(f"Created {created} relationships via timestamp heuristic (dry_run={dry_run})")
                    # If summary lacks app_id, fall back to elementId merging
                    session.run("MATCH (s),(orig:Memory{app_id: $orig_app}) WHERE elementId(s) = $s_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_app': str(orig_app_id)})
    def append_csv(path, row):
        write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
        with open(path, 'a', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(['s_eid', 's_app_id', 's_created_at', 'orig_eid', 'orig_app_id', 'orig_created_at'])
            w.writerow(row)


                    session.run("MATCH (s),(orig) WHERE elementId(s) = $s_eid AND elementId(orig) = $orig_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {'s_eid': str(s_eid), 'orig_eid': str(orig_eid)})
        parser = argparse.ArgumentParser(description='Repair missing DISTILLED_FROM links using timestamp heuristics')
        parser.add_argument('--window', type=int, default=CONFIDENCE_WINDOW_SECONDS, help='Confidence window in seconds to search for original memory created before summary (default 7200)')
        parser.add_argument('--dry-run', action='store_true', help='Do not write DB changes; instead emit candidate pairs or write CSV')
        parser.add_argument('--limit', type=int, default=1000, help='Limit number of summary candidates to process')
        parser.add_argument('--csv-out', type=str, default=None, help='If set, append dry-run candidate pairs to this CSV file')
        args = parser.parse_args()
        run_repair(window_seconds=args.window, dry_run=args.dry_run, limit=args.limit, csv_out=args.csv_out)
    print(f"Created {created} relationships via timestamp heuristic")
    driver.close()

if __name__ == '__main__':
    run_repair()
