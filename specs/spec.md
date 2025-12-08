# System Specification

## Identity
- **Name**: Coda
- **Role**: Cognitive Augmentation Platform
- **Philosophy**: Local-first, User-sovereign, Agentic.

## Architecture
The system follows a **Bridge-Core** architecture.

### The Bridge (Extension)

- **Type**: Chrome Extension (MV3)
- **Communication**: HTTP/SSE to `localhost:8000`
- **State**: Local Storage (Persistence)

### The Core (Backend)
- **Type**: Python FastAPI
- **Logic**: Recipe-based (Modular)
- **Memory**:
    - **Episodic**: Neo4j (Graph)
    - **Short-term**: Redis (Key-Value)
- **Inference**: Local LLM (via `llama.cpp` or compatible server)

## Data Models
- **Session**: Unique ID per conversation thread.
- **Context**: Aggregated text from Memory + Active Page.
- **Action**: JSON block `:::action {...} :::` for browser execution.
