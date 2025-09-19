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
