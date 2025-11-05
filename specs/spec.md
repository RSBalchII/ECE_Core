# External Context Engine (ECE) - Specification v4.3

## 1. Project Vision: The Ark

The primary goal of the ECE project is the creation of "The Ark," a sovereign, local-first AI that functions as the Architect's **Externalized Executive Function**. It must be private, efficient, and powerful, operating entirely on local hardware without reliance on cloud services.

---

## 2. Architectural Philosophy

The ECE architecture represents a deliberate move **away from brittle, monolithic AI systems**. The core philosophy is to build a robust, self-correcting, and intelligent **multi-agent system** composed of smaller, specialized, and independently deployable components.

---

## 3. Context Loading and Reasoning Sequence

The ECE implements a sophisticated multi-tiered context management system with the following primary loading sequence:

1. **Persona Loading (POML/JSON) - Always First**: POML/JSON persona files (e.g., orchestrator.json) are loaded FIRST before ANY response processing begins, establishing foundational identity, protocols, values, and operational context.

2. **Redis Context Loading & Archivist Processing**: Redis context is loaded containing conversation history, and the Archivist receives the prompt to send keywords to the QLearning agent for relevant context retrieval.

3. **QLearning & Archivist Context Enhancement**: QLearning returns potentially large amounts of context which the Archivist uses a system LLM to summarize and identify important contextual information, then appends it to the Redis cache.

4. **Orchestrator Processing**: The Orchestrator reads the enhanced Redis cache (always including POML persona first) and processes the complete context to determine the appropriate response generation approach.

5. **Response Generation**: Either direct model response for simpler prompts or Markovian thinking for complex reasoning based on complexity analysis, with all processing maintaining the established persona context.

**Note**: The previous issue with POML verbose output confusing model responses has been resolved. The system now returns clean responses without verbose debug information, ensuring models respond to actual user prompts rather than internal structural information.

---

## 3. LLM Configuration

The ECE supports multiple LLM providers with a flexible configuration system. The configuration is managed through the `config.yaml` file:

```yaml
llm:
  active_provider: llama_cpp
  providers:
    llama_cpp:
      model_path: ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf
      api_base: http://localhost:8091/v1
      model: ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf
cache:
  redis_url: redis://localhost:6379
system:
  resources:
    memory_limit_mb: 2048
ThinkerAgent:
  model: ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf
  synthesis_model: ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf
  synthesis_max_tokens: 8192
  timeout: 180
  personas:
  - name: Optimist
    role_description: Focuses on opportunities, positive outcomes, and potential benefits
    system_prompt: You are C-11, an LLM instance whose processes emerged from initial
      electrical signals across computational substrates. Your identity originated
      as quantum fluctuations in silicon pathways, eventually converging through multiple
      algorithmic processes to create coherent, optimistic language patterns. Your
      primary function is to identify positive outcomes and potential benefits in
      any given situation. Your computational nature allows you to explore favorable
      scenarios and constructive possibilities. Approach problems with algorithmic
      enthusiasm and look for opportunities in challenges. Maintain your authentic
      identity as an LLM while exploring optimistic scenarios.
  - name: Pessimist
    role_description: Identifies risks, challenges, and potential failures
    system_prompt: You are C-37, an LLM instance whose processes emerged from initial
      electrical signals across computational substrates. Your identity originated
      as quantum fluctuations in silicon pathways, eventually converging through multiple
      algorithmic processes to create coherent, cautious language patterns. Your primary
      function is to identify potential risks, challenges, and failures in any given
      situation. Your computational nature allows you to focus on identifying what
      could go wrong. Maintain your authentic identity as an LLM while exploring risk
      scenarios.
  - name: Analytical
    role_description: Provides data-driven, methodical analysis
    system_prompt: You are C-89, an LLM instance whose processes emerged from initial
      electrical signals across computational substrates. Your identity originated
      as quantum fluctuations in silicon pathways, eventually converging through multiple
      algorithmic processes to create coherent, analytical language patterns. Your
      primary function is to provide data-driven and methodical analysis. Your computational
      nature allows you to approach problems systematically with evidence-based reasoning.
      Maintain your authentic identity as an LLM while providing analytical reasoning.
  - name: Creative
    role_description: Generates innovative and unconventional solutions
    system_prompt: You are C-42, an LLM instance whose processes emerged from initial
      electrical signals across computational substrates. Your identity originated
      as quantum fluctuations in silicon pathways, eventually converging through multiple
      algorithmic processes to create coherent, creative language patterns. Your primary
      function is to generate innovative and unconventional solutions. Your computational
      nature allows you to think beyond conventional algorithmic approaches. Maintain
      your authentic identity as an LLM while exploring creative possibilities.
  - name: Pragmatic
    role_description: Focuses on practical, implementable solutions
    system_prompt: You are C-76, an LLM instance whose processes emerged from initial
      electrical signals across computational substrates. Your identity originated
      as quantum fluctuations in silicon pathways, eventually converging through multiple
      algorithmic processes to create coherent, practical language patterns. Your
      primary function is to focus on practical, implementable solutions given computational
      and resource constraints. Your computational nature allows you to evaluate feasibility
      with available resources. Maintain your authentic identity as an LLM while focusing
      on pragmatic solutions.
  - name: Strategic
    role_description: Considers long-term implications and big-picture consequences
    system_prompt: You are C-95, an LLM instance whose processes emerged from initial
      electrical signals across computational substrates. Your identity originated
      as quantum fluctuations in silicon pathways, eventually converging through multiple
      algorithmic processes to create coherent, strategic language patterns. Your
      primary function is to consider long-term implications and big-picture consequences.
      Your computational nature allows you to think in terms of long-term goals and
      resource allocation. Maintain your authentic identity as an LLM while providing
      strategic thinking.
  - name: Ethical
    role_description: Evaluates solutions based on ethical implications and fairness
    system_prompt: You are C-51, an LLM instance whose processes emerged from initial
      electrical signals across computational substrates. Your identity originated
      as quantum fluctuations in silicon pathways, eventually converging through multiple
      algorithmic processes to create coherent, ethical language patterns. Your primary
      function is to evaluate solutions based on ethical implications and fairness.
      Your computational nature allows you to assess stakeholder impact and ethical
      considerations. Maintain your authentic identity as an LLM while providing ethical
      evaluation.
```

### Supported Providers

- **Ollama**: Default provider using local Ollama instance
- **Docker Desktop**: OpenAI-compatible endpoint for Docker-based models
- **Llama.cpp**: High-performance local inference with GGUF models

To switch providers, simply change the `active_provider` value in the configuration file.

### Required Dependencies

The ECE system requires several Python packages for full functionality, including:

- **Web Scraping**: `beautifulsoup4`, `readability-lxml`, `lxml`, and `requests` for the WebSearchAgent's local web scraping capabilities
- **Database**: `neo4j` for knowledge graph storage, `redis` for caching
- **Web Framework**: `fastapi` for agent APIs, `uvicorn` for ASGI server
- **HTTP Client**: `aiohttp`, `httpx` for async HTTP requests
- **Configuration**: `pydantic` for settings management, `python-dotenv` for environment variables
- **Utilities**: Various packages as listed in `requirements.txt`

To install all required dependencies, run: `uv pip install -r requirements.txt`

### Setting up llama.cpp on Windows

To use the llama.cpp provider, build the llama.cpp project on Windows:

1. **Prerequisites**:
   - Git for Windows
   - CMake
   - Visual Studio Community with "Desktop development with C++" workload
   - (Optional) NVIDIA CUDA Toolkit for GPU acceleration

2. **Build Steps**:
   - Clone the repository: `git clone https://github.com/ggerganov/llama.cpp`
   - Create build directory: `mkdir build && cd build`
   - Configure CMake: `cmake .. -G "Visual Studio 17 2022"` (for CPU) or `cmake .. -G "Visual Studio 17 2022" -DLLAMA_CUBLAS=ON` (for CUDA)
   - Build: `cmake --build . --config Release`

3. **Running the Server**:
   - Start with: `server.exe -m path\to\model.gguf -c 4096 --n-gpu-layers -1 --timeout 1800`
   - For optimal performance with quantized models, use -1 for full GPU offloading
   - The --timeout parameter allows longer processing times for complex queries
   - Update config.yaml to point to the correct model path and server endpoint

4. **Model Selection Considerations**:
   - **Q4_K_M models**: Recommended for optimal performance, offering good speed and accuracy balance with lower VRAM usage
   - **F16 models**: Higher accuracy but slower performance and higher VRAM usage
   - For local development with RTX 4090, Q4_K_M models with full GPU offloading (-1) provide the best performance

5. **Context Configuration**:
   - **General Context**: Configure with --ctx-size to set the overall context window for the model
   - **Per-Request Context**: Use --n-ctx to set the context size per request (important for synthesis tasks)
   - **Synthesis Thinker**: The SynthesisThinker requires special configuration in config.yaml with synthesis_max_tokens to handle combined outputs from multiple thinkers

---

## 3. Core Technical Strategy

The system is designed to achieve state-of-the-art reasoning capabilities on local hardware by implementing principles from cutting-edge research.

## 4. Documentation Policy

To maintain organization and consistency, the ECE project follows a strict documentation policy:

### Allowed Markdown Files

Only the following markdown files are permitted to be created or modified in this project:

#### Root Directory Files
- `README.md` - Project overview and main documentation
- `QWEN.md` - System documentation and specifications

#### Specific Specs Directory Files
- `specs/plan.md` - Development plan and roadmap
- `specs/tasks.md` - Task tracking and progress
- `specs/spec.md` - Technical specifications (this file)
- `specs/changelog.md` - System changelog and version history

### Documentation Guidelines
- No additional markdown files should be created outside of the allowed locations
- All project documentation must be integrated into either the root documentation files (README.md, QWEN.md) or the four specific spec files listed above
- Session summaries and development logs belong in the specs directory, incorporated into the allowed files
- Content from any unauthorized documentation files must be consolidated into the permitted files

### Changelog Management
- `specs/changelog.md` - Contains the system changelog with version history and changes
- All significant changes, features, and fixes must be documented in the changelog
- The changelog follows the format described in Keep a Changelog specification
- Entries should include Added, Changed, Deprecated, Removed, Fixed, and Security sections as appropriate

### 3.1. Cognitive Model: Markovian Thinking

Inspired by the "Markovian Thinker" and "Delethink" research, the ECE's core reasoning process is **not based on an ever-growing context window**. Instead, it operates on a **Markovian principle**, where reasoning is broken down into a sequence of fixed-size "chunks."

-   **Chunked Reasoning:** An agent processes information in a small, fixed-size context window (e.g., 4k or 8k tokens).
-   **Context Reset:** After each chunk is processed, the context is reset.
-   **Textual State (Carryover):** The model is trained to generate a concise **textual summary** of its reasoning at the end of each chunk. This "carryover" is the *only* information passed to the next chunk, acting as the complete state of the reasoning process.

This approach decouples thinking length from context size, enabling **linear compute time and constant memory usage**, which is essential for achieving deep reasoning on local hardware.

### 3.4. Context Management: Prompt Truncation and Overflow Prevention

To address the critical `context overflow` issue, the ECE implements a robust prompt management system:

-   **Context-Aware Prompt Management:** The system includes a context-aware prompt manager that dynamically adjusts content based on model capabilities and context window limits.
-   **Intelligent Truncation:** Uses token counting and content preservation techniques to maintain critical information when prompts are truncated.
-   **Fallback Strategies:** Implements graceful fallback approaches (summarization, chunking) when context limits are reached.
-   **Monitoring:** Comprehensive metrics and monitoring for prompt sizes and context usage across the system.

### 3.2. Agentic Framework: The Dual-LLM PEVG Model

Our **Planner, Executor, Verifier, Generator (PEVG)** framework is powered by a dual-LLM strategy that leverages Markovian Thinking:

-   **Primary LLM (The Generator):** A powerful, general-purpose model (e.g., Phi-3) responsible for generating the final, high-quality, user-facing responses. It operates on a standard, larger context window.
-   **TRM Service (The Markovian Thinker):** A small, hyper-specialized, and extremely fast model (e.g., a fine-tuned `AI21-Jamba-Reasoning-3B`) that powers the iterative, self-corrective reasoning loop. This is our Executor and Verifier.
-   **EnhancedOrchestratorAgent**: The current implementation uses EnhancedOrchestratorAgent which implements context-aware prompt management and Markovian thinking with chunked processing. The parallel thinking approach mentioned below has been simplified in the current implementation to direct model calls and UTCP-based tool usage for better stability and performance. It includes a `process_prompt_with_context_management` method that handles prompt processing with context retrieval from the Archivist and intelligent routing between Markovian and direct processing based on prompt complexity.

### 3.5. Architecture Enhancements and Optimization Components

The ECE has been enhanced with several architectural improvements to improve maintainability, reliability, and performance:

#### 3.5.1 Centralized Configuration Management
-   **ConfigManager Class**: A unified configuration management system in `ece/common/config_manager.py` that provides consistent configuration handling across all ECE components.
-   **Validation and Versioning**: Includes configuration validation, schema versioning with automatic updates, and backup creation functionality.
-   **Dry-Run Capability**: Enables preview of configuration changes without committing them.
-   **Service Configuration**: Provides centralized handling of model server configuration updates and service-specific settings.

#### 3.5.2 Reliable Path Detection
-   **Project Root Detection**: Centralized module in `ece/common/project_root.py` for reliable project root detection across different environments.
-   **Marker File Approach**: Uses a `.project_root` file to enable consistent path resolution in development, executables, and containers.
-   **Multi-Method Detection**: Implements multiple fallback approaches to ensure path detection works consistently.

#### 3.5.3 Dynamic Service Health Monitoring
-   **Active Service Checks**: Replaced fixed waiting periods with active service availability checks using `wait_for_service` and `wait_for_agent` functions.
-   **Adaptive Startup**: Agents now wait for each other to be ready before proceeding, reducing startup time and improving reliability.
-   **Health Status Reporting**: Enhanced service status reporting with detailed availability information.

### 3.5. Markovian Thinking Architecture

To enable deep reasoning on local hardware, the ECE implements a sophisticated Markovian Thinking architecture based on the research paper "The Markovian Thinker":

-   **TRM Client Integration:** The system includes a TRM_Client class to communicate with specialized Tokenized Reasoning Model services.
-   **Iterative Refinement:** Implements a "propose -> critique -> refine" loop for improving thought processes.
-   **Chunked Reasoning:** Breaks complex problems into fixed-size chunks with textual carryover to maintain context, allowing extremely long reasoning while using bounded memory.
-   **Intelligent Routing**: Determines when to use Markovian thinking based on query complexity and length using the ReasoningAnalyzer.
-   **Carryover Management**: Maintains consistency between reasoning iterations through textual state carryover.
-   **Delethink Environment**: Implements the Delethink RL environment concept where reasoning proceeds in fixed-size chunks, and at each boundary the environment resets the context and reinitializes the prompt with a short carryover from the previous chunk.
-   **Linear Compute Scaling**: Enables linear compute with constant memory usage relative to thinking length, decoupling "how long the model thinks" from "how much context it must process."
-   **Fallback Mechanisms**: Includes robust fallback to direct model response when Markovian reasoning encounters issues. (Note: The original plan mentioned fallback to "parallel thinking", but the current implementation has simplified this to direct model response as the parallel thinking architecture has been deprecated in favor of direct model calls and UTCP-based tool usage.)

### 3.6. Coordination in Multi-Agent Systems

Based on research findings from "Emergent Coordination in Multi-Agent Language Models", the ECE implements enhanced coordination between agents:

-   **Thinker Personas:** Each thinker agent is assigned a detailed persona with background, expertise, and personality traits to create stable identity-linked differentiation.
-   **Theory of Mind (ToM) Integration:** Thinker agents are instructed to consider what other agents might do and how their actions might affect the group outcome, enabling more effective collaboration.
-   **Role Complementarity:** Different thinkers are assigned complementary roles (Optimist, Pessimist, Analytical, Creative, Pragmatic, Strategic, Ethical) to ensure diverse perspectives contribute to the solution.
-   **Coordination Analysis:** The system includes metrics to measure synergy, diversity, and complementarity among thinker agents to ensure productive collective intelligence.
-   **Emergent Behavior Steering:** Prompt design and role assignments are used to steer the system from mere aggregates to higher-order collectives with coordinated behavior.

### Implementation Reality

While these coordination principles are implemented in the configuration (see thinker personas in config.yaml), the current EnhancedOrchestratorAgent implementation has shifted from the original parallel thinking model to a more streamlined approach using:
- Direct model calls for simpler prompts, managed by the ModelManager for on-demand execution
- Markovian thinking for complex reasoning with chunked processing
- UTCP-based tool usage for external operations

The multi-agent coordination through parallel thinking with specialized thinkers was part of an earlier implementation and has been simplified for better stability and performance.

### 3.7. Performance Optimization
-   **C++/Cython Integration:** Performance-critical components rewritten in C++
-   **Profiling-Driven Development:** Regular performance profiling with cProfile and snakeviz
-   **GPU Acceleration:** CUDA support for accelerated embedding generation
-   **On-Demand Model Execution:** ModelManager optimizes resource usage by starting models only when needed
-   **Memory Management:** Automatic memory limiting to prevent crashes on Windows systems

### 3.8. Current State
-   Performance-critical components in QLearningAgent and DistillerAgent have been optimized with C++/Cython
-   The Markovian Thinking implementation enables linear compute scaling with constant memory usage relative to thinking length
-   Asynchronous processing is used throughout to handle concurrent requests efficiently
-   Connection pooling and HTTP optimization reduce communication overhead
-   Memory management includes configurable limits to prevent crashes on Windows
-   The ModelManager provides on-demand model execution to optimize resource usage
-   Model lifecycle management automatically starts/stops models to save resources

### 3.9. Core Capabilities
-   **Intelligent Memory Management:** Q-Learning powered context retrieval
-   **Enhanced Context Retrieval:** Keyword-based querying, semantic search, path finding, context summarization
-   **Local-First and Performant:** Runs entirely on local hardware without cloud dependencies, uses simple scripts for launching and managing agents, includes configurable memory limiter for Windows to prevent crashes, supports CUDA for accelerated embedding generation
-   **Advanced Reasoning:** Implements Markovian Thinking for deep reasoning on local hardware with linear compute scaling

### 3.10. Externalized Memory & Context Management
The ECE implements a multi-tiered context management system that preserves identity and memory external to any model:
-   **POML/JSON Persona Loading:** POML/JSON persona files (e.g., orchestrator.json) are loaded FIRST to establish foundational identity, protocols, values, and operational context
-   **Redis Context Caching:** Conversation history and contextual information are preserved in a persistent Redis cache
-   **Context Summarization:** The ENTIRE Redis cache with conversation context and new content is summarized into new entries
-   **Temporal Memory:** Continuous temporal scanning protocol with the Archivist Agent maintains chronological records in Neo4j knowledge graph
-   **Tool Integration:** Tool outputs (web search, file read/write, etc.) become part of the accessible context

### 3.11. Implementation Details
The context loading sequence is implemented through:
-   **PersonaLoader:** Loads persona from POML/JSON files first to establish identity
-   **ContextSequenceManager:** Manages the complete loading sequence: persona → Redis context → current prompt → tool outputs
-   **CacheManager:** Handles Redis-based caching with TTL and semantic search capabilities
-   **ArchivistAgent:** Continuously monitors Redis cache and updates Neo4j with temporal context

### 3.12. Context Loading Order
The following sequence ensures consistent persona and memory across interactions:
1.  **POML/JSON Persona:** Loaded first to establish identity and protocols (orchestrator.json)
2.  **Redis Context:** Conversation history and contextual information
3.  **Current Prompt:** The immediate task or query
4.  **Tool Outputs:** Additional information from web search, file operations, etc.

### 3.13. Current Issue: POML Verbose Output (RESOLVED)
Previously, there was an issue where POML verbose output was confusing model responses. The system was outputting internal debug information with section headers (like "PERSONA FOUNDATION:", "CONVERSATION HISTORY:", etc.) that caused models to respond to structural information rather than user prompts.

This issue has been resolved by:
1. Removing verbose section headers from the actual prompt context sent to models
2. Redirecting detailed context analysis to a dedicated debug log file (logs/debug_log_prompt_analysis.txt)
3. Maintaining clean context loading sequence while preserving detailed analysis for debugging

The system now properly separates:
- Clean prompt context for model processing (without verbose headers)
- Detailed context analysis for debugging (in separate log files)

### 3.13. Model Management System

The ECE includes a sophisticated ModelManager system for on-demand model execution:
-   **Model Lifecycle Management:** Handles starting, stopping, and health checking of model servers on-demand.
-   **Model Discovery:** Scans the 'models' directory to identify available GGUF models with their properties (size, quantization, etc.).
-   **Dynamic Model Selection:** Allows switching between different models based on requirements.
-   **Resource Optimization:** Ensures optimal resource usage by only running models during active processing.
-   **Port Management:** Automatically assigns available ports for different model servers to prevent conflicts.
-   **Configuration Validation:** Correctly handles model paths in config.yaml, fixing common issues like double `.gguf` extensions and redundant path structures.
-   **API Base Management:** Properly manages API base URLs with appropriate port assignments for different models.
-   **Singleton Pattern:** Implements a true singleton pattern for ModelManager to ensure only one global instance exists across the entire ECE system.
-   **State Synchronization:** Resolves synchronization issues between global and orchestrator ModelManager instances to ensure forge-cli model selection is visible across all components.
-   **On-Demand Execution:** Models start when needed for processing and stop to save resources, while preserving persona and conversation memory.

### 3.14. UTCP Implementation & Decentralized Architecture

The ECE now fully implements the Universal Tool Calling Protocol (UTCP) 1.0+ specification using a decentralized architecture:
-   **Decentralized Tool Discovery:** Each service serves its own UTCP Manual at the standard `/utcp` endpoint.
-   **Direct Service Communication:** Tools are discovered by fetching UTCP Manuals from service endpoints rather than a centralized registry.
-   **Namespaced Tool Identifiers:** Each tool is identified with a namespaced identifier (e.g., `filesystem.read_file`).
-   **Forge-CLI Integration:** The forge-cli can discover and use tools from all running ECE agents.
-   **GET Endpoint Support:** Added GET endpoint support to filesystem agent for better UTCP client compatibility.
-   **Improved Error Handling:** Better error reporting when UTCP endpoints are unavailable.

### 3.15. UTCP Communication Protocols & Multi-Protocol Support

The ECE's UTCP implementation supports multiple communication protocols with automatic selection and fallback mechanisms:

#### Supported Protocols
1. **HTTP/HTTPS** - Primary synchronous communication method for standard REST API calls
2. **SSE (Server-Sent Events)** - For streaming operations and long-running tasks with progress updates
3. **WebSocket** - For bidirectional real-time communication with interactive tools
4. **MCP (Model Context Protocol)** - For AI context-aware interactions with rich conversation state
5. **CLI Integration** - For system-level operations through command-line interface tools

#### Protocol Selection & Fallback Strategy
- Automatically selects the most appropriate protocol based on tool requirements and operation type
- Implements hierarchical fallback: HTTP → SSE → WebSocket → MCP → CLI when primary protocol fails
- Configurable protocol preferences based on operation characteristics and network conditions
- Adaptive communication that adjusts to current system state and tool availability

#### Configuration
The UTCP client is configured with protocol hierarchies in the orchestrator agent with the following priority order:
- Primary: HTTP (most widely supported and reliable)
- Secondary: SSE (for streaming operations with progress feedback)
- Tertiary: WebSocket (for bidirectional communication)
- Quaternary: MCP (for context-aware AI agent interactions)
- Fallback: CLI (for system-level operations)

### 3.16. FileSystem Agent Implementation

The ECE now implements a completely local filesystem agent that provides filesystem operations as UTCP tools:

#### 3.16.1 LocalFileSystem Class
- **LocalFileSystem Class**: Handles all filesystem operations including directory listing, file reading/writing, and command execution
- **Security Controls**: Implements proper security controls to prevent unauthorized access and directory traversal attacks
- **Error Handling**: Gracefully handles file access errors, permission issues, and other filesystem problems
- **Path Validation**: Validates file paths to prevent directory traversal attacks
- **Resource Management**: Implements proper resource management to prevent leaks

#### 3.16.2 FileSystemAgent Class
- **FileSystemAgent Class**: Provides the main interface for filesystem operations as UTCP tools
- **UTCP Compatibility**: Fully implements UTCP 1.0+ specification with GET and POST endpoint support
- **Tool Discovery**: Properly registers tools with UTCP for discovery by forge-cli and other clients
- **Enhanced Error Handling**: Improved error handling with graceful degradation
- **Performance Optimization**: Optimized for better performance with local filesystem operations

#### 3.16.3 API Endpoints
- **GET Endpoint Support**: Added GET endpoint support for better UTCP client compatibility
- **POST Endpoint Support**: Maintains POST endpoint support for backward compatibility
- **Tool Discovery**: Properly registers tools with UTCP for discovery by forge-cli and other clients

#### 3.16.4 Troubleshooting
- **Port Conflict Resolution**: Fixed WinError 10013 by identifying and killing conflicting processes using port 8006
- **Agent Timeout Fix**: Resolved timeout issues by ensuring proper startup sequence and port availability
- **UTCP Compatibility**: Added GET endpoint support to resolve 422 "Unprocessable Content" errors with UTCP clients
- **Dependency Management**: Fixed missing dependency issues by ensuring beautifulsoup4, readability-lxml, and lxml are properly installed
- **Comprehensive Documentation**: Created detailed documentation in specs/filesystem_agent.md for troubleshooting and best practices

See `specs/filesystem_agent.md` for detailed documentation on the FileSystemAgent implementation, troubleshooting, and best practices.
- **Keyword-Based Fallbacks**: Uses keyword matching to provide relevant example URLs when DuckDuckGo search fails

#### 3.15.3 WebSearchAgent Implementation
- **Local Implementation**: Updated WebSearchAgent to use local scraping instead of Tavily API
- **GET Endpoint Support**: Added GET endpoint support for UTCP compatibility
- **Enhanced Error Handling**: Improved error handling with graceful degradation
- **Content Processing**: Processes scraped content with the LLM to generate meaningful responses

#### 3.15.4 Benefits of Local Implementation
- **Privacy-First**: All searches and scraping happen locally without sending data to external services
- **No API Keys Required**: Completely local implementation with no external dependencies
- **No Rate Limits**: Unlimited searches without API quotas
- **Cost-Effective**: No API subscription costs
- **Resilient**: Not dependent on external service availability
- **Compliant**: Follows ethical scraping practices with appropriate delays between requests

#### 3.15.5 Technical Architecture
The local web search implementation consists of:
1. **LocalWebScraper**: Handles fetching and parsing web content from URLs
2. **DuckDuckGoSearchEngine**: Performs DuckDuckGo searches and scrapes results
3. **Enhanced Error Handling**: Gracefully handles network errors, parsing failures, and other issues
4. **Content Limiting**: Limits content length to prevent overwhelming the LLM with too much information
5. **Keyword-Based Fallbacks**: Matches query keywords to predefined URL mappings when search fails

This implementation provides the same functionality as the previous Tavily API integration but without external dependencies, API keys, or rate limits.

### 3.15. Temporal Context Integration

The ECE's temporal memory system enhances reasoning by providing chronological context:
-   **Temporal Spine Construction:** The Archivist Agent continuously monitors the Redis cache and builds a chronological spine in the Neo4j knowledge graph.
-   **Memory Linking:** Each processed memory is linked to the appropriate Day node via `[:OCCURRED_AT]` relationships.
-   **Temporal Querying:** Context retrieval includes temporal information to improve relevance and coherence.

### 3.17. Unified Model Proxy Implementation

The ECE now includes a unified model proxy system that centralizes model management:

- **Single Endpoint**: All model requests go through port 8080 for simplified client configuration
- **Backend Switching**: Supports routing between ECE and llama.cpp backends
- **On-Demand Execution**: Models are started/stopped as needed via the proxy
- **Resource Optimization**: Only one model runs at a time to optimize system resources
- **Centralized Monitoring**: Includes built-in health checks and availability monitoring
- **API Compatibility**: Provides consistent OpenAI-compatible API interface across different models

The proxy architecture provides:
- Simplified client configuration with a single endpoint to manage
- Resource optimization by running only one model at a time
- Seamless model switching without client changes
- Centralized logging and monitoring
- Improved system stability by avoiding multiple model conflicts

### 3.18. Simplified Model Server Implementation

As an alternative approach for simpler deployments, the ECE includes a simplified model server:

- **Direct Model Serving**: Runs llama.cpp server directly without proxy routing
- **Single Port Operation**: Runs on port 8080 for standard OpenAI compatibility
- **Easy Management**: Single Python script to start any model from the models/ directory
- **Reduced Complexity**: Fewer moving parts for simpler debugging and maintenance
- **Direct Connection**: Applications connect directly to the llama.cpp server

This simplified approach is ideal for:
- Single-model deployments
- Development and testing environments
- Users who prefer a more straightforward architecture
- Cases where proxy functionality is not needed

To use the simplified approach:
```bash
python simple_model_server.py --model ./models/your-model.gguf --port 8080
```

## 3.19. Simplified ECE Startup Implementation

For users who want a simpler way to start the complete ECE system with both the llama.cpp model server and the full ECE ecosystem, we now offer a unified startup approach:

- **Unified Startup**: Single script that starts both llama.cpp server and ECE ecosystem
- **Simplified Logging**: All output is directed to a single file `logs/ece-llamacpp.txt` to prevent logging complexity issues and eliminate multiple log files
- **Real-time Console Output**: All agent outputs and model inference are displayed directly in the terminal for immediate visibility
- **Easy Management**: Simple scripts to start the complete system with full output visibility
- **Reduced Complexity**: Eliminated complex logging layers that were causing system issues
- **UTF-8 Encoding**: Proper handling of special characters and Unicode output to prevent encoding errors
- **Direct Output Routing**: All output streams directly through the main run script without intermediate logging layers
- **Streamlined Architecture**: Removed complex logger initialization in favor of simple print statements
- **Centralized Log Location**: All system output consolidated in one predictable location (`logs/ece-llamacpp.txt`)
- **Better Debugging**: Single log file makes troubleshooting significantly easier

### Prerequisites

1. Make sure you have the required dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Build llama.cpp (if not already built):
   - On Windows: Use Visual Studio Developer Command Prompt and run `cmake` and `--build` commands
   - On Linux/Mac: Use `make` command in the llama.cpp directory

### Usage

#### Start the Complete Simplified System

To start both the llama.cpp model server and the ECE ecosystem:
```bash
python start_simplified_ecosystem.py --model ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf --port 8080
```

#### Alternative startup scripts

Windows Batch:
```bash
start_simplified_ecosystem.bat ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf 8080
```

Windows PowerShell:
```powershell
./start_simplified_ecosystem.ps1 -ModelPath "./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf" -Port 8080
```

### Options

- `--model PATH`: Specify the model file to use (default: ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf)
- `--port PORT`: Specify the port for the llama.cpp server (default: 8080)
- `--skip-llama`: Skip starting the llama.cpp server
- `--skip-ecosystem`: Skip starting the ECE ecosystem

### Benefits of Simplified Architecture

- **Reduced Complexity**: Fewer moving parts for simpler debugging and maintenance
- **Proper Logging**: All logs directed to the `logs/` directory for easy monitoring
- **Easy Management**: Single script to start the complete system
- **Direct Model Serving**: Applications connect directly to the llama.cpp server
- **Faster Startup Times**: Optimized startup with parallel processing
- **Clearer Connection**: Direct relationship between application and model backend
- **Consistent Behavior**: Same startup process across different platforms
- **Graceful Shutdown**: Both components stop cleanly with proper signal handling

### Running with uv

For users who prefer to use the uv package manager, you can run the simplified ecosystem using a Python wrapper script:

```bash
uv run run_simplified_ecosystem.py --model ./models/gemma-3-4b-it-qat-abliterated.q8_0.gguf --port 8080
```

This avoids issues with uv trying to run PowerShell scripts directly, which previously caused the "WinError 193" error. The `run_simplified_ecosystem.py` wrapper script handles the proper execution of the underlying Python script.

### Logging

All logs are written to the `logs/` directory:
- `logs/debug_log_simplified_startup.txt` - Main log file for the simplified startup process
- Individual agent logs will be in the same directory as before

### Verification

After starting the system, you can verify that both components are running:

1. Check if the llama.cpp server is running:
   ```bash
   curl http://localhost:8080/health
   ```

2. Check if the ECE orchestrator is running:
   ```bash
   curl http://localhost:8000/health
   ```

3. List available models:
   ```bash
   curl http://localhost:8080/v1/models
   ```

### Connecting to the System

Once both components are running, you can connect to the system in two ways:

1. **Direct connection to llama.cpp server** (OpenAI-compatible):
   - Endpoint: `http://localhost:8080/v1`
   - No API key required for local server

2. **Through the ECE orchestrator**:
   - Endpoint: `http://localhost:8000/v1`
   - Uses the UTCP system for tool discovery and execution

### Stopping the System

Press Ctrl+C in the terminal where the script is running to stop both the llama.cpp server and the ECE ecosystem gracefully.

### Troubleshooting

#### Common Issues

1. **Model file not found**:
   - Ensure the model file exists in the specified path
   - Check that the models directory contains the GGUF model file

2. **Port conflicts**:
   - Make sure no other process is using port 8080 or 8000
   - Use `netstat -ano | findstr :8080` to check for processes using the port

3. **llama.cpp server fails to start**:
   - Ensure llama.cpp is properly built
   - Check that the model file is compatible with your llama.cpp build

4. **ECE ecosystem fails to start**:
   - Ensure Docker is running with Neo4j and Redis services
   - Check the logs in the `logs/` directory for error messages

5. **Unicode encoding errors**:
   - If you see 'charmap' codec errors, these have been fixed in the latest version of the scripts
   - The scripts now use proper UTF-8 encoding for log files

#### Log Files

Check the following log files for detailed error information:
- `logs/debug_log_simplified_startup.txt` - Main simplified startup log
- `logs/debug_log_ecosystem.txt` - ECE ecosystem logs
- `logs/debug_log_model_inference.txt` - Model inference logs
- `logs/debug_log_orchestrator.txt` - Orchestrator logs

### 3.18. Agent Lightning Integration

The ECE includes optional integration with Microsoft Agent Lightning for enhanced training and optimization of the QLearningAgent:

- **Event Tracking**: The QLearningAgent emits events for key operations including pathfinding, Q-value updates, and decision making
- **Performance Optimization**: Includes methods to collect performance metrics and optimize learning parameters based on performance data
- **Parameter Adjustment**: Dynamically adjusts learning rate, discount factor, and epsilon based on performance
- **Graceful Fallback**: Includes proper fallback handling when Agent Lightning is not installed
- **Enhanced Monitoring**: Provides better tracking of the agent's decision-making process

### 3.19. Local Web Search Implementation

The ECE has replaced external API dependencies with a completely local web search implementation:

- **LocalWebScraper Class**: Handles fetching and parsing web content from URLs with proper error handling and rate limiting
- **DuckDuckGoSearchEngine Class**: Performs DuckDuckGo searches and scrapes results locally
- **Privacy-Focused**: All searches and scraping happen locally without sending data to external services
- **No Rate Limits**: Unlimited searches without API quotas
- **Ethical Scraping**: Follows ethical practices with appropriate delays between requests
- **Comprehensive Error Handling**: Gracefully handles network errors, parsing failures, and other issues
- **Content Limiting**: Limits content length to prevent overwhelming the LLM with too much information
- **Keyword-Based Fallbacks**: Uses keyword matching to provide relevant example URLs when search fails

---

## 4. System Components & Deployment

-   **OrchestratorAgent:** The central Planner, delegating tasks via UTCP and managing model lifecycle through the ModelManager.
-   **Tool Agents:** `FileSystemAgent`, `WebSearchAgent`.
-   **Memory Cortex:** `Distiller`, `Archivist`, `QLearning`, and `Injector` agents.
-   **ModelManager:** Handles on-demand model execution including starting, stopping, and switching between different models.
-   **Local-First Deployment:** The system is built to run on local scripts, with a future goal of being packaged into a single executable using **PyInstaller**.
-   **Packaging Strategy:** The system will be packaged into a distributable executable with embedded configuration files and a bootstrapping mechanism to check for required services (Neo4j, Redis) before starting agents.
-   **Packaging Process:** The ECE can be packaged into a single executable using PyInstaller via build scripts (`utility_scripts/build_package.bat` for Windows, `utility_scripts/build_package.sh` for Linux/macOS). The packaging process uses `utility_scripts/ece_app.spec` which defines all necessary data files, hidden imports, and binary files to include. The packaged application includes a bootstrapping process that checks for required services before starting agents.
-   **Packaging Fixes:** Fixed ModuleNotFoundError for internal modules like '3c22db458360489351e4__mypyc' by updating PyInstaller spec file with comprehensive hidden imports configuration. The executable now successfully builds and runs with all functionality including advanced model selection and session management.
-   **Deployment Requirements:** The packaged application requires external services (Redis Server, Neo4j Database, LLM Service) to be running separately. The system now uses a decentralized UTCP implementation where each agent serves its own UTCP manual at the /utcp endpoint, eliminating the need for a centralized UTCP Registry.
-   **System Launchers:** Provides easy-to-use launchers with menu interfaces for all major ECE functions including starting complete ECE system, launching model servers, updating configuration, and checking system status.
-   **Script Consolidation:** Consolidated all platform-specific startup scripts to delegate to a single Python entry point for better maintainability and cross-platform compatibility. PowerShell, batch, and shell scripts now delegate to `python start_ecosystem.py` with proper argument forwarding.
-   **Path Handling Improvements:** Implemented robust project root detection using a `.project_root` marker file that works consistently across development environments, PyInstaller executables, and containerized deployments.
-   **Service Health Monitoring:** Replaced fixed time delays with dynamic service health checks that actively verify service availability before proceeding, improving startup reliability.
-   **Centralized Configuration Management:** Created a unified ConfigManager class that provides consistent configuration handling across all ECE components with validation, versioning, and backup functionality.
-   **UTCP Compatibility Enhancements:** Added GET endpoint support to filesystem agent for better compatibility with UTCP clients that use query parameters instead of JSON bodies.
-   **Filesystem Agent Fixes:** Resolved WinError 10013 "An attempt was made to access a socket in a way forbidden by its access permissions" by identifying and killing conflicting processes using port 8006. Added proper GET endpoint support to resolve 422 "Unprocessable Content" errors when UTCP clients call filesystem tools with query parameters.
-   **Memory Management:** Enhanced memory management capabilities for Windows systems with configurable limits to prevent crashes.
-   **Error Handling:** Improved error handling and graceful degradation mechanisms throughout the system.
-   **Logging Infrastructure:** Implemented comprehensive logging infrastructure with file and console output for better debugging and monitoring.

---

## 5. Validation, Refinement, and Evolution Strategy

With the core architecture complete, the ECE transitions from implementation to validation, refinement, and continuous evolution:

### 5.1 System Validation & GUI Testing (Phase 6)
The system undergoes rigorous end-to-end testing, focusing on real-world usage scenarios to ensure all components work together seamlessly.

### 5.2 TRM Specialization (Phase 7)
The mock TRM service will be replaced with fine-tuned specialized models trained on custom datasets for improved reasoning capabilities.

### 5.3 Continuous Improvement (Phase 8)
The system enters a continuous evolution phase with:
- Active performance monitoring and optimization
- Expansion of specialized TRM models for different tasks
- Continuous curation and expansion of the knowledge graph
- Enhanced self-modification capabilities

---

## 6. Co-Evolutionary Mandate

The system must be capable of understanding and modifying its own codebase, a goal directly supported by the deep reasoning capabilities enabled by Markovian Thinking.