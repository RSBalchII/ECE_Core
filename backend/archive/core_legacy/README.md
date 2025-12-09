# Core System

Core memory management, configuration, and LLM integration.

## Files

**`config.py`** - Comprehensive configuration system
- Organized by component (LLM, Memory, Q-Learning, etc.)
- Environment variable overrides
- Settings for Josiefied-Qwen3-4B model
- Context windows, batch sizes, all tunables

**`llm_client.py`** - LLM integration with fallback
- Primary: llama.cpp server API (http://localhost:8080)
- Fallback: Direct GGUF loading via llama-cpp-python
- Async generation with configurable parameters

**`distiller.py`** - Intelligent context compression (replaces `archivist.py`)
- Chunked summarization with overlap
- Meta-summarization for large contexts
- Target: 30% compression ratio
- Preserves key facts while reducing tokens

**`context_manager.py`** - Context assembly and management
- Combines Redis + SQLite + Neo4j data
- Triggers Distiller when context too large
- Manages summarization thresholds

## Usage

```python
from core.config import settings
from core.llm_client import LLMClient
from core.distiller import Distiller

# LLM client
llm = LLMClient()
response = await llm.generate("Your prompt here")

# Distiller
distiller = Distiller(None)  # pass LLM client as needed
compressed = await distiller.distill_moment(large_context)

# Config
print(f"Model: {settings.llm_model_path}")
print(f"Context: {settings.llm_context_size} tokens")
```

## Configuration Sections

- **LLM Settings**: Model path, context size, generation params
- **Memory Settings**: Redis TTL, SQLite paths, thresholds
- **Distiller Settings**: Chunk size, overlap, compression ratio
- **Q-Learning Settings**: Learning rate, exploration, max hops
- **Entity Extraction**: Batch size, delay, confidence threshold
- **Neo4j Settings**: URI, credentials, pool size
