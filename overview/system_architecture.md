# System Architecture

## High-Level Overview

The Coda Platform consists of a Chrome Extension (The Bridge) communicating with a local FastAPI Backend (The Core), which orchestrates memory (Neo4j/Redis) and cognition (LLM).

```mermaid
graph TD
    User[User] -->|Interacts| Ext[Chrome Extension (Bridge)]
    
    subgraph "The Bridge (Client)"
        Ext -->|Voice: Chat Stream| SP[Side Panel]
        Ext -->|Sight: Read Page| CS[Content Script]
        Ext -->|Hands: Execute| Exec[Scripting API]
    end
    
    subgraph "The Core (Backend)"
        SP -->|POST /chat/stream| API[FastAPI Server]
        API -->|Orchestrates| Recipe[CodaChatRecipe]
        Recipe -->|Retrieves| Mem[Memory (Neo4j/Redis)]
        Recipe -->|Generates| LLM[LLM Inference]
        Recipe -->|Logs| Audit[Audit Logger]
    end
    
    Recipe -->|Returns JSON Stream| SP
```

## Components

1.  **Extension (`extension/`)**:
    *   **Manifest V3**: Secure, modern browser integration.
    *   **Side Panel**: Persistent chat UI with Markdown rendering.
    *   **Content Script**: On-demand DOM scraping.
    *   **Scripting API**: User-authorized JavaScript execution.

2.  **Backend (`backend/`)**:
    *   **FastAPI**: High-performance async web server.
    *   **Recipes**: Modular logic units (e.g., `CodaChatRecipe`).
    *   **Memory**: GraphRAG (Neo4j) + Session Cache (Redis).
