# Function Graph Report: Context Engine & Archivist Protocol

## 1. Project Structure Overview

The project is organized into a Monorepo structure containing the Backend (FastAPI), Chrome Extension (MV3), and various support scripts.

### Root Directory
- **`Context-Engine/`**: Main project root.
  - **`backend/`**: Python FastAPI application.
  - **`extension/`**: Chrome Extension source code.
  - **`archive/`**: Deprecated or archival scripts.
  - **`models/`**: Local LLM model files (symlinked).

## 2. Backend Architecture (`backend/src`)

The backend is the core of the Context Engine, handling memory management, reasoning, and the Archivist protocol.

### Core Components
- **`app_factory.py`**: Application entry point. Wires together routers and middleware.
  - **Routers**: `health`, `reason`, `plugins`, `audit`, `plan`.
  - **Recipes**: `coda_chat` (`/chat`), `archivist` (`/archivist`).
- **`bootstrap.py`**: Initializes the application context and dependency injection.
- **`config.py`**: Configuration management (Env vars, YAML).

### Agents (`backend/src/agents`)
- **Orchestrator (`orchestrator/orchestrator.py`)**:
  - **Role**: Cross-Team Orchestration.
  - **Status**: Skeleton Implementation.
  - **Functions**:
    - `spawn_teams()`: Initializes planner/reasoner teams.
    - `collect_plans()`: Gathers execution plans from teams.
    - `greedy_aggregate()`: Selects the best plan.
- **Archivist (`archivist.py`)**:
  - **Role**: Knowledge Graph Maintenance & Curation.
  - **Functions**:
    - `_maintenance_loop()`: Background task for freshness and pruning.
    - `purge_contaminated_nodes()`: Removes invalid data.
    - `run_weaving_cycle()`: Triggers `MemoryWeaver` to consolidate memory.
- **Planner (`planner.py`)**: Generates execution plans.
- **Verifier (`verifier.py`)**: Validates information against the Knowledge Graph.

### Recipes (`backend/src/recipes`)
- **Archivist Recipe (`archivist.py`)**:
  - **Endpoint**: `POST /archivist/ingest`
  - **Role**: Ingestion Pipeline entry point.
  - **Flow**: Receives `PlaintextMemory` -> Saves to `ark_corpus.jsonl` -> Triggers Neo4j Indexing.

### Memory System (`backend/src/memory`)
- **`manager.py`**: `TieredMemory` manager (Redis + Neo4j).
- **`neo4j_store.py`**: Graph database interactions.
- **`redis_cache.py`**: Hot memory cache.

## 3. Extension Architecture (`extension/`)

The Chrome Extension serves as the primary data ingestion interface for the Archivist Protocol.

- **`manifest.json`**: Manifest V3 configuration. Permissions: `sidePanel`, `activeTab`, `scripting`, `storage`.
- **`content.js`**: Content Scripts & Adapters.
  - **Adapters**:
    - `GeminiAdapter`: Scrapes Google Gemini chat interface.
    - `ChatGPTAdapter`: Scrapes ChatGPT interface.
    - `ClaudeAdapter`: Scrapes Claude interface.
    - `GenericAdapter`: Fallback for standard web pages.
  - **Function**: Listens for `EXTRACT_CONTENT` messages, selects the appropriate adapter, and returns structured text.
- **`sidepanel.js`**: UI Logic.
  - **Function**: Handles "Save to Memory" button click.
  - **Flow**: Triggers content extraction -> Sends data to Backend (`/archivist/ingest`) with API Key.
- **`background.js`**: Service Worker. Handles side panel toggling.

## 4. Data Flow: The Archivist Pipeline

1.  **Capture**: User clicks "Save to Memory" in Chrome Extension.
2.  **Extraction**: `content.js` identifies the site (e.g., Gemini) and extracts chat history/content.
3.  **Transmission**: `sidepanel.js` sends payload to `http://localhost:8000/archivist/ingest`.
4.  **Ingestion**:
    - Backend validates API Key.
    - `Archivist` recipe validates schema (`PlaintextMemory`).
    - Data is appended to `ark_corpus.jsonl` (Immutable Log).
    - Data is indexed into Neo4j (Graph Memory).
5.  **Maintenance**: `ArchivistAgent` runs background cycles to weave and prune the graph.

## 5. Current State & Next Steps

- **Branch**: `main-5` (Source New Truth).
- **Status**: Fully Functional Ingestion Pipeline.
- **Pending**:
    - Full implementation of Orchestrator logic.
    - Enhanced "Weaving" algorithms for graph consolidation.
