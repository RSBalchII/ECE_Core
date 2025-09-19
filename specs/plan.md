# Core ECE Project - Implementation Plan v3.0

This document outlines the high-level technical plan for the enhanced ECE.

### 1. MVP Battle Plan: The Core Cohesion Loop

The immediate priority is to implement a full, closed-loop cycle of context processing, learning, and memory management. This will provide a powerful and complete story to tell, demonstrating the core value of the ECE.

*   **Context Cache:** Must be fully operational as a fixed-size, short-term memory buffer.
*   **Distiller Agent:** Periodically reads the entire contents of the Context Cache, condenses this raw context into a targeted, summarized memory, and sends the condensed memory back to the Archivist Agent.
*   **Archivist Agent:** Must successfully route data between the Q-Learning Agent, Distiller, and Injector. It must also intercept and capture truncated data from the Context Cache before it's lost.
*   **Injector Agent:** Before writing any new data to the graph, it must check for verbatim duplicates. If the data is new, it creates a new node. If the data is a duplicate, it locates the existing node and appends the new information as a timestamped "additional context."
*   **Q-Learning Agent:** Must be operational and actively analyzing the data flow to refine relationships within the graph.

### 2. Environment and Containerization
* **Strategy:** Continue using **Docker Compose** to orchestrate all services (`Orchestrator`, agents, `Neo4j`, `Redis`). The environment will be updated to include the new `ExplorerAgent`, `CritiqueAgent`, `VaultAgent`, `JanitorAgent`, `OculusAgent`, and a secure `SandboxModule` container.

### 3. Inter-Agent Communication
* **Strategy:** Implement the **`POML` Inter-Agent Communication Protocol**. All internal API calls between agents (via FastAPI) will pass `POML` documents as the payload, ensuring structured, unambiguous tasking. This will involve refactoring existing agent endpoints and updating data parsing logic in agents like the `Archivist` and `QLearningAgent`.

### 4. Core Logic Enhancements
* **Orchestrator:** The `Orchestrator`'s main loop has been refactored to handle complex reasoning tasks asynchronously. It now initiates a background task for the thinking and synthesis process and immediately returns an `analysis_id` to the user. It also extracts keywords from the user's prompt and sends them to the `Archivist` for context retrieval.
* **Archivist:** The `Archivist` has been updated to receive keywords from the `Orchestrator` and use them to query the `QLearningAgent` for relevant context. It will be further enhanced to manage the context from the `QLearningAgent` and update the context cache. It will also be updated to parse incoming POML blocks.
* **QLearningAgent:** The `QLearningAgent` has been updated to perform keyword-based searches on the knowledge graph. The continuous training loop has been activated, but the reward mechanism and exploration strategy are still basic and need to be improved. It will also be updated to parse incoming POML blocks.
* **Injector:** The `Injector` will be updated to serialize all incoming data into the **`POML` cognitive datatype** before writing to the Neo4j knowledge graph.

### 5. Database Schema
* **Strategy:** The Neo4j schema will be updated to include `TimeNodes` to form the chronological spine. All `MemoryNodes` will be linked to a `TimeNode` via a `[:OCCURRED_AT]` relationship.

### 6. Immediate Priority: Context Cache Solidification
*   **Strategy:** Focus on robust implementation and testing of the Context Cache. This includes ensuring reliable population during multi-step conversations and verifying its effective utilization to inform subsequent responses. Comprehensive unit and integration tests will be developed.

### 7. New Agent Implementation Strategies

#### 7.1. "Vault" Agent (Tier 0 Security)
*   **Strategy:** Implement as a dedicated FastAPI service, positioned as the absolute first point of contact for all external inputs. It will utilize a lightweight, security-focused LLM for intent classification and pattern matching for sanitization. Threat logs will be written to a secure, append-only file.

#### 7.2. "Janitor" Agent (Memory & Graph Hygiene)
*   **Strategy:** Implement as a background service, potentially a scheduled task within the `Archivist` or a standalone container. It will periodically query the Neo4j graph for nodes requiring maintenance (e.g., unstructured text, non-standard timestamps) and use the `Distiller` and `Injector` to re-process and update them. De-duplication will involve graph traversal and merging algorithms.

#### 7.3. "Oculus" Agent (Tier 1 Visual Cortex & Motor Control)
*   **Strategy:** Implement as a dedicated service that integrates with screen capture utilities (e.g., `mss` or platform-specific APIs) and an input control library (`pyautogui`). A specialized Visual Language Model (VLM) will be integrated to interpret screen captures and generate structured POML descriptions of UI elements. The operational loop will involve continuous perception, planning (via Orchestrator), and execution of actions.
