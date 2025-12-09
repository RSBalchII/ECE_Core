#!/usr/bin/env python3
from neo4j import GraphDatabase
from src.config import Settings

s=Settings()
if not s.neo4j_enabled:
    print('Neo4j disabled')
    raise SystemExit(1)

driver=GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

ids_to_check=['4:e6d0034d-19a9-4c59-9d15-1264d8ea24ad:22458','4:e6d0034d-19a9-4c59-9d15-1264d8ea24ad:22459','4:e6d0034d-19a9-4c59-9d15-1264d8ea24ad:0']

q='MATCH (m:Memory) WHERE elementId(m) = $eid RETURN m.content as content, m.content_cleaned as content_cleaned, m.tags as tags, m.app_id as app_id, m.created_at as created_at'

with driver.session() as session:
    for eid in ids_to_check:
        res = session.run(q, {'eid': eid}).single()
        print('EID:', eid)
        if not res:
            print('  Not found')
            continue
        print('  content:', (res['content'] or '')[:500])
        print('  content_cleaned:', (res['content_cleaned'] or '')[:500])
        print('  tags:', res['tags'])
        print('  created_at:', res['created_at'])

driver.close()
