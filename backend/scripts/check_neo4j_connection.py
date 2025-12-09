#!/usr/bin/env python3
from neo4j import GraphDatabase
from src.config import Settings
import sys
s=Settings()
if not s.neo4j_enabled:
    print('Neo4j disabled')
    sys.exit(1)

try:
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    with driver.session() as session:
        res = session.run('RETURN 1 as ok').single()
        print('Neo4j connection ok:', res['ok'])
    driver.close()
except Exception as e:
    print('Neo4j connection failed:', e)
    sys.exit(2)
