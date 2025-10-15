# External Context Engine (ECE) - Project Overview

## Project Description
The External Context Engine (ECE) is a sophisticated cognitive architecture designed to provide persistent memory and context management for AI systems. It's an advanced agentic system that enables AI applications to maintain long-term relationships, recall past conversations, and build coherent narratives from fragmented knowledge. The system is designed to operate entirely on local hardware without cloud dependencies.

## Architecture Overview
The ECE implements a multi-tier agent architecture:

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

## Key Features

### Markovian Thinking Architecture
The ECE implements a sophisticated reasoning system called "Markovian Thinking":
- **Chunked Reasoning**: Processes information in fixed-size context windows
- **Dual-LLM PEVG Model**: Uses a Primary LLM (Generator) and TRM Service (Executor/Verifier)
- **Iterative Refinement**: Implements "propose -> critique -> refine" loops via specialized TRM service
- **Textual Carryover**: Maintains context between chunks with concise summaries

### Multi-Agent Coordination & Emergence
Based on research findings from "Emergent Coordination in Multi-Agent Language Models", the ECE implements enhanced coordination between agents:
- **Thinker Personas**: Each thinker agent is assigned a detailed persona with background, expertise, and personality traits to create stable identity-linked differentiation.
- **Theory of Mind (ToM) Integration**: Thinker agents are instructed to consider what other agents might do and how their actions might affect the group outcome, enabling more effective collaboration.
- **Role Complementarity**: Different thinkers are assigned complementary roles (Optimist, Pessimist, Analytical, Creative, Pragmatic, Strategic, Ethical) to ensure diverse perspectives contribute to the solution.
- **Coordination Analysis**: The system includes metrics to measure synergy, diversity, and complementarity among thinker agents to ensure productive collective intelligence.
- **Emergent Behavior Steering**: Prompt design and role assignments are used to steer the system from mere aggregates to higher-order collectives with coordinated behavior.

### Performance Optimization
- **C++/Cython Integration**: Performance-critical components rewritten in C++
- **Profiling-Driven Development**: Regular performance profiling with cProfile and snakeviz
- **GPU Acceleration**: CUDA support for accelerated embedding generation

### Core Capabilities
- **Intelligent Memory Management**: Q-Learning powered context retrieval
- **Context-Aware Prompt Management**: Dynamic adjustment of content based on model capabilities
- **Token-Aware Summarization**: Processes large contexts up to 1M tokens
- **Local-First Architecture**: Runs entirely on local hardware without cloud dependencies

## Building and Running

### Prerequisites
- Python 3.11+
- Neo4j database
- Redis server
- CUDA-compatible GPU (for GPU acceleration)

### Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment: Create `.env` file with Neo4j and Redis connection details
3. Configure LLM provider in `config.yaml`:
   ```yaml
   llm:
     active_provider: llama_cpp  # or ollama
     providers:
       llama_cpp:
         model_path: "./models/your-model.gguf"
         api_base: "http://localhost:8080/v1"
     ```

### Running the System
1. Start required services (Neo4j, Redis)
2. If using llama.cpp, run it first:
   - Use `run_llama_server.bat` (Windows) or appropriate script
3. Start all ECE agents:
   ```
   python run_all_agents.py
   ```
   This starts all agents on different ports (8000-8007)

### Packaging
To create a distributable executable:
1. Install PyInstaller: `pip install pyinstaller`
2. Run appropriate build script:
   - Windows: `build_package.bat`
   - Linux/macOS: `./build_package.sh`

## Development Conventions

### Architecture Philosophy
- **Modular Components**: Smaller, specialized, independently deployable components
- **Local-First**: All processing occurs on local hardware
- **Multi-Agent System**: Specialized agents handle different tasks
- **Script-Based Deployment**: Simple scripts for launching and managing agents

### Testing Approach
- Unit tests for individual components (in Tests/ directory)
- Integration tests for agent communication
- Performance testing for optimized components
- Markovian thinking validation tests

### Code Structure
- `ece/`: Main source code organized by agent tiers
- `specs/`: Specification documents for architecture and development plans
- `Tests/`: Test suites for different components
- `models/`: Location for LLM model files
- `poml/`: POML specification files

## Current Development Phases
The project has completed major architectural implementation phases and is now focused on:

1. **Phase 6**: System Validation & GUI Testing - End-to-end testing of workflows
2. **Phase 7**: TRM Fine-Tuning & Specialization - Replacing mock TRM with fine-tuned models
3. **Phase 8**: Continuous Improvement & Co-Evolution - Ongoing system enhancement

## Configuration
The system uses multiple configuration files:
- `config.yaml`: Main system configuration including LLM providers and memory limits
- `.env`: Environment-specific settings like API keys and service URLs
- Individual agent configuration files for specific behaviors

## Key Files
- `run_all_agents.py`: Main entry point to start all ECE agents
- `config.yaml`: Main configuration file for the system
- `requirements.txt`: Python dependencies
- `specs/`: Directory containing architectural specifications and plans
- Various agent files in `ece/agents/` directories

## Recent Enhancements

### Coordination Analyzer Module
- Created `coordination_analyzer.py` with classes to measure synergy, diversity, and complementarity among thinker agents
- Implemented `CoordinationAnalyzer` with metrics based on information theory concepts from the research
- Created `ThinkerCoordinator` to manage persona assignments and Theory of Mind (ToM) instructions

### Enhanced Thinker Architecture
- Updated `BaseThinker` class to include persona assignments and ToM capabilities
- Modified the `think` method to accept information about other thinkers and incorporate ToM considerations
- Updated `SynthesisThinker` to be compatible with the new architecture

### Coordinated Parallel Thinking
- Enhanced the `parallel_thinking` method to use coordination-aware thinking
- Added collection of thinker roles and descriptions for ToM instructions
- Implemented coordination metrics analysis during the parallel thinking process

### Configuration Updates
- Updated `config.yaml` with detailed persona definitions for each thinker type
- Added role descriptions and system prompts that align with the research findings

### Spec Documentation Updates
- **spec.md**: Added section 3.6 on "Coordination in Multi-Agent Systems" detailing the implementation
- **reasoning_flow.md**: Added section on "Multi-Agent Coordination & Emergence" explaining the coordination approach
- **tasks.md**: Added T-015 for "Multi-Agent Coordination Implementation" with detailed tasks
- **plan.md**: Added Phase 20 for "Multi-Agent Coordination & Emergence" with implementation goals
- **specs/README.md**: Updated to reflect the new multi-agent coordination implementation