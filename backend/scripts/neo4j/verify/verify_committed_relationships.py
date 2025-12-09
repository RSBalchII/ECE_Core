#!/usr/bin/env python3
import csv
import sys
import os
from neo4j import GraphDatabase
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.config import Settings

CSV='repair_canary_commit.csv'
import argparse

parser = argparse.ArgumentParser(description='Verify committed relationships by CSV or run id')
parser.add_argument('--run-id', default=None, help='Optional run id to verify directly from database')
parser.add_argument('--csv', default=None, help='Optional CSV file to use instead of default')
args = parser.parse_args()
if args.csv:
    CSV = args.csv

s=Settings()
if not s.neo4j_enabled:
    print('Neo4j not enabled; aborting')
    sys.exit(1)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

pairs=[]
with open(CSV,'r',encoding='utf-8') as fh:
    rdr=csv.DictReader(fh)
    for r in rdr:
        s_eid=r.get('s_eid')
        orig_eid=r.get('orig_eid')
        if s_eid and orig_eid:
            pairs.append((s_eid,orig_eid))

print('Checking',len(pairs),'pairs')

verify_q='MATCH (s:Memory)-[r:DISTILLED_FROM]->(o) WHERE elementId(s)=$s_eid AND elementId(o)=$orig_eid RETURN count(r) as c'

with driver.session() as session:
    count=0
    missing=[]
    if args.run_id:
        # verify relationships present for a run_id
        find_by_run_q = "MATCH (s:Memory)-[r:DISTILLED_FROM]->(o) WHERE r.auto_commit_run_id = $run_id RETURN elementId(s) as s_eid, elementId(o) as orig_eid, count(r) as c"
        res = session.run(find_by_run_q, {'run_id': args.run_id})
        for row in res:
            pairs.append((row['s_eid'], row['orig_eid']))
    for s_eid,orig_eid in pairs:
        res=session.run(verify_q, {'s_eid': s_eid, 'orig_eid': orig_eid}).single()
        c=res.get('c') if res else 0
        if c and int(c)>0:
            count+=1
        else:
            missing.append((s_eid,orig_eid))

print('Found committed relationships:', count)
if missing:
    print('Missing count:',len(missing))
    for m in missing[:10]:
        print('Missing pair:',m)

driver.close()
