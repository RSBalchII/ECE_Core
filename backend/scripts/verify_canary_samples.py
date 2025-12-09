#!/usr/bin/env python3
import csv
import os
import sys
from neo4j import GraphDatabase
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config import Settings

REPORT='canary_clean_report.csv'

s=Settings()
if not s.neo4j_enabled:
    print('Neo4j not enabled; aborting')
    sys.exit(1)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

# Read CSV and pick some samples
updated=[]
skipped=[]
with open(REPORT, 'r', encoding='utf-8') as fh:
    rdr=csv.reader(fh)
    for r in rdr:
        if not r:
            continue
        # skip potential header that may be missing - header: eid,app_id,status,len
        if r[0]=='eid' or r[0]=='s_eid':
            continue
        eid=r[0]
        status=r[2] if len(r)>2 else ''
        if status=='updated':
            updated.append(eid)
        if status.startswith('skipped'):
            skipped.append(eid)

# pick one updated and one skipped
sample_updated = updated[0] if updated else None
sample_skipped = skipped[0] if skipped else None

print('Updated count:', len(updated))
print('Skipped count:', len(skipped))
print('Sample updated:', sample_updated)
print('Sample skipped:', sample_skipped)

# Query the DB for the chosen samples and try to find a technical node

def get_node_by_element_id(session, eid):
    q = 'MATCH (m:Memory) WHERE elementId(m) = $eid RETURN m.content as content, m.content_cleaned as content_cleaned, m.tags as tags, m.app_id as app_id, m.created_at as created_at'
    res = session.run(q, {'eid': eid})
    r = res.single()
    return r

with driver.session() as session:
    if sample_updated:
        r = get_node_by_element_id(session, sample_updated)
        print('\n-- Updated Node:')
        if r:
            print('content:', (r['content'] or '')[:400])
            print('content_cleaned:', (r['content_cleaned'] or '')[:400])
            print('tags:', r['tags'])
            print('app_id:', r['app_id'])
            print('created_at:', r['created_at'])
        else:
            print('No updated node found for', sample_updated)
    else:
        print('No updated samples in CSV')

    if sample_skipped:
        r2 = get_node_by_element_id(session, sample_skipped)
        print('\n-- Skipped Node:')
        if r2:
            print('content:', (r2['content'] or '')[:400])
            print('content_cleaned:', (r2['content_cleaned'] or '')[:400])
            print('tags:', r2['tags'])
            print('app_id:', r2['app_id'])
            print('created_at:', r2['created_at'])
        else:
            print('No skipped node found for', sample_skipped)

    # Search for technical nodes in the canary run subset
    # Build a list of updated eids to search within
    eids = updated[:100]
    if eids:
        q2 = 'MATCH (m:Memory) WHERE elementId(m) IN $eids AND (m.content CONTAINS "sudo" OR m.content CONTAINS "apt-get" OR m.content CONTAINS "pip" OR m.content CONTAINS "npm" OR m.content CONTAINS "docker" OR m.content CONTAINS "v1.") RETURN elementId(m) as id, m.content as content, m.content_cleaned as content_cleaned, m.tags as tags LIMIT 10'
        res2 = session.run(q2, {'eids': eids})
        technical_nodes = [row for row in res2]
        print('\n-- Technical nodes found in updated sample:')
        if technical_nodes:
            for node in technical_nodes:
                print('ID:', node['id'])
                print('content:', (node['content'] or '')[:300])
                print('content_cleaned:', (node['content_cleaned'] or '')[:300])
                print('tags:', node['tags'])
                print('---')
        else:
            print('No technical nodes found in updated subset. You might run a wider search.')
    else:
        print('No updated eids to search for technical nodes')

driver.close()
