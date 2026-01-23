# Standard 065: Graph-Based Associative Retrieval (Semantic-Lite)

**Category:** Architecture / Search
**Status:** Approved
**Date:** 2026-01-19

## Context
Traditional Vector Search (HNSW) poses significant resource overhead (RAM/CPU) and can be unstable in local environments (CozoDB driver issues). Furthermore, for personal knowledge bases, "fuzzy" vector neighbors often hallucinate connections that lack explicit structural relevance.

## The Strategy: "Tag-Walker"
We replace the Vector Layer with a **Graph-Based Associative Retrieval** protocol. This trades geometric distance for explicit graph traversals using `tags` and `buckets`.

### Architecture
| Feature | Vector Architecture | Tag-Walker Architecture |
| --- | --- | --- |
| **Storage** | Atoms + 768d Vectors (Float32) | Atoms + Strings |
| **Index** | HNSW Index (Heavy) | Inverted Index (Light) |
| **Logic** | "Find nearest neighbors in embedding space" | "Traverse edges: Atom -> Tag -> Atom" |

### The Algorithm (70/30 Split)

#### Phase 1: Iterative Anchor Search (Precision First)
**Goal:** Address "Low Recall" by progressively simplifying the query.
1.  **Standard Execution**: Run 70/30 Tag-Walker with the full user query (expanded with NLP).
2.  **Recall Check**: If results < 10 atoms:
    *   **Fallback 1 (Strict Nouns/Dates)**: Strip Verbs/Adjectives, keep only Nouns and Temporal markers ("2025").
    *   **Fallback 2 (Entities Only)**: Strip everything but Proper Nouns ("Rob", "Sovereign").
3.  **Result**: Returns the best possible set of anchors.

#### Phase 2: Smart Multi-Context (The "Markovian" Split)
**Goal:** Ensure broad coverage for complex, multi-subject queries (e.g., "chain of events in Rob's life").
1.  **Trigger**: If Iterative Search still yields **< 10 atoms** (Low Recall).
2.  **Split**: The query is decomposed into its top 3 semantic entities (e.g., "Rob", "Life", "Events").
3.  **Parallel Execution**:
    *   Spawn 3 independent Tag-Walker searches (one per entity).
    *   Allocate sub-budgets to each.
4.  **Merge**: Deduplicate and combine results into a single context window.
5.  **Effect**: The LLM receives context about "Rob" AND "Life", even if they never appear in the same file together.

#### Phase 3: Tag Harvest & Neighbor Walk (Associative)
**Goal:** Find hidden context using "Bridge Tags" from the anchored results.
1.  **Harvest**: Collect unique `tags` from Phase 1 & 2 results.
2.  **Walk**: Find atoms that share these tags but lack the keywords.
3.  **Selection**: Fill the remaining ~30% of the token budget.

### Implementation Guidelines (CozoDB)

**Anchor Search Query (Simplified)**
```cozo
?[id, score, content, tags] := *memory{id, content, tags},
                               ~memory:content_fts{id | query: $query, bind_score: score}
```

**Neighbor Walk Query**
```cozo
?[neighbor_id, neighbor_content] := *memory{id, tags},
                                    member($tag, tags),        # Explode tags from source
                                    *memory{id: neighbor_id, tags: n_tags},
                                    member($tag, n_tags),      # Match neighbor tags
                                    id != neighbor_id          # Exclude self
```

### The "Lazy Tax" Mitigation
To ensure graph connectivity even when users fail to tag notes manually, the **Dreamer Service** should be employed to auto-tag atoms during idle cycles, ensuring a dense node-edge-node graph.

## The Projection: Mirror 2.0 (The Tangible Graph)
To audit and browse the graph without database tools, the engine projects its internal state onto the filesystem.

1. **Structure**: `@bucket/#tag/[Source_Name]_[PathHash].md`
2. **Bundling**: Atoms are bundled by source and tag to prevent file explosion. 
3. **Pagination**: Each bundle is limited to **100 atoms** (approx. 150-300KB) to ensure high readability and fast loading.
4. **Sync Trigger**: Mirror synchronizes immediately after every successful ingestion and during every Dreamer cycle.
5. **Wipe Policy**: The `mirrored_brain` directory is explicitly wiped before synchronization.
6. **Navigation**: Uses `## [ID] Snippet` headers and horizontal rules to separate atoms within a bundle.
