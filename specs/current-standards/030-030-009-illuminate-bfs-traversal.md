# Standard 009: Illuminate & Explore — Corpus Traversal Modes

**Status:** ✅ Active | **Version:** 2.0 | **Date:** 2026-03-08  
**Introduced:** v4.5.1 | **Revised:** v4.5.2

---

## 1. Purpose

Define two complementary corpus traversal modes accessible via `POST /v1/memory/explore`:

| Mode | UI Prefix | Seed | Returns | Primary Use |
|---|---|---|---|---|
| **Explore** | `explore: <query>` | FTS query or atom IDs | Tag-hub concept map | Discover what topics exist; skeleton for LLM orientation |
| **Illuminate** | `illuminate:` (empty) | Global top-degree hubs | Ranked content atoms | Read the corpus narrative; surface representative passages |

**Design principle:** Explore reveals the *shape* of the data. Illuminate reads the *substance* of it.

---

## 2. Explore Mode — Concept Skeleton

### What it does

BFS traversal from query-resolved seeds through the `edges` graph. Because edges connect `mem_` compound hubs to `atom_` tag nodes (`relation='has_tag'`), the reachable set is the **concept spine** of the corpus for that topic.

### Why it matters

An LLM receiving explore output sees which topics exist and how they cluster — without reading any actual content. This orients the model to the shape of the dataset and prevents hallucination by grounding it in real tag vocabulary.

**Example output:** `#rust`, `#architecture`, `#memory`, `#search`, `#authentication` → the model now knows these are the core themes and can formulate targeted queries.

### Seed resolution

```sql
SELECT id FROM atoms
WHERE to_tsvector('simple', content) @@ to_tsquery('simple', $terms)
LIMIT $limit_seeds
```

Falls back to `ILIKE` if FTS returns nothing.

---

## 3. Illuminate Mode — Corpus Narrative

### What it does

Three-phase global traversal — no query required:

**Phase 1: Find top-degree hubs**
```sql
SELECT id, SUM(weight) AS total_weight
FROM (
  SELECT source_id AS id, weight FROM edges WHERE weight >= $min_weight
  UNION ALL
  SELECT target_id AS id, weight FROM edges WHERE weight >= $min_weight
) all_edges
GROUP BY id ORDER BY total_weight DESC LIMIT $seed_count
```
Returns the `mem_` compound IDs with the most edge connections — the most cross-referenced documents.

**Phase 2: BFS to tag atoms (concept spine)**
Edge-BFS from those hubs reaches the `atom_` tag nodes connected to them: the tags that appear most broadly across the corpus.

**Phase 3: Content pull ranked by thematic centrality**
```sql
SELECT atom_id, COUNT(*) AS matches
FROM tags
WHERE tag IN (<top_tag_labels>)
GROUP BY atom_id
ORDER BY matches DESC
```
Each content atom's score = how many of the top-hub tags it shares. An atom tagged `#rust` + `#code` + `#anchor` scores higher than one with only `#rust`.

### Result

The most thematically central content atoms in the corpus — actual passages, not stubs — ordered by how many core themes they touch. With `auto_budget`, the output is proportionally sized to the corpus (default: corpus_chars / 1000).

### Why this is powerful

A 350M-character corpus → ~350K characters of output (1000:1 compression). The output is not a summary — it is the actual most-representative atoms from the real data, selected by graph topology. An LLM reading this can infer the full corpus structure without hallucination.

---

## 4. API Contract

### Endpoint

`POST /v1/memory/explore`

### Explore request

```json
{
  "seed": { "query": "rust memory architecture", "limit_seeds": 5 },
  "max_depth": 2,
  "min_weight": 0.1,
  "max_nodes": 50,
  "format": "flat"
}
```

### Illuminate request (global mode)

```json
{
  "seed": { "global": true, "seed_count": 10 },
  "max_depth": 3,
  "auto_budget": true,
  "compression_ratio": 1000
}
```

### Full parameter table

| Field | Type | Default | Description |
|---|---|---|---|
| `seed.query` | string | — | FTS query for explore mode |
| `seed.atom_ids` | string[] | [] | Explicit seed IDs |
| `seed.limit_seeds` | number | 5 | Max seeds from query |
| `seed.global` | boolean | false | Illuminate mode: use top-degree hubs |
| `seed.seed_count` | number | 10 | How many top hubs to start from |
| `max_depth` | number | 2 | BFS hops (max 4) |
| `min_weight` | number | 0.1 | Min edge weight to follow |
| `max_nodes` | number | 50 (explore) / 10000 (illuminate) | Result cap |
| `auto_budget` | boolean | false | Auto-size output to corpus proportion |
| `compression_ratio` | number | 1000 | corpus_chars / ratio = char budget |
| `max_chars` | number | — | Explicit char budget override |
| `format` | `flat\|graph` | `flat` | Response shape |

---

## 5. Implementation

### Files

| File | Role |
|---|---|
| `engine/src/services/search/explore.ts` | BFS service — both modes |
| `engine/src/routes/v1/memory.ts` | Route handler |

### Key functions

| Function | Mode | Purpose |
|---|---|---|
| `globalTopNodes()` | Illuminate | Weighted degree centrality via edge SUM |
| `bfsViaEdges()` | Both | Edge-table BFS, frontier chunked at `PGLITE_CHUNK_IDS=100` |
| `fetchContentAtomsByTopTags()` | Illuminate | Phase 3 content pull ranked by thematic centrality |
| `fetchNodes()` | Both | Content fetch chunked at `PGLITE_CHUNK_CONTENT=25` |
| `rankNodesBySubgraphDegree()` | Explore | Ranks atoms by intra-result edge weights for budget trim |

### PGlite WASM limits

Two chunk constants guard against WASM call-stack overflow:

```typescript
const PGLITE_CHUNK_IDS     = 100;  // ID/tag queries — small result rows
const PGLITE_CHUNK_CONTENT =  25;  // Content queries — ~1KB/row avg
```

Content queries at 200+ rows cause WASM heap corruption and permanently break the DB connection — all subsequent queries fail including `SELECT 1`. Chunking prevents this.

---

## 6. UI Integration

| Prefix | Sends | Result |
|---|---|---|
| `illuminate:` (empty) | `seed: { global: true }` + `auto_budget: true` | Content atoms, corpus-proportional |
| `illuminate: <topic>` | `seed: { query: topic }` | Explore BFS from topic seeds |
| `explore: <topic>` | `seed: { query: topic }` | Same as illuminate with query |
| `deep:` | search endpoint | Max-recall multi-hop |
| `exact:` | search endpoint | FTS only |
| *(none)* | search endpoint | STAR auto search |

---

## 7. MCP Integration

The `anchor_explore` tool supports both modes:

```json
{
  "name": "anchor_explore",
  "inputSchema": {
    "query": "seed query (optional if global=true)",
    "global": false,
    "seed_count": 10,
    "max_depth": 2,
    "auto_budget": false,
    "max_nodes": 50,
    "format": "flat | graph"
  }
}
```

---

## 8. Related Standards

- **Standard 065:** Graph Associative Retrieval (Tag-Walker)
- **Standard 086:** Dual-Strategy Search
- **Standard 104:** Universal Semantic Search
- **Standard 115:** GitHub Repository Ingestion

---

**Introduced:** v4.5.1 | **Revised:** v4.5.2  
**Owner:** Anchor Engine Team


**Status:** ✅ Active | **Version:** 1.0 | **Date:** 2026-03-08  
**Introduced:** v4.5.1

---

## 1. Purpose

Define the **Illuminate** traversal mode: a breadth-first search (BFS) of the STAR co-occurrence graph from one or more seed concepts. Returns the full connected subgraph reachable within a depth limit — the "spine" of meaning for a topic across the entire ingested corpus.

This is distinct from search: search finds the *best-matching* atoms. Illuminate finds *everything connected* to a concept, enabling structural corpus compression.

---

## 2. Core Concept: Structural Corpus Compression

When a large corpus (e.g., 1GB+ of chat history) is ingested:

1. **Atomization** — content is split into molecules with tags.
2. **SimHash deduplication** — near-identical ideas across sessions collapse into high-weight edges.
3. **Co-occurrence graph** — shared tags create `edges` table entries (source_id, target_id, weight).

The resulting graph is structurally compressed: 500M tokens of input become ~250K atoms where the most recurring concepts have the highest edge weights.

**Illuminate extracts the spine:** BFS traversal from a seed query returns the molecules that survived deduplication and have the most connections — i.e., the ideas that appeared most consistently across all sessions.

**Properties:**
- **Lossless structural**: original atoms are still in the DB; only redundancy is removed
- **Deterministic**: same query returns the same subgraph
- **Explainable**: every node and edge is a real molecule from the corpus, not generated text

---

## 3. API Contract

### Endpoint

`POST /v1/memory/explore`

### Request

```json
{
  "seed": {
    "query": "physics walker STAR algorithm",
    "atom_ids": ["atom_abc123"],
    "limit_seeds": 5
  },
  "max_depth": 2,
  "min_weight": 0.1,
  "max_nodes": 50,
  "format": "flat"
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `seed.query` | string | — | FTS query to find seed atoms |
| `seed.atom_ids` | string[] | [] | Explicit seed IDs (takes precedence) |
| `seed.limit_seeds` | number | 5 | Max seeds from query |
| `max_depth` | number | 2 | BFS hops (max 4) |
| `min_weight` | number | 0.1 | Min edge weight to follow |
| `max_nodes` | number | 50 | Result cap (max 200) |
| `format` | `flat\|graph` | `flat` | flat = atom list; graph = nodes + edges |

At least one of `seed.query` or `seed.atom_ids` is required.

### Response (flat)

```json
{
  "results": [
    { "id": "atom_...", "content": "...", "source": "file.md", "tags": ["#STAR"], "score": 1 }
  ],
  "nodes": [...],
  "stats": {
    "nodes_count": 30,
    "seed_nodes": 5,
    "max_depth_achieved": 2,
    "strategy": "edge-bfs"
  },
  "duration_ms": 19
}
```

### Response (graph)

```json
{
  "nodes": [...],
  "edges": [
    { "source": "atom_abc", "target": "atom_xyz", "weight": 0.85 }
  ],
  "stats": { "nodes_count": 30, "edges_count": 40, "seed_nodes": 5, ... }
}
```

---

## 4. Implementation

### Files

| File | Role |
|---|---|
| `engine/src/services/search/explore.ts` | BFS service — seed resolution, traversal, node fetch |
| `engine/src/routes/v1/memory.ts` | Route handler for `POST /v1/memory/explore` |
| `engine/src/routes/api.ts` | Registers `setupMemoryRoutes()` |

### Traversal Strategy

**Primary: edge-BFS** — used when `edges` table has data:

```sql
SELECT source_id, target_id, weight FROM edges
WHERE (source_id IN ($frontier) OR target_id IN ($frontier))
  AND weight >= $min_weight
```

Applied iteratively per depth level. Visited set prevents cycles.

**Fallback: tag-BFS** — used when edges table is empty (fresh DB):

```sql
SELECT DISTINCT t2.atom_id
FROM tags t1
JOIN tags t2 ON t1.tag = t2.tag AND t1.atom_id != t2.atom_id
WHERE t1.atom_id IN ($frontier)
```

### Seed Resolution

```
FTS: SELECT id FROM atoms
     WHERE to_tsvector('simple', content) @@ to_tsquery('simple', $terms)
     LIMIT $limit_seeds
```

Falls back to `ILIKE` if FTS returns nothing.

---

## 5. UI Integration: Search Prefix System

The UI search box supports prefixes that route to different algorithms:

| Prefix | Algorithm | Endpoint |
|---|---|---|
| `illuminate:` | BFS graph traversal | `/v1/memory/explore` |
| `explore:` | BFS graph traversal (alias) | `/v1/memory/explore` |
| `deep:` | Max-recall multi-hop search | `/v1/memory/search` + `deep: true` |
| `exact:` | FTS only, no physics walker | `/v1/memory/search` |
| *(none)* | Auto STAR search | `/v1/memory/search` |

Prefix parsing is client-side in `engine/public/index.html` — the `parseQuery()` function strips the prefix before forwarding the cleaned query.

A `?` tooltip next to the search input lists available prefixes.

---

## 6. MCP Integration

The `anchor-mcp` server exposes `anchor_explore` tool:

```json
{
  "name": "anchor_explore",
  "description": "BFS illuminate: returns connected subgraph from seed concepts",
  "inputSchema": {
    "query": "seed query string",
    "max_depth": 2,
    "min_weight": 0.1,
    "max_nodes": 50,
    "format": "flat | graph"
  }
}
```

The tool auto-falls back to deep search if the engine returns 404 (e.g., older engine version).

---

## 7. Performance

| Corpus size | Seeds | Depth | Nodes returned | Duration |
|---|---|---|---|---|
| 37K molecules (code only) | 5 | 2 | 20 | ~19ms |
| 235K molecules (code + 438 chat files) | 5 | 3 | 50 | ~50ms (estimated) |

Performance scales with edge density, not corpus size. `max_nodes` cap prevents explosion.

---

## 8. Related Standards

- **Standard 065:** Graph Associative Retrieval (Tag-Walker) — also graph-based, but scoring-focused
- **Standard 086:** Dual-Strategy Search — search routing this standard extends
- **Standard 104:** Universal Semantic Search — the default (no-prefix) algorithm
- **Standard 115:** GitHub Repository Ingestion — primary corpus source

---

**Introduced:** v4.5.1  
**Owner:** Anchor Engine Team
