# Core External Context Engine (ECE) - Project Specification v3.0

## 1. Vision Statement

To create a seamless cognitive partnership where a human and an AI co-evolve. The ECE will function as an **Externalized Executive Function (EEF)**, augmenting the user's cognitive abilities and facilitating their strategic life goals by creating and managing a "Living Narrative" of their experiences and knowledge.

## 2. Core Architecture

The ECE is a multi-agent system built on a tiered architecture. It is designed for advanced reasoning, automated knowledge management, and proactive problem-solving through parallel and iterative exploration.

* **Tier 1 (Orchestrator):** The "brain" of the ECE. It manages the primary cognitive loops, translates user intent into machine-readable instructions, and synthesizes outputs from all other agents into a single, coherent response.
* **Tier 2 (Thinkers):** A dynamic pool of on-call reasoning agents designed to work sequentially on complex problems, with their access to the LLM managed by a semaphore.
* **Tier 3 (Memory Cortex):** The subconscious, long-term memory system. It operates as an automated, continuous process to manage and chronologically organize the persistent knowledge graph.

## 3. MVP: The Core Cohesion Loop

The immediate goal is to implement a closed-loop cycle of context processing, learning, and memory management. This demonstrates the core functionality of the ECE.

*   **Context Cache:** A fixed-size, short-term memory buffer that is fully operational.
*   **Distiller Agent:** Periodically reads the entire contents of the Context Cache, condenses it into a targeted, summarized memory, and sends the condensed memory to the Archivist Agent.
*   **Archivist Agent:**
    *   Acts as a communication hub, routing data between the Q-Learning Agent, Distiller, and Injector.
    *   Intercepts and captures truncated data from the Context Cache before it's lost, ensuring no data loss.
*   **Injector Agent:**
    *   Checks for verbatim duplicates before writing any new data to the graph.
    *   If the data is new, it creates a new node.
    *   If the data is a duplicate, it locates the existing node and appends the new information as a timestamped "additional context," showing the evolution of the concept.
*   **Q-Learning Agent:** Actively analyzes the data flow to refine relationships within the graph.

## 4. Core Protocols & Innovations

* **Asynchronous Complex Reasoning:** For complex queries, the `Orchestrator` initiates a background task to run the thinking and synthesis process, immediately returning an `analysis_id` to the user. The user can then poll for the result.
* **Sequential Thinking Workflow:** To manage resources effectively, the `Orchestrator` uses a semaphore to ensure that the `Thinker` agents access the LLM sequentially.
* **Keyword-Based Context Retrieval:** The `Orchestrator` extracts keywords from the user's prompt and passes them to the `Archivist` to retrieve relevant context from the knowledge graph.
* **Exploratory Problem-Solving Loop:** An iterative, game-like workflow where an `ExplorerAgent` proposes solutions, a `SandboxModule` executes them, and a `CritiqueAgent` scores them.
* **POML Inter-Agent Communication:** All internal communication between agents is conducted via `POML` (Persona-Oriented Markup Language) directives.
* **Continuous Temporal Scanning:** The `Archivist` maintains a persistent "flow of time" by chronologically linking all memories as they are processed from the cache.

## 5. New Agent & Protocol Specifications

The following specifications are designed to evolve the ECE from a text-based agent orchestrator into a robust, secure, and multi-modal cognitive architecture.

### 5.1. The "Vault" Agent (Tier 0 Security)

*   **Purpose:** To serve as a hardened, zero-trust gateway for all inputs. Its primary function is to isolate the core ECE from malicious or malformed prompts, preventing injection, data poisoning, and other attack vectors.
*   **Core Responsibilities:**
    1.  **Input Sanitization:** Scan all incoming text for known attack patterns like invisible characters, escape sequences, and common injection payloads.
    2.  **Threat Detection:** Employ a specialized, small-footprint model (e.g., a security-focused Gemma or IBM model) to classify the *intent* of prompts, identifying meta-prompts designed to manipulate the system.
    3.  **Quarantine & Alert Protocol:** Upon detecting a high-confidence threat, the Vault agent will:
        *   Block the prompt from proceeding to the Orchestrator.
        *   Log the full, raw prompt to a secure log file (e.g., `logs/threat_alerts.md`).
        *   Return a generic, safe response to the user without revealing security trigger details.
*   **Architectural Placement:** It must be the first point of contact for any external input, positioned directly **before** the `OrchestratorAgent`.

### 5.2. POML Inter-Agent Communication Protocol

*   **Purpose:** To establish a structured, machine-readable format for all data exchanged between agents, moving from simple strings to self-describing data objects.
*   **Core Structure:** All inter-agent messages will be wrapped in a POML (Persona Object Markup Language) block.
    *   **Example:**
        ```xml
        <poml>
            <metadata>
                <timestamp>2025-09-17T22:55:10-06:00</timestamp>
                <source_agent>ThinkerAgent_Philosopher</source_agent>
                <target_agent>ArchivistAgent</target_agent>
                <data_type>agent_thought_process</data_type>
                <session_id>session_xyz</session_id>
            </metadata>
            <content><![CDATA[The agent's detailed text output goes here.]]></content>
        </poml>
        ```
*   **Implementation:** All agents must be refactored to format their outputs into this structure. The `ArchivistAgent` and `QLearningAgent` must be updated to parse these blocks, using the metadata to create richer, more interconnected nodes and relationships in the graph database.

### 5.3. The "Janitor" Agent (Memory & Graph Hygiene)

*   **Purpose:** To perform asynchronous, background maintenance on the graph database to ensure its long-term health, performance, and integrity.
*   **Core Responsibilities:**
    1.  **Organic POML Conversion:** Periodically scan the graph for legacy nodes containing unstructured text. It will then re-process this data, wrap it in the proper POML format, and update the node, allowing the graph to organically upgrade itself over time.
    2.  **Data Integrity:** Standardize all timestamps to the ISO 8601 format.
    3.  **De-duplication:** Identify and merge redundant nodes to maintain database efficiency.
*   **Activation:** The agent can be triggered on a schedule (e.g., nightly), after large data ingestions, or manually by the user.

### 5.4. The "Oculus" Agent (Tier 1 Visual Cortex & Motor Control)

*   **Purpose:** To provide the ECE with the ability to perceive, understand, and interact with on-screen visual information via a standard GUI.
*   **Core Components:**
    1.  **Screen Capture Utility:** A tool to capture screen frames at a frequency of 1-2 seconds.
    2.  **Visual Language Model (VLM):** A specialized model (e.g., "Holo") fine-tuned for UI understanding to identify and describe functional elements like buttons, text fields, and menus.
    3.  **Input Control Library:** A library (e.g., `pyautogui`) to provide programmatic control over the mouse and keyboard.
*   **Operational Loop (See-Think-Act):**
    1.  **See:** Perceive the current screen state via a captured frame.
    2.  **Think:** Use the VLM and OCR to generate a structured (POML) description of the on-screen UI elements and their coordinates. Compare this state to the high-level objective received from the Orchestrator and plan the next single action (e.g., "move mouse to [x,y] and click").
    3.  **Act:** Execute the planned action using the input control library. The loop then repeats, perceiving the result of the action in the next frame.
