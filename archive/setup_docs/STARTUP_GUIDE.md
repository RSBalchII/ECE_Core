# ECE Context Engine - Clean Architecture

This project now uses a streamlined 3-script architecture for easier management:

## 🚀 Quick Start

### 1. Start the LLM Server (with interactive model selection)
```bash
python start_llm_server.py
# Or with specific model:
python start_llm_server.py --model models/your_model.gguf
# Or list available models:
python start_llm_server.py --list
```

### 2. Start the ECE Core + MCP Server (unified)
```bash
python start_ece.py
```

### 3. Start the Embedding Server (auto-selects gemma-300m)
```bash
python start_embedding_server.py
# Or specify port:
python start_embedding_server.py --port 8081
```

## 🏗️ Clean Architecture

### `start_ece.py` - ECE Core with Integrated MCP
- **Port**: 8000 (default)
- **Features**:
  - Main ECE API endpoints
  - MCP endpoints integrated when `mcp.enabled: true` in config
  - Single server for both ECE and MCP functionality
  - No more separate MCP server needed

### `start_llm_server.py` - LLM Server with Model Selection
- **Port**: 8080 (default)
- **Features**:
  - Interactive model selection from models/ directory
  - RTX 4090 optimized settings (16k context, full GPU layers)
  - Reka-style configuration with mirostat and temp=1.0
  - Automatic detection of available models

### `start_embedding_server.py` - Embedding Server
- **Port**: 8081 (default)
- **Features**:
  - Auto-detects and selects gemma-300m or similar embedding model
  - Optimized for embedding tasks
  - Separate server for embedding operations

## 🚀 Additional Scripts

### `start-reka.bat` - Reka-optimized startup
- Starts all services with Reka Flash 3 21B optimized settings
- Uses RTX 4090 tuned parameters for reasoning models

### `start_all_safe.py` - Safe/Conservative startup (Python)
- Starts all services with conservative settings suitable for development
- Uses background threads for easy management

### `start_all_safe_simple.bat` - Safe startup (Batch)
- Simple batch wrapper for the Python safe startup
- Good for users who prefer batch scripts

### `stop_all_ece.bat` - Process killer utility
- Stops all ECE-related processes when needed
- Helpful when services get stuck

## 🔧 Configuration

All configuration is done in `configs/config.yaml`:

### MCP Integration
```yaml
mcp:
  enabled: true  # When true, MCP endpoints are available at /mcp on main server
  timeout: 30
  max_tool_iterations: 5
```

### LLM Configuration (for Reka-style models)
```yaml
llm:
  context_size: 16384
  max_tokens: 4096
  temperature: 1.0
  top_p: 0.95
  stop_tokens: ["< sep >", ""]
```

### RTX 4090 Optimization
The LLM server automatically uses these settings for RTX 4090 16GB VRAM:
- `--ctx-size 16384` - 16k context for reasoning
- `--n-gpu-layers 99` - Full GPU offload
- `--mirostat 2` - Advanced sampling
- `--temp 1.0` - Temperature for reasoning models
- `--cache-type-k f16` - Optimized KV cache

## 🛠️ MCP Endpoints (available when mcp.enabled: true)

When MCP is enabled in the ECE server, these endpoints are available:

```
GET  http://localhost:8000/mcp/tools     # List available tools
POST http://localhost:8000/mcp/call      # Execute tools
GET  http://localhost:8000/mcp/sse      # Streaming status
```

Available tools:
- `add_memory` - Add memories to Neo4j
- `search_memories` - Search memory graph
- `get_summaries` - Get session summaries
- Aliases: `write_memory`, `read_memory`, `get_memory_summaries`

## 🔁 Service Management

### For development: Start services individually
1. Start LLM: `python start_llm_server.py`
2. Start ECE: `python start_ece.py`
3. Start Embeddings: `python start_embedding_server.py` (optional)

### For Reka configuration: Use the batch script
```bash
start-reka.bat
```

### For safe/conservative start: Use the safe scripts
```bash
python start_all_safe.py
# OR
start_all_safe_simple.bat
```

## 📋 Endpoints Reference

After starting the services:

**LLM Server (port 8080):**
- Health: `http://localhost:8080/v1/models`
- API: `http://localhost:8080/v1/chat/completions`

**ECE Server (port 8000):**
- Health: `http://localhost:8000/health`
- Main API: `http://localhost:8000/chat`, `/memories`, etc.
- MCP Tools: `http://localhost:8000/mcp/tools` (if enabled)
- MCP Call: `http://localhost:8000/mcp/call` (if enabled)
- MCP Health: `http://localhost:8000/health/mcp` (if enabled)

**Embedding Server (port 8081):**
- Health: `http://localhost:8081/v1/models`
- Embeddings: `http://localhost:8081/v1/embeddings`

This clean architecture eliminates the confusion of multiple startup scripts while maintaining all functionality!