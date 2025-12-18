# Sovereign WASM Layer Specification

**Browser-native inference, memory, and chat interface. Zero backend required.**

---

## Identity

- **Name:** Sovereign Stack (formerly "Coda")
- **Scope:** Browser-side compute layer
- **Technologies:** WebGPU (MLCEngine), CozoDB (WASM), Transformers.js
- **Storage:** IndexedDB (persistent, local)

---

## Architecture Overview

```
User Browser
├── Chat Interface (model-server-chat.html)
│   ├── WebGPU LLM Inference (WebLLM)
│   ├── Local Memory Query (CozoDB WASM)
│   └── Embedding Pipeline (Transformers.js)
│
├── Memory Builder (sovereign-db-builder.html)
│   ├── JSON Drag-and-Drop Ingestion
│   ├── Batch Embedding & Storage
│   ├── CozoDB Schema Management
│   └── Corruption Recovery System
│
├── Persistent Storage (IndexedDB)
│   └── CozoDb.new_from_indexed_db('coda_memory', 'cozo_store')
│
├── Log Viewer (log-viewer.html)
│   └── BroadcastChannel Logging ('sovereign-logs')
│
└── Hub (index.html)
    └── Central navigation interface
```

---

## Component Specifications

### 1. Chat Interface (`model-server-chat.html`)

**Purpose:** Main conversational interface with local memory recall.

**Key Features:**
- Model selection dropdown (DeepSeek R1 7B, Qwen 2.5, Gemma 2, Llama 3.2 via WebLLM)
- Memory recall via vector similarity search (CozoDB WASM)
- Streaming response display with reasoning traces
- Context priming (Graph-R1 historical lookups)
- BroadcastChannel integration for multi-tab logging

**Data Flow:**
```
User Input
  ↓
Embedder (Transformers.js: all-MiniLM-L6-v2, 384-dim)
  ↓
CozoDB Query: ?[content, role, timestamp] := *memory{embedding ~= input_vector}
  ↓
Relevant Memories (top-K by similarity)
  ↓
Prepend to LLM prompt
  ↓
MLCEngine inference (WebGPU)
  ↓
Stream response to UI
```

**Schema Access:**
```cozo
memory {
    id: String
    =>
    timestamp: Int,       # Unix milliseconds (sortable)
    role: String,         # 'user', 'assistant', 'system'
    content: String,      # Full message text
    source: String,       # Origin (neo4j, ingestion, etc.)
    embedding: <F32; 384> # Vector embedding
}
```

### 2. Memory Builder (`sovereign-db-builder.html`)

**Purpose:** Ingest external data (JSON, CSV, logs, markdown) into local CozoDB.

**Workflow:**
1. User drags file(s) onto drop zone
2. Parser detects format (JSON array, CSV, plaintext)
3. For each record:
   - Extract `id`, `content`, `timestamp`, `role` (infer if missing)
   - Embed using Transformers.js
   - Batch into groups of 10
4. Each batch: `:put memory {...}` Datalog statement
5. Display memory count and ingestion logs

**Key Functions:**
- `createSchema()` — Initializes memory table with correct structure
- `insertBatch(rows)` — Inserts up to 10 records per batch
- `updateStats()` — Queries memory count and reports status
- `log()` — Real-time UI logging

**Nuke Database Button:**
- Clears old IndexedDB store
- Recreates schema (ensures `timestamp` is a VALUE, not KEY)
- Prepares for fresh ingestion

**Corruption Recovery System:**
- Automatic fallback to in-memory DB on IndexedDB corruption
- Manual recovery button for clearing corrupted data
- Timeout protection against hanging WASM calls
- Nuclear option to completely reset all data

### 4. Corruption Recovery Procedures

**Symptoms:**
- `Failed to convert Uint8Array to Vec<u8>` WASM panic
- `RuntimeError: unreachable` during CozoDB initialization
- Hanging on "Loading from IndexedDb..."

**Recovery Steps:**
1. **Automatic Recovery**: Page refresh triggers fallback logic
2. **Manual Recovery**: Click "🚨 Recover from Crash" button
3. **Nuclear Option**: Use "Nuke Database" to clear everything

**Technical Details:**
- Timeout: 5 seconds for IndexedDB load attempts
- Fallback: In-memory database (non-persistent)
- Data Preservation: Export functionality before recovery
- Browser Storage: Uses IndexedDB API with OPFS backend

### 3. CozoDB Integration

**Database:** `CozoDb.new_from_indexed_db('coda_memory', 'cozo_store', callback)`

**Protocol:**
- All queries use Datalog (Cozo's native query language)
- All `db.run(query, params)` calls must stringify params: `JSON.stringify({...})`
- Sorting works on VALUE fields only (timestamp must be in `=>` section, not before)
- **Date Formatting:** `strftime` is not supported in this WASM build; perform date formatting in client-side JavaScript.

**Example Query (Similarity Search):**
```cozo
?[id, content, role, timestamp] :=
  *memory{id, content, role, timestamp, embedding},
  (embedding ~= input_embedding),
  timestamp >= (now - 7_days_in_ms)
| limit 5
```

**Example Mutation:**
```cozo
:put memory {
    id: "mem-123",
    =>
    timestamp: 1753176645000,
    role: "user",
    content: "What is Project Chronos?",
    source: "neo4j",
    embedding: [0.1, 0.2, 0.3, ..., 0.384]
}
```

### 4. Model Loading (`model-server-chat.html`)

**Engine:** MLCEngine (WebLLM)

**Configuration:**
```javascript
const appConfig = {
    model_list: [
        {
            model_id: "deepseek-r1-7b-instruct-q4f16_1-MLC",
            model_lib: "https://huggingface.co/.../deepseek-r1-7b-...-q4f16_1-MLC/resolve/main/deepseek-r1-7b-instruct-q4f16_1-MLC-GGUF.wasm",
            vram_required_MB: 4096
        },
        // ... other models
    ]
};
```

**Fallback Logic:**
```
1. Try selectedModel (user's choice)
2. If not found in registry, try simpleId (model name only)
3. If still not found, fallback to default (Qwen 2.5)
```

**Working Models:**
- DeepSeek R1 7B (primary reasoning)
- Qwen 2.5 7B, 3B, 1.5B Coder
- Gemma 2 9B, 2B
- Llama 3.2 1B, 3B, 8B
- **Hermes 7B Family:** OpenHermes 2.5, NeuralHermes 2.5, Hermes 2 Pro (Mapped to Mistral v0.3 WASM)

### 5. Embedder Integration

**Library:** Transformers.js (`@xenova/transformers`)

**Model:** `all-MiniLM-L6-v2` (384 dimensions)

**Usage:**
```javascript
const embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
const embedding = await embedder(text, { pooling: 'mean', normalize: true });
```

---

## Data Flow: Ingestion → Query → Chat

```
Step 1: User drags combined_memory.json (211 records from Neo4j)
  ↓
Step 2: Memory Builder parses records
  {id, timestamp, role, content, source}
  ↓
Step 3: Embedding Pipeline
  content → Transformers.js → 384-dim vector
  ↓
Step 4: CozoDB Insert (batched, 10 at a time)
  :put memory {id, timestamp, role, content, source, embedding}
  ↓
Step 5: User opens Chat Interface
  ↓
Step 6: User types "Tell me about Chronos"
  ↓
Step 7: Memory Recall
  Query embedding similar records → returns [mem-1, mem-2, mem-3]
  ↓
Step 8: LLM Context
  Prepend memories to prompt → send to MLCEngine
  ↓
Step 9: Stream response to UI
```

---

## Storage Layer Details

**IndexedDB Structure:**
```
Database: "coda_memory"
  ├── Store: "cozo_store" (key-value pairs)
  │   ├── "schema" → memory table definition
  │   ├── "data:mem-1" → row data
  │   ├── "data:mem-2" → row data
  │   └── ... (one key per memory record + metadata)
```

**Persistence:**
- Survives browser restart
- Not shared across browser profiles
- Max ~50MB per origin (depends on browser)

---

## Logging & Debugging

**BroadcastChannel for Cross-Tab Communication:**
```javascript
const channel = new BroadcastChannel('sovereign-logs');
channel.postMessage({
    timestamp: Date.now(),
    component: 'builder',
    level: 'info',
    message: 'Inserted 10 records'
});
```

**Log Viewer (`log-viewer.html`)** subscribes to this channel and displays real-time logs.

---

## Performance Considerations

- **Model Loading:** First load ~30-60 seconds (downloads GGUF weights), cached thereafter
- **Embedding:** ~100ms per record (Transformers.js on GPU)
- **Batch Insert:** ~500ms per 10 records (CozoDB Datalog)
- **Total for 211 records:** ~15-30 seconds

---

## Known Limitations

1. **No sync with backend** — Sovereign is standalone (Neo4j export is one-way)
2. **VRAM constraint** — Can only load models fitting in GPU VRAM
3. **First-load latency** — Model weights download on first use
4. **Storage limit** — IndexedDB quota per origin (~50MB)

---

## Related Specs

- See [Memory Layer Spec](memory-layer.spec.md) for Neo4j export and Neo4j→Sovereign data format
- See [Extension Bridge Spec](extension-bridge.spec.md) for Gemini integration
- See [API Spec](api.spec.md) for backend connection patterns

---

**Last Updated:** 2025-12-15  
**Status:** Production (211 memories ingested, schema fixed)
