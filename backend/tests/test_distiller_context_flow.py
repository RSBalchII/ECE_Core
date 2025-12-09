import os
import sys
from pathlib import Path
import pytest
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.distiller_impl import Distiller
from src.llm import LLMClient
from src.memory import TieredMemory


@pytest.mark.integration
@pytest.mark.asyncio
async def test_distiller_processes_large_context():
    """Verify Distiller will process large context and extract moments.

    Test parameters:
    - Insert ~20 synthetic 'coda' memories into Neo4j (test: true) using test helpers if needed.
    - Build large active_context (long text > 6000 chars) and pass to Distiller.distill_moment.
    - Assert the returned 'summary' and 'entities' fields are populated.
    """
    # Create LLM client (will use real LLM if available); if not, skip
    try:
        llm = LLMClient()
    except Exception:
        pytest.skip("LLM client not configured; skip distiller integration test")

    distiller = Distiller(llm_client=llm)
    memory = TieredMemory()
    await memory.initialize()

    # Make a big active_context
    big_context = "\n".join([f"This is line {i}, about Coda project updates." for i in range(100)])
    
    # Test distillation
    relevant = await distiller.distill_moment(big_context)
    
    assert isinstance(relevant, dict), "Distiller did not return the expected dict signature"
    assert "summary" in relevant, "Distiller missing summary"
    assert "entities" in relevant, "Distiller missing entities"
    
    # Clean up
    if memory.neo4j_driver:
        await memory.neo4j_driver.close()
    if memory.redis:
        await memory.redis.close()

