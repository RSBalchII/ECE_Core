from neo4j import GraphDatabase
import json
from src.config import Settings

s = Settings()
if not s.neo4j_enabled:
    print('Neo4j not enabled in settings')
    exit(1)

driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

with driver.session() as session:
    # Find summary nodes with metadata containing distilled_from
    results = session.run("""
        MATCH (s:Memory)
        WHERE s.metadata IS NOT NULL AND s.metadata CONTAINS 'distilled_from'
        RETURN elementId(s) as s_eid, s.metadata as metadata
    """)
    rows = list(results)
    created = 0
    for r in rows:
        s_eid = r['s_eid']
        metadata = r['metadata']
        try:
            md = json.loads(metadata)
        except Exception:
            # Not valid JSON, skip
            continue
        # Try to determine the original node id
        orig_app_id = md.get('distilled_from_app_id')
        orig_id = md.get('distilled_from')
        if not orig_id and not orig_app_id:
            continue
        found = []
        # Prefer app_id lookup (stable and non-deprecated)
        if orig_app_id:
            res = session.run("MATCH (orig:Memory {app_id: $orig_app_id}) RETURN elementId(orig) as e, orig.app_id as app_id", {"orig_app_id": str(orig_app_id)})
            found = list(res)
        if not found and orig_id:
            # orig_id might be string like '4:12345' (elementId) - try elementId first
            res = session.run("MATCH (orig) WHERE elementId(orig) = $orig_id RETURN elementId(orig) as e", {"orig_id": str(orig_id)})
            found = list(res)
        if not found and orig_id:
            # As a last resort, if orig_id is numeric, try the integer id comparison (deprecated)
            try:
                res = session.run("MATCH (orig) WHERE id(orig) = $oid RETURN elementId(orig) as e, orig.app_id as app_id", {"oid": int(orig_id)})
                found = list(res)
            except Exception:
                found = []
        if found:
            # create relationship if not exists
            session.run("MATCH (s),(orig) WHERE elementId(s) = $s_eid AND elementId(orig) = $orig_eid MERGE (s)-[:DISTILLED_FROM]->(orig)", {"s_eid": str(s_eid), "orig_eid": str(found[0]['e'])})
            created += 1
    print(f"Created {created} DISTILLED_FROM relationships")

driver.close()
