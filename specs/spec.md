# Root Coda: The Visual Monolith (v3.0)

**Status:** Unified Anchor | **Philosophy:** One Port, One Truth.

## 1. The Anchor Architecture
The **Anchor Core** (`webgpu_bridge.py`) is the monolithic server. The **Ghost Engine** is a browser window acting as the GPU Worker.

```mermaid
graph TD
    subgraph Host_Machine [Localhost:8000]
        Core[Anchor Core (Python)]

        subgraph Static_Serving
            UI[chat.html]
            Term[terminal.html]
            Models[Model Artifacts]
        end

        subgraph API_Layer
            ChatAPI["/v1/chat/completions"]
            ShellAPI["/v1/shell/exec"]
        end
    end

    subgraph Ghost_Engine [Minimized Browser]
        Worker[WebLLM (WASM)]
        Memory[CozoDB (WASM)]
    end

    User -->|HTTP| UI
    User -->|HTTP| Term

    UI -->|WebSocket| Core
    Term -->|REST| ShellAPI

    Core <-->|WebSocket Relay| Worker
    ShellAPI -->|Subprocess| OS[Operating System]

```

## 2. Port Map

* **8000**: **The One Port.** Serves HTML, JS, Models, and API.
