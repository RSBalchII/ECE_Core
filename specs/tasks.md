# Core ECE Project - Task List v3.0

This document outlines the tasks required to implement the ECE v3.0 architecture.

### MVP: Implement Core Cohesion Loop

- [x] **Task 1: Context Cache**
  - [x] Ensure it is fully operational as a fixed-size, short-term memory buffer.
- [x] **Task 2: Distiller Agent**
  - [x] Periodically read the entire contents of the Context Cache.
  - [x] Condense the raw context into a targeted, summarized memory.
  - [x] Send the condensed memory to the Archivist Agent.
- [x] **Task 3: Archivist Agent**
  - [x] Successfully route data between the Q-Learning Agent, Distiller, and Injector.
  - [x] Intercept and capture truncated data from the Context Cache before it's lost.
- [ ] **Task 4: Injector Agent**
  - [ ] Check for verbatim duplicates before writing any new data to the graph.
  - [ ] If the data is new, it creates a new node.
  - [ ] If the data is a duplicate, it locates the existing node and appends the new information as a timestamped "additional context".
- [x] **Task 5: Q-Learning Agent**
  - [x] Ensure it is operational and actively analyzing the data flow to refine relationships within the graph.

### Phase 1: Foundational Upgrades (Lower Priority)

- [ ] **Task 1.1: Stabilize Core Environment**
  - [ ] Resolve all startup errors and Docker networking issues.
  - [ ] Ensure all Tier 2 agents are correctly configured and communicating with the Ollama server.
- [ ] **Task 1.2: Implement POML Protocol**
  - [ ] Define the core `POML` schemas for inter-agent communication.
  - [ ] Refactor all agent API endpoints to send and receive `POML` directives.

### Phase 2: Implement Memory Cortex (Lower Priority)

- [ ] **Task 2.1: Implement ArchivistAgent**
  - [ ] Resolve the `404` error between the Orchestrator and the Archivist.
  - [ ] Implement the `continuous_temporal_scanning` function as a robust, always-on process.
  - [ ] Implement intelligent context retrieval in the `/context` endpoint.
- [ ] **Task 2.2: Implement DistillerAgent**
  - [ ] Create the `DistillerAgent` to summarize and structure data from the Redis cache.
- [ ] **Task 2.3: Implement InjectorAgent and QLearningAgent**
  - [ ] Implement the `InjectorAgent` to persist data to the Neo4j knowledge graph.
  - [ ] Implement the `QLearningAgent` to optimize context retrieval.
  - [ ] Activate the continuous training loop in the `QLearningAgent`.
  - [ ] Improve the reward mechanism and exploration strategy in the `QLearningAgent`.

### Phase 3: Advanced Reasoning Workflows (Lower Priority)

- [ ] **Task 3.1: Implement Asynchronous Complex Reasoning**
  - [ ] Refactor the `Orchestrator` to handle complex reasoning tasks asynchronously.
  - [ ] Implement a polling mechanism in the client to retrieve the results of complex reasoning tasks.
- [ ] **Task 3.2: Implement Exploratory Problem-Solving Loop**
  - [ ] Create the `ExplorerAgent` and `CritiqueAgent`.
  - [ ] Develop the secure `SandboxModule` for code execution.
  - [ ] Implement the iterative, score-based loop logic within the `Orchestrator`.

### Phase 4: Improve Conversational Flow (Lower Priority)

- [ ] **Task 4.1: Enhance Final Response Generation**
  - [ ] Modify the `OrchestratorAgent` to use the context from the cache and the synthesized thoughts from the thinkers to generate a final, more conversational response.

### Phase 5: Context Cache Solidification (Immediate Priority)

- [ ] **Task 5.1: Solidify Context Cache Functionality**
  - [ ] Ensure robust population of the Context Cache during multi-step conversations.
  - [ ] Verify successful utilization of cached content to inform subsequent responses.
  - [ ] Implement comprehensive unit and integration tests for the Context Cache.

### Phase 6: Advanced System Enhancements (Lower Priority)

- [ ] **Task 6.1: Implement "Vault" Agent (Tier 0 Security)**
  - [ ] Design and implement the `VaultAgent` as the first point of contact for all external inputs.
  - [ ] Integrate input sanitization and threat detection mechanisms.
  - [ ] Develop quarantine and alert protocols, including secure logging.
- [ ] **Task 6.2: Refactor for POML Inter-Agent Communication**
  - [ ] Update all agents to format their outputs into the new POML structure.
  - [ ] Modify `ArchivistAgent` and `QLearningAgent` to parse POML blocks and utilize metadata for richer graph creation.
- [ ] **Task 6.3: Implement "Janitor" Agent (Memory & Graph Hygiene)**
  - [ ] Design and implement the `JanitorAgent` for asynchronous graph maintenance.
  - [ ] Implement organic POML conversion for legacy nodes.
  - [ ] Develop data integrity checks (e.g., ISO 8601 timestamp standardization).
  - [ ] Implement de-duplication logic for graph nodes.
- [ ] **Task 6.4: Implement "Oculus" Agent (Tier 1 Visual Cortex & Motor Control)**
  - [ ] Integrate a screen capture utility.
  - [ ] Develop or integrate a Visual Language Model (VLM) for UI understanding.
  - [ ] Implement an input control library for programmatic mouse and keyboard control.
  - [ ] Design and implement the See-Think-Act operational loop for visual interaction.