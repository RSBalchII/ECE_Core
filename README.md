# ECE_Core - Sovereign Context Engine

> **Sovereign Context Engine (SCE)** - A local-first, graph-native memory system for cognitive augmentation.

**Version**: 3.0.0 | **Architecture**: Tag-Walker (Graph-Native) | **Stack**: Node.js/C++ Hybrid + CozoDB (RocksDB)

---

## 🚀 Hybrid Architecture (The "Iron Lung" Protocol)

ECE_Core implements a **hybrid architecture** combining Node.js orchestration with high-performance C++ native modules for critical path operations:

- **Node.js**: Application logic, I/O handling, and service orchestration
- **C++ Native Modules**: Performance-critical text processing (refinement, atomization, deduplication)
- **Zero-Copy Operations**: Using `std::string_view` to avoid unnecessary memory allocation
- **Graceful Degradation**: Falls back to JavaScript implementations if native modules unavailable

### Platform Notes
- **Linux/macOS**: Full functionality with persistent CozoDB storage
- **Windows**: Native modules functional; CozoDB requires binary placement at `C:\Users\ECE_Core\engine\cozo_node_prebuilt.node` for persistent storage
- **Native Module Performance**: Consistent across all platforms (2.3x improvement achieved)

## 🌟 Overview

The **ECE_Core** is a sovereign memory engine that transforms your local file system into a structured, queryable knowledge graph. Unlike traditional RAG systems that rely on heavy, probabilistic vector embeddings, ECE uses a **deterministic "Tag-Walker" protocol** to navigate your data.

It runs 100% locally, protecting your privacy while enabling "Deep Context" retrieval on consumer hardware (low RAM/VRAM requirements).

### Key Features

* **🕷️ The Tag-Walker Protocol**: Replaces resource-heavy Vector Search with a lightweight, 3-phase graph traversal (Anchor → Bridge → Walk).
* **👑 Sovereign Provenance**: Implements "Trust Hierarchy." Data created by you (Sovereign) receives a 3.0x retrieval boost over external scrapes.
* **🪞 Mirror Protocol 2.0**: Projects your AI's internal graph onto your filesystem as readable Markdown files organized by `@bucket` and `#tag`.
* **👻 Ghost Data Protocol**: "Read-After-Write" verification ensures zero data loss during high-velocity ingestion.
* **⚛️ Atomic Ingestion**: Chemically splits content into "Atoms" (thoughts) rather than arbitrary text chunks, preserving semantic integrity.

---

## 🏗️ Architecture

### 1. The Core (Node.js/C++ Hybrid Monolith)
The engine runs as a single, efficient Node.js process with high-performance C++ native modules for critical path operations:

1.  **Ingestion (The Refiner)**:
    * **Atomizer**: Splits text/code into logical units (accelerated with C++ native module).
    * **Key Assassin**: Surgically removes JSON artifacts from code (Data Hygiene) (accelerated with C++ native module).
    * **Fingerprint (SimHash)**: Generates locality-sensitive hashes for fuzzy deduplication (C++ native module).
    * **Enricher**: Assigns `source_id`, `sequence`, and `provenance`.
    * **Zero-Vector**: Stubs embedding slots to maintain schema compatibility without VRAM cost.

**Performance Benefits**:
    * **2.3x faster** code processing compared to pure JavaScript
    * **Zero-copy string processing** using `std::string_view` to reduce memory pressure
    * **Sub-millisecond processing** for typical operations
    * **Graceful fallback** to JavaScript implementations when native modules unavailable

2.  **Retrieval (Tag-Walker)**:
    * **Phase 1 (Anchors)**: Uses optimized FTS (Full Text Search) to find direct keyword matches (70% context budget).
    * **Phase 2 (The Walk)**: Pivots via shared tags/buckets to find "Associative Neighbors" that share context but lack keywords (30% context budget).

3.  **Persistence (CozoDB)**:
    * Backed by **RocksDB** for high-performance local storage.
    * Manages a Datalog graph of `*memory`, `*source`, and `*engrams`.

### 2. The Application Layer
* **API**: RESTful interface at `http://localhost:3000/v1/`.
* **Frontend**: Modern React + Vite dashboard.
    *   **Dual Copy**: "Copy Limit" (Context Window) vs "Copy All" (Full Results).
    *   **Visual Context**: Visual indicators for when atoms fall outside the token budget.
* **Desktop Overlay**: Electron "Thin Client" for Always-on-Top assistance.

---

## 🚀 Quick Start

### Prerequisites
* Node.js >= 18.0.0
* pnpm (`npm i -g pnpm`)
* Git

### 1. Installation
```bash
git clone https://github.com/External-Context-Engine/ECE_Core.git
cd ECE_Core
pnpm install
```

### 1.5. Platform Specific Setup (CRITICAL)
**You must manually place the database binary for your OS.** The engine uses a hybrid architecture that requires the native `cozo-node` binary to be explicitly located in the `engine/` root.

1.  **Locate the Binary**: After `pnpm install`, search your `node_modules` for `cozo_node_prebuilt.node`.
    *   *Tip*: It is usually deep in `node_modules/.pnpm/cozo-node@.../native/`.
2.  **Copy & Rename**: Copy the file to the `engine/` folder and rename it based on your OS:
    *   **Windows**: `engine/cozo_node_win32.node`
    *   **macOS**: `engine/cozo_node_darwin.node`
    *   **Linux**: `engine/cozo_node_linux.node`

### 2. Configuration

Copy the example configuration:

```bash
cp .env.example .env
```

Ensure your `.env` is configured for **Tag-Walker Mode** (Embeddings Disabled):

```env
# Core
PORT=3000

# Models (Chat Only)
LLM_MODEL_PATH=Qwen3-4B-Instruct.gguf
LLM_CTX_SIZE=4096
LLM_GPU_LAYERS=33

# Tech Debt Removal (Disable Embeddings)
EMBEDDING_GPU_LAYERS=0
```

### 3. Run Engine (One-Click)
Windows users can simply run the included batch script to build and launch everything:

```bash
start.bat
```

Or manually:

```bash
pnpm build
pnpm start
```

* **Server**: `http://localhost:3000`
* **Health Check**: `http://localhost:3000/health`

### 4. Run Desktop Overlay (Optional)

```bash
cd desktop-overlay
pnpm install
pnpm start
```

---

## 📂 Project Structure

* **`engine/`**: The neural center.
* `src/core/`: Database (CozoDB) and Batch processors.
* `src/services/ingest/`: Watchdog, Refiner, and Atomizer.
* `src/services/search/`: The **Tag-Walker** implementation.
* `src/services/mirror/`: Filesystem projection logic.


* **`frontend/`**: React dashboard.
* **`desktop-overlay/`**: Electron app.
* **`specs/`**: The **Sovereign Engineering Code (SEC)** - The laws governing this system.

---

## 📚 Documentation Standards

This project follows strict engineering standards documented in `specs/standards/`. Key references:

* **Standard 065**: [Graph-Based Associative Retrieval](./specs/standards/065-graph-associative-retrieval.md)
* **Standard 059**: [Reliable Ingestion (Ghost Data Protocol)](./specs/standards/059_reliable_ingestion.md)
* **Standard 058**: [UniversalRAG API](./specs/standards/058_universal_rag_api.md)
* **Standard 073**: [Data Hygiene Protocol (The Immune System)](./specs/standards/073-data-hygiene-protocol.md)

---

## 🧰 Utility Tools

### Codebase Scraper (`read_all.js`)
**The Official Ingestion Bridge**

Consolidate an entire project into a digestable corpus for the engine. 

```bash
node read_all.js <path_to_project_root>
```

**Output**: `codebase/combined_context.yaml`
**Usage**: Drop the result into `notebook/inbox`.
**Mechanism**: The Refiner detects this YAML format and performs **Virtual Atomization**:
*   Decomposes the YAML back into virtual files (e.g., `src/index.ts`).
*   **Hygiene Check**: Filters binaries and circular logs.
*   Auto-tags them with `#code`, `#doc`, and `#project:{name}`.
*   Enables precise filtering (Code vs. Docs) even for massive codebases.

## 🛡️ Data Hygiene & Tagging (Standard 073)

The engine implements a rigorous "Immune System" to ensure your context remains clean and high-signal.

### 1. The Dual Inboxes (Provenance)
*   **`notebook/inbox/`**: For **Sovereign Data** (Your notes, code, thoughts).
    *   **Trust Score**: High (2.0x - 3.0x Boost).
    *   **Use Case**: Manual drops, Obsidian vault sync.
*   **`notebook/external-inbox/`**: For **External Data** (Web scrapes, news, documentation).
    *   **Trust Score**: Low (supporting evidence only).
    *   **Use Case**: News Agent outputs, documentation dumps.

### 2. Sovereign Tags (`context/sovereign_tags.json`)
You can define specific keywords that should ALWAYS trigger a tag, regardless of context.
*   **Config**: Edit `context/sovereign_tags.json`.
*   **Behavior**: If the Refiner sees the word "Sybil" in an atom, it stamps it with `#Sybil`.
*   **Benefit**: Ensures your core terminology is always indexed for retrieval.

### 3. Automatic Project Tagging
The engine reads your file paths to generate context.
*   Path: `notebook/inbox/Job-Context/Resume.md`
*   Resulting Tags: `#project:Job-Context`, `#inbox`, `#Sovereign`
*   **Tip**: Organize your files into named folders to automatically categorize them.

### 4. The Refiner's "Key Assassin"
The engine automatically strips:
*   JSON Metadata wrappers (`"response_content": "..."`)
*   Excessive backslashes (`C:\\\\Users` -> `C:/Users`)
*   "Thinking" logs from LLM outputs.
*   **Result**: You can dump raw logs into the inbox, and the engine will distill the actual content.

---

## 🧠 Querying Best Practices

The **Tag-Walker** engine interprets intents differently than vector databases. Use these patterns for optimal results:

### 1. Concept Recall (The Net)
*   **Pattern**: Single Keyword / Concept
*   **Example**: `"Memory"` or `"WebGPU"`
*   **Mechanism**: Triggers **Tag-Walker**. The engine treats the query as a conceptual node and "walks" the graph to find everything related to it, even if the exact word isn't present in the target.
*   **Use Case**: "Tell me everything about X."

### 2. Precision Intersection (The Laser)
*   **Pattern**: Multi-Keyword Constraint
*   **Example**: `"WebGPU buffer mapping"`
*   **Mechanism**: Triggers **FTS Intersection**. The engine demands that *all* terms (or highly correlated concepts) be present. It filters out broad associations to give you the specific implementation details.
*   **Use Case**: "How do I implement X?" or "Find the specific error log."

### 3. Natural Language (The Conversation)
*   **Pattern**: Questions or Sentences
*   **Example**: `"How is Coda doing today?"`
*   **Mechanism**: Uses **Wink-NLP** to extract the core intent (`Coda` + `Status`). It strips stop words ("How", "is", "doing") and executes a graph query on the entities.
*   **Use Case**: Chatting with the system or asking about high-level status.

---

## License

Elastic License 2.0. Copyright (c) 2026 External Context Engine. See [LICENSE](LICENSE) for full terms.
