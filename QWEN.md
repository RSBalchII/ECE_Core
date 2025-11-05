# External Context Engine (ECE) - System Documentation

## Documentation Policy

The ECE project follows a strict documentation policy to maintain organization and clarity. Only the following markdown files are permitted to be created or modified in this project:

### Allowed Root Directory Files
- `README.md` - Project overview and main documentation 
- `QWEN.md` - System documentation and specifications (this file)

### Specific Allowed Spec Files
Only the following specific markdown files in the `specs/` directory are allowed:
- `specs/plan.md` - Development plan and roadmap
- `specs/tasks.md` - Task tracking and progress
- `specs/spec.md` - Technical specifications
- `specs/changelog.md` - System changelog and version history

### Documentation Guidelines
- No additional markdown files should be created outside of the allowed locations
- All project documentation must be integrated into either the root documentation files or the specified spec files above
- All other documentation must be consolidated into the allowed files
- Session summaries and development logs should be placed in the `specs/` directory, specifically in the allowed files

## System Specifications Summary

The External Context Engine (ECE) is a sophisticated cognitive architecture designed to provide persistent memory and context management for AI systems. The system implements a multi-tier agent architecture with the following key features:

### Architecture Overview
- **Tier 1**: Orchestrator Agent - Central coordinator that routes prompts to appropriate agents
- **Tier 2**: Tool Agents - Specialized agents like WebSearchAgent and FileSystemAgent
- **Tier 3**: Memory Cortex - Core memory management agents including:
  - ArchivistAgent: Central coordinator for knowledge graph operations
  - QLearningAgent: Reinforcement learning for optimal path finding in the knowledge graph
  - DistillerAgent: Processes raw text to extract structured information
  - InjectorAgent: Optimizes the knowledge graph through reinforcement learning

### Core Technologies
- **LLM Integration**: Supports multiple providers (Ollama, llama.cpp, Docker Desktop)
- **Knowledge Graph**: Neo4j for persistent memory storage
- **Caching**: Redis-based context cache with 32GB allocation
- **Framework**: FastAPI for web services
- **Communication**: UTCP (Universal Tool Calling Protocol) for tool discovery and execution

### Key Features
- Intelligent memory management with Q-Learning powered context retrieval
- Enhanced context retrieval with keyword-based querying and semantic search
- Local-first execution running entirely on local hardware without cloud dependencies
- Script-based management for launching and managing agents
- Memory optimization with configurable memory limiter for Windows systems
- GPU acceleration support for accelerated embedding generation
- On-demand model execution with ModelManager for automatic start/stop of models
- Model lifecycle management to save resources when not in use
- UTCP integration with decentralized manual-based discovery

### UTCP Multi-Protocol Implementation
ECE implements a multi-protocol approach for Universal Tool Calling Protocol (UTCP) with the following capabilities:

#### Supported Communication Protocols
1. **HTTP/HTTPS**: Primary synchronous communication with REST API calls and JSON payloads
2. **Server-Sent Events (SSE)**: Streaming communication for long-running operations with progress updates
3. **WebSocket**: Bidirectional real-time communication for interactive operations
4. **Model Context Protocol (MCP)**: AI agent context-aware communication with structured exchanges
5. **Command-Line Interface (CLI)**: System-level tool access through command-line integration

#### Protocol Selection and Fallback
- Automatic protocol selection based on tool requirements, operation type, and network conditions
- Hierarchical fallback mechanism with HTTP/HTTPS as primary, followed by SSE, WebSocket, MCP, and CLI
- Protocol-specific configuration parameters for different communication needs

### Markovian Thinking Architecture
ECE implements a sophisticated reasoning system called "Markovian Thinking":

- **Chunked Reasoning**: Processes information in fixed-size context windows
- **Dual-LLM PEVG Model**: Uses a Primary LLM (Generator) and TRM Service (Executor/Verifier)
- **Iterative Refinement**: Implements "propose -> critique -> refine" loops via specialized TRM service
- **Textual Carryover**: Maintains context between chunks with concise summaries

### Context Loading and Reasoning Sequence
The ECE implements a sophisticated multi-tiered context management system with the following primary loading sequence:

1. **Persona Loading (POML/JSON) - Always First**: POML/JSON persona files are loaded FIRST before ANY response processing begins, establishing foundational identity, protocols, values, and operational context.

2. **Redis Context Loading & Archivist Processing**: Redis context is loaded containing conversation history, and the Archivist receives the prompt to send keywords to the QLearning agent for relevant context retrieval.

3. **QLearning & Archivist Context Enhancement**: QLearning returns potentially large amounts of context which the Archivist uses a system LLM to summarize and identify important contextual information, then appends it to the Redis cache.

4. **Orchestrator Processing**: The Orchestrator reads the enhanced Redis cache (always including POML persona first) and processes the complete context.

5. **Response Generation**: Either direct model response for simpler prompts or Markovian thinking for complex reasoning based on complexity analysis, with all processing maintaining the established persona context.

### Simplified Logging and Output Management
ECE has adopted a simplified logging and output management system that consolidates all output to a single log file (`logs/ece-llamacpp.txt`) while maintaining real-time console visibility:

- Eliminates complex logging layers that caused confusion and system instability
- Centralizes all system output to a single, predictable location
- Maintains real-time visibility in the terminal for immediate feedback during development
- Fixes encoding issues that were causing crashes with Unicode output
- Maintains file-based logging for record keeping while adding console output for development

### Model Management
ECE includes a sophisticated model management system with the following capabilities:

- **On-Demand Execution**: Models start and stop automatically based on demand, saving resources
- **Dynamic Switching**: Ability to switch between different models as needed
- **Automatic Port Assignment**: Automatic assignment of ports to avoid conflicts
- **Configuration Management**: Centralized configuration with environment variable support
- **Resource Optimization**: Efficient resource usage by running only one model at a time