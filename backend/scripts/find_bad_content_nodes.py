#!/usr/bin/env python3
"""
Find Memory nodes containing a string pattern and print origin details for diagnosis
Usage: python scripts/find_bad_content_nodes.py --pattern 襁 --limit 50
"""
import argparse
from neo4j import GraphDatabase
from src.config import Settings

s = Settings()


def main(pattern, limit=50):
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    with driver.session() as session:
        q = "MATCH (m:Memory) WHERE m.content CONTAINS $pattern RETURN elementId(m) as eid, m.app_id as app_id, m.category as category, m.metadata as metadata, m.created_at as created_at, m.content as content LIMIT $limit"
        res = session.run(q, {'pattern': pattern, 'limit': limit})
        rows = list(res)
        if not rows:
            print('No nodes found')
            return
        for r in rows:
            print('EID:', r['eid'])
            print('app_id:', r.get('app_id'))
            print('created_at:', r.get('created_at'))
            print('category:', r.get('category'))
            print('metadata:', r.get('metadata'))
            print('content snippet:', (r.get('content') or '')[:200])
            print('-' * 40)
    driver.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pattern', type=str, required=True)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    main(args.pattern, limit=args.limit)
