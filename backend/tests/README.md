# ARCHIVED: This README was moved to `archive/docs_removed/tests/README.md` during documentation consolidation.

**Purpose**: Validate system components with isolated, type-safe, clean output.

**Philosophy**: 
- Each component tested in isolation
- Type safety enforced
- Clean, readable output
- No side effects between tests
- Code reduction where possible

---

## Optional Integration Services (Docker)

This repository provides a small `docker-compose.test.yml` that will start Redis and Neo4j for running integration tests locally or in CI.

Environment variable `ECE_USE_DOCKER` controls this behavior (default 1):
- `ECE_USE_DOCKER=1` — Start Redis+Neo4j automatically for the test session using Docker.
- `ECE_USE_DOCKER=0` — Skip starting Docker (useful if you already have Redis/Neo4j running).

Make sure Docker is installed and available in the PATH before enabling this option.

LLM testing without an API server
--------------------------------
If you want to run LLM-related tests without a real LLM or Ollama server running, you can enable the fake LLM test server that returns deterministic replies:
- Set environment variable: `ECE_USE_FAKE_LLM=1` (default is 0)
- The fake server listens on `http://127.0.0.1:8080` and responds to `/v1/chat/completions`.
This can be combined with `ECE_USE_DOCKER=1` for a full integration stack.

Local integration testing (PowerShell)
-------------------------------
1. Make sure Docker desktop is running
2. From project root run:
  $env:ECE_USE_DOCKER = '1'
  cd ECE_Core
  pytest -q --maxfail=1

Or use the helper script:
  cd ECE_Core\tests
  ./run_integration_tests.ps1

CI note
-------
The GitHub Actions workflow `integration-tests.yml` starts the compose stack and runs `pytest` in the `ECE_Core` folder. The workflow runs on push/PR.

Testing Neo4j end-to-end without the full server/runtime
-------------------------------------------------------
If you only want to drive a Neo4j-backed test (no ECE server/exe required):
1. Start only Neo4j with the compose file:
  docker compose -f ECE_Core/docker-compose.test.yml up -d neo4j
2. Export the host info (defaults used by our tests):
  $env:NEO4J_URI = 'bolt://localhost:7687'
3. Run only the Neo4j E2E test:
  $env:PYTHONPATH = 'c:\Users\rsbiiw\Projects\ECE_Core'
  pytest -q tests/test_neo4j_e2e.py -q

TieredMemory E2E tests
----------------------
The repo includes tests that use the `TieredMemory` API (Python-level interface) that exercises the Neo4j-backed memory flow (`add_memory`, `search_memories`).
1. Start Neo4j: `docker compose -f ECE_Core/docker-compose.test.yml up -d neo4j`
2. Run the TieredMemory tests:
  $env:ECE_USE_DOCKER = '1'
  $env:PYTHONPATH = 'c:\Users\rsbiiw\Projects\ECE_Core'
  pytest -q tests/test_tieredmemory_neo4j.py -q

Notes:
- Tests are safe to run in CI with `ECE_USE_DOCKER=1` set.
- If you want to test against a running Neo4j instance (not the compose one), set `NEO4J_URI` to the running Bolt URI and ensure it's reachable.


For testing guidelines and the active test documentation, see `specs/TROUBLESHOOTING.md` and the `tests/` folder for the current instructions and examples.

### Core Components (`test_core_*.py`)
-- `test_core_memory.py` - Memory system (Redis + Neo4j)
- `test_core_llm.py` - LLM client and communication
- `test_core_context.py` - Context manager assembly
- `test_core_config.py` - Configuration loading and validation

### Retrieval Components (`test_retrieval_*.py`)
- `test_retrieval_markov.py` - Markovian reasoning
- `test_retrieval_graph.py` - Graph reasoning
- `test_retrieval_integration.py` - Combined retrieval strategies

### UTCP Integration (`test_utcp_*.py`)
- `test_utcp_client.py` - UTCP client import & discovery
- `test_utcp_plugin_manager.py` - UTCP plugin manager & tools
- `test_utcp_llm_integration.py` - End-to-end UTCP flow

### System Tests (`test_system_*.py`)
- `test_system_startup.py` - Launcher and initialization
- `test_system_endpoints.py` - FastAPI endpoints
- `test_system_integration.py` - Full system flow

---

## Running Tests

```bash
# All tests
python -m pytest tests/

# Specific component
python tests/test_core_memory.py

# With verbose output
python -m pytest tests/ -v

# Coverage report
python -m pytest tests/ --cov=. --cov-report=html
```

---

## Test Output Standards

Each test provides:
1. ✅ **Pass/Fail Status** - Clear visual indicator
2. 📊 **Metrics** - Performance, token counts, timing
3. 🔍 **Isolated Results** - No cross-contamination
4. 📝 **Type Validation** - All returns match expectations
5. 🧹 **Cleanup** - Resources released, connections closed

Example output:
```
Testing: memory.search_memories_neo4j()
  ✅ Neo4j connection established
  ✅ Query executed: 'test query'
  ✅ Returns List[Dict[str, Any]]
  📊 Results: 5 memories in 45ms
  🔍 Type validation: PASS
  🧹 Cleanup: COMPLETE
```

---

## Current Test Files

**Core Tests:**
- `test_chunker.py` - IntelligentChunker validation
- `test_distiller.py` - Distiller filtering & summarization

**Retrieval Tests:**
- `test_graphr1.py` - Graph-R1 reasoning
- `test_retrieval_debug.py` - Retrieval debugging

**System Tests:**
- `test_comprehensive_validation.py` - Full system check
- `test_end_to_end.py` - Complete flow validation
- `test_neo4j_embedded.py` - Neo4j server startup

**Memory Tests:**
- `test_memory_recall.py` - Memory retrieval accuracy
- `test_entity_flow.py` - Entity extraction flow

**Integration Tests:**
- `test_utcp_improvements.py` - UTCP (legacy)
- `test_model_detection.py` - LLM model detection

---

## Adding New Tests

Template:
```python
"""
Test: <Component Name>
Purpose: <What this validates>
Dependencies: <What needs to be running>
"""
import asyncio
from typing import Any, Dict, List

async def test_<component>() -> bool:
    \"\"\"Test <component> functionality.\"\"\"
    print(f"Testing: <component>")
    
    # Setup
    # ... initialize component ...
    
    # Test
    result = await component.method()
    
    # Validate types
    assert isinstance(result, expected_type), f"Type mismatch: {type(result)}"
    
    # Validate behavior
    assert result.condition, "Behavior validation failed"
    
    # Cleanup
    await component.close()
    
    print("  ✅ Test PASSED")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_<component>())
    exit(0 if success else 1)
```

---

## Test Coverage Goals

- [ ] **Core**: 100% of public methods
- [ ] **Retrieval**: All reasoning strategies
- [ ] **MCP**: All tool calls
-- [ ] **Memory**: Neo4j + Redis

## Test data and seeding (new)
When tests require DB-backed content, we follow a seeded, deterministic model:
- Use `tests/helpers.py` for seeding/cleanup. Functions:
  - `seed_coda_nodes(count=5)` — seed deterministic Coda nodes tagged `test: true`.
  - `clear_test_nodes()` — remove test nodes created with `test: true` flag.
- Tests that rely on seeded data should declare in their docstring:
  - Count of seeded nodes
  - Query text used
  - Expected number of retrieved records or behaviors

### Example: E2E Coda test
- Docstring explains seeding behavior (5 nodes) and the endpoint/mode used.
- Test ensures retrieved count <= DB count and at least one overlapping content token.

### Best practices
- Tests must cleanup seeded nodes or rely on `clear_test_nodes()` to remove test data.
- Document seeds in the test docstring; prefer `test=true` tags to remove tests easily.

## Neo4j migration & types

If your Neo4j instance contains Memory nodes with `tags` stored as JSON strings (legacy import), the tag-list search `ANY(t in m.tags WHERE t IN $tags)` won't match them. Run the `scripts/neo4j_fix_tags_metadata.py` script to detect/convert these properties into native lists or maps.

Example:
```powershell
# Dry run
python scripts/neo4j_fix_tags_metadata.py --dry-run

# Apply the changes
python scripts/neo4j_fix_tags_metadata.py --apply
```

When running tests with `ECE_USE_FAKE_LLM=1`, tests that depend on LLM behaviour will use the deterministic fake LLM server and assertions are adapted accordingly. Use this mode to make CI runs deterministic and remove a dependency on having a live LLM service.

## Distiller & Context Flow (POML -> Context Cache -> User prompt)
The expected runtime flow is:
1. Immutable system prompt (server-side POML) is prepended to the prompt
2. The Distiller reads incoming context (Redis active context) and Neo4j
3. The Distiller decides to either summarize or include blocks of text
   to fit Redis's context size limits; it writes summaries back for future use
4. The user's message is appended and sent to the LLM

Integration tests should confirm this flow by:
- Verifying an initial POML is present in the request pipeline
- Setting a long active context in Redis, adding many Neo4j memories, and
  asserting Distiller returns summarized context (via `distiller.filter_and_consolidate`)
- For API-level tests, seed the context and call `/reason` or `/chat` and examine the reasoning trace
  (or check saved summaries) to see if Archivist consolidated inputs

- [ ] **System**: Startup, shutdown, error handling

---

## Philosophy: Code Reduction

If tests reveal duplicate code:
1. Extract to utility functions
2. Update documentation
3. Remove redundancy
4. Re-test to ensure no regression
