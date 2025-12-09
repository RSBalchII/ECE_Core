#!/usr/bin/env python3
import csv
import sys
from neo4j import GraphDatabase
sys.path.insert(0, '..')
from src.config import Settings

s=Settings()
CSV='calibration_run_filtered.csv'
rows=[]
with open(CSV,'r',encoding='utf-8') as fh:
    rdr=csv.DictReader(fh)
    for r in rdr:
        try:
            sc=float(r.get('score') or 0.0)
        except:
            continue
        rows.append((sc,r))
rows.sort(key=lambda x: x[0], reverse=True)
print('Top 3 matches in', CSV)

if not s.neo4j_enabled:
    print('Neo4j not enabled; exiting')
    sys.exit(1)

# Connect to Neo4j and print excerpts and tags
driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
q = 'MATCH (m:Memory) WHERE elementId(m) = $eid RETURN m.content as content, m.content_cleaned as content_cleaned, m.tags as tags, m.app_id as app_id'
with driver.session() as session:
    for sc,r in rows[:3]:
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
