# ECE - Task List v4.1

This document outlines the high-priority tasks for the current development cycle of the External Context Engine.

---

## T-001: Local Development Transition

**Objective:** Transition the ECE from a Docker-dependent architecture to a fully local, script-based development environment.

-   **T-001.1:** Update all configuration files (`.env`, `config.yaml`) to use `localhost` for all service URLs (Redis, Neo4j, UTCP Registry, etc.). This includes properly configuring LLM providers as detailed in `spec.md`.
-   **T-001.2:** Create individual startup scripts (`.bat` or `.sh`) for each agent and service (`Distiller`, `Injector`, `Archivist`, `QLearning`, `UTCP Registry`, `FileSystemAgent`, `WebSearchAgent`).
-   **T-001.3:** Create a main master script (`start_ece_local.bat`) that launches all necessary services and agents in the correct order.
-   **T-001.4:** Document the new local setup process in `README.md`.

---

## T-012: LLM Configuration and Setup

**Objective:** Ensure proper setup and configuration of all supported LLM providers.

-   **T-012.1:** Verify Ollama provider configuration and connectivity.
-   **T-012.2:** Verify Docker Desktop provider configuration and connectivity.
-   **T-012.3:** Implement automated setup script for llama.cpp if not already available on the system.
-   **T-012.4:** Document Windows-specific setup procedures for llama.cpp in the project specifications.
-   **T-012.5:** Create validation tests to ensure each LLM provider works correctly with the ECE.

---

## T-002: Performance Optimization with Cython/C++

**Objective:** Identify and optimize performance-critical bottlenecks by integrating C++ code via Cython.

-   **T-002.1:** Profile the ECE application using `cProfile` and `snakeviz` to identify hotspots, particularly within the `QLearningAgent` and `DistillerAgent`.
-   **T-002.2:** Rewrite the identified bottleneck functions (e.g., Q-table updates, pathfinding algorithms) in C++.
-   **T-002.3:** Create Cython wrapper files (`.pyx`) to bridge the new C++ code with the existing Python codebase.
-   **T-002.4:** Implement a `setup.py` file to compile the Cython extensions.
-   **T-002.5:** Integrate the compiled, high-performance modules back into the Python agents.

## T-005: Phase 3 - Performance Profiling and Optimization

**Objective:** Execute the full Phase 3 plan for performance profiling and optimization using C++ and Cython.

-   **T-005.1:** Conduct comprehensive profiling of the ECE stack under load using `cProfile` and `snakeviz` to identify bottlenecks across all agents.
-   **T-005.2:** Focus on the `QLearningAgent` for initial optimization, identifying the most computationally expensive functions (e.g., Q-table updates, pathfinding algorithms).
-   **T-005.3:** Design and implement C++ equivalents of the most critical bottleneck functions identified in profiling.
-   **T-005.4:** Create Cython integration layer to bridge C++ implementations with existing Python codebase.
-   **T-005.5:** Update `setup.py` to include all new Cython extensions and C++ compilation steps.
-   **T-005.6:** Integrate optimized modules back into the ECE agents and conduct benchmarking tests.
-   **T-005.7:** Document performance improvements achieved and update development guidelines to include C++/Cython optimization workflow.

---

## T-003: Core Logic Hardening

**Objective:** Address the known prompt-sizing issue to improve system stability.

-   **T-003.1:** Analyze the `OrchestratorAgent` and its interaction with the `llama.cpp` server to identify the root cause of the `context overflow` and `invalid argument` errors.
-   **T-003.2:** Implement logic within the ECE to intelligently truncate or manage prompts, ensuring they do not exceed the `llama.cpp` server's configured context window (currently stabilized at 32k).
-   **T-003.3:** Add unit tests to verify that oversized prompts are handled gracefully.

## T-006: Phase 4 - Core Logic and Stability Enhancements

**Objective:** Execute the full Phase 4 plan to resolve context overflow issues and improve system stability.

-   **T-006.1:** Implement robust prompt truncation and management logic within the `OrchestratorAgent` using token counting and intelligent content preservation techniques.
-   **T-006.2:** Develop a context-aware prompt manager that can dynamically adjust content based on model capabilities and context window limits.
-   **T-006.3:** Enhance error handling and reporting across all agents with detailed logging for debugging context overflow issues.
-   **T-006.4:** Create a comprehensive integration test suite specifically targeting prompt management and context overflow scenarios.
-   **T-006.5:** Implement graceful fallback strategies when context limits are reached, including summarization or chunking approaches.
-   **T-006.6:** Add detailed metrics and monitoring for prompt sizes and context usage across the system.
-   **T-006.7:** Update documentation to include best practices for prompt management and context handling.

---

## T-004: Application Packaging

**Objective:** Package the entire ECE application into a single, distributable executable.

-   **T-004.1:** Install and configure **PyInstaller**.
-   **T-004.2:** Create a main entry point script (`run_all_agents.py`) that initializes and runs all agent FastAPI applications.
-   **T-004.3:** Develop a build script (`build.bat`) that uses PyInstaller to package the application, ensuring all necessary data files (`config.yaml`, `.env`, and the `ece` directory) are included.
-   **T-004.4:** Test the generated executable to ensure all agents start and communicate correctly in the packaged environment.

## T-007: Phase 5 - Packaging and Distribution

**Objective:** Execute the full Phase 5 plan to package the ECE into a distributable executable.

-   **T-007.1:** Configure PyInstaller with proper hooks and spec file to handle all ECE dependencies including FastAPI, async components, and C++ extensions.
-   **T-007.2:** Create a comprehensive build script that automates the entire packaging process for different platforms (Windows, Linux, macOS).
-   **T-007.3:** Implement a bootstrapping mechanism in the packaged application to check for required services (Neo4j, Redis) before starting agents.
-   **T-007.4:** Add embedded configuration files to the executable to simplify deployment.
-   **T-007.5:** Create distribution testing procedures to verify the executable works correctly on clean systems without Python dependencies.
-   **T-007.6:** Document the packaging process and deployment requirements for end users.
-   **T-007.7:** Implement versioning and update mechanisms for the packaged application.

---

## Phase 17: Architectural Evolution (Markovian Thinking)

-   **TASK-17.3: Implement TRM Service Client**
    -   **Description:** Develop a generic `TRM_Client` class in Python. This class will be responsible for communicating with the specialized TRM Service (the "Markovian Thinker") running on a separate port (e.g., 8081).
-   **TASK-17.4: Implement Markovian Loop in Orchestrator**
    -   **Description:** Refactor the `OrchestratorAgent` to implement the full Markovian reasoning loop as described in `specs/reasoning_flow.md`. This involves:
        1.  Calling the Primary LLM for the initial draft.
        2.  Iteratively calling the `TRM_Client` for refinement.
        3.  Managing the "carryover" state between chunks.
        4.  Sending the final, polished thought process to the Primary LLM for the final answer.

## T-008: Phase 17 - Markovian Thinking Implementation

**Objective:** Execute the full Phase 17 plan to implement the Markovian Thinking paradigm.

-   **T-008.1:** [COMPLETED] Develop the TRM_Client class for communicating with the specialized TRM Service.
-   **T-008.2:** [COMPLETED] Create a TRM service mock or implementation that can perform iterative refinement.
-   **T-008.3:** [COMPLETED] Refactor OrchestratorAgent to implement the Markovian reasoning loop.
-   **T-008.4:** [COMPLETED] Implement carryover state management between reasoning chunks.
-   **T-008.5:** [COMPLETED] Add configuration options to enable/disable Markovian thinking for specific queries.
-   **T-008.6:** [IN PROGRESS] Create integration tests for the Markovian reasoning workflow.
-   **T-008.7:** [IN PROGRESS] Document the Markovian thinking implementation and usage.

## T-014: Phase 19 - Enhanced Markovian Integration

**Objective:** Fully integrate Markovian Thinking with the EnhancedOrchestratorAgent and ensure robust operation.

-   **T-014.1:** [COMPLETED] Implement the Markovian reasoning analyzer to determine when to use Markovian thinking vs. parallel thinking.
-   **T-014.2:** [COMPLETED] Integrate the MarkovianThinker class with the EnhancedOrchestratorAgent.
-   **T-014.3:** [COMPLETED] Implement proper error handling and fallback mechanisms from Markovian to parallel thinking.
-   **T-014.4:** [COMPLETED] Optimize chunk size and state carryover parameters based on performance testing.
-   **T-014.5:** [IN PROGRESS] Create comprehensive test suite for Markovian reasoning functionality.
-   **T-014.6:** [IN PROGRESS] Document performance characteristics and ideal use cases for Markovian reasoning.

## T-015: Phase 20 - Multi-Agent Coordination Implementation

**Objective:** Implement enhanced coordination between agents based on research findings from "Emergent Coordination in Multi-Agent Language Models".

-   **T-015.1:** [COMPLETED] Assign detailed personas to each thinker agent to create stable identity-linked differentiation.
-   **T-015.2:** [COMPLETED] Implement Theory of Mind (ToM) instructions for thinkers to consider other agents' likely actions.
-   **T-015.3:** [COMPLETED] Add coordination analysis metrics (synergy, diversity, complementarity) to measure collective intelligence.
-   **T-015.4:** [COMPLETED] Update thinker communication to incorporate ToM considerations during parallel thinking.
-   **T-015.5:** [IN PROGRESS] Validate coordination improvements through performance testing and metrics analysis.
-   **T-015.6:** [PENDING] Document coordination analysis tools and their interpretation for system optimization.

## T-013: Phase 18 - Enhanced Orchestrator Implementation

**Objective:** Execute the full Phase 18 plan to implement the EnhancedOrchestratorAgent with improved context management, parallel thinking, and response synthesis.

-   **T-013.1:** Implement the `process_prompt_with_context_management` method with proper context overflow prevention.
-   **T-013.2:** Develop parallel thinking architecture with multiple specialized thinkers.
-   **T-013.3:** Create synthesis thinker to combine insights from multiple sources into coherent responses.
-   **T-013.4:** Integrate ArchivistClient for knowledge retrieval and context management.
-   **T-013.5:** Implement robust error handling for individual thinker failures.
-   **T-013.6:** Create integration tests for the EnhancedOrchestratorAgent's processing flow.
-   **T-013.7:** Ensure backward compatibility with existing endpoints and update documentation.

---

## T-009: Phase 6 - System Validation & GUI Testing

**Objective:** Execute comprehensive end-to-end validation of the ECE system.

-   **T-009.1:** Design comprehensive test scenarios covering all ECE functionality.
-   **T-009.2:** Perform end-to-end testing of the complete workflow from user input to final output.
-   **T-009.3:** Validate GUI integration with all ECE components.
-   **T-009.4:** Test Markovian reasoning loop with complex real-world queries.
-   **T-009.5:** Conduct performance testing under load with multiple concurrent requests.
-   **T-009.6:** Identify and document any bugs or integration issues.
-   **T-009.7:** Create automated test suites for ongoing validation.

---

## T-010: Phase 7 - TRM Fine-Tuning & Specialization

**Objective:** Replace the mock TRM service with a fine-tuned specialized model.

-   **T-010.1:** Create a dataset of critique and refined_plan examples for fine-tuning.
-   **T-010.2:** Fine-tune the AI21-Jamba-Reasoning-3B model on the custom dataset.
-   **T-010.3:** Deploy the fine-tuned model locally on port 8081.
-   **T-010.4:** Validate the fine-tuned TRM service performance against the mock.
-   **T-010.5:** Optimize the fine-tuned model for latency and accuracy.
-   **T-010.6:** Document the fine-tuning process and results.

---

## T-011: Phase 8 - Continuous Improvement & Co-Evolution

**Objective:** Implement continuous improvement processes for ongoing system evolution.

-   **T-011.1:** Implement performance monitoring and profiling tools for ongoing optimization.
-   **T-011.2:** Identify additional tasks suitable for specialized TRM models.
-   **T-011.3:** Develop processes for continuous knowledge graph curation and expansion.
-   **T-011.4:** Enhance self-modification capabilities for codebase understanding.
-   **T-011.5:** Create quality assurance procedures for ongoing validation.
-   **T-011.6:** Document the continuous improvement processes and protocols.