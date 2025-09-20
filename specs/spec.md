# Core External Context Engine (ECE) - Project Specification v3.1
## Updated to Reflect Current Implementation

## 1. Vision Statement

To create a seamless cognitive partnership where a human and an AI co-evolve. The ECE will function as an **Externalized Executive Function (EEF)**, augmenting the user's cognitive abilities and facilitating their strategic life goals by creating and managing a "Living Narrative" of their experiences and knowledge.

## 2. Core Architecture

The ECE is a multi-agent system built on a tiered architecture. It is designed for advanced reasoning, automated knowledge management, and proactive problem-solving through parallel and iterative exploration.

* **Tier 1 (Orchestrator):** The "brain" of the ECE. It manages the primary cognitive loops, translates user intent into machine-readable instructions, and synthesizes outputs from all other agents into a single, coherent response.
* **Tier 2 (Thinkers):** A dynamic pool of on-call reasoning agents designed to work sequentially on complex problems, with their access to the LLM managed by a semaphore.
* **Tier 3 (Memory Cortex):** The subconscious, long-term memory system. It operates as an automated, continuous process to manage and chronologically organize the persistent knowledge graph.

## 3. MVP: The Core Cohesion Loop

The immediate goal is to implement a closed-loop cycle of context processing, learning, and memory management. This demonstrates the core functionality of the ECE.

*   **Context Cache:** A fixed-size, short-term memory buffer that is fully operational using Redis for key-value storage and vector similarity search.
*   **Distiller Agent:** Periodically reads the entire contents of the Context Cache, condenses it into a targeted, summarized memory using NLP (spaCy) for entity extraction, and sends the condensed memory to the Archivist Agent.
*   **Archivist Agent:**
    *   Acts as a communication hub, routing data between the Q-Learning Agent, Distiller, and Injector.
    *   Intercepts and captures truncated data from the Context Cache before it's lost, ensuring no data loss.
    *   Implements periodic self-analysis through the Cohesion Loop, creating timeline-style explanations of events.
    *   Continuously scans the Redis cache for new entries and processes them through the full pipeline.
*   **Injector Agent:**
    *   Checks for verbatim duplicates before writing any new data to the graph.
    *   If the data is new, it creates a new node.
    *   If the data is a duplicate, it locates the existing node and appends the new information as a timestamped "additional context," showing the evolution of the concept.
    *   Uses MERGE operations in Neo4j to handle both creation and updating of nodes and relationships.
    *   Implements content history tracking for nodes and relationships.
*   **Q-Learning Agent:** Actively analyzes the data flow to refine relationships within the graph using reinforcement learning algorithms.

## 4. Core Protocols & Innovations

* **Asynchronous Complex Reasoning:** For complex queries, the `Orchestrator` initiates a background task to run the thinking and synthesis process, immediately returning an `analysis_id` to the user. The user can then poll for the result.
* **Sequential Thinking Workflow:** To manage resources effectively, the `Orchestrator` uses a semaphore to ensure that the `Thinker` agents access the LLM sequentially.
* **Keyword-Based Context Retrieval:** The `Orchestrator` extracts keywords from the user's prompt and passes them to the `Archivist` to retrieve relevant context from the knowledge graph.
* **Exploratory Problem-Solving Loop:** An iterative, game-like workflow where an `ExplorerAgent` proposes solutions, a `SandboxModule` executes them, and a `CritiqueAgent` scores them.
* **POML Inter-Agent Communication:** All internal communication between agents is conducted via `POML` (Persona-Oriented Markup Language) directives with structured metadata.
* **Continuous Temporal Scanning:** The `Archivist` maintains a persistent "flow of time" by chronologically linking all memories as they are processed from the cache using a Year->Month->Day node structure in Neo4j.
* **Self-Sustaining Memory System (Cohesion Loop):** The `Orchestrator` periodically analyzes the context cache every 5 seconds without user input, creating timeline-style explanations and querying the `Archivist` for related memories with resource limits (`max_contexts` parameter).

## 5. Data Flow and Storage Implementation

### 5.1. Context Cache Implementation
- Uses Redis for high-speed key-value storage
- Supports TTL (time-to-live) for automatic cache management
- Implements vector embeddings for semantic search capabilities
- Maintains statistics tracking for cache hit/miss rates

### 5.2. Distiller Agent Implementation
- Processes raw text using spaCy NLP library for entity extraction
- Identifies named entities (PERSON, ORG, GPE, DATE, etc.)
- Structures data into entities and relationships format
- Adds timestamp information for temporal tracking

### 5.3. Archivist Agent Implementation
- Acts as central coordinator between Distiller, Injector, and Q-Learning agents
- Continuously monitors Redis cache for new entries
- Transforms data from Distiller format to Injector format
- Applies business rules for filtering and processing
- Manages temporal linking of memories to chronological nodes

### 5.4. Injector Agent Implementation
- Connects to Neo4j graph database using official Neo4j driver
- Translates structured JSON data into Cypher MERGE queries
- Implements duplicate detection using node ID matching
- Maintains content history through array properties
- Creates chronological spine using Year->Month->Day node structure
- Links memory nodes to temporal nodes via OCCURRED_AT relationships

### 5.5. Neo4j Schema Implementation
- **Entity Nodes:** Represent extracted concepts with properties and content history
- **Relationships:** Connect entities with typed relationships and content history
- **Temporal Nodes:** Chronological structure (Year->Month->Day) for time-based organization
- **Content History:** Arrays tracking the evolution of nodes and relationships over time

## 6. Agent Communication Protocol

All inter-agent communication follows the POML (Persona-Oriented Markup Language) protocol:

```xml
<poml>
    <identity>
        <name>ArchivistAgent</name>
        <version>1.0</version>
        <type>Memory Cortex Controller</type>
    </identity>
    <operational_context>
        <project>External Context Engine (ECE) v3.0</project>
        <objective>Send data to Injector for persistence in Neo4j knowledge graph.</objective>
    </operational_context>
    <directive>
        <goal>Request data injection into Neo4j knowledge graph.</goal>
        <task>
            <name>InjectData</name>
            <data>{structured_data}</data>
        </task>
    </directive>
    <timestamp>2025-09-20T10:30:00Z</timestamp>
</poml>
```

## 7. Completed Agents and Features

### 7.1. Fully Implemented Agents
- ✅ **Orchestrator Agent** - Central coordinator with decision tree routing
- ✅ **Distiller Agent** - NLP-based text processing and entity extraction
- ✅ **Archivist Agent** - Memory cortex controller with continuous scanning
- ✅ **Injector Agent** - Neo4j data persistence with duplicate handling
- ✅ **Q-Learning Agent** - Graph optimization and relationship refinement

### 7.2. Core Features
- ✅ **Context Cache** - Redis-based short-term memory
- ✅ **Continuous Temporal Scanning** - Automatic processing of cache entries
- ✅ **POML Communication** - Structured inter-agent messaging
- ✅ **Cohesion Loop** - Periodic self-analysis and timeline synthesis
- ✅ **Asynchronous Processing** - Non-blocking operations with background tasks
- ✅ **Duplicate Handling** - Content history tracking in Neo4j

## 8. Future Enhancements (Not Yet Implemented)

### 8.1. Security Layer
- **Vault Agent (Tier 0 Security):** Hardened gateway for input sanitization and threat detection

### 8.2. Maintenance Agents
- **Janitor Agent:** Background maintenance for data integrity and de-duplication
- **Oculus Agent:** Visual cortex for screen capture and UI interaction

This updated specification reflects the current implementation status of the ECE system, with all core MVP components fully functional and integrated.