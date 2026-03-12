# API Route Map

**Complete reference for Anchor Engine API endpoints**

**Version:** 4.7.0 | **Last Updated:** March 12, 2026

---

## 📚 API Route Categories

Anchor Engine provides different endpoints for different needs. Here's a quick guide:

| Category | Purpose | Library Analogy | Example |
|----------|---------|-----------------|---------|
| **🔍 Search** | Find specific content | "Find books about dragons" | `POST /v1/memory/search` |
| **🧭 Explore** | Discover connections | "Show me books by this author + related authors" | `POST /v1/memory/explore` |
| **📦 Distill** | Compress knowledge | "Summarize all dragon lore across all books" | `POST /v1/memory/distill` |
| **📥 Ingest** | Add new content | "Add this new book to the library" | `POST /v1/ingest` |
| **📂 Files** | Read/upload files | "Read this specific book" | `GET /v1/files/read` |
| **⚙️ System** | Management | "Is the library open?" | `GET /v1/system/status` |

---

## 🔍 Search Routes

### `POST /v1/memory/search`

**Purpose:** Primary search endpoint with streaming results

**Use when:** You need to find specific content by query

**Request:**
```json
{
  "query": "Zod validation schemas",
  "max_chars": 5000,
  "buckets": ["anchor-engine-node"],
  "provenance": "all",
  "strategy": "standard",
  "batch_size": 20
}
```

**Response (SSE):**
```
event: result
data: {"results": [...], "context": "..."}

event: metadata
data: {"strategy": "standard", "totalResults": 42, "durationMs": 156}
```

**Schema:** `searchSchema` (see `engine/src/schemas/api-schemas.ts`)

---

### `POST /v1/memory/molecule-search`

**Purpose:** Search with molecule-level granularity

**Use when:** You need fine-grained paragraph-level results

**Request:**
```json
{
  "query": "streaming search implementation",
  "deep": false,
  "max_chars": 8000
}
```

**Schema:** `moleculeSearchSchema`

---

### `POST /v1/memory/search-max-recall`

**Purpose:** Maximum recall search for comprehensive results

**Use when:** You need to find everything related to a topic

**Request:**
```json
{
  "query": "physics tag walker",
  "max_chars": 16384
}
```

**Schema:** `maxRecallSearchSchema`

---

## 🧭 Explore Routes

### `POST /v1/memory/explore`

**Purpose:** Graph-based exploration (Illuminate algorithm)

**Use when:** You want to discover connections and related concepts

**Request:**
```json
{
  "seed": {
    "query": "radial distillation",
    "global": false
  },
  "max_depth": 3,
  "max_nodes": 50,
  "format": "flat"
}
```

**Schema:** `exploreSchema`

---

## 📦 Distill Routes

### `POST /v1/memory/distill`

**Purpose:** Lossless corpus compression

**Use when:** You need a condensed summary of a topic across multiple documents

**Request:**
```json
{
  "seed": {
    "query": "Anchor Engine architecture"
  },
  "radius": 3,
  "max_nodes": 500,
  "output_format": "yaml",
  "normalization": "strict"
}
```

**Schema:** `distillSchema`

---

## 📥 Ingest Routes

### `POST /v1/ingest`

**Purpose:** Add new content to the knowledge graph

**Use when:** You have new documents, code, or text to index

**Request:**
```json
{
  "content": "Full text content here...",
  "source": "github:RSBalchII/anchor-engine-node:README.md",
  "type": "markdown",
  "bucket": "anchor-engine-node",
  "tags": ["documentation", "readme"]
}
```

**Schema:** `ingestSchema`

---

## 📂 File Routes

### `GET /v1/files/read`

**Purpose:** Read file content with optional line range

**Use when:** You need to read a specific file

**Request:**
```
GET /v1/files/read?path=/path/to/file.ts&start_line=0&end_line=100
```

**Schema:** `fileReadSchema`

---

## ⚙️ System Routes

### `GET /v1/system/status`

**Purpose:** Check system health and database status

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-12T22:00:00.000Z",
  "message": "Anchor Context Engine is running and database is responsive"
}
```

### `GET /v1/stats`

**Purpose:** Get database statistics

**Response:**
```json
{
  "atoms": 281690,
  "molecules": 45230,
  "compounds": 1250
}
```

---

## 🎯 Decision Tree

**Need to...?**

- **Find specific content?** → `POST /v1/memory/search`
- **See related concepts?** → `POST /v1/memory/explore`
- **Summarize a topic?** → `POST /v1/memory/distill`
- **Add new documents?** → `POST /v1/ingest`
- **Read a specific file?** → `GET /v1/files/read`
- **Check system health?** → `GET /v1/system/status`

---

## 📋 Shared Schemas

All request validation uses shared Zod schemas from `engine/src/schemas/api-schemas.ts`:

| Schema | Used By |
|--------|---------|
| `contextOptionsSchema` | Base for search/explore/distill |
| `searchSchema` | `/v1/memory/search` |
| `moleculeSearchSchema` | `/v1/memory/molecule-search` |
| `maxRecallSearchSchema` | `/v1/memory/search-max-recall` |
| `ingestSchema` | `/v1/ingest` |
| `exploreSchema` | `/v1/memory/explore` |
| `distillSchema` | `/v1/memory/distill` |
| `fileReadSchema` | `/v1/files/read` |
| `errorResponseSchema` | All error responses |

---

## 🔗 Related Standards

- **Standard 104:** Universal Semantic Search
- **Standard 128:** Illuminate BFS Traversal
- **Standard 133:** Radial Distillation
- **Standard 136:** Streaming Search

---

**See also:** [README.md](../README.md) for quick start guide
