"""
Import extracted conversation turns into Neo4j as Memory nodes.

This is the Neo4j version of the legacy SQLite importer. It assumes the
Neo4j server is available (bolt protocol). The module is small and
intended for batch imports. It uses the TurnExtractor used by the
legacy importer to produce Turn objects and creates Memory nodes with
basic properties.

Usage:
    python -m data_pipeline.import_turns_neo4j
"""
from typing import List
from neo4j import GraphDatabase
import os
import sys
from pathlib import Path
try:
    from extract_turns import TurnExtractor, Turn
except Exception:
    # Optional helper – if extract_turns isn't present (e.g. CI/test), fall back to a local Turn dataclass
    from dataclasses import dataclass

    @dataclass
    class Turn:
        session_id: str
        turn_num: int
        timestamp: str | None
        speaker: str
        content: str

    TurnExtractor = None
from datetime import datetime


class TurnImporterNeo4j:
    def __init__(self, bolt_uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = None):
        if not bolt_uri:
            raise ValueError("Bolt URI required for Neo4j import")
        self.bolt_uri = bolt_uri
        auth = (user, password) if password else None
        self.driver = GraphDatabase.driver(self.bolt_uri, auth=auth)

    def close(self):
        self.driver.close()

    def import_turns(self, turns: List[Turn]):
        """Import a list of Turn objects into Neo4j as Memory nodes.

        For each Turn, create a Memory node with properties: session_id, turn_num,
        speaker, content, timestamp. We also create a NEXT relationship between
        sequential turns in the same session for ordering.
        """
        with self.driver.session() as session:
            for turn in turns:
                session.execute_write(self._create_memory_node, turn)
            # Create NEXT relationships per session
            sessions = {}
            for t in turns:
                sessions.setdefault(t.session_id, []).append(t)
            for session_id, s_turns in sessions.items():
                s_turns_sorted = sorted(s_turns, key=lambda x: x.turn_num)
                for idx in range(len(s_turns_sorted) - 1):
                    session.execute_write(self._create_next_relationship, s_turns_sorted[idx], s_turns_sorted[idx + 1])

    @staticmethod
    def _create_memory_node(tx, turn: Turn):
        tx.run(
            """
            CREATE (m:Memory {
                session_id: $session_id,
                turn_num: $turn_num,
                speaker: $speaker,
                content: $content,
                timestamp: $timestamp
            })
        """,
            {
                "session_id": turn.session_id,
                "turn_num": int(turn.turn_num),
                "speaker": turn.speaker,
                "content": turn.content,
                "timestamp": turn.timestamp.isoformat() if turn.timestamp else None,
            },
        )

    @staticmethod
    def _create_next_relationship(tx, from_turn: Turn, to_turn: Turn):
        tx.run(
            """
            MATCH (a:Memory {session_id: $session_id, turn_num: $from_turn_num}),
                  (b:Memory {session_id: $session_id, turn_num: $to_turn_num})
            MERGE (a)-[:NEXT]->(b)
            """,
            {
                "session_id": from_turn.session_id,
                "from_turn_num": int(from_turn.turn_num),
                "to_turn_num": int(to_turn.turn_num),
            },
        )


def main():
    # Can override via env
    bolt = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", None)

    print("Extracting turns...")
    if TurnExtractor is None:
        print("No TurnExtractor available; please pass Turns manually or place extract_turns.py in the path.")
        return
    extractor = TurnExtractor()
    turns = extractor.extract_all()
    if not turns:
        print("No turns found; aborting")
        return

    importer = TurnImporterNeo4j(bolt, user, pwd)
    try:
        print(f"Importing {len(turns)} turns into Neo4j at {bolt}...")
        importer.import_turns(turns)
        print("Import complete")
    finally:
        importer.close()


if __name__ == "__main__":
    main()
