# External Context Engine (ECE)

The External Context Engine is a multi-agent AI system designed to function as an Externalized Executive Function (EEF). It augments a user's cognitive abilities by creating and managing a "Living Narrative" of their experiences and knowledge.

## Features

- **Multi-Agent Architecture**: A tiered system of specialized AI agents for deep, multi-turn reasoning.
- **Automated Knowledge Management**: Continuously processes and organizes information into a Neo4j knowledge graph with a chronological spine.
- **Advanced Reasoning**: Capable of parallel thinking and exploratory problem-solving to tackle complex queries.
- **Asynchronous Workflow**: For complex reasoning tasks, the system initiates a background process and immediately returns an `analysis_id`, allowing the user to poll for the result without blocking.
- **Resource Management**: Uses a semaphore to control access to the LLM, preventing resource contention and ensuring smooth operation.
- **POML Protocol**: Uses Persona-Oriented Markup Language for clear, unambiguous inter-agent communication.

## Core Architecture

The ECE is built on a tiered architecture:

* **Tier 1 (Orchestrator):** The central cognitive unit that manages the primary cognitive loops, translates user intent, and synthesizes outputs from other agents.
* **Tier 2 (Thinkers):** A dynamic pool of specialized reasoning agents that work sequentially on complex problems, with their access to the LLM managed by a semaphore.
* **Tier 3 (Memory Cortex):** The long-term memory system that continuously scans the context cache, distills information, and injects it into the knowledge graph.

## Core Cohesion Loop (v3.0)

The Core Cohesion Loop is a self-sustaining memory system that **periodically analyzes and synthesizes context** without requiring user input. This is the foundation of our memory architecture.

### How It Works

1. **Periodic Ping Mechanism**:
   - The Orchestrator agent **receives an empty prompt** every 5 seconds
   - This triggers the "thinking" cycle without user input
   - The Orchestrator reads the context cache and initiates analysis

2. **Archivist's Role**:
   - The Archivist agent **synthesizes context** from the context cache
   - It creates a **timeline-style explanation** of events
   - It compares the current state to previous context states
   - It queries the QLearning agent for relevant memory associations

3. **Memory Querying**:
   - When the Archivist needs context for a specific event:
     ```python
     # Example POML query format
     {
       "type": "memory_query",
       "context_id": "cd06bd2f-846a-4d28-9ab4-090e9ee9abc8",
       "max_contexts": 5  # Resource limit to prevent memory bloat
     }
     ```
   - The QLearning agent responds with relevant memory associations

4. **Resource Management**:
   - `max_contexts` parameter ensures only the most relevant memories are retrieved
   - Default value: 5 (can be adjusted based on system load)
   - This prevents memory bloat and maintains system responsiveness

### Why This Matters

This implementation creates a **self-sustaining memory system** that:
- Works without user input (periodic analysis)
- Maintains memory efficiency through resource limits
- Provides contextual awareness through timeline synthesis
- Enables the system to "think" about past interactions

## System Status

All core MVP components have been successfully implemented and are fully operational:
- Context Cache (Redis-based short-term memory)
- Distiller Agent (NLP-based text processing)
- Archivist Agent (Memory cortex controller)
- Injector Agent (Neo4j data persistence)
- Q-Learning Agent (Graph optimization)

For detailed specifications, see:
- [Updated Specification](specs/updated_spec.md)
- [Implementation Plan](specs/updated_plan.md)
- [Task Status](specs/updated_tasks.md)

## Getting Started

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd External-Context-Engine
    ```
2.  **Start the services:**
    ```bash
    docker-compose up --build
    ```

The main application will be available at `http://localhost:8000`.

## API Endpoints

*   `GET /process_prompt`: The main endpoint for interacting with the ECE.
*   `GET /get_analysis_result`: Used to retrieve the results of a complex reasoning task.
