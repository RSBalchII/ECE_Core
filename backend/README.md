# ECE_Core Backend

> **Executive Cognitive Enhancement (ECE)** - Backend component for the Context-Engine

**Philosophy**: Your mind, augmented. Your data, sovereign. Your tools, open.

---

## Architecture: The Brain

The ECE_Core backend is the cognitive engine of the Context-Engine system. It manages the memory system, reasoning engine, and cognitive orchestration.

### Memory Architecture
- **Neo4j** (port 7687) - PRIMARY STORAGE
  - All memories, summaries, relationships in graph format
  - ContextGist nodes for historical compressed context
  - Node types: `(:Memory)`, `(:Event)`, `(:Person)`, `(:Idea)`, `(:Code)`, `(:ContextGist)`
  - Relationship types: `[:RELATED_TO]`, `[:MENTIONS]`, `[:CAUSED_BY]`, `[:NEXT_GIST]`
- **Redis** (port 6379) - ACTIVE SESSION CACHE
  - Hot cache for active conversations (24h TTL)
  - Graceful fallback to Neo4j if unavailable

### Cognitive Architecture
- **Verifier Agent**: Truth-checking via Empirical Distrust
- **Distiller Agent**: Memory summarization, compression + Context Rotation Protocol
- **Archivist Agent**: Knowledge base maintenance and freshness + Context Continuity
- **Memory Weaver**: Automated relationship repair with full traceability

### Reasoning Architecture
- **Graph-R1 Reasoning Pattern**: "Think → Query → Retrieve → Rethink" iteration
- **Markovian Reasoner**: Infinite-length task handling with state preservation
- **Hybrid Retrieval**: Vector + Graph + Full-text search with ContextGist integration

---

## Quick Start

### Installation
```bash
cd backend
pip install -e .
```

### Configuration
- **Primary Config**: `backend/.env` (from `.env.example`)
- **LLM Settings**: Context size, GPU layers, model path
- **Memory Settings**: Redis/Neo4j connection strings
- **Agent Settings**: Enable/disable Verifier, Archivist, Distiller

### Run Server
```bash
# Start ECE_Core server
python launcher.py
# Server runs on http://localhost:8000
```

---

## Key Features

### ✅ Infinite Context Pipeline
- **64k Context Windows**: All servers configured with 65,536 token capacity
- **Context Rotation Protocol**: Automatic rotation when context approaches 55k tokens
- **Intelligent Distillation**: Old context compressed to "Narrative Gists" using Distiller agent
- **Historical Continuity**: ContextGist nodes maintain reasoning across rotations

### ✅ Cognitive Agents
- **Truth Verification**: Provenance-aware fact-checking
- **Memory Hygiene**: Automatic summarization and maintenance
- **Relationship Repair**: Automated graph integrity maintenance with audit trail

### ✅ Tool Architecture
- **Plugin System**: UTCP-based tool system in `plugins/` directory
- **Safety Layers**: Whitelist/blacklist with human confirmation for dangerous operations
- **MCP Integration**: Memory tools via integrated MCP endpoints

---

## Development

### Run Tests
```bash
python -m pytest tests/
```

### Package Distribution
```bash
python -m build
```

---

## Documentation

- `specs/spec.md` - Technical architecture and design
- `specs/plan.md` - Vision, roadmap, and strategic priorities
- `specs/tasks.md` - Implementation backlog and current tasks
- `specs/TROUBLESHOOTING.md` - Operational debugging and error resolution

---

## Research Foundation

- **Graph-R1**: Memory retrieval patterns with iterative graph traversal
- **Markovian Reasoning**: Chunked thinking with state preservation
- **Hierarchical Reasoning Model (HRM)**: Multi-level context processing
- **Empirical Distrust**: Primary source supremacy for verification

---

## Target Users

- **Cognitive Enhancement**: Users needing personal external memory systems
- **Privacy-Conscious**: Users wanting 100% local, zero-telemetry systems
- **AI Developers**: Users needing extensible, memory-enhanced workflows

---

## Acknowledgments

Built for the cognitive architecture that bridges human and machine intelligence.

**"Your data, sovereign. Your tools, open. Your mind, augmented."**

---

## Need Help?

- **Architecture Questions**: See `specs/spec.md`
- **Vision & Roadmap**: See `specs/plan.md`
- **Current Tasks**: See `specs/tasks.md`
- **Troubleshooting**: See `specs/TROUBLESHOOTING.md`