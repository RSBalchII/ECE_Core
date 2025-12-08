# Context-Engine

> **Executive Cognitive Enhancement (ECE)** - A local-first memory system and agentic toolkit for cognitive augmentation.

**Philosophy**: Your mind, augmented. Your data, sovereign. Your tools, open.

---

## Architecture: Two Components, One System

Context-Engine consists of two primary components working in harmony:

### 🧠 **The Core** - The Brain
**Role**: Memory system, reasoning engine, and cognitive orchestration
**Location**: `backend/`

- **Memory Architecture**: Neo4j (primary graph storage) + Redis (hot cache)
- **Cognitive Agents**: Verifier (truth-checking), Archivist (maintenance), Distiller (summarization)
- **Retrieval**: Graph-R1 + Markovian reasoning for context-aware memory recall
- **Tool Integration**: Plugin-based architecture via UTCP (Simple Tool Mode)
- **API**: FastAPI server on port 8000

**Key Features**:
- ✅ Graph-based memory with relationship traversal
- ✅ Empirical Distrust verification (primary source supremacy)
- ✅ Automatic memory distillation and summarization
- ✅ Traceability & rollback for automated repairs
- ✅ Circuit breakers and graceful degradation

### 🤖 **Anchor** - The Body
**Role**: Terminal interface and interaction layer
**Location**: `anchor/`

- **Interface**: Lightweight CLI with streaming responses
- **Integration**: Connects to ECE_Core API for memory-enhanced conversations
- **Tool Execution**: Pattern-based tool mode for small models (4B-8B)
- **Deployment**: Can be packaged as standalone executable

**Key Features**:
- ✅ Real-time streaming responses
- ✅ Memory-enhanced conversations
- ✅ Simple tool mode for reliable tool execution
- ✅ Security hardening (whitelist, confirmation flows)

### 🌉 **Extension** - The Bridge
**Role**: Browser integration and active context injection
**Location**: `extension/`

- **Interface**: Chrome Side Panel with persistent chat
- **Integration**: Connects to ECE_Core API for context-aware browsing
- **Ingestion**: "Save to Memory" capability to archive web content and chat transcripts directly to the knowledge graph.
- **Capabilities**:
  - 👁️ **Sight**: Reads active page content on demand
  - 🗣️ **Voice**: Streaming chat interface
  - ✋ **Hands**: Executes JavaScript actions on the page

---

## Data Flow

```
User Input (Anchor CLI / Extension)
    ↓
ECE_Core API (:8000)
    ↓
├─ Redis: Check active session cache
├─ Neo4j: Graph traversal + semantic search
└─ LLM: Generate response with full context
    ↓
Cognitive Agents (optional)
├─ Verifier: Fact-check via Empirical Distrust
├─ Distiller: Summarize and extract entities
└─ Archivist: Maintain freshness, schedule repairs
    ↓
Response → Anchor → User
```

---

## Memory Architecture

### Current (Production)
- **Neo4j** (port 7687) - PRIMARY STORAGE
  - All memories, summaries, relationships
  - Graph-based retrieval with Q-Learning optimization
- **Redis** (port 6379) - ACTIVE SESSION CACHE
  - Hot cache for active conversations (24h TTL)
  - Graceful fallback to Neo4j if unavailable

### Deprecated
- ~~**SQLite**~~ - Fully removed 2025-11-13, migrated to Neo4j

---

## Quick Start

### Prerequisites
- Python 3.11+
- Neo4j database (local or remote)
- Redis server (optional, but recommended)
- llama.cpp server (will be started by our scripts)

### Clean Architecture - 3 Main Scripts
This project now uses a simplified 3-script architecture:

1. **`python start_llm_server.py`** - Interactive LLM server with model selection
2. **`python start_ece.py`** - ECE Core with integrated MCP memory system  
3. **`python start_embedding_server.py`** - Auto-selects gemma-300m embedding server

### Three-Terminal Startup

**Terminal 1 - LLM Server:**
```bash
python start_llm_server.py  # Interactive model selection
```

**Terminal 2 - ECE_Core (The Brain):**
```bash
python start_ece.py  # Includes MCP endpoints at port 8000
```

**Terminal 3 - Embedding Server (optional):**
```bash
python start_embedding_server.py  # Auto-selects gemma-300m
```

### Quick Reka Configuration
For Reka Flash 3 21B optimized settings:
```bash
start-reka.bat  # Starts all services with RTX 4090 optimized parameters
```

### Alternative: All-in-one Safe Startup

To start all services with conservative defaults using the new Python architecture:
```bash
python start_all_safe.py  # Python version (recommended)
# OR
start_all_safe_simple.bat  # Batch wrapper
```

### Health Checks
```bash
# Verify LLM
curl http://localhost:8080/v1/models

# Verify ECE_Core
curl http://localhost:8000/health
```

### Troubleshooting: Proxy & Missing Dependencies

If your `start-openai-stream-proxy.*` script returns an error such as:

```
ModuleNotFoundError: No module named 'sse_starlette'
```

then your Python environment is missing the `sse-starlette` package. The proxy requires `sse-starlette` for SSE support and `uvicorn` to run.

Quick fix (Windows PowerShell):
```pwsh
cd C:\Users\rsbiiw\Projects\Context-Engine\ece-core
.\.venv\Scripts\Activate  # Or whichever venv you use
pip install -r requirements.txt
```

Quick fix (Unix/macOS):
```bash
cd /path/to/Context-Engine\ece-core
source .venv/bin/activate
pip install -r requirements.txt
```

After installing dependencies, re-run the proxy script or the `start-all-safe.*` wrapper.

If you see "The filename, directory name, or volume label syntax is incorrect.", ensure you're running the start script from the repo root and that there are no stray quotes or illegal characters in your path. The wrapper assumes `start-openai-stream-proxy.*` will be run from the repo root (so `%~dp0` works as expected).

## All-in-one Safe Startup (recommended for devs)

To start all core services in a single command using conservative defaults that reduce OOMs and contention, use the safe startup scripts.

This wrapper starts (in order):
- LLaMa safe server (lower ubatch & single parallel-slot)
- LLaMa embedding server (optional)
- LLM Server with Reka-optimized settings
- ECE Core with MCP enabled
- MCP server (integrated into ECE Core when enabled)

Usage:
```bash
# Windows (Python version - recommended)
python start_all_safe.py

# Windows (Batch wrapper)
start_all_safe_simple.bat

# Windows (Reka-optimized)
start-reka.bat
```

The scripts perform basic health checks and will wait for LLaMa and ECE Core to be reachable before starting dependent components.

## Configuration

### ECE_Core Configuration
- **Primary config**: `ece-core/.env` (from `.env.example`)
- **LLM settings**: Context size, GPU layers, model path
- **Memory settings**: Redis/Neo4j connection strings
- **Agent settings**: Enable/disable Verifier, Archivist, Distiller

### Anchor Configuration
- **Primary config**: `anchor/.env` (from `.env.example`)
- **ECE connection**: `ECE_URL=http://localhost:8000`
- **Tool settings**: `PLUGINS_ENABLED=true` to enable tools

---

## Documentation

### Core Specs (Single Source of Truth)
- `ece-core/specs/spec.md` - Technical architecture
- `ece-core/specs/plan.md` - Vision, roadmap, ADRs
- `ece-core/specs/tasks.md` - Implementation backlog
- `ece-core/specs/TROUBLESHOOTING.md` - Operational debugging

### Supplementary
- `ece-core/README.md` - ECE_Core quick start
- `anchor/README.md` - Anchor quick start
- `ece-core/CHANGELOG.md` - Complete project history
- `ece-core/archive/README.md` - Archived code explanation

---

## Tool Architecture

**Current**: Plugin-based UTCP (Simple Tool Mode) and MCP Integration

Tools are discovered via multiple methods:
- **Plugin-based UTCP**: `ece-core/plugins/` directory
  - `web_search` - DuckDuckGo search
  - `filesystem_read` - File and directory operations
  - `shell_execute` - Shell command execution (with safety checks)
  - `mgrep` - Semantic code search
- **MCP Integration**: Memory tools via `/mcp` endpoints
  - `add_memory` - Add to Neo4j memory graph
  - `search_memories` - Search memory graph with relationships
  - `get_summaries` - Get session summaries

**Note**: MCP (Model Context Protocol) is now integrated into the main ECE server when `mcp.enabled: true` in config.

---

## Cognitive Architecture: Agents

ECE_Core implements an agent-based architecture for memory hygiene and cognitive enhancement:

### Verifier Agent
- **Role**: Truth-checking via Empirical Distrust
- **Method**: Provenance-aware scoring (primary sources > summaries)
- **Goal**: Reduce hallucinations, increase factual accuracy

### Distiller Agent
- **Role**: Memory summarization and compression
- **Method**: LLM-assisted distillation with salience scoring
- **Goal**: Maintain high-value context, prune noise

### Archivist Agent
- **Role**: Knowledge base maintenance and freshness
- **Method**: Scheduled verification, stale node detection
- **Goal**: Keep memory graph current and trustworthy

### Memory Weaver (Maintenance Engine)
- **Role**: Automated relationship repair
- **Method**: Embedding-based similarity with audit trail
- **Goal**: Maintain graph integrity with full traceability

---

## Small Model Considerations

**Tool Usage**:
- ⚠️ Models < 14B parameters are **unreliable** for structured tool protocols
- ✅ Use "Simple Tool Mode" (pattern-based execution) for 4B-8B models
- ✅ Use 14B+ models (DeepSeek-R1, Qwen2.5-14B) for full tool support
- ✅ MCP Integration works with any model for memory operations

**Recommended Models**:
- **Gemma-3 4B** - Best for speed (chat only, tools unreliable)
- **Qwen3-8B** - Best for reasoning (Simple Tool Mode works)
- **DeepSeek-R1-14B** - Best for tools (full structured protocol support)
- **Reka Flash 3 21B** - Best for reasoning (use start-reka.bat)

---

## Development

### Install Dependencies
```bash
# ECE_Core
cd ece-core
pip install -e .

# Anchor
cd anchor
pip install -e .
```

### Run Tests
```bash
# ECE_Core tests
cd ece-core
python -m pytest tests/

# Anchor tests
cd anchor
python -m pytest tests/
```

### Package Distribution
```bash
# ECE_Core wheel
cd ece-core
python -m build

# Anchor standalone executable
cd anchor
pyinstaller anchor.spec
```

---

## Project Status

**Current Phase**: Cognitive Refinement (Phase 4)
**Version**: ECE_Core 1.0.0, Anchor 0.1.0-alpha
**Last Updated**: 2025-11-30

### ✅ Completed
- Neo4j + Redis architecture (SQLite removed)
- Plugin-based tool system (UTCP)
- MCP integration into main ECE server
- Cognitive agents (Verifier, Archivist, Distiller)
- Traceability & rollback for automated repairs
- Security hardening (API auth, audit logs)
- PyInstaller packaging

### 🔄 In Progress
- Vector adapter + C2C hot-replica for semantic retrieval
- Compressed summaries + passage recall (EC-T-133)
- SLM benchmarking and ALScore measurements

### 📅 Planned
- CLI wrapper for script operations (`ece-cli`)
- Increase test coverage to 80%+
- Developer onboarding (`docker-compose.dev.yaml`)

---

## Target Users

### Primary: Developers with Executive Function Challenges
**Pain Points**: Memory decay, context switching, project knowledge retention
**Solution**: Persistent external memory with automatic retrieval

### Secondary: Privacy-Conscious Developers
**Pain Points**: Cloud dependency, data sovereignty, vendor lock-in
**Solution**: 100% local, zero telemetry, your data stays yours

### Tertiary: AI Power Users
**Pain Points**: Need long-term memory, tool integration, customization
**Solution**: Memory-enhanced workflows, extensible architecture, open source

---

## Research Foundation

- **Graph-R1**: Memory retrieval patterns (https://arxiv.org/abs/2507.21892)
- **Markovian Reasoning**: Chunked thinking (https://arxiv.org/abs/2506.21734)
- **Hierarchical Reasoning Model (HRM)**: Multi-level context processing
- **Empirical Distrust**: Primary source supremacy for verification

See `ece-core/specs/references.md` for complete bibliography.

---

## License

MIT - Use, modify, and distribute freely.

---

## Acknowledgments

Built for neurodivergent hackers who need their tools to work reliably.

**"Your mind, augmented. Your data, sovereign. Your tools, open."**

---

## Need Help?

- **Operational Issues**: See `ece-core/specs/TROUBLESHOOTING.md`
- **Architecture Questions**: See `ece-core/specs/spec.md`
- **Implementation Tasks**: See `ece-core/specs/tasks.md`
- **Project History**: See `ece-core/CHANGELOG.md`