# Context-Engine Changelog

## [Unreleased]

### Added
- **CozoDB Corruption Recovery**: Enhanced error handling for IndexedDB corruption with automatic fallback to in-memory database, manual recovery button, and timeout protection against hanging WASM calls.
- **Bulk CozoDB Import Tool**: Added `tools/prepare_cozo_import.py` to transform `combined_memory.json` into the canonical `relations` payload (`cozo_import_memory.json`) for atomic bulk imports into CozoDB.
- **Import Safety & Verification**: Added recommended import procedure and a post-import verification + backup step to avoid Schema Detachment.

### Changed
- **Ingestion Defaults**: Recommended batch size increased to 100 to prevent long-running slow writes that can desync CozoDB's in-memory metadata.

---

## [1.2.3] - 2025-12-19 "Snapdragon Optimization"

### Added
- **Qwen3 Support**: Added `Qwen3-4B-Instruct` to the verified model list.
- **Llama 3.2 Support**: Added `Llama-3.2-1B-Instruct` as the recommended lightweight model.
- **Buffer Override**: Implemented `appConfig` overrides to force high-end performance on 256MB GPUs (fixing Adreno throttling).

### Changed
- **Portable Launchers**: All scripts now use `--user-data-dir="%~dp0browser_data"` for fully portable, clean-running instances.
- **Model Config**: Refactored `CreateMLCEngine` initialization to handle both URL-based and ID-based model definitions reliably.

---

## [1.2.2] - 2025-12-18 "Hermes & CozoDB Fixes"

### Fixed
- **Hermes Model Support**: Fixed 404 errors for OpenHermes and NeuralHermes by mapping them to the verified `Mistral-v0.3` WASM library.
- **CozoDB Date Formatting**: Removed `strftime` dependency from WASM queries (causing `no_implementation` errors) and moved date formatting to client-side JavaScript.
- **Drag-and-Drop Import**: Fixed handling of CozoDB `relations` export format in drag-and-drop ingestion.
- **Documentation**: Established `specs/mlc-urls.md` as a registry for verified WASM binaries.

---

## [1.2.1] - 2025-12-15 "DeepSeek & CozoDB Stabilization"

### Fixed
- **CozoDB Initialization**: Resolved `CozoDb.new_from_path is not a function` error by switching to `CozoDb.new_from_indexed_db` for persistent browser storage (IndexedDB backend).
- **WASM Memory Access**: Fixed "memory access out of bounds" error in `sovereign-db-builder.html` and `unified-coda.html` by correctly stringifying JSON parameters passed to `db.run()`.
- **DeepSeek Configuration**: Fixed "Cannot find model record" error in `unified-coda.html` by decoupling the internal model ID from the HuggingFace URL.

### Added
- **Sovereign Hub**: Created `tools/index.html` as a central dashboard for the Console, Builder, and Log Viewer.
- **Log Viewer Upgrade**: Refactored `tools/log-viewer.html` to use `BroadcastChannel` for real-time, polling-free log updates from the console.
- **Expanded File Support**: Updated `sovereign-db-builder.html` to support ingestion of a wider range of code and config files (ts, rs, go, sql, ini, xml, etc.).

## [1.2.0] - 2025-12-15 "Sovereign Architecture"

### Added
- **Sovereign Console**: Created `tools/unified-coda.html`, a standalone WASM-based chat console with local CozoDB (OPFS) and Transformers.js.
- **Sovereign DB Builder**: Created `tools/sovereign-db-builder.html` for ingesting JSON logs into the browser-based database.
- **Model Support**: Expanded `unified-coda.html` to support the full range of MLC-compatible models (Llama 3.2, Qwen 2.5, Gemma 2, etc.).

### Changed
- **Log Management**: Updated backend logging to truncate files at 500KB to prevent disk bloat.

## [1.1.0] - 2025-12-14 "Browser Stability & Bridge Fixes"

### Fixed
- **WebGPU Bridge**: Patched `tools/webgpu_bridge.py` to accept any model name, resolving 503 errors during embedding requests.
- **LLM Client**: Updated `backend/src/llm.py` to correctly identify and use the configured embedding model (`nomic-embed-text-v1.5`).
- **Coda Chat**: Modified `backend/src/recipes/coda_chat.py` to sanitize and truncate `retrieve_memory` outputs. Large JSON payloads were causing `Maximum call stack size exceeded` errors in the browser-based LLM worker.

## [1.0.0] - 2025-12-08 "Infinite Context Pipeline"

### Added
- **Phase 1: Hardware Foundation**: All LLM servers now boot with 65,536 context window and Flash Attention enabled
- **Phase 2: Context Rotation Protocol**: ContextManager automatically rotates context when exceeding 55k tokens
- **Phase 3: Graph-R1 Enhancement**: GraphReasoner now retrieves ContextGist memories for historical continuity
- **ContextGist Nodes**: Neo4j storage for compressed historical context summaries with chronological links
- **Context Shifting Logic**: Intelligent distillation of old content using Distiller agent with gist creation
- **Documentation Structure**: Organized specs/ directories at root, backend, and anchor levels with spec.md, plan.md, tasks.md
- **Infinite Context Pipeline**: Complete end-to-end implementation enabling unlimited context window management

### Changed
- **Upgraded Context Windows**: All start scripts now default to 64k context for infinite work capability
- **Enhanced Memory Architecture**: Neo4j now stores both active memories and ContextGist historical summaries
- **Improved ContextManager**: Added check_and_rotate_context() logic with automatic gist creation and storage
- **Extended GraphReasoner**: Updated retrieval queries to include ContextGist nodes alongside regular memories
- **Optimized Distiller Integration**: Enhanced _chunk_and_distill functionality for context rotation use cases
- **Refined Archivist Agent**: Now coordinates context rotation and gist management operations

### Fixed
- **Context Limit Elimination**: Fixed issue where systems would crash when reaching context limits
- **Memory Continuity**: Resolved problems with historical context access across conversation boundaries
- **Performance Optimization**: Fixed inefficiencies in large context handling with 64k window support
- **Rotation Logic**: Fixed issues with context preservation during rotation cycles

---

## [0.9.0] - 2025-12-07 "Reka & Local Proxy"

### Added
- **Reka Configuration**: Full support for Reka-Flash-3-21B (Q4_K_S) with 16k context, stop tokens, and optimized LLaMa server flags.
- **Local API Proxy**: Added `scripts/local_api_proxy.py` to enforce static API keys for local LLaMa instances (fixes Cline extension "OpenAI API Key" requirement).
- **VS Code Integration**: Added `.vscode/settings.json` template and `VSCODE_CLINE_SETUP.md` for seamless local development.
- **MCP Health**: Added `/health` endpoint to Unified Launcher for better compatibility.

### Fixed
- **MCP Routing**: Resolved duplicate `/mcp` prefix in Unified Launcher routes (`/mcp/tools` is now accessible).
- **LLM Client**: Added `stop` token support to API payloads and local GGUF generation.

## [0.8.0] - 2025-12-06 "Archivist Protocol"

### Added
- **Archivist Ingestion**: Implemented `POST /archivist/ingest` endpoint to accept live data from the browser.
- **Memory Schema**: Enforced **Directive INJ-A1** (`PlaintextMemory`) for immutable "Page-Store" records.
- **Modular DOM Adapters**:
    - `GeminiAdapter`: Clean extraction for Google Gemini.
    - `ChatGPTAdapter`: Clean extraction for ChatGPT.
    - `ClaudeAdapter`: Clean extraction for Claude.ai.
    - `GenericAdapter`: Universal fallback for any webpage.
- **Extension UI**: Added **[Save to Memory]** button to the Side Panel for manual ingestion.

### Fixed
- **Encoding Crash**: Resolved Windows `charmap` error by enforcing `PYTHONIOENCODING='utf-8'`.
- **Server Stability**: Fixed startup crashes caused by `MemoryWeaver` resource contention.

## [0.7.0] - 2025-12-06 "Operation Concrete"

### Added
- **Browser Bridge**: A Chrome Extension (MV3) capable of:
    - **Voice**: Streaming chat interface via Side Panel.
    - **Sight**: Context injection (reading active tab).
    - **Hands**: JavaScript execution on active pages (User-ratified).
- **Backend Architecture**: Migrated from monolithic scripts to **Modular Recipes** (MAX Agentic Cookbook standard).
    - `CodaChatRecipe`: Handles orchestration, context, and tool execution.
- **Persistence**: Side panel now saves chat history to local storage.
- **Markdown Support**: Chat interface renders code blocks and syntax highlighting.

### Changed
- **Identity**: System formally renamed from "Sybil" to **"Coda"**.
- **Documentation**: Adopted `specs/` based documentation policy.

### Fixed
- **Audit Logger**: Patched critical `NameError` in streaming endpoints.
- **Security**: Hardened extension execution via `world: "MAIN"` to bypass strict CSP on some sites.

---

## [0.6.0] - 2025-11-30 "Operation MCP Integrated"

### Added
- **MCP Integration**: Complete integration of MCP server into main ECE Core server
- **Unified Endpoint**: All MCP functionality now available at `/mcp` on main server (port 8000)
- **Memory Tools**: Enhanced MCP tools for memory operations:
    - `add_memory` - Add to Neo4j memory graph
    - `search_memories` - Search memory graph with relationships
    - `get_summaries` - Get session summaries
- **Configuration**: New `mcp_enabled` setting in config.yaml to toggle integration
- **Authentication**: MCP endpoints now inherit main server authentication settings

### Changed
- **Architecture**: MCP server no longer runs as separate process, now integrated into main ECE server
- **Endpoints**: MCP tools now accessed via `/mcp/tools` and `/mcp/call` instead of separate server
- **Deployment**: Simplified deployment - no need to start separate MCP service
- **Resources**: Reduced memory footprint by eliminating duplicate server processes

### Fixed
- **Connection Issues**: Resolved intermittent connection failures between ECE and external MCP server
- **Latency**: Reduced tool call latency by eliminating inter-service communication overhead
- **Synchronization**: Fixed race conditions in concurrent tool executions

---

## [0.5.1] - 2025-11-29 "Memory Weaver Security Audit"

### Added
- **Security Hardening**: Added input validation for all GraphReasoner queries
- **Audit Trail**: Enhanced logging for all automated relationship repairs
- **Circuit Breakers**: Added fail safes for Weaver operations

### Changed
- **Weaver Engine**: Refactored to use parameterized queries, preventing Cypher injection
- **Permission Model**: Strengthened access controls for relationship modification operations

### Fixed
- **Cypher Injection**: Patched vulnerability in Neo4j relationship queries
- **Race Conditions**: Fixed concurrency issues in automated repair operations
- **Resource Exhaustion**: Added limits to prevent DoS via excessive repair requests

---

## [0.5.0] - 2025-11-28 "Memory Weaver (Automated Repair)"

### Added
- **Memory Weaver Engine**: Automated system for detecting and repairing broken relationships in Neo4j
- **Similarity Detection**: Embedding-based relationship discovery for linking related memories
- **Audit System**: Complete traceability for all automated repairs with `auto_commit_run_id`
- **Rollback Capability**: Deterministic reversal of automated changes via `rollback_commits_by_run.py`
- **Scheduler**: Background maintenance tasks for continuous graph integrity

### Changed
- **Graph Maintenance**: Automated relationship repair now runs as background process
- **Quality Assurance**: Enhanced relationship validation with similarity scoring
- **Traceability**: All automated changes now logged with unique run identifiers

### Fixed
- **Orphaned Nodes**: Automatically discovers and connects isolated memories
- **Broken Links**: Repairs missing relationships between related concepts
- **Data Drift**: Corrects inconsistent metadata across related nodes

---

## [0.4.0] - 2025-11-25 "Graph-R1 Implementation"

### Added
- **Graph Reasoner**: Iterative "Think → Query → Retrieve → Rethink" reasoning engine
- **Q-Learning Retrieval**: Reinforcement learning for optimized memory access patterns
- **Markovian Reasoning**: Chunked thinking with state preservation across context shifts
- **Multi-Hop Queries**: Complex graph traversal for answering compound questions
- **Cognitive Agents**: Plugin architecture for specialized reasoning tasks

### Changed
- **Retrieval Method**: Replaced simple vector search with Graph-R1 retrieval
- **Memory Access**: Graph-based traversal now primary method for context assembly
- **Agent Architecture**: Modular cognitive agents for specialized tasks
- **Context Building**: Enhanced context with relationship-aware retrieval

### Fixed
- **Context Relevance**: Improved precision of memory retrieval
- **Chain of Thought**: Better preservation of reasoning pathways
- **Memory Decay**: Reduced loss of historical context in long conversations

---

## [0.3.1] - 2025-11-20 "Security Hardening"

### Added
- **API Authentication**: Token-based authentication for all endpoints
- **Rate Limiting**: Request throttling to prevent abuse
- **Input Sanitization**: Enhanced validation for all user inputs
- **Audit Logging**: Comprehensive logging of all sensitive operations
- **Secure Defaults**: Safe configuration presets for common deployment scenarios

### Changed
- **Security Model**: Implemented zero-trust architecture
- **Credential Handling**: Secure storage and transmission of API keys
- **Access Controls**: Granular permissions for different API endpoints

### Fixed
- **Authentication Bypass**: Patched critical vulnerability in API access
- **Data Exposure**: Resolved information disclosure in error messages
- **Injection Attacks**: Fixed potential SQL injection in Neo4j queries

---

## [0.3.0] - 2025-11-15 "Neo4j Migration Complete"

### Added
- **Neo4j Integration**: Complete migration from SQLite to Neo4j graph database
- **Redis Cache**: Hot cache layer for active session management
- **Graph Schema**: Formal schema definition for memory relationships
- **Migration Tools**: Scripts to migrate existing SQLite data to Neo4j
- **Backup System**: Automated graph backup and restoration procedures

### Changed
- **Storage Architecture**: Tiered storage (Redis hot cache + Neo4j persistent)
- **Query Language**: Cypher queries for graph operations
- **Relationship Modeling**: Graph-based connections between memories
- **Indexing Strategy**: Graph-based indices for faster retrieval

### Fixed
- **Performance**: Significantly improved query performance for complex relationships
- **Scalability**: Better handling of large-scale memory graphs
- **Consistency**: Stronger data integrity with ACID-compliant transactions

---

## [0.2.0] - 2025-10-30 "Cognitive Agents"

### Added
- **Verifier Agent**: Fact-checking via empirical distrust protocol
- **Archivist Agent**: Memory maintenance and staleness detection
- **Distiller Agent**: Content summarization and extraction
- **Agent Framework**: Plugin system for extensible cognitive capabilities
- **Truth Scoring**: Provenance-aware fact-checking with primary source priority

### Changed
- **Memory Hygiene**: Automated maintenance of memory quality
- **Verification Process**: Evidence-based fact-checking system
- **Quality Assurance**: Continuous assessment of memory reliability
- **Maintenance Schedule**: Regular memory grooming operations

### Fixed
- **Hallucinations**: Reduced false information in responses
- **Stale Information**: Automatic detection and updating of outdated memories
- **Data Quality**: Improved content validation and cleaning procedures

---

## [0.1.0] - 2025-09-15 "Initial Architecture"

### Added
- **Core Backend**: Initial ECE_Core with SQLite memory system
- **Anchor Interface**: Terminal interface for user interaction
- **Basic Memory**: Text-based memory storage and retrieval
- **LLM Integration**: Support for various local LLM servers
- **Plugin System**: Extensible tool architecture (UTCP)

### Changed
- **Foundation**: Established core architecture patterns
- **API Design**: Defined RESTful API structure for components

### Fixed
- **Basic Functionality**: Initial implementation of core features