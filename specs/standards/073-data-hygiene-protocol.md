# Standard 073: Data Hygiene Protocol (The Immune System)

## Status: ACTIVE
**Related Standards**: [059-reliable-ingestion](./059-reliable-ingestion.md), [065-graph-retrieval](./065-graph-associative-retrieval.md)

---

## 1. Core Philosophy: "Garbage In, Garbage Out"

The sophistication of the ECE Architecture (Graph-Walkers, RAG, Vector Search) is irrelevant if the input signal is noisy. The **Data Hygiene Protocol** is the system's "Immune System," ensuring that only high-quality, sanitized, and correctly tagged data enters the Knowledge Graph.

The protocol operates on three layers:
1.  **Aggregation Layer**: Rejection of binary and circular trash.
2.  **Refinement Layer**: Surgical removal of artifacts and auto-classification.
3.  **Ingestion Layer**: Merge-based tagging strategies.

---

## 2. Layer 1: Aggregation (The Shield)
**Component**: `read_all.js` (Universal Scraper)

Before data allows enters the pipeline, it must pass a "Allow List" approach:

### 2.1 Binary Inspection
*   **Rule**: Files must be inspected at the buffer level.
*   **Mechanism**: If the first 8000 bytes contain `null` bytes, the file is rejected.
*   **Why**: Extensions like `.ts` or `.txt` can sometimes mask binary dumps.

### 2.2 Feedback Loop Prevention
*   **Rule**: The Aggregator must ignore its own output artifacts.
*   **Mechanism**: Explicit exclusion of `combined_context.yaml`, `combined_memory.yaml`, `combined_context.json`, etc.
*   **Why**: Prevents "infinite mirror" bugs where the system reads its own logs about reading its own logs, exponentially increasing token count.

---

## 3. Layer 2: Refinement (The Surgeon)
**Component**: `refiner.ts`

The Refiner transforms raw text into "Atoms" (Thoughts). It is responsible for **Sanitization** and **Classification**.

### 3.1 The Key Assassin
A heuristic algorithm designed to strip JSON wrappers and execution logs from "Code" files while preserving the actual code structure.

*   **Problem**: When LLMs generate code, they often wrap it in JSON logs (`"response_content": "def foo()..."`). Ingesting this as "code" corrupts the search index with meta-noise.
*   **Solution**:
    1.  **Mask Code Blocks**: Preserve ` ``` ` content.
    2.  **Purge Keys**: Remove `response_content`, `timestamp`: `...`, `type`: `...`.
    3.  **Unescape**: Fix `\n` and `\"` artifacts.
    4.  **Unmask**: Restore the code blocks.

### 3.2 Project Root Extraction (Auto-Tagging)
Context is derived from the filesystem path, not just the content.

*   **Logic**: `path/to/project/src/file.ts` ->
    *   `#project:{project_name}`
    *   `#src` (Structural Tag)
    *   `#code` (Type Tag)

*   **Mapping**:
    *   `/src/` -> `#src`
    *   `/docs/` -> `#docs`
    *   `/tests/` -> `#test`
    *   `/specs/` -> `#specs`

---

## 4. Layer 3: Ingestion (The Librarian)
**Component**: `ingest.ts`

The Ingestion Service is the final checkpoint. Its job is **Integration**.

### 4.1 Merged Tagging Strategy
When atoms arrive with `AutoTags` (from Refiner) and `BatchTags` (from the user/watchdog), they must be merged without duplication.

*   **Formula**: `FinalTags = Unique(BatchTags + AtomTags)`
*   **Example**:
    *   Batch: `["inbox"]`
    *   Atom: `["#src", "#project:ECE_Core"]`
    *   **Result**: `["inbox", "#src", "#project:ECE_Core"]`

### 4.2 Deduplication
*   **Rule**: Idempotency is key.
*   **Mechanism**: Atoms use a deterministic hash of `(FilePath + Content + Sequence Index)`. Re-ingesting the same file generates the same IDs.
*   **Action**: `UPSERT` (Update if exists, Insert if new).

---

## 5. Verification
Every ingestion run must be verified by a "Read-After-Write" check (Standard 059).

*   **Query**: Select ID from DB immediately after write.
*   **Failure**: If ID is missing, throw CRITICAL error and rollback batch (if transaction supported) or alert Watchdog.
