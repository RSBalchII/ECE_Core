/**
 * Explore Service — Illuminate / BFS Graph Traversal
 *
 * Given seed concepts or atom IDs, performs a breadth-first traversal of the
 * STAR co-occurrence graph and returns the reachable subgraph. This is
 * "structural corpus compression": the returned molecule set is the distilled
 * meaning of the seed topic, extracted from the full knowledge graph.
 *
 * Two traversal strategies:
 *   1. Edge-based  — follows the `edges` table (source_id / target_id / weight)
 *   2. Tag-based   — follows shared tags in the `tags` table (fallback if no edges)
 */

import { db } from '../../core/db.js';
import { StructuredLogger } from '../../utils/structured-logger.js';

/** PGlite WASM has a practical call-stack limit on large parameter arrays
 *  AND on large result payloads (result data is marshaled through WASM stack).
 *
 *  Three limits:
 *  - CHUNK_IDS: INPUT parameter count for ID/tag queries
 *  - CHUNK_CONTENT: rows returned when query includes content column (~1KB/row)
 *  - CHUNK_RESULT_IDS: rows returned for ID-only queries (large fan-out joins)
 *    e.g. 100 hub IN-params → potentially 10K molecule rows — must cap output.
 *    ~500 × 20 bytes ≈ 10KB per batch — well below WASM limit.
 */
const PGLITE_CHUNK_IDS        = 100;  // IN-param count for lightweight queries
const PGLITE_CHUNK_CONTENT    =  25;  // Rows returned when content column included
const PGLITE_CHUNK_RESULT_IDS = 500;  // Rows returned for ID-only fan-out queries

export interface ExploreRequest {
  seed: {
    query?: string;
    atom_ids?: string[];
    limit_seeds?: number;
    /** Global mode: use top-degree nodes as seeds, no query required */
    global?: boolean;
    /** How many top-degree nodes to use as seeds (global mode only, default 10) */
    seed_count?: number;
  };
  max_depth?: number;
  min_weight?: number;
  max_nodes?: number;
  format?: 'flat' | 'graph';
  /**
   * Character budget for output content. BFS collects freely then trims to
   * fit. Most-connected nodes (by subgraph degree) are kept first.
   * ~4 chars ≈ 1 token, so 200_000 chars ≈ 50k tokens.
   */
  max_chars?: number;
  /**
   * Auto-derive max_chars from corpus size.
   * Budget = (total corpus chars) / compression_ratio (default 1000).
   * e.g. 500M-token corpus (~2B chars) → 2M chars at ratio 1000.
   */
  auto_budget?: boolean;
  /** Compression ratio for auto_budget (default 1000) */
  compression_ratio?: number;
}

export interface ExploreNode {
  id: string;
  content: string;
  source: string;
  tags: string[];
  /** Hub-rank score: 1.0 = most connected node, approaches 0 for least connected.
   *  Only present for illuminate-global results; undefined for BFS results. */
  score?: number;
  /** Source content timestamp (epoch ms). Reflects date of original content,
   *  not ingestion time. Use to reconstruct chronology. */
  timestamp?: number;
}

export interface ExploreEdge {
  source: string;
  target: string;
  weight: number;
}

export interface ExploreResult {
  nodes: ExploreNode[];
  edges?: ExploreEdge[];
  stats: {
    nodes_count: number;
    edges_count?: number;
    seed_nodes: number;
    max_depth_achieved: number;
    strategy: string;
    chars_used?: number;
    char_budget?: number;
  };
}

/** Resolve seed atom IDs from query text via FTS */
async function resolveSeedsByQuery(query: string, limit: number): Promise<string[]> {
  const terms = query
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map(t => `${t}:*`)
    .join(' & ');

  if (!terms) return [];

  try {
    const result = await db.run(
      `SELECT id FROM atoms
       WHERE to_tsvector('simple', content) @@ to_tsquery('simple', $1)
       LIMIT $2`,
      [terms, limit]
    );
    return (result.rows as any[]).map(r => r.id);
  } catch {
    // Fallback: LIKE search
    const like = `%${query.split(' ')[0]}%`;
    const result = await db.run(
      `SELECT id FROM atoms WHERE content ILIKE $1 LIMIT $2`,
      [like, limit]
    );
    return (result.rows as any[]).map(r => r.id);
  }
}

/** BFS via edges table */
async function bfsViaEdges(
  seeds: string[],
  maxDepth: number,
  minWeight: number,
  maxNodes: number
): Promise<{ nodeIds: string[]; edges: ExploreEdge[] }> {
  const visited = new Set<string>(seeds);
  let frontier = [...seeds];
  const allEdges: ExploreEdge[] = [];

  for (let depth = 0; depth < maxDepth && frontier.length > 0; depth++) {
    // Chunk frontier to stay under PGlite parameter limit
    const chunks: string[][] = [];
    for (let i = 0; i < frontier.length; i += PGLITE_CHUNK_IDS) {
      chunks.push(frontier.slice(i, i + PGLITE_CHUNK_IDS));
    }

    const nextFrontier: string[] = [];

    // Execute all chunk queries in parallel
    const queryPromises = chunks.map(chunk => {
      const placeholders = chunk.map((_, i) => `$${i + 2}`).join(', ');
      return db.run(
        `SELECT source_id, target_id, weight FROM edges
         WHERE (source_id IN (${placeholders}) OR target_id IN (${placeholders}))
           AND weight >= $1`,
        [minWeight, ...chunk]
      );
    });

    const results = await Promise.all(queryPromises);

    // Process results synchronously to maintain graph traversal properties
    for (const result of results) {
      for (const row of result.rows as any[]) {
        const neighbor = visited.has(row.source_id) ? row.target_id : row.source_id;
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          nextFrontier.push(neighbor);
        }
        allEdges.push({ source: row.source_id, target: row.target_id, weight: row.weight });
      }
    }

    frontier = nextFrontier;
    if (visited.size >= maxNodes) break;
  }

  // visited contains both mem_ (compound hubs) and atom_ IDs — only atoms have content
  const atomIds = [...visited].filter(id => id.startsWith('atom_')).slice(0, maxNodes);
  return {
    nodeIds: atomIds,
    edges: allEdges
  };
}

/** BFS via shared tags (fallback when edges table is sparse/empty) */
async function bfsViaTags(
  seeds: string[],
  maxDepth: number,
  maxNodes: number
): Promise<{ nodeIds: string[] }> {
  const visited = new Set<string>(seeds);
  let frontier = [...seeds];

  for (let depth = 0; depth < maxDepth && frontier.length > 0; depth++) {
    const chunks: string[][] = [];
    for (let i = 0; i < frontier.length; i += PGLITE_CHUNK_IDS) {
      chunks.push(frontier.slice(i, i + PGLITE_CHUNK_IDS));
    }

    const nextFrontier: string[] = [];

    // Execute all chunk queries in parallel
    const queryPromises = chunks.map(chunk => {
      const placeholders = chunk.map((_, i) => `$${i + 1}`).join(', ');
      return db.run(
        `SELECT DISTINCT t2.atom_id
         FROM tags t1
         JOIN tags t2 ON t1.tag = t2.tag AND t1.atom_id != t2.atom_id
         WHERE t1.atom_id IN (${placeholders})`,
        chunk
      );
    });

    const results = await Promise.all(queryPromises);

    // Process results synchronously to maintain graph traversal properties
    for (const result of results) {
      for (const row of result.rows as any[]) {
        if (!visited.has(row.atom_id)) {
          visited.add(row.atom_id);
          nextFrontier.push(row.atom_id);
        }
      }
    }

    frontier = nextFrontier;
    if (visited.size >= maxNodes) break;
  }

  return { nodeIds: [...visited].slice(0, maxNodes) };
}

/** Fetch full atom details for a list of IDs — chunked to avoid PGlite param overflow */
async function fetchNodes(ids: string[]): Promise<ExploreNode[]> {
  if (ids.length === 0) return [];

  const atomRows: any[] = [];
  const tagRows: any[] = [];

  // Execute Content and Tag queries in parallel chunks
  const contentPromises = [];
  for (let i = 0; i < ids.length; i += PGLITE_CHUNK_CONTENT) {
    const chunk = ids.slice(i, i + PGLITE_CHUNK_CONTENT);
    const placeholders = chunk.map((_, j) => `$${j + 1}`).join(', ');
    contentPromises.push(db.run(
      `SELECT id, content, source_path, timestamp FROM atoms WHERE id IN (${placeholders})`,
      chunk
    ));
  }

  const tagPromises = [];
  for (let i = 0; i < ids.length; i += PGLITE_CHUNK_IDS) {
    const chunk = ids.slice(i, i + PGLITE_CHUNK_IDS);
    const placeholders = chunk.map((_, j) => `$${j + 1}`).join(', ');
    tagPromises.push(db.run(
      `SELECT atom_id, tag FROM tags WHERE atom_id IN (${placeholders})`,
      chunk
    ));
  }

  const [contentResults, tagResults] = await Promise.all([
    Promise.all(contentPromises),
    Promise.all(tagPromises)
  ]);

  for (const aResult of contentResults) {
    atomRows.push(...(aResult.rows as any[]));
  }

  for (const tResult of tagResults) {
    tagRows.push(...(tResult.rows as any[]));
  }

  const tagMap = new Map<string, string[]>();
  for (const row of tagRows) {
    if (!tagMap.has(row.atom_id)) tagMap.set(row.atom_id, []);
    tagMap.get(row.atom_id)!.push(row.tag);
  }

  return atomRows.map(r => ({
    id: r.id,
    content: r.content,
    source: r.source_path || '',
    tags: tagMap.get(r.id) || [],
    ...(r.timestamp != null && { timestamp: Number(r.timestamp) })
  }));
}

/** Check if the edges table has any rows */
async function edgesTableHasData(): Promise<boolean> {
  try {
    const result = await db.run(`SELECT 1 FROM edges LIMIT 1`, []);
    return (result.rows as any[]).length > 0;
  } catch {
    return false;
  }
}

/**
 * Global mode: return the top N atom IDs by weighted degree centrality.
 * These are the most interconnected nodes in the entire corpus — the spine.
 */
async function globalTopNodes(seedCount: number, minWeight: number): Promise<string[]> {
  const result = await db.run(
    `SELECT id, SUM(weight) AS total_weight
     FROM (
       SELECT source_id AS id, weight FROM edges WHERE weight >= $1
       UNION ALL
       SELECT target_id AS id, weight FROM edges WHERE weight >= $1
     ) all_edges
     GROUP BY id
     ORDER BY total_weight DESC
     LIMIT $2`,
    [minWeight, seedCount]
  );
  return (result.rows as any[]).map(r => r.id);
}

/** Estimate total corpus char size for auto_budget calculation */
async function estimateCorpusChars(): Promise<number> {
  const result = await db.run(
    `SELECT COUNT(*) AS atom_count, AVG(LENGTH(content)) AS avg_len FROM atoms`,
    []
  );
  const row = (result.rows as any[])[0];
  return Math.round((row.atom_count ?? 0) * (row.avg_len ?? 0));
}

/**
 * Rank nodes by their subgraph degree (sum of edge weights within result set).
 * Returns node IDs ordered most-connected first.
 */
function rankNodesBySubgraphDegree(
  nodeIds: string[],
  edges: ExploreEdge[]
): string[] {
  // Edges connect mem_ hubs → atom_ nodes; score each atom by how many edges touch it
  const score = new Map<string, number>();
  for (const id of nodeIds) score.set(id, 0);
  for (const e of edges) {
    // source may be mem_ or atom_; target is typically atom_
    if (score.has(e.source)) score.set(e.source, score.get(e.source)! + e.weight);
    if (score.has(e.target)) score.set(e.target, score.get(e.target)! + e.weight);
  }
  return [...score.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([id]) => id);
}

/** For global illuminate: fetch content atoms from the top-degree compound hubs.
 *
 *  Content atoms have a compound_id pointing to their parent mem_ compound.
 *  The most-connected compounds (highest weighted degree) contain the most
 *  cross-referenced content in the corpus — their atoms are the corpus narrative.
 *
 *  Atoms are returned in compound rank order (most-connected compound first),
 *  then by start_byte within each compound (document reading order).
 *
 *  NOTE: the tags table only indexes tag stub atoms (source_path='atom_source').
 *  Content atom tags live in atoms.tags (JSON column). The compound_id link is
 *  the reliable path to content from a hub compound.
 */
async function fetchContentAtomsByHubs(
  hubIds: string[],  // mem_ compound IDs ordered by importance (most connected first)
  maxCount: number
): Promise<string[]> {
  if (hubIds.length === 0) return [];

  const allIds: string[] = [];

  // Parallelize by batching a controlled number of chunk queries together
  // to avoid over-fetching while still improving throughput.
  // E.g. fetch 3 chunks at a time (300 hubs).
  const BATCH_SIZE = 3;

  for (let i = 0; i < hubIds.length && allIds.length < maxCount; i += PGLITE_CHUNK_IDS * BATCH_SIZE) {
    const batchPromises = [];
    const remaining = maxCount - allIds.length;

    // Create up to BATCH_SIZE promises
    for (let j = 0; j < BATCH_SIZE; j++) {
      const chunkStart = i + (j * PGLITE_CHUNK_IDS);
      if (chunkStart >= hubIds.length) break;

      const chunk = hubIds.slice(chunkStart, chunkStart + PGLITE_CHUNK_IDS);
      const placeholders = chunk.map((_, k) => `$${k + 1}`).join(', ');

      batchPromises.push(db.run(
        `SELECT id FROM atoms
         WHERE compound_id IN (${placeholders})
           AND source_path != 'atom_source'
           AND id NOT LIKE 'mem_%'
         ORDER BY start_byte
         LIMIT ${Math.min(remaining, PGLITE_CHUNK_RESULT_IDS)}`,
        chunk
      ));
    }

    const batchResults = await Promise.all(batchPromises);

    // Flatten batch results maintaining order
    for (const result of batchResults) {
      allIds.push(...(result.rows as any[]).map((r: any) => r.id));
    }
  }

  // Trim the final result to maxCount
  return allIds.slice(0, maxCount);
}


export async function exploreMemory(req: ExploreRequest): Promise<ExploreResult> {
  const maxDepth= Math.min(req.max_depth ?? 2, 4);
  const minWeight = req.min_weight ?? 0.1;
  const limitSeeds = req.seed.limit_seeds ?? 5;
  const seedCount = req.seed.seed_count ?? 10;
  const format = req.format ?? 'flat';

  // Budget-aware max_nodes: if a char budget is active, allow up to 10k nodes
  // (trimming happens after fetch). Otherwise honour explicit max_nodes cap.
  const hasBudget = req.max_chars !== undefined || req.auto_budget;
  const maxNodes = hasBudget
    ? Math.min(req.max_nodes ?? 10_000, 10_000)
    : Math.min(req.max_nodes ?? 50, 200);

  // 1. Resolve seeds
  let seedIds: string[] = [];

  if (req.seed.global) {
    // Global mode: top-degree nodes, no query needed
    seedIds = await globalTopNodes(seedCount, minWeight);
  } else {
    if (req.seed.atom_ids?.length) {
      seedIds = req.seed.atom_ids;
    }
    if (req.seed.query && seedIds.length < limitSeeds) {
      const fromQuery = await resolveSeedsByQuery(req.seed.query, limitSeeds - seedIds.length);
      seedIds = [...new Set([...seedIds, ...fromQuery])];
    }
  }

  if (seedIds.length === 0) {
    StructuredLogger.warn('EXPLORE_NO_SEEDS', { query: req.seed.query, global: req.seed.global });
    return {
      nodes: [],
      stats: { nodes_count: 0, seed_nodes: 0, max_depth_achieved: 0, strategy: 'none' }
    };
  }

  const actualSeedCount = seedIds.length;
  StructuredLogger.info('EXPLORE_START', { seeds: actualSeedCount, max_depth: maxDepth, max_nodes: maxNodes });

  // 2. BFS traversal — prefer edges table, fall back to tag-based
  let nodeIds: string[];
  let edges: ExploreEdge[] = [];
  let strategy: string;

  if (req.seed.global) {
    // Illuminate mode: skip edge-BFS entirely.
    // Get a larger pool of top-degree compound hubs (seed_count × 20, max 500),
    // then pull their content atoms directly via compound_id.
    // Hub order = weighted degree rank → atoms from most-connected compounds come first.
    const hubCount = Math.min((req.seed.seed_count ?? 10) * 20, 500);
    const hubIds = await globalTopNodes(hubCount, minWeight);
    const contentIds = await fetchContentAtomsByHubs(hubIds, maxNodes);
    StructuredLogger.info('EXPLORE_ILLUMINATE_CONTENT', {
      hubs_queried: hubIds.length,
      content_atoms: contentIds.length
    });
    nodeIds = contentIds;
    strategy = 'illuminate-global';
  } else {
    const hasEdges = await edgesTableHasData();
    if (hasEdges) {
      const result = await bfsViaEdges(seedIds, maxDepth, minWeight, maxNodes);
      nodeIds = result.nodeIds;
      edges = result.edges;
      strategy = 'edge-bfs';
    } else {
      const result = await bfsViaTags(seedIds, maxDepth, maxNodes);
      nodeIds = result.nodeIds;
      strategy = 'tag-bfs';
    }
  }

  // 4. Resolve char budget
  let charBudget: number | undefined;
  if (req.auto_budget) {
    const corpusChars = await estimateCorpusChars();
    const ratio = req.compression_ratio ?? 1000;
    charBudget = Math.max(Math.round(corpusChars / ratio), 50_000); // floor 50k chars
    StructuredLogger.info('EXPLORE_AUTO_BUDGET', { corpus_chars: corpusChars, ratio, budget: charBudget });
  } else if (req.max_chars !== undefined) {
    charBudget = req.max_chars;
  }

  // 5. Fetch node details — then trim to budget by importance
  let finalNodeIds = nodeIds;
  if (charBudget !== undefined) {
    // illuminate-global: nodeIds already ranked by tag centrality; just trim by char budget
    // edge-bfs: rank by subgraph degree first
    const ranked = edges.length > 0
      ? rankNodesBySubgraphDegree(nodeIds, edges)
      : nodeIds; // already ranked
    const trimmed: string[] = [];
    let usedChars = 0;
    const allNodes = await fetchNodes(ranked);
    for (const node of allNodes) {
      if (usedChars + node.content.length > charBudget) break;
      trimmed.push(node.id);
      usedChars += node.content.length;
    }
    finalNodeIds = trimmed;
    StructuredLogger.info('EXPLORE_BUDGET_TRIM', {
      before: nodeIds.length,
      after: trimmed.length,
      chars_used: usedChars,
      budget: charBudget
    });
  }

  const nodes = await fetchNodes(finalNodeIds);

  // For illuminate-global: assign hub-rank score (1.0 = most central, ~0 = least).
  // finalNodeIds is already ordered by centrality; map position → score.
  let scoredNodes: ExploreNode[];
  if (req.seed.global) {
    const total = finalNodeIds.length;
    const rankMap = new Map<string, number>();
    finalNodeIds.forEach((id, i) => rankMap.set(id, parseFloat(((total - i) / total).toFixed(4))));
    scoredNodes = nodes.map(n => ({ ...n, score: rankMap.get(n.id) ?? 0 }));
    // Re-sort by score descending so output order matches centrality rank
    scoredNodes.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  } else {
    scoredNodes = nodes;
  }

  StructuredLogger.info('EXPLORE_DONE', { nodes: scoredNodes.length, edges: edges.length, strategy });

  const charsUsed = scoredNodes.reduce((sum, n) => sum + n.content.length, 0);

  if (format === 'graph') {
    const nodeSet = new Set(finalNodeIds);
    const filteredEdges = edges.filter(e => nodeSet.has(e.source) && nodeSet.has(e.target));
    return {
      nodes: scoredNodes,
      edges: filteredEdges,
      stats: {
        nodes_count: scoredNodes.length,
        edges_count: filteredEdges.length,
        seed_nodes: actualSeedCount,
        max_depth_achieved: maxDepth,
        strategy,
        chars_used: charsUsed,
        ...(charBudget !== undefined && { char_budget: charBudget })
      }
    };
  }

  return {
    nodes: scoredNodes,
    stats: {
      nodes_count: scoredNodes.length,
      seed_nodes: actualSeedCount,
      max_depth_achieved: maxDepth,
      strategy,
      chars_used: charsUsed,
      ...(charBudget !== undefined && { char_budget: charBudget })
    }
  };
}
