import os
import socket
import pytest
import asyncio
import sys
from pathlib import Path
from neo4j import GraphDatabase
import httpx
from typing import List, Set
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.memory import TieredMemory


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _setup_driver(uri: str, user: str = None, password: str = None):
    auth = (user, password) if user else None
    return GraphDatabase.driver(uri, auth=auth)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_coda_qa():
    """End-to-end: Ensure LLM retrieval corresponds to Neo4j contents for the token 'Coda'."""
    bolt_host = "127.0.0.1"
    bolt_port = 7687
    bolt_uri = os.getenv("NEO4J_URI", f"bolt://{bolt_host}:{bolt_port}")
    neo4j_user = os.getenv("NEO4J_USER", None)
    neo4j_password = os.getenv("NEO4J_PASSWORD", None)

    # Ensure Neo4j and ECE / LLM are available
    ece_url = os.getenv("ECE_URL", "http://localhost:8000")
    llm_host = os.getenv("LLM_HOST", "localhost")
    llm_port = int(os.getenv("LLM_PORT", 8080))

    if not _is_port_open(bolt_host, bolt_port):
        pytest.skip("Neo4j is not available on 7687, skip e2e test")
    if not _is_port_open(llm_host, llm_port):
        pytest.skip("LLM server not available on 8080, skip e2e test")
    if not _is_port_open('127.0.0.1', 8000):
        pytest.skip("ECE Core not available on 8000, skip e2e test")

    driver = _setup_driver(bolt_uri, neo4j_user, neo4j_password)
    try:
        with driver.session() as session:
            query = """
                MATCH (m:Memory)
                WHERE toLower(m.content) CONTAINS 'coda' OR (m.tags IS NOT NULL AND toLower(m.tags) CONTAINS 'coda')
                RETURN elementId(m) as id, m.content as content, m.tags as tags
            """
            result = session.run(query)
            records = [r for r in result]
            db_ids: Set[str] = set()
            db_contents: List[str] = []
            for rec in records:
                db_ids.add(str(rec["id"]))
                db_contents.append(rec.get("content") or "")

            count_db = len(db_ids)
            if count_db == 0:
                # Seed test nodes deterministically if none exist for 'Coda'
                clear_test_nodes()
                seeded = seed_coda_nodes(count=5)
                if not seeded:
                    pytest.skip("No 'Coda' memories in Neo4j and unable to seed; skip e2e test")
                count_db = len(seeded)

    finally:
        driver.close()

    # 2. Call the /reason endpoint via ECE to get the model's retrieval trace/answer
    fake_llm = os.getenv("ECE_USE_FAKE_LLM", "0") == "1"
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {"session_id": "test_coda_e2e", "question": "What do we know about Coda?", "mode": "graph"}
        response = await client.post(f"{ece_url}/reason", json=payload)
        assert response.status_code == 200, f"ECE /reason call failed: {response.text}"
        result = response.json()

    # Extract generated queries from reasoning_trace
    queries: List[str] = []
    for trace in result.get("reasoning_trace", []):
        if trace.get("type") == "query_generation" and trace.get("query"):
            queries.append(trace.get("query"))

    if fake_llm:
        # With fake LLM we may not have generated queries; assert we got an answer and the fake marker
        assert result.get("answer") is not None, "No answer returned by ECE"
        assert "[fake llm response]" in result.get("answer", "").lower()
        return
    else:
        assert queries, "No generated queries found in reasoning_trace; cannot verify retrieval"

    # 3. Initialize TieredMemory and run search_memories for each query to find what was retrieved
    mem = TieredMemory()
    await mem.initialize()
    try:
        all_retrieved_ids = set()
        all_retrieved_contents = []
        for q in queries:
            # Search by query text - this uses content CONTAINS matching
            results = await mem.search_memories(query_text=q, limit=10)
            for r in results:
                all_retrieved_ids.add(str(r.get("memory_id") or r.get("id")))
                all_retrieved_contents.append(r.get("content"))

        # Basic assertions
        assert all_retrieved_ids, "Model didn't retrieve any memories for generated queries"
        # The number retrieved should be <= DB count
        assert len(all_retrieved_ids) <= count_db, f"Model retrieved {len(all_retrieved_ids)} which is more than DB has ({count_db})"

        # At least one overlap in content words between DB and retrieved contents
        overlap = 0
        db_words = set(' '.join(db_contents).lower().split())
        for c in all_retrieved_contents:
            if any(w for w in c.lower().split() if w in db_words):
                overlap += 1

        assert overlap > 0, "No overlap between DB contents and retrieved content; model may have retrieved unrelated memories"

        # Additionally, confirm answer mentions 'Coda' or relevant content
        answer_text = result.get("answer", "").lower()
        assert 'coda' in answer_text or overlap > 0, "Answer doesn't reference 'Coda' nor overlaps with retrieved content"
    finally:
        await mem.close()
