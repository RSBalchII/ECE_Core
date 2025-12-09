# ECE_Core - Technical Specification

## Mission

Build a **personal external memory system** as an assistive cognitive tool using:
- Redis + Neo4j tiered memory (pure graph architecture)
- Markovian reasoning (chunked thinking)
- Graph-R1 reasoning (iterative retrieval)
- Local-first LLM integration (llama.cpp)
- Plugin-based tool system (UTCP - Simple Tool Mode)

**Current**: Neo4j + Redis architecture (SQLite removed)
**Protocol**: Plugin System (migrated from MCP 2025-11-13)
**Tools**: Tools loaded via `PluginManager` from `plugins/` directory:
  - `web_search` - DuckDuckGo search with results
  - `filesystem_read` - File and directory operations
  - `shell_execute` - Shell command execution (with safety checks)
  - `mgrep` - Semantic code & natural language file search (semantic `grep`) - Implemented as a standalone plugin in `plugins/mgrep/`

## Architecture Overview

### Memory Architecture: Neo4j + Redis Tiered System

**Neo4j (port 7687)** - PRIMARY STORAGE
- All memories, summaries, relationships in graph format
- Node types: `(:Memory)`, `(:Event)`, `(:Person)`, `(:Idea)`, `(:Code)`, `(:ContextGist)`
- Relationship types: `[:RELATED_TO]`, `[:MENTIONS]`, `[:CAUSED_BY]`, `[:NEXT_GIST]`
- Full-text search capabilities with Cypher
- Temporal reasoning with creation timestamps

**Redis (port 6379)** - ACTIVE SESSION CACHE
- Hot cache for active conversations (24h TTL)
- Session state management
- Temporary context assembly
- Graceful fallback to Neo4j if unavailable

### Cognitive Architecture: Agent-Based System

**Verifier Agent** - Truth Verification
- **Role**: Fact-checking via Empirical Distrust
- **Method**: Provenance-aware scoring (primary sources > summaries)
- **Goal**: Reduce hallucinations, increase factual accuracy

**Distiller Agent** - Memory Compression & Context Rotation
- **Role**: Memory summarization and compression + Context Rotation Protocol
- **Method**: LLM-assisted distillation with salience scoring + context gist creation
- **Goal**: Maintain high-value context, enable infinite context, prune noise

**Archivist Agent** - Memory Maintenance & Context Management
- **Role**: Knowledge base maintenance, freshness checks + Context Coordination
- **Method**: Scheduled verification, stale node detection, context rotation oversight
- **Goal**: Keep memory graph current and trustworthy, manage context windows

**Memory Weaver** - Automated Relationship Repair
- **Role**: Automated graph relationship repair and optimization
- **Method**: Embedding-based similarity with audit trail (`auto_commit_run_id`)
- **Goal**: Maintain graph integrity with full traceability

### Reasoning Architecture: Graph-R1 + Markovian Reasoning

**Graph-R1 Reasoning Pattern**:
1. **Think** - High-level planning based on question
2. **Generate Query** - Create Cypher query for Neo4j
3. **Retrieve Subgraph** - Fetch relevant memories and relationships  
4. **Rethink** - Plan next iteration based on retrieved context
5. **Repeat** - Iterate until confident or max iterations reached

**Markovian Memory**: Chunked context management for infinite windows
- **Active Context**: Current working memory (in Redis)
- **Gist Memory**: Compressed historical context (in Neo4j as `:ContextGist`)
- **Rotation Protocol**: When active context approaches 55k tokens, compress oldest segments to gists

### Tool Architecture: UTCP Plugin System

**Current Implementation**: Plugin-based UTCP (Simple Tool Mode)
- Discovery via `plugins/` directory
- Safety layers with whitelist/blacklist
- Human confirmation flows for dangerous operations

**Available Tools**:
- `web_search` - DuckDuckGo with result limits
- `filesystem_read` - File operations with path restrictions
- `shell_execute` - Command execution with safety checks
- `mgrep` - Semantic code search with context

## Infinite Context Pipeline

### Phase 1: Hardware Foundation
- **64k Context Windows**: All LLM servers boot with 65,536 token capacity
- **GPU Optimization**: Full layer offload with Q8 quantized KV cache
- **Flash Attention**: Enabled when available for optimal long-context performance

### Phase 2: Context Rotation Protocol
- **Monitoring**: ContextManager monitors total context length
- **Trigger**: When context approaches 55k tokens (safety buffer for 64k window)
- **Compression**: Distiller compresses old segments into "Narrative Gists"
- **Storage**: Gists stored in Neo4j as `(:ContextGist)` nodes with `[:NEXT_GIST]` relationships
- **Rewriting**: New context = `[System Prompt] + [Historical Gists Summary] + [Recent Context] + [New Input]`

### Phase 3: Graph-R1 Enhancement
- **Historical Retrieval**: GraphReasoner includes `:ContextGist` nodes in retrieval
- **Continuity Maintenance**: Reasoning flow maintained across context rotations
- **Temporal Awareness**: Reasoning considers chronological relationships in gists

## API Specification

### Core Endpoints (Port 8000)

**Chat Interface**:
- `POST /chat/stream` - Streaming conversation with full memory context
- Request: `{"session_id": str, "message": str, "stream": bool}`
- Response: Streaming SSE with full context injection

**Memory Operations**:
- `POST /memory/add` - Add memory to Neo4j graph
- `POST /memory/search` - Semantic search with relationships  
- `GET /memory/summaries` - Session summary retrieval
- `POST /archivist/ingest` - Ingest content with distillation

**Health & Info**:
- `GET /health` - Server health check
- `GET /v1/models` - Available models
- `GET /health/memory` - Memory system status

**MCP Integration** (when enabled):
- `GET /mcp/tools` - Available memory tools
- `POST /mcp/call` - Execute memory tools

## Configuration

### Required Parameters (in `.env` or config.yaml)
- `NEO4J_URI` - Neo4j connection URI (default: bolt://localhost:7687)
- `REDIS_URL` - Redis connection URL (default: redis://localhost:6379)
- `LLM_MODEL_PATH` - Path to GGUF model file
- `ECE_HOST` - Host for ECE server (default: 127.0.0.1)
- `ECE_PORT` - Port for ECE server (default: 8000)

### Optional Parameters
- `ECE_REQUIRE_AUTH` - Enable API token authentication (default: false)
- `ECE_API_KEY` - Static API key when auth enabled
- `MCP_ENABLED` - Enable Model Context Protocol integration (default: true)
- `VERIFIER_AGENT_ENABLED` - Enable truth-checking agent (default: true)
- `ARCHIVIST_AGENT_ENABLED` - Enable memory maintenance agent (default: true)
- `DISTILLER_AGENT_ENABLED` - Enable summarization agent (default: true)

## Security

### Authentication
- Optional API token authentication (controlled by `ECE_REQUIRE_AUTH`)
- Session isolation with UUID-based session IDs
- Memory access limited to owner's session

### Authorization
- Path restrictions on filesystem operations
- Command whitelisting for shell execution
- Rate limiting on all endpoints
- Input validation on all parameters

### Data Protection
- All data stored locally by default
- End-to-end encryption for sensitive memories (optional)
- Audit logging for all memory operations
- Traceability for automated repairs and context rotations

## Performance Optimization

### Hardware Recommendations
- **Minimum**: 16GB RAM, CUDA-capable GPU (RTX series)
- **Recommended**: 32GB+ RAM, RTX 4090 or similar
- **Context Windows**: 64k requires ~8GB VRAM for KV cache with 7B-14B models

### Memory Management
- **Hot Cache**: Redis for active session context (24h TTL)
- **Cold Storage**: Neo4j for persistent memories with relationships
- **Context Rotation**: Automatic compression of old context when approaching limits
- **Caching Strategy**: L1 (Redis) for active context, L2 (Neo4j) for historical context

## Integration Points

### With Anchor CLI
- HTTP API communication on configured port (default: 8000)
- Streaming responses via Server-Sent Events
- Memory operations through dedicated endpoints

### With Browser Extension
- HTTP API communication for context injection and memory saving
- Streaming chat interface via Side Panel
- Page content reading and memory ingestion

### With LLM Servers
- OpenAI-compatible API for LLM communication
- Streaming response handling via SSE
- Context window management with rotation protocol