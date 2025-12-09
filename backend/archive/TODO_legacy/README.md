# TODO - Future Features

Components moved here until text-based MVP is working and validated.

## ✅ COMPLETED: Embedded Neo4j

**Status:** Working! Neo4j now runs embedded in ECE_Core launcher.
- Launches as subprocess alongside Redis
- Auto-configures with auth disabled for local use
- Uses External-Context-Engine-ECE's Neo4j installation
- Ready for enhanced graph queries and Q-Learning integration

**Next steps:**
1. Enhance Neo4j-based memory retrieval with Q-Learning (see qlearning_retriever.py)
2. Implement advanced graph queries in memory.py
3. Optimize Redis ↔ Neo4j synchronization patterns

---

## Not Needed Yet

**qlearning_retriever.py** - Neo4j graph navigation with Q-Learning
- **Why moved:** Requires Neo4j to be set up ✅ **NOW READY TO USE**
- **When to add:** After Neo4j graph is built + basic graph retrieval works
- **Blocker:** ~~Neo4j not yet implemented~~ **DONE - Neo4j embedded and tested**

**graph_reasoner.py** - GraphR1 think-retrieve-rethink loop
- **Why moved:** Advanced reasoning, need basic retrieval working first
- **When to add:** After simple retrieval proves insufficient
- **Blocker:** No evidence yet that simple search fails

**distiller.py** - Intelligent context compression (formerly archivist)
- **Why moved:** Not wired into context_manager, unclear if needed
- **When to add:** When context window becomes actual problem (test first)
- **Blocker:** Haven't hit context limits yet

**extract_entities.py** - LLM-based entity extraction to Neo4j
- **Why moved:** Requires Neo4j setup + LLM overhead
- **When to add:** After basic Neo4j graph is built
- **Blocker:** Neo4j not yet set up

**import_combined_context.py** - Legacy Markovian import approach
- **Why moved:** Complex, not needed (import_turns.py works)
- **When to add:** Probably never (replaced by import_turns.py)
- **Blocker:** Redundant with current import flow

## The Decision Process

Before moving ANY file back from TODO/:

1. **Test Neo4j retrieval** - Are there gaps in current graph-based search?
2. **Collect data** - What's the actual pain point?
3. **Measure need** - Is this feature worth the complexity?
4. **One at a time** - Move back ONE feature, test, validate

## Learning Value

These files aren't wasted:
- ✅ You learned Q-Learning implementation
- ✅ You learned Neo4j schema design
- ✅ You learned GraphR1 architecture
- ✅ You learned agent patterns

The code is here when you need it. But MVP doesn't need it yet.
