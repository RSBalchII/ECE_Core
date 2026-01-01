# Anchor Core: The Visual Monolith (v3.2)

**Status:** Browser-Controlled Architecture | **Philosophy:** Visual Command Center, Resource-Queued.

## 1. The Anchor Architecture
The **Anchor Core** (`webgpu_bridge.py`) is the unified server. The **Ghost Engine** is a headless browser window acting as the GPU Worker.

```mermaid
graph TD
    subgraph Anchor_Core [Localhost:8000]
        Bridge[WebGPU Bridge (Python)]

        subgraph Assets
            UI[chat.html]
            Context[context.html]
            Sidecar[sidecar.html]
            Vision[vision_engine.py]
            Dreamer[memory-builder.html]
        end

        subgraph API_Endpoints
            ChatAPI["/v1/chat/completions"]
            SearchAPI["/v1/memory/search"]
            VisionAPI["/v1/vision/ingest"]
            GPUAPI["/v1/gpu/lock, /v1/gpu/unlock, /v1/gpu/status"]
            LogAPI["/logs/recent, /logs/collect"]
        end
    end

    subgraph Ghost_Engine [Headless Browser]
        Worker[WebLLM (WASM)]
        Memory[CozoDB (WASM)]
        Search[Hybrid Search]
        GPU[WebGPU Resources]
    end

    User -->|HTTP| Sidecar
    User -->|HTTP| Context

    Sidecar -->|Vision Ingest| VisionAPI
    Sidecar -->|Search| SearchAPI
    VisionAPI -->|VLM Analysis| Vision
    Vision -->|Memory Ingest| Ghost_Engine
    SearchAPI -->|Query| Ghost_Engine
    Ghost_Engine -->|Ground Truth| Sidecar

    Sidecar -->|GPU Lock| GPUAPI
    GPUAPI -->|Queue Manager| Ghost_Engine
    Ghost_Engine -->|GPU| Worker

    Bridge -->|API| Ghost_Engine
    Ghost_Engine -->|GPU| Worker
    ChatAPI -->|MLC-LLM| Worker
    SearchAPI -->|Memory Query| Memory
    Dreamer -->|Background Processing| Memory
    Resolver -->|File Redirect| Models[Local Model Files]
    UI -->|Context Retrieval| Search_Engine
    Search_Engine -->|Hybrid Results| UI
    Bridge -->|Log Collection| LogAPI
    LogAPI -->|Central Buffer| LogViewer[log-viewer.html]
```

## 2. Model Loading Strategy (Standard 007)
The system now uses an online-first model loading approach for reliability:
- **Primary**: Direct HuggingFace URLs for immediate availability
- **Fallback**: Local model files when available
- **Bridge Redirect**: `/models/{model}/resolve/main/{file}` handles resolution logic
- **Simplified Configuration**: Online-only approach prevents loading hangs (Standard 007)

## 3. Port Map

* **8000**: **The One Port.** Serves UI, API, Models, and WebSocket connections.

## 4. Search Architecture

* **Hybrid Retrieval**: Combines Vector search (semantic) with BM25 (lexical) for optimal results.
* **BM25 FTS**: CozoDB Full Text Search with stemming and relevance scoring.
* **Context Manager**: Intelligent retrieval system in `ContextManager` class.