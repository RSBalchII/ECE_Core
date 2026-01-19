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

#### Phase 1: Anchor Search (70% Budget)
**Goal:** Find "Direct Hits" using Weighted Keyword Search (BM25).
1.  **Execute FTS**: Search for atoms matching the user query.
    *   **Rule**: All FTS queries MUST be passed through `sanitizeFtsQuery` to prevent parser crashes on special characters (e.g., `.org`).
2.  **Boosting**: Boost results that contain query terms in `tags` or `buckets` (2x boost).
3.  **Selection**: Allocate **70%** of the context character budget to these results.

#### Phase 2: Tag Harvest
**Goal:** Identify "Bridge Tags" to find hidden context.
1.  **Extract**: Collect all unique `tags` and `buckets` from the top X results of Phase 1.
2.  **Filter**: Exclude generic system tags if necessary (though strict filtering is often not needed).
3.  **Bridge**: These tags represent the *structural* context of the query.

#### Phase 3: Neighbor Walk (30% Budget)
**Goal:** Find "Associative Hits" (Hidden connections).
1.  **Query**: Find atoms that share the **Harvested Tags** but *do not* contain the original query keywords (or are duplicates of Phase 1).
    *   *Logic*: `atom -> has_tag -> tag -> has_tag -> neighbor_atom`
2.  **Selection**: Allocate the remaining **30%** of the budget to these associative neighbors.

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
