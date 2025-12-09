from neo4j import GraphDatabase
from src.config import Settings
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--s-eid', required=True)
parser.add_argument('--orig-eid', required=True)
args = parser.parse_args()

s = Settings()
if not s.neo4j_enabled:
    print('Neo4j not enabled')
    exit(1)

drv = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
with drv.session() as session:
    res = session.run('MATCH (s),(o) WHERE elementId(s)= $s_eid AND elementId(o) = $orig_eid RETURN s.app_id as s_app_id, s.metadata as s_meta, s.content as s_content, s.created_at as s_created_at, elementId(s) as s_eid, elementId(o) as orig_eid, o.app_id as orig_app_id, o.content as orig_content, o.created_at as orig_created_at', {'s_eid': args.s_eid, 'orig_eid': args.orig_eid}).single()
    if not res:
        print('No results')
    else:
        print('SUMMARY:')
        print('s_eid=', res['s_eid'])
        print('s_app_id=', res.get('s_app_id'))
        print('s_created_at=', res.get('s_created_at'))
        print('s_meta=', res.get('s_meta'))
        print('s_content_snippet=', (res.get('s_content')[:400] if res.get('s_content') else ''))
        print('\nORIGIN:')
        print('orig_eid=', res['orig_eid'])
        print('orig_app_id=', res.get('orig_app_id'))
        print('orig_created_at=', res.get('orig_created_at'))
        print('orig_content_snippet=', (res.get('orig_content')[:400] if res.get('orig_content') else ''))

drv.close()
