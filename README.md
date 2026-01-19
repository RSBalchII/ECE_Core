# ECE_Core - Sovereign Context Engine

> **Sovereign Context Engine (SCE)** - A local-first, graph-native memory system for cognitive augmentation.

**Version**: 3.0.0 | **Architecture**: Tag-Walker (Graph-Native) | **Stack**: Node.js Monolith + CozoDB (RocksDB)

---

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

### 1. The Core (Node.js Monolith)
The engine runs as a single, efficient Node.js process managing three distinct layers:

1.  **Ingestion (The Refiner)**:
    * **Atomizer**: Splits text/code into logical units.
    * **Enricher**: Assigns `source_id`, `sequence`, and `provenance`.
    * **Zero-Vector**: Stubs embedding slots to maintain schema compatibility without VRAM cost.

2.  **Retrieval (Tag-Walker)**:
    * **Phase 1 (Anchors)**: Uses optimized FTS (Full Text Search) to find direct keyword matches (70% context budget).
    * **Phase 2 (The Walk)**: Pivots via shared tags/buckets to find "Associative Neighbors" that share context but lack keywords (30% context budget).

3.  **Persistence (CozoDB)**:
    * Backed by **RocksDB** for high-performance local storage.
    * Manages a Datalog graph of `*memory`, `*source`, and `*engrams`.

### 2. The Application Layer
* **API**: RESTful interface at `http://localhost:3000/v1/`.
* **Frontend**: Modern React + Vite dashboard for managing memories.
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

### 3. Run Engine

```bash
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

---

## 🧰 Utility Tools

### Codebase Scraper (`read_all.js`)

Consolidate an entire project into a digestable corpus for the engine.

```bash
node read_all.js <path_to_project_root>
```

**Output**: `codebase/combined_context.yaml`
**Usage**: Drop the result into `notebook/inbox` to instantly ingest a project.

---

## License

Elastic License 2.0. Copyright (c) 2026 External Context Engine. See [LICENSE](LICENSE) for full terms.