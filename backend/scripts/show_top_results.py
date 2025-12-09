#!/usr/bin/env python3
import csv
import sys
import os
from neo4j import GraphDatabase
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config import Settings
import os

# Usage: python scripts/show_top_results.py hybrid_repair_run.csv 3

CSV='calibration_run.csv'
TOP=3
if len(sys.argv) > 1:
    CSV = sys.argv[1]
if len(sys.argv) > 2:
    try:
        TOP = int(sys.argv[2])
    except Exception:
        TOP = 3

s=Settings()
rows=[]
with open(CSV,'r',encoding='utf-8') as fh:
    rdr=csv.DictReader(fh)
    for r in rdr:
        try:
            sc = float(r.get('score') or 0.0)
        except Exception:
            continue
        rows.append((sc,r))
rows.sort(key=lambda x: x[0], reverse=True)

print('Top', TOP, 'rows from', CSV)

if not s.neo4j_enabled:
    print('Neo4j not enabled')
    sys.exit(1)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
q = 'MATCH (m:Memory) WHERE elementId(m) = $eid RETURN m.content as content, m.content_cleaned as content_cleaned, m.tags as tags, m.app_id as app_id'
with driver.session() as session:
    for sc,r in rows[:TOP]:
        print('\n---')
        print('Score:', sc)
        print('s_eid:', r.get('s_eid'))
        print('orig_eid:', r.get('orig_eid'))
        sres = session.run(q, {'eid': r.get('s_eid')}).single()
        ores = session.run(q, {'eid': r.get('orig_eid')}).single()
        s_content = sres.get('content_cleaned') or sres.get('content') or ''
        o_content = ores.get('content_cleaned') or ores.get('content') or ''
        print('s_excerpt (cleaned/content):', s_content[:400])
        print('orig_excerpt (cleaned/content):', o_content[:400])
        print('s_tags:', sres.get('tags'))
        print('orig_tags:', ores.get('tags'))

driver.close()
