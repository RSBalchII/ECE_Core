#!/usr/bin/env python3
import csv
import sys
import os
from neo4j import GraphDatabase
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from src.config import Settings

CSV='repair_canary_commit.csv'

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

print('Removing',len(pairs),'relationships...')

q='MATCH (s:Memory)-[r:DISTILLED_FROM]->(o) WHERE elementId(s)=$s_eid AND elementId(o)=$orig_eid DELETE r RETURN COUNT(r) as removed'

with driver.session() as session:
    total_removed=0
    for s_eid,orig_eid in pairs:
        res=session.run(q, {'s_eid': s_eid, 'orig_eid': orig_eid}).single()
        removed=res.get('removed') if res else 0
        total_removed += removed if removed else 0

print('Total removed relationships:', total_removed)

driver.close()
