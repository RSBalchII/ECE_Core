#!/usr/bin/env python3
"""
Neo4j migration helper: convert string-encoded 'tags' and 'metadata' properties on Memory nodes
to native list/map properties. Useful when old imports stored tags/metadata as JSON strings.

Usage:
  python scripts/neo4j/maintenance/neo4j_fix_tags_metadata.py --dry-run
  python scripts/neo4j/maintenance/neo4j_fix_tags_metadata.py --apply

This script connects to Neo4j using settings in core.config.Settings (NEO4J_URI, etc.).
It will iterate Memory nodes and detect when 'tags' or 'metadata' are strings and attempt to
parse them as JSON; if successful, it will write the converted property back to the node.
"""
import argparse
import json
import logging
from typing import Any
from neo4j import GraphDatabase
from src.config import settings

logger = logging.getLogger("neo4j_migration")


def detect_and_fix(driver: GraphDatabase.driver, apply: bool = False, limit: int = 500):
    updated = 0
    scanned = 0
    with driver.session() as session:
        # Pull a batch to examine
        cypher = "MATCH (m:Memory) RETURN elementId(m) as id, m.tags as tags, m.metadata as metadata LIMIT $limit"
        result = session.run(cypher, {"limit": limit})
        records = list(result)
        for r in records:
            scanned += 1
            tags = r["tags"]
            metadata = r["metadata"]
            eid = r["id"]
            needs_update = False
            updates = {}

            # Check tags
            if tags is not None and isinstance(tags, str):
                try:
                    parsed = json.loads(tags)
                    if isinstance(parsed, list):
                        updates["tags"] = parsed
                        needs_update = True
                except Exception:
                    logger.debug(f"Node {eid} tags is a string but not JSON-parsable: {tags}")

            # Check metadata
            if metadata is not None and isinstance(metadata, str):
                try:
                    parsed_md = json.loads(metadata)
                    if isinstance(parsed_md, dict):
                        updates["metadata"] = parsed_md
                        needs_update = True
                except Exception:
                    logger.debug(f"Node {eid} metadata is a string but not JSON-parsable: {metadata}")

            if needs_update:
                logger.info(f"Node {eid} requires update: {updates}")
                if apply:
                    # apply update
                    cur_cypher = ""
                    params = {"id": eid}
                    set_items = []
                    if "tags" in updates:
                        set_items.append("m.tags = $tags")
                        params["tags"] = updates["tags"]
                    if "metadata" in updates:
                        set_items.append("m.metadata = $metadata")
                        params["metadata"] = updates["metadata"]
                    cur_cypher = "MATCH (m) WHERE elementId(m) = $id SET " + ", ".join(set_items)
                    session.run(cur_cypher, params)
                    updated += 1

    return scanned, updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually apply updates")
    parser.add_argument("--limit", type=int, default=500, help="Number of nodes to scan in one run")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    bolt = settings.neo4j_uri
    user = settings.neo4j_user
    pwd = settings.neo4j_password

    logger.info(f"Connecting to Neo4j at {bolt}")
    driver = GraphDatabase.driver(bolt, auth=(user, pwd))
    try:
        scanned, updated = detect_and_fix(driver, apply=args.apply, limit=args.limit)
        logger.info(f"Scanned: {scanned}, Updated: {updated}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
