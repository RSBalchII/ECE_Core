# Memory Layer Specification

**Neo4j + Redis tiered architecture. Source of truth for all memories.**

---

## Identity

- **Primary Store:** Neo4j (bolt://localhost:7687)
- **Hot Cache:** Redis (localhost:6379)
- **Export Bridge:** `scripts/export_neo4j_to_sovereign.py`
- **Retention:** Permanent (Neo4j), 24h TTL (Redis)

---

## Architecture Overview

```
User Input
  ↓
FastAPI Backend
  ├─→ Redis (hot cache, 24h TTL)
  │    └─ miss/expire?
  │       ↓
  └─→ Neo4j (primary store, permanent)
         └─ store result in Redis for future hits
```

---

## Neo4j Graph Structure

### Node Types

#### `:Memory` (Primary)
**Purpose:** Individual user interactions, logs, session captures.

**Properties:**
```
{
    id: String (Neo4j internal ID, stringified)
    content: String (message text, log entry, etc.)
    created_at: ISO 8601 or Unix timestamp
    category: String (e.g., "user_input", "system_msg", "assistant_response")
    tags: [String] (optional: topics, entities, importance levels)
    importance: Float (0-1 scale, for prioritization)
    freshness_score: Float (recency boost)
    provenance_score: Float (source reliability)
    metadata: JSON (custom fields, origin tracking)
    app_id: String (which app/context created this)
    session_id: String (which session)
}
```

#### `:Summary` (Distilled)
**Purpose:** Compressed representations of memory groups (context gists).

**Properties:**
```
{
    id: String
    gist: String (1-2 sentence summary)
    period: String (time range covered)
    salience_score: Float (importance of this summary)
    created_at: Timestamp
}
```

### Relationship Types

#### `[:RELATED_TO]` (Semantic)
Connects memories that discuss similar topics.
```
(mem1:Memory) -[:RELATED_TO {similarity_score: 0.87}]-> (mem2:Memory)
```

#### `[:CAUSED_BY]` (Causal)
Memory A triggered or influenced Memory B.
```
(mem1:Memory) -[:CAUSED_BY]-> (mem2:Memory)
```

#### `[:MENTIONS]` (Entity Reference)
Memory mentions an entity (person, project, concept).
```
(mem:Memory) -[:MENTIONS {count: 3}]-> (entity:Entity)
```

#### `[:NEXT_IN_SERIES]` (Chronological Gists)
Chains summaries across time for Graph-R1 retrieval.
```
(gist1:Summary) -[:NEXT_IN_SERIES]-> (gist2:Summary)
```

---

## Redis Cache Strategy

**Purpose:** Reduce Neo4j query load for recent/hot data.

**TTL:** 24 hours

**Cache Keys Pattern:**
```
memory:recency:{time_range}       → [mem_id_1, mem_id_2, ...]
memory:similarity:{query_hash}    → [mem_id_1, mem_id_2, ...]
memory:tag:{tag_name}             → [mem_id_1, mem_id_2, ...]
memory:session:{session_id}       → [mem_id_1, mem_id_2, ...]
```

**Invalidation:**
- Manual: When user tags/labels memories
- Automatic: 24-hour expiration

---

## Data Export: Neo4j → Sovereign

**Tool:** `scripts/export_neo4j_to_sovereign.py`

**Process:**
1. Connect to Neo4j (bolt://localhost:7687)
2. Query all `:Memory` nodes with properties
3. Map Neo4j properties → Sovereign JSON format
4. Timestamp conversion (ISO 8601 → Unix milliseconds)
5. Write to `combined_memory.json`

**Input Mapping:**
```
Neo4j Property      → Sovereign Format
─────────────────────────────────────
id(node)            → id (stringified node ID)
content             → content
created_at          → timestamp (Unix ms)
category            → role (infer: assistant, user, system)
metadata            → source
```

**Output Format:**
```json
[
  {
    "id": "123",
    "timestamp": 1753176645000,
    "role": "user",
    "content": "What is Project Chronos?",
    "source": "neo4j"
  },
  {
    "id": "124",
    "timestamp": 1753176646000,
    "role": "assistant",
    "content": "Project Chronos is...",
    "source": "neo4j"
  }
]
```

**Usage:**
```bash
python scripts/export_neo4j_to_sovereign.py --output combined_memory.json
```

---

## Query Patterns

### Recency-Based Retrieval
```cypher
MATCH (m:Memory)
WHERE m.created_at >= (now() - duration('P7D'))
RETURN m
ORDER BY m.created_at DESC
LIMIT 10
```

### Semantic Search (Entity Mentions)
```cypher
MATCH (m:Memory) -[:MENTIONS]-> (e:Entity {name: "Project Chronos"})
RETURN m
ORDER BY m.importance DESC, m.created_at DESC
```

### Graph-R1 Context Retrieval (Chronological Gists)
```cypher
MATCH (s1:Summary) -[:NEXT_IN_SERIES*]-> (s2:Summary)
WHERE s2.period CONTAINS (now() - duration('P30D'))
RETURN s1, s2
ORDER BY s1.created_at ASC
```

---

## Timestamp Handling

**Neo4j Storage:** ISO 8601 format
```
"2025-12-15T10:30:45Z"
```

**Redis Cache:** Unix epoch (milliseconds)
```
1753176645000
```

**Export (Sovereign):** Unix epoch (milliseconds)
```
1753176645000
```

**Conversion Function:**
```python
def to_unix_ms(neo4j_timestamp):
    if isinstance(neo4j_timestamp, str):
        return int(datetime.fromisoformat(neo4j_timestamp.rstrip('Z')).timestamp() * 1000)
    elif isinstance(neo4j_timestamp, int):
        return neo4j_timestamp if neo4j_timestamp > 10000000000 else neo4j_timestamp * 1000
    return None
```

---

## Write Operations (Neo4j)

### Creating a Memory
```cypher
CREATE (m:Memory {
    id: randomUUID(),
    content: "User message",
    created_at: datetime(),
    category: "user_input",
    tags: ["chronos", "planning"],
    importance: 0.8,
    freshness_score: 0.95,
    provenance_score: 0.9,
    metadata: {source: "local_chat", app: "sovereign"},
    app_id: "context-engine",
    session_id: "sess-xyz"
})
RETURN m
```

### Linking Memories (Semantic)
```cypher
MATCH (m1:Memory {id: "123"}), (m2:Memory {id: "124"})
CREATE (m1) -[:RELATED_TO {similarity_score: 0.85}]-> (m2)
```

### Creating Context Gist
```cypher
CREATE (s:Summary {
    id: randomUUID(),
    gist: "User explored time-travel concepts in context window rotation",
    period: "2025-12-08 to 2025-12-15",
    salience_score: 0.9,
    created_at: datetime()
})
```

---

## Maintenance Operations

### Importance Scoring (Verifier Agent)
```cypher
MATCH (m:Memory)
WHERE m.created_at < (now() - duration('P7D'))
SET m.importance = m.importance * 0.95,
    m.freshness_score = m.freshness_score * 0.90
```

### Archival (Distiller Agent)
```cypher
MATCH (memories) WHERE count(memories) > 1000
CREATE (s:Summary {...}) -[:SUMMARIZES]-> (memories)
```

### Cleanup (Archivist Agent)
```cypher
MATCH (m:Memory)
WHERE m.importance < 0.1 AND m.created_at < (now() - duration('P90D'))
DELETE m
```

---

## Performance Characteristics

- **Query latency:** <100ms (Redis hit), <500ms (Neo4j hit)
- **Write latency:** <200ms (Neo4j + Redis update)
- **Storage:** ~1KB per memory (Neo4j), hot subset in Redis
- **Connection pooling:** 10 connections (configurable)

---

## Related Specs

- See [Sovereign WASM Spec](sovereign-wasm.spec.md) for export consumption
- See [Agents Spec](agents.spec.md) for Verifier, Distiller, Archivist operations
- See [API Spec](api.spec.md) for backend endpoints

---

**Last Updated:** 2025-12-15  
**Status:** Production (211 memories tracked)
