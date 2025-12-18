# Context-Engine Specification

## Identity
- **Name**: Context-Engine
- **Role**: Executive Cognitive Enhancement (ECE) System
- **Philosophy**: Local-first, user-sovereign, agentic.

## Architecture Overview

The system follows a **Sovereign-First** architecture with browser-native compute:

### 1. Browser-Native Layer (tools/)
- **Type**: Zero-dependency HTML files
- **Technologies**: WebLLM (WASM), CozoDB (WASM), Transformers.js
- **Storage**: IndexedDB (persistent, local)
- **Components**:
  - **Chat Interface** (`model-server-chat.html`): WebGPU LLM inference + memory recall
  - **Memory Builder** (`sovereign-db-builder.html`): Document ingestion & embedding
  - **Log Viewer** (`log-viewer.html`): Real-time debugging interface
  - **Hub** (`index.html`): Central navigation

### 2. Optional Backend (backend/) - DEPRECATED
- **Type**: Python FastAPI service (legacy support only)
- **Status**: Archived in favor of browser-native approach
- **Memory**: Neo4j + Redis (replaced by CozoDB WASM)

### 3. Browser Extension (extension/) - OPTIONAL
- **Type**: Chrome Extension (MV3)
- **Communication**: Direct HTML file integration
- **Capabilities**:
  - **Voice**: Streaming chat via Side Panel
  - **Sight**: Context injection (reading active tab)
  - **Memory**: **[Save to Memory]** button for CozoDB ingestion
  - **Hands**: JavaScript execution (User-ratified)

## Infinite Context Pipeline Architecture

### Phase 1: Hardware Foundation
- **64k Context Window**: All LLM servers boot with 65,536 token capacity
- **GPU Optimization**: Full layer offload with Q8 quantized KV cache
- **Flash Attention**: Enabled for optimal performance with long contexts

### Phase 2: Context Rotation Protocol
- **Context Shifting**: Automatic rotation when context approaches 55k tokens
- **Intelligent Distillation**: Old context compressed to "Narrative Gists" using Distiller
- **Persistent Storage**: Gists stored in Neo4j as `:ContextGist` nodes with chronological links

### Phase 3: Graph-R1 Reasoning Enhancement
- **Gist Retrieval**: GraphReasoner searches `:ContextGist` nodes for historical context
- **Continuity Maintenance**: Maintains reasoning flow across context rotations
- **Smart Querying**: Enhanced retrieval with historical context awareness

## Memory Architecture (Current - Production)

### Neo4j Graph Database (port 7687) - PRIMARY
- **Purpose**: Permanent storage of memories, summaries, and relationships
- **Structure**: 
  - `(:Memory)` nodes with content, timestamp, importance, tags
  - `(:Summary)` nodes for distilled content
  - `[:RELATED_TO]`, `[:CAUSED_BY]`, `[:MENTIONS]` relationships for semantic connections
  - `[:NEXT_IN_SERIES]` relationships for chronological context gists
- **Features**: Full-text search, graph traversal, semantic queries

### Redis Cache (port 6379) - HOT CACHE  
- **Purpose**: Active session state and recent conversation cache
- **TTL**: 24-hour expiration for hot data
- **Content**: Recent exchanges, temporary context, session variables
- **Behavior**: Falls back to Neo4j when unavailable

## Cognitive Architecture: Agent System

### Verifier Agent
- **Role**: Truth-checking via Empirical Distrust
- **Method**: Provenance-aware scoring (primary sources > summaries)
- **Goal**: Reduce hallucinations, increase factual accuracy

### Distiller Agent  
- **Role**: Memory summarization and compression + Context Rotation
- **Method**: LLM-assisted distillation with salience scoring + context gist creation
- **Goal**: Maintain high-value context, prune noise, enable infinite context

### Archivist Agent
- **Role**: Knowledge base maintenance and freshness + Context Management
- **Method**: Scheduled verification, stale node detection, context rotation oversight
- **Goal**: Keep memory graph current and trustworthy, manage context windows

### Memory Weaver (Maintenance Engine)
- **Role**: Automated relationship repair
- **Method**: Embedding-based similarity with audit trail (`auto_commit_run_id`)
- **Goal**: Maintain graph integrity with full traceability

## Tool Integration Architecture

### UTCP (Simple Tool Mode) - Current
- **Discovery**: Plugin-based via `backend/plugins/` directory
- **Plugins**: 
  - `web_search` - DuckDuckGo search
  - `filesystem_read` - File and directory operations  
  - `shell_execute` - Shell command execution (with safety checks)

## Appendix A: Infinite Context Pipeline Details

### Troubleshooting

#### Role Alternation Errors
**Issue**: `Conversation roles must alternate user/assistant/user/assistant/...`
**Cause**: Improperly formatted conversation history sent to the LLM
**Solution**: Proper message structure with alternating user/assistant roles

#### Template Parsing Issues
**Issue**: `.->.->.->` pattern errors
**Cause**: Template processing conflicts between CLI and backend
**Solution**: Proper separation of concerns and template configuration

#### Context Overflow
**Issue**: Context window limitations
**Solution**: Automatic context rotation and distillation

### Usage
The system works seamlessly with Qwen Code CLI, providing infinite context capabilities without interfering with the CLI's own functionality. The context rotation happens transparently in the background.

## Appendix B: WebGPU Model Guide

### Finding Existing Models
The "For Sure" way to find models is to look for the **MLC Format**.

#### Trusted Sources
*   **[mlc-ai](https://huggingface.co/mlc-ai):** The official creators. All models here are guaranteed to work.
*   **[vulcan-llm](https://huggingface.co/vulcan-llm):** Community members often upload converted models.

#### Search Strategy
When searching Hugging Face, look for these keywords in the model name:
*   `MLC`
*   `q4f16_1` (The standard 4-bit quantization for WebGPU)
*   `q4f32_1`

**The "Golden Rule" Check:**
Before trying a model, go to the **"Files and versions"** tab on Hugging Face. It **MUST** contain:
1.  `ndarray-cache.json` (The manifest)
2.  `mlc-chat-config.json` (The config)
3.  `params_shard_*.bin` (The weights)

### Converting Custom Models
Your `webgpu-chat.html` uses **WebLLM** (by MLC AI), which requires models to be in a specific **MLC Format** (compiled for TVM runtime). It **cannot** load raw `.safetensors`, `.bin`, or `.onnx` files directly.

#### Prerequisites
You need a Python environment with `mlc_llm` installed.
```powershell
pip install --pre --force-reinstall mlc-llm-nightly-cu122 mlc-ai-nightly-cu122 -f https://mlc.ai/wheels
# OR standard install
pip install mlc-llm
```

#### Conversion Steps
1.  **Download**: Download the model to a local folder (e.g., `models/Ministral-3-14B`).
2.  **Convert Weights**:
    ```powershell
    mlc_llm convert_weight ./models/Ministral-3-14B ^
        --quantization q4f16_1 ^
        -o ./dist/Ministral-3-14B-MLC
    ```
3.  **Generate Config**:
    ```powershell
    mlc_llm gen_config ./models/Ministral-3-14B ^
        --quantization q4f16_1 ^
        --convention mistral ^
        -o ./dist/Ministral-3-14B-MLC
    ```
4.  **Serve**: Host the `./dist` folder on a local web server (CORS enabled) or upload to Hugging Face.

#### Loading in WebGPU Chat
1.  Open `webgpu-chat.html`.
2.  Select **"Custom"** in the dropdown.
3.  Enter the Model ID (e.g., `username/Ministral-3-14B-MLC-q4f16_1`).
  - `mgrep` - Semantic code search
- **Execution**: Pattern-based for <14B models, structured for >14B models

### MCP Integration - Now Part of Main Server
- **Location**: Integrated into main ECE server when `mcp.enabled: true`
- **Endpoints**: `/mcp/tools`, `/mcp/call` on main port (8000)
- **Tools**:
  - `add_memory` - Add to Neo4j graph
  - `search_memories` - Graph search with relationships  
  - `get_summaries` - Session summary retrieval

## API Interface

### Core Endpoints (Port 8000)
- `POST /chat/stream` - Streaming conversation with full memory context
- `POST /archivist/ingest` - Ingest content to Neo4j memory graph
- `GET /health` - Server health check
- `GET /models` - Available models information
- `POST /mcp/call` - Memory tool operations (when MCP enabled)

### Security
- **API Keys**: Optional token authentication for all endpoints
- **Rate Limiting**: Request throttling to prevent abuse
- **Input Sanitization**: Validation for all user inputs

## Development & Deployment

### Requirements
- **Python**: 3.11+ 
- **Neo4j**: Graph database (local or remote)
- **Redis**: Cache server (recommended)
- **llama.cpp**: Server for local LLMs

### Startup Architecture
- **3-Script Model**:
  1. `python start_llm_server.py` - Interactive LLM with 64k context
  2. `python start_ece.py` - ECE Core with MCP and cognitive agents  
  3. `python start_embedding_server.py` - Optional embedding server

## Technology Stack

### Backend (Python)
- **Framework**: FastAPI
- **Database**: Neo4j (graph), Redis (cache)
- **Models**: llama.cpp server integration
- **Tools**: UTCP plugin system

### Frontend Components
- **Anchor**: Pure Python CLI with streaming
- **Extension**: Manifest V3 Chrome Extension with Side Panel UI

## Small Model Considerations

### Tool Usage
- ⚠️ Models < 14B: Use "Simple Tool Mode" (pattern-based execution)
- ✅ Models ≥ 14B: Full structured protocol support
- ✅ MCP Tools: Work with any model for memory operations

### Recommended Models
- **Gemma-3 4B** - Speed (chat only, tools unreliable)
- **Qwen3-8B** - Reasoning (Simple Tool Mode works)  
- **DeepSeek-R1-14B** - Tools (full structured protocol support)
- **Reka Flash 3 21B** - Reasoning (use start-reka.bat)

## Performance Optimization

### Context Windows
- **64k Context**: Full capacity for infinite work capability
- **Rotation Threshold**: 55k tokens triggers automatic context rotation
- **Gist Creation**: Old content compressed to maintain continuity

### Memory Management
- **Hot Cache**: Redis for active sessions (24h TTL)
- **Cold Storage**: Neo4j for permanent memories
- **Automatic Cleanup**: Scheduled pruning of expired sessions

---

## Research Foundation

- **Graph-R1**: Memory retrieval patterns (https://arxiv.org/abs/2507.21892)  
- **Markovian Reasoning**: Chunked thinking (https://arxiv.org/abs/2506.21734)
- **Hierarchical Reasoning Model (HRM)**: Multi-level context processing
- **Empirical Distrust**: Primary source supremacy for verification
- **Infinite Context Pipeline**: Hardware-software context rotation protocol