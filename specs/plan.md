# ECE - Development Plan v4.1

This document outlines the phased development plan for the External Context Engine, focusing on the transition to a local, high-performance architecture.

---

## Phase 1: Transition to Local-First Development (Current Focus)

**Goal:** Eliminate the Docker dependency for core development and enable a streamlined, script-based local workflow.

1.  **Configuration Update:** Modify all service URLs in `.env` and `config.yaml` to point to `localhost`. This includes updating LLM provider configurations as detailed in `spec.md`.
2.  **Script Creation:** Develop individual and master startup scripts for all agents and services.
3.  **Testing:** Thoroughly test the local script-based setup to ensure all agents can communicate correctly.
4.  **Documentation:** Update the main `README.md` to reflect the new local setup process.

---

## Phase 2: Core Architectural Upgrade (Markovian Thinking)

**Goal:** Implement the Markovian Thinking paradigm to enable deep reasoning on local hardware. This involves integrating a dual-LLM PEVG model with a specialized TRM service.

1.  **TRM Service Integration:** Develop a client (the `TRM_Solver` class) to interact with the specialized TRM Service (the "Markovian Thinker").
2.  **OrchestratorAgent Upgrade:** Refactor the `OrchestratorAgent` to implement the full Markovian reasoning loop as described in `specs/reasoning_flow.md`. This includes managing the interaction between the Primary LLM and the TRM Service.
3.  **Integration and Testing:** Conduct thorough testing to validate the new Markovian-based reasoning workflow.

---

## Phase 3: Performance Profiling and Optimization

**Goal:** Identify and refactor performance bottlenecks using C++ and Cython.

1.  **Profiling:** Use `cProfile` and `snakeviz` to conduct a thorough performance analysis of the entire ECE stack under load. This includes all agents with a particular focus on the `QLearningAgent` and `DistillerAgent` which are expected to have significant computational overhead.
2.  **C++ Implementation:** Rewrite the most computationally expensive functions (identified in profiling) in C++. The initial focus will be on the `QLearningAgent`, specifically Q-table updates, pathfinding algorithms, and embedding generation functions.
3.  **Cython Integration:** Bridge the new C++ code into the Python application using Cython extensions, creating efficient interfaces between Python and C++ components.
4.  **Build System Integration:** Update the build process to include compilation of C++ code and Cython extensions, ensuring seamless integration into the development and deployment pipeline.
5.  **Benchmarking:** Re-run performance tests to measure the impact of the optimizations, comparing before and after metrics for key operations.
6.  **Documentation:** Update development documentation to include guidelines for implementing performance-critical components using C++ and Cython.

---

## Phase 4: Core Logic and Stability Enhancements

**Goal:** Resolve the critical `context overflow` issue and improve the overall stability of the system.

1.  **Prompt Management:** Implement robust prompt truncation and management logic within the `OrchestratorAgent`. This includes developing a context-aware prompt manager that can dynamically adjust content based on model capabilities and context window limits.
2.  **Intelligent Truncation:** Use token counting and intelligent content preservation techniques to ensure critical information is maintained when prompts are truncated.
3.  **Error Handling:** Enhance error handling and reporting across all agents with detailed logging for debugging context overflow issues.
4.  **Fallback Strategies:** Implement graceful fallback strategies when context limits are reached, using summarization or chunking approaches.
5.  **Integration Testing:** Create a comprehensive suite of integration tests specifically targeting prompt management and context overflow scenarios.
6.  **Monitoring:** Add detailed metrics and monitoring for prompt sizes and context usage across the system.
7.  **Documentation:** Update development documentation to include best practices for prompt management and context handling.

---

## Phase 5: Packaging and Distribution

**Goal:** Package the ECE into a single, distributable executable for ease of deployment.

1.  **PyInstaller Setup:** Configure PyInstaller with proper hooks and spec file to handle all ECE dependencies including FastAPI, async components, and C++ extensions.
2.  **Build Automation:** Develop cross-platform build scripts to automate the PyInstaller packaging process for Windows, Linux, and macOS.
3.  **Bootstrapping Mechanism:** Implement a bootstrapping mechanism in the packaged application to check for required services (Neo4j, Redis) before starting agents.
4.  **Embedded Configuration:** Add embedded configuration files to the executable to simplify deployment while allowing for customization.
5.  **Distribution Testing:** Create comprehensive testing procedures to verify the executable works correctly on clean systems without Python dependencies.
6.  **Versioning and Updates:** Implement versioning and update mechanisms for the packaged application.
7.  **Documentation:** Document the packaging process and deployment requirements for end users.

## Phase 17: Architectural Evolution (Markovian Thinking)

**Goal:** Implement the Markovian Thinking paradigm to enable deep reasoning on local hardware through a dual-LLM PEVG model with a specialized TRM service.

1.  **TRM Service Integration:** [COMPLETED] Develop the TRM_Client class to interact with the specialized TRM Service (the "Markovian Thinker").
2.  **Markovian Thinker Implementation:** [COMPLETED] Implement the core Markovian reasoning logic that breaks down complex problems into chunks with textual carryover.
3.  **OrchestratorAgent Integration:** [COMPLETED] Refactor the OrchestratorAgent to implement the full Markovian reasoning loop, including: (1) calling the Primary LLM for the initial draft, (2) iteratively calling the TRM_Client for refinement, (3) managing the "carryover" state between chunks, and (4) sending the final, polished thought process to the Primary LLM for the final answer.
4.  **Chunked Reasoning:** [COMPLETED] Implement chunked reasoning capabilities for processing long texts using the Markovian approach.
5.  **Intelligent Routing:** [COMPLETED] Add logic to determine when to use Markovian thinking vs. standard processing based on query complexity.
6.  **Integration and Testing:** [IN PROGRESS] Conduct thorough testing to validate the new Markovian-based reasoning workflow.

## Phase 18: Enhanced Orchestrator Implementation

**Goal:** Implement the EnhancedOrchestratorAgent with improved context management, parallel thinking, and response synthesis.

1.  **Context-Aware Processing:** [COMPLETED] Implement the `process_prompt_with_context_management` method to handle context overflow prevention.
2.  **Parallel Thinking Architecture:** [COMPLETED] Develop system for engaging multiple specialized thinkers in parallel to process prompts from different perspectives.
3.  **Response Synthesis:** [COMPLETED] Create synthesis thinker to combine insights from multiple specialized thinkers into coherent responses.
4.  **Archivist Integration:** [COMPLETED] Ensure proper integration with ArchivistClient for knowledge retrieval and context management.
5.  **Enhanced Error Handling:** [COMPLETED] Implement robust error handling for individual thinker failures while maintaining system stability.
6.  **Integration and Testing:** [COMPLETED] Validate the EnhancedOrchestratorAgent's new processing flow end-to-end.

## Phase 19: Markovian Reasoning Integration & Optimization

**Goal:** Fully integrate Markovian Thinking with the EnhancedOrchestratorAgent and optimize its operation.

1.  **[COMPLETED] Markovian Analyzer Integration:** Integrate the reasoning analyzer to determine when to use Markovian vs. parallel thinking based on prompt characteristics.
2.  **[COMPLETED] Fallback Mechanisms:** Implement robust fallback systems from Markovian to parallel thinking in case of failures.
3.  **[COMPLETED] Performance Optimization:** Fine-tune chunk size and state carryover parameters for optimal performance.
4.  **[IN PROGRESS] Comprehensive Testing:** Create extensive test suite covering various reasoning scenarios and edge cases.
5.  **[IN PROGRESS] Documentation:** Document performance characteristics, ideal use cases, and operation guidelines for Markovian reasoning.

## Phase 20: Multi-Agent Coordination & Emergence

**Goal:** Implement enhanced coordination between agents based on research findings from "Emergent Coordination in Multi-Agent Language Models".

1.  **[COMPLETED] Thinker Personas:** Assign detailed personas to each thinker agent to create stable identity-linked differentiation and specialized roles.
2.  **[COMPLETED] Theory of Mind Integration:** Implement instructions for thinkers to consider what other agents might do and how their actions affect the group outcome.
3.  **[COMPLETED] Coordination Analysis:** Implement metrics to measure synergy, diversity, and complementarity among thinker agents to ensure productive collective intelligence.
4.  **[COMPLETED] Emergent Behavior Steering:** Use prompt design and role assignments to steer the system from mere aggregates to higher-order collectives.
5.  **[IN PROGRESS] Performance Validation:** Validate that coordination improvements lead to better collective performance, balancing complementarity with integration.
6.  **[PENDING] Coordination Documentation:** Document coordination mechanisms, analysis tools, and optimization strategies for multi-agent systems.

---

## Phase 6: System Validation & GUI Testing

**Goal:** Rigorously test the entire end-to-end workflow through the GUI to ensure every agent, every protocol, and every new reasoning loop functions as expected in a real-world use case.

1.  **End-to-End Testing:** Perform comprehensive testing of the complete system workflow from user input to final output.
2.  **GUI Integration Testing:** Validate that the GUI properly interfaces with all ECE components.
3.  **Agent Communication Verification:** Ensure all agents communicate correctly through UTCP and other protocols.
4.  **Markovian Loop Validation:** Test the Markovian reasoning flow with complex real-world queries.
5.  **Performance Under Load:** Test system performance with multiple concurrent requests.
6.  **Bug Identification & Fixing:** Identify and resolve any latent bugs or integration issues that emerge during testing.

---

## Phase 7: TRM Fine-Tuning & Specialization

**Goal:** Replace the mock TRM service with a real, fine-tuned model to create specialized reasoning capabilities.

1.  **Dataset Creation:** Collaborate to generate a dataset of critique and refined_plan examples for fine-tuning.
2.  **TRM Training:** Fine-tune the AI21-Jamba-Reasoning-3B model on the custom dataset to create a specialized "Planner Refinement Model".
3.  **Model Deployment:** Deploy the fine-tuned model locally on port 8081, replacing the mock service.
4.  **Validation:** Test the fine-tuned TRM service to ensure it performs better than the mock implementation.
5.  **Iteration:** Fine-tune additional TRM models for different specialized tasks as needed.

---

## Phase 8: Continuous Improvement & Co-Evolution (The Kaizen Phase)

**Goal:** Enter a continuous loop of improvement to evolve the system into an intelligent, sovereign AI.

1.  **Performance Monitoring:** Actively profile the system during use to identify new bottlenecks for C++/Cython optimization.
2.  **TRM Expansion:** Identify other tasks within the ECE that would benefit from specialized TRM models (e.g., "Code Refinement Model," "Data Analysis Model").
3.  **Knowledge Graph Curation:** Continuously refine and expand the Neo4j knowledge graph based on interactions.
4.  **Architecture Evolution:** Adapt and improve the multi-agent architecture based on usage patterns and requirements.
5.  **Self-Modification:** Enhance the system's ability to understand and modify its own codebase.
6.  **Quality Assurance:** Maintain ongoing testing and validation procedures to ensure system reliability.
