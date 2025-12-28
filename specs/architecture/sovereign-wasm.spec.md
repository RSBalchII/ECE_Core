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

### 3.1 Local Model Serving (Storage Quota Bypass)
**Problem**: Browsers (especially in Incognito/Guest modes) strictly limit persistent storage (e.g., <300MB), preventing the caching of large LLM weights (~2GB+).
**Solution**: The Bridge acts as a local HTTP File Server.
- **Endpoint**: `http://localhost:8080/models/{model_id}/...`
- **Mechanism**: 
    1. Frontend requests model from localhost.
    2. If 404, Frontend triggers `POST /v1/models/pull`.
    3. Bridge downloads artifacts from Hugging Face to `./models`.
    4. Frontend polls status and loads the model into RAM (bypassing IndexedDB quota).

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

## 6. Resource Management (Orchestrator)
**Problem**: Multiple browser tabs (Mic, Console, Dreamer) competing for the single GPU resource led to deadlocks, timeouts, and "Device Lost" errors.
**Solution**: A Priority-Queue based Locking System with enhanced timeout handling and emergency procedures.

### 6.1 GPU Controller (`tools/modules/sovereign.js`)
- **Serialized Loading**: `withModelLoadLock()` ensures only one tab loads a model at a time, preventing GPU overload during initial loading.
- **Access Priority**:
  - **Priority 0 (High)**: Root Mic (Voice Input - cannot wait)
  - **Priority 10 (Med)**: Root Console (Chat - user waiting)
  - **Priority 15 (Med)**: Default priority
  - **Priority 20 (Low)**: Root Dreamer (Background tasks)
- **Timeouts**: Increased broken-lock timeout from 60s to **120s** (2 minutes) to accommodate large model loading.
- **Retry Logic**: Added retry mechanism with proper error handling.
- **Fallback Mechanism**: Direct WebGPU access when bridge unavailable.
- **Status Checking**: Added GPU status check functionality.
- **Emergency Release**: If a lock is held >120s, it is forcibly broken to prevent system deadlock.

### 6.2 Bridge Orchestration (`smart_gpu_bridge.py`)
- **Queue Tracking**: Tracks request start times to prevent starvation.
- **Enhanced Timeouts**: Increased timeout from 60s to 120s for lock acquisition.
- **Request Tracking**: Added request_start_times to prevent queue starvation.
- **Enhanced Status**: Detailed queue information in status endpoint.
- **Endpoints**:
  - `GET /v1/gpu/status`: Monitor active locks and queue depth.
  - `POST /v1/gpu/lock`: Acquire lock (blocking).
  - `POST /v1/gpu/unlock`: Release GPU lock.
  - `POST /v1/gpu/reset`: Standard reset.
  - `POST /v1/gpu/force-release-all`: Nuclear option for stuck states.
  - `POST /v1/gpu/force-release`: Emergency release endpoint.
  - `POST /v1/hot-reload`: Hot reload endpoint for development.

### 6.3 GPU Management Utilities
- **GPU Manager Script** (`scripts/gpu_manager.py`): Command-line tool to monitor and manage GPU resources.
- **Test Script** (`scripts/test_gpu_fixes.py`): Comprehensive testing of GPU resource management.
- **Monitoring Commands**:
  - `python scripts/gpu_manager.py --status`: Check GPU status
  - `python scripts/gpu_manager.py --monitor --interval 10`: Monitor continuously
  - `python scripts/gpu_manager.py --force-release`: Force release GPU locks
  - `python scripts/gpu_manager.py --reset`: Standard reset
  - `python scripts/gpu_manager.py --hot-reload`: Trigger hot reload

## 7. Development Infrastructure
**Problem**: Restarting the Python bridge and refreshing 3 browser tabs for every small code change is slow.

### 7.1 Hot Reload System
- **Backend**: `smart_gpu_bridge.py` monitors its own source code (and `download_models.py`) for changes. It automatically reloads the Python process while preserving active WebSocket connections if possible.
- **Frontend**: `gpu-hot-reloader.js` connects to the bridge via WebSocket. When the bridge signals a reload (or detects an HTML update), the browser auto-refreshes.
- **Safety**: Automatically releases all GPU locks during a reload event to prevent "Ghost Locks".
