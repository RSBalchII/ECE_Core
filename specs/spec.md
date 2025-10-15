# External Context Engine (ECE) - Specification v4.2

## 1. Project Vision: The Ark

The primary goal of the ECE project is the creation of "The Ark," a sovereign, local-first AI that functions as the Architect's **Externalized Executive Function**. It must be private, efficient, and powerful, operating entirely on local hardware without reliance on cloud services.

---

## 2. Architectural Philosophy

The ECE architecture represents a deliberate move **away from brittle, monolithic AI systems**. The core philosophy is to build a robust, self-correcting, and intelligent **multi-agent system** composed of smaller, specialized, and independently deployable components.

---

## 3. LLM Configuration

The ECE supports multiple LLM providers with a flexible configuration system. The configuration is managed through the `config.yaml` file:

```yaml
llm:
  active_provider: ollama  # Can be ollama, docker_desktop, or llama_cpp
  providers:
    ollama:
      model: "granite3.1-moe:3b-instruct-q8_0"
      api_base: "http://localhost:11434/v1"
    docker_desktop:
      model: "ai/mistral:latest"
      api_base: "http://localhost:12434/v1"
    llama_cpp:
      model_path: "/path/to/your/model.gguf"
      api_base: "http://localhost:8080/v1"
```

### Supported Providers

- **Ollama**: Default provider using local Ollama instance
- **Docker Desktop**: OpenAI-compatible endpoint for Docker-based models
- **Llama.cpp**: High-performance local inference with GGUF models

To switch providers, simply change the `active_provider` value in the configuration file.

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
   - Start with: `server.exe -m path\to\model.gguf -c 4096`
   - Update config.yaml to point to the correct model path and server endpoint

---

## 3. Core Technical Strategy

The system is designed to achieve state-of-the-art reasoning capabilities on local hardware by implementing principles from cutting-edge research.

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
-   **EnhancedOrchestratorAgent:** The current implementation uses EnhancedOrchestratorAgent which implements context-aware prompt management, parallel thinking with specialized thinkers, and synthesis of responses. It includes a `process_prompt_with_context_management` method that handles prompt processing with context retrieval from the Archivist, parallel thinking with multiple specialized thinkers, and synthesis of responses.

### 3.5. Markovian Thinking Architecture

To enable deep reasoning on local hardware, the ECE implements a sophisticated Markovian Thinking architecture based on the research paper "The Markovian Thinker":

-   **TRM Client Integration:** The system includes a TRM_Client class to communicate with specialized Tokenized Reasoning Model services.
-   **Iterative Refinement:** Implements a "propose -> critique -> refine" loop for improving thought processes.
-   **Chunked Reasoning:** Breaks complex problems into fixed-size chunks with textual carryover to maintain context, allowing extremely long reasoning while using bounded memory.
-   **Intelligent Routing:** Determines when to use Markovian thinking based on query complexity and length using the ReasoningAnalyzer.
-   **Carryover Management:** Maintains consistency between reasoning iterations through textual state carryover.
-   **Delethink Environment:** Implements the Delethink RL environment concept where reasoning proceeds in fixed-size chunks, and at each boundary the environment resets the context and reinitializes the prompt with a short carryover from the previous chunk.
-   **Linear Compute Scaling:** Enables linear compute with constant memory with respect to thinking length, decoupling "how long the model thinks" from "how much context it must process."
-   **Fallback Mechanisms:** Includes robust fallback to parallel thinking when Markovian reasoning encounters issues.

### 3.6. Coordination in Multi-Agent Systems

Based on research findings from "Emergent Coordination in Multi-Agent Language Models", the ECE implements enhanced coordination between agents:

-   **Thinker Personas:** Each thinker agent is assigned a detailed persona with background, expertise, and personality traits to create stable identity-linked differentiation.
-   **Theory of Mind (ToM) Integration:** Thinker agents are instructed to consider what other agents might do and how their actions might affect the group outcome, enabling more effective collaboration.
-   **Role Complementarity:** Different thinkers are assigned complementary roles (Optimist, Pessimist, Analytical, Creative, Pragmatic, Strategic, Ethical) to ensure diverse perspectives contribute to the solution.
-   **Coordination Analysis:** The system includes metrics to measure synergy, diversity, and complementarity among thinker agents to ensure productive collective intelligence.
-   **Emergent Behavior Steering:** Prompt design and role assignments are used to steer the system from mere aggregates to higher-order collectives with coordinated behavior.

### 3.3. Performance Optimization: Python, Cython, and C++

To achieve the required performance, the ECE will adopt a hybrid development model:
-   **Python:** Used for high-level orchestration and non-performance-critical logic.
-   **C++/Cython:** Performance-critical components, identified through profiling with tools like `cProfile` and `snakeviz`, will be rewritten in C++ and bridged to Python using Cython.
-   **Profiling-Driven Development:** Regular performance profiling will be integrated into the development process to continuously identify and address bottlenecks as the system evolves.

---

## 4. System Components & Deployment

-   **OrchestratorAgent:** The central Planner, delegating tasks via UTCP.
-   **Tool Agents:** `FileSystemAgent`, `WebSearchAgent`.
-   **Memory Cortex:** `Distiller`, `Archivist`, `QLearning`, and `Injector` agents.
-   **Local-First Deployment:** The system is built to run on local scripts, with a future goal of being packaged into a single executable using **PyInstaller**.
-   **Packaging Strategy:** The system will be packaged into a distributable executable with embedded configuration files and a bootstrapping mechanism to check for required services (Neo4j, Redis) before starting agents.

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