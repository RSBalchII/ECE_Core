#!/usr/bin/env python3
import csv
import sys
import os
from neo4j import GraphDatabase
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config import Settings

CSV='repair_canary_run2.csv'
THRESH=0.5

s=Settings()
if not s.neo4j_enabled:
    print('Neo4j not enabled; aborting')
    sys.exit(1)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

rows=[]
with open(CSV,'r',encoding='utf-8') as fh:
    rdr=csv.DictReader(fh)
    for r in rdr:
        score = 0.0
        try:
            score = float(r.get('score') or 0.0)
        except:
            score = 0.0
        if score >= THRESH:
            rows.append((score,r))

rows=sorted(rows,key=lambda x: x[0],reverse=True)

print('Found', len(rows), f'rows with score >= {THRESH}')

# For each selected row, query Neo4j and print content + content_cleaned

q = 'MATCH (m:Memory) WHERE elementId(m) = $eid RETURN m.content as content, m.content_cleaned as content_cleaned, m.tags as tags, m.app_id as app_id'

with driver.session() as session:
    for score,r in rows[:10]:
        s_eid = r['s_eid']
        orig_eid = r['orig_eid']
        print('\n---- Candidate: score=%.4f s=%s o=%s' % (score, s_eid, orig_eid))
        sres = session.run(q, {'eid': s_eid}).single()
        ores = session.run(q, {'eid': orig_eid}).single()
        print('Summary content (cleaned):', (sres.get('content_cleaned') or '')[:400])
        print('Original content (cleaned):', (ores.get('content_cleaned') or '')[:400])
        print('Summary tags:', sres.get('tags'))
        print('Original tags:', ores.get('tags'))

driver.close()
