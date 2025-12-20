# Sovereign WASM Specification (Reflex & Context)

## Architecture Overview
The "Sovereign" layer runs entirely in the browser using WebAssembly (WASM), specifically `web-llm` for inference and `cozo-lib-wasm` for memory.

## 1. Context Injection ("Reflex")
The `retrieveInitialContext(userText)` function in `model-server-chat.html` is the "Reflex" system. It performs a fast, keyword-based lookup in CozoDB before the heavy LLM is invoked.

### 1.1 The "Reflex Flood" & Protection
**Critical Constraint**: Large models (14B+) running in WebGPU are extremely sensitive to context length and memory pressure. 
**Incident**: A query like "what do you know about X" causes a flood because "you", "know", and "about" are common words, matching 100+ documents.
**Solution**: 
1.  **Stop-Word Filtering**: A robust `Set` of stop words is applied (e.g., `you`, `know`, `about`, `can`, `have`).
2.  **Result Capping**: Reflex results are strictly capped (e.g., Top 10) to prevents OOM crashes.

## 2. CozoDB Schema
The in-browser database uses the following Datalog schema:
```datalog
:create memory {
    id: String 
    => 
    timestamp: Int, 
    role: String, 
    content: String, 
    source: String, 
    embedding: <F32; 384> 
}
```

## 3. Secure Bridge
The `webgpu_bridge.py` acts as a secure relay (websocket <-> http) on a random port (or 8080).
- **Authentication**: Bearer Token required for all non-static endpoints.
- **Mobile Access**: Serves `mobile-chat.html` for LAN access.
