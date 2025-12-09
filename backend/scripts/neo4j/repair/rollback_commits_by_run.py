#!/usr/bin/env python3
"""
Rollback committed DISTILLED_FROM relationships by run id.

Usage:
  python scripts/neo4j/repair/rollback_commits_by_run.py --run-id <uuid> --confirm
"""
import argparse
import csv
import sys
import os
from neo4j import GraphDatabase
import uuid
from datetime import datetime, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from src.config import Settings

parser = argparse.ArgumentParser(description='Rollback committed relationships by run id')
parser.add_argument('--run-id', required=True, help='The run id to rollback')
parser.add_argument('--confirm', action='store_true', help='Confirm deletion (required to actually delete)')
parser.add_argument('--csv-out', default=None, help='Optional CSV file to write the deleted pairs')
args = parser.parse_args()

s = Settings()
if not s.neo4j_enabled:
    print('Neo4j not enabled; aborting')
    sys.exit(1)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

q_find = """
MATCH (s:Memory)-[r:DISTILLED_FROM]->(o)
WHERE r.auto_commit_run_id = $run_id
RETURN elementId(s) as s_eid, elementId(o) as o_eid, r.auto_commit_score as score
"""

q_delete = """
MATCH (s:Memory)-[r:DISTILLED_FROM]->(o)
WHERE r.auto_commit_run_id = $run_id
DELETE r
RETURN count(*) as deleted
"""

with driver.session() as session:
    samples = session.run(q_find, {'run_id': args.run_id})
    rows = [ (r['s_eid'], r['o_eid'], r.get('score')) for r in samples ]
    print(f"Found {len(rows)} relationships for run_id={args.run_id}")
    if len(rows) == 0:
        print('Nothing to delete; exiting')
        driver.close()
        sys.exit(0)
    # print sample rows
    for r in rows[:10]:
        print('Sample:', r)
    if not args.confirm:
        print('\nDRY RUN - no changes applied. Use --confirm to delete these relationships.')
        driver.close()
        sys.exit(0)
    # proceed to delete
    res = session.run(q_delete, {'run_id': args.run_id}).single()
    deleted = res.get('deleted') if res else 0
    print(f'Deleted relationships: {deleted}')
    # optionally write CSV of deleted pairs
    if args.csv_out:
        with open(args.csv_out, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(['run_id','s_eid','o_eid','score','deleted_at'])
            for s_eid, o_eid, score in rows:
                w.writerow([args.run_id, s_eid, o_eid, score, datetime.now(timezone.utc).isoformat()])

driver.close()
print('Rollback complete')
