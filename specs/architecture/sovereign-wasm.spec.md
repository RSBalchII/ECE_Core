# Sovereign WASM Specification (Root Kernel)

## Architecture Overview
The **Root Coda** system runs entirely in the browser using a unified Kernel (`sovereign.js`) that manages Compute (WebLLM) and Memory (CozoDB).

## 1. The Kernel (`tools/modules/sovereign.js`)
The Kernel is the standard library for all Root Tools. It enforces consistency and safety.

### 1.1 Hardware Abstraction ("Snapdragon Fix")
**Problem**: Adreno GPUs (Snapdragon X Elite) and some mobile chips crash if a WebGPU buffer >256MB is requested, or if context exceeds 4k tokens without specific driver flags.
**Solution**: `getWebGPUConfig(profile)`
- **Lite**: Clamps buffer to 256MB, Context to 2048.
- **Mid**: Clamps buffer to 1GB, Context to 4096.
- **High/Ultra**: Unlocked.

### 1.2 Unified Logging
**Problem**: `console.log` is invisible on mobile or when running as a PWA.
**Solution**: `SovereignLogger`
- Broadcasts all logs to `BroadcastChannel('sovereign-logs')`.
- Consumed by `log-viewer.html` for real-time remote debugging.

### 1.3 Reactive State
**Problem**: Spaghetti code updating DOM elements manually.
**Solution**: `createStore(initialState)`
- Lightweight `Proxy`-based store.
- Components subscribe to changes: `subscribe((key, val) => updateUI(key, val))`.

## 2. Memory Layer (CozoDB WASM)
The Kernel provides a standardized loader: `initCozo(wasmPath)`.

### Data Portability
- **Lossless Export**: The Root Builder features a "Lossless Export" button.
- **Mechanism**: Dumps full Cozo relations (including vectors) to a JSON file.
- **Use Case**: Transfer full "Brain" state between devices or backup.

### Schema
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

## 3. Tool Bridge (Legacy Support)
The `webgpu_bridge.py` acts as a secure relay (websocket <-> http) for external tools (like VS Code extensions) to access the Browser's LLM.
- **Input**: HTTP/REST (`/v1/chat/completions`)
- **Output**: WebSocket (`ws://localhost:8080/ws/chat`)

## 4. Audio Input (Root Mic)
**Goal**: Pure client-side speech-to-text without sending audio to a cloud.

### 4.1 Pipeline
1. **Capture**: `MediaRecorder` (WebM) -> 48kHz decoding.
2. **Preprocessing**:
   - Downsampling to 16kHz (Whisper Native).
   - **Noise Gate**: Discards audio if peak amplitude < 0.01 (Prevents transcribing silence).
   - **Amplification**: Smart gain (max 5x) for quiet voices, but capped to avoid boosting noise floor.
3. **Inference (WASM)**: 
   - Model: `Xenova/whisper-tiny.en` (Quantized).
   - **Long-form Strategy**: Uses `chunk_length_s: 30` and `stride_length_s: 5` to process audio exceeding the model's native 30s window.
4. **Post-Processing (Refinement)**:
   - **Hallucination Filter**: Regex removal of common Whisper artifacts (e.g., "[Music]", "Applause", "Amara.org").
   - **LLM Cleanup**: The raw transcript is passed to the local Qwen2.5 instance with a system prompt to fix grammar/punctuation without altering meaning.

### 4.2 Summarization Loop
- **Trigger**: User clicks "Summarize & Clarify" after a successful transcription.
- **Process**: The cleaned transcript is sent back to the Local Kernel (Qwen2.5) with a prompt to "summarize and clarify core meaning."
- **Output**: The transcript is replaced by the summary, which is automatically copied to the clipboard.

## 5. Parallel Compute (The Worker)
To prevent UI freezing during heavy inference, the LLM runs in a dedicated Web Worker.

### 5.1 `tools/modules/llm-worker.js`
- **Role**: Hosts the `MLCEngine` instance.
- **Communication**: Uses `WebWorkerMLCEngineHandler` to bridge messages between the main thread and the worker.
- **Benefit**: Ensures the UI remains responsive (scrolling, typing) even while the GPU is crunching tokens.