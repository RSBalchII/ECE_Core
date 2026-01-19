/**
 * Search Service with Engram Layer and Provenance Boosting
 *
 * Implements:
 * 1. Engram Layer (Fast Lookup) - O(1) lookup for known entities
 * 2. Provenance Boosting - Sovereign content gets boost
 * 3. Tag-Walker Protocol - Graph-based associative retrieval (Replacing Vector Search)
 */

import { db } from '../../core/db.js';
import { createHash } from 'crypto';
import { composeRollingContext } from '../../core/inference/context_manager.js';

interface SearchResult {
  id: string;
  content: string;
  source: string;
  timestamp: number;
  buckets: string[];
  tags: string;
  epochs: string;
  provenance: string;
  score: number;
}

/**
 * Helper to sanitize queries for CozoDB FTS engine
 */
function sanitizeFtsQuery(query: string): string {
  return query
    .replace(/[^a-zA-Z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

/**
 * Create or update an engram (lexical sidecar) for fast entity lookup
 */
export async function createEngram(key: string, memoryIds: string[]): Promise<void> {
  const normalizedKey = key.toLowerCase().trim();
  const engramId = createHash('md5').update(normalizedKey).digest('hex');

  const insertQuery = `?[key, value] <- $data :put engrams {key, value}`;
  await db.run(insertQuery, {
    data: [[engramId, JSON.stringify(memoryIds)]]
  });
}

/**
 * Lookup memories by engram key (O(1) operation)
 */
export async function lookupByEngram(key: string): Promise<string[]> {
  const normalizedKey = key.toLowerCase().trim();
  const engramId = createHash('md5').update(normalizedKey).digest('hex');

  const query = `?[value] := *engrams{key, value}, key = $engramId`;
  const result = await db.run(query, { engramId });

  if (result.rows && result.rows.length > 0) {
    return JSON.parse(result.rows[0][0] as string);
  }

  return [];
}

/**
 * Perform Graph-Based Associative "Neighbor Walk"
 * Phase 3 of Tag-Walker Algorithm
 */
/**
 * Tag-Walker Associative Search (Replaces Vector Search)
 * Strategy:
 * 1. Anchor (70%): Find direct text matches (FTS).
 * 2. Walk (30%): Find neighbors that share specific tags with the Anchors.
 */
export async function tagWalkerSearch(
  query: string,
  buckets: string[] = [],
  _maxChars: number = 524288
): Promise<SearchResult[]> {
  try {
    const sanitizedQuery = sanitizeFtsQuery(query);
    if (!sanitizedQuery) return [];

    // 1. Direct Search (The Anchor)
    // We use FTS to find the "Entry Nodes" into the graph
    const anchorQuery = `
            ?[id, content, source, timestamp, buckets, tags, epochs, provenance, score] := 
            ~memory:content_fts{id | query: $query, k: 50, bind_score: fts_score},
            *memory{id, content, source, timestamp, buckets, tags, epochs, provenance},
            score = 100.0 * fts_score
            ${buckets.length > 0 ? ', length(intersection(buckets, $buckets)) > 0' : ''}
            :limit 20
        `;

    const anchorResult = await db.run(anchorQuery, { query: sanitizedQuery, buckets });
    if (!anchorResult.rows || anchorResult.rows.length === 0) return [];

    // Map Anchors
    const anchors = anchorResult.rows.map((row: any[]) => ({
      id: row[0],
      content: row[1],
      source: row[2],
      timestamp: row[3],
      buckets: row[4],
      tags: row[5],
      epochs: row[6],
      provenance: row[7],
      score: row[8]
    }));

    // 2. The Walk (Associative Discovery)
    const anchorIds = anchors.map((a: any) => a.id);

    // Cozo Query: Find nodes sharing tags with our anchors
    const walkQuery = `
            ?[id, content, source, timestamp, buckets, tags, epochs, provenance, score] := 
            *memory{id: anchor_id, tags: anchor_tags},
            anchor_id in $anchorIds,
            tag in anchor_tags,
            *memory{id, content, source, timestamp, buckets, tags, epochs, provenance},
            tag in tags,
            id != anchor_id,
            score = 50.0
            :limit 10
        `;

    const walkResult = await db.run(walkQuery, { anchorIds });
    const neighbors = (walkResult.rows || []).map((row: any[]) => ({
      id: row[0],
      content: row[1],
      source: row[2],
      timestamp: row[3],
      buckets: row[4],
      tags: row[5],
      epochs: row[6],
      provenance: row[7],
      score: row[8]
    }));

    return [...anchors, ...neighbors];

  } catch (e) {
    console.error('[Search] Tag-Walker failed:', e);
    return [];
  }
}


/**
 * Execute search with Tag-Walker Protocol
 */
export async function executeSearch(
  query: string,
  bucket?: string,
  buckets?: string[],
  maxChars: number = 524288,
  _deep: boolean = false,
  provenance: 'sovereign' | 'external' | 'all' = 'all'
): Promise<{ context: string; results: SearchResult[]; toAgentString: () => string; metadata?: any }> {
  console.log(`[Search] executeSearch (Tag-Walker) called with provenance: ${provenance}`);

  const targetBuckets = buckets || (bucket ? [bucket] : []);

  // 1. ENGRAM LOOKUP
  const engramResults = await lookupByEngram(query);
  let finalResults: SearchResult[] = [];
  const includedIds = new Set<string>();

  if (engramResults.length > 0) {
    console.log(`[Search] Found ${engramResults.length} via Engram: ${query}`);
    const engramContextQuery = `?[id, content, source, timestamp, buckets, tags, epochs, provenance] := *memory{id, content, source, timestamp, buckets, tags, epochs, provenance}, id in $ids`;
    const engramContentResult = await db.run(engramContextQuery, { ids: engramResults });
    if (engramContentResult.rows) {
      engramContentResult.rows.forEach((row: any[]) => {
        if (!includedIds.has(row[0])) {
          finalResults.push({
            id: row[0], content: row[1], source: row[2], timestamp: row[3], buckets: row[4], tags: row[5], epochs: row[6], provenance: row[7], score: 200
          });
          includedIds.add(row[0]);
        }
      });
    }
  }

  // 2. TAG-WALKER SEARCH (Hybrid FTS + Graph)
  const walkerResults = await tagWalkerSearch(query, targetBuckets, maxChars);

  // Merge and Apply Provenance Boosting
  walkerResults.forEach(r => {
    let score = r.score;

    // Apply Sovereign Bias
    if (provenance === 'sovereign') {
      if (r.provenance === 'sovereign') score *= 3.0;
      else score *= 0.5;
    } else if (provenance === 'external') {
      if (r.provenance !== 'sovereign') score *= 1.5;
    } else {
      if (r.provenance === 'sovereign') score *= 2.0;
    }

    if (!includedIds.has(r.id)) {
      finalResults.push({ ...r, score });
      includedIds.add(r.id);
    }
  });

  console.log(`[Search] Total Results: ${finalResults.length}`);

  // Final Sort by Score
  finalResults.sort((a, b) => b.score - a.score);

  return formatResults(finalResults, maxChars);
}


// Helper for FTS
export async function runTraditionalSearch(query: string, buckets: string[]): Promise<SearchResult[]> {
  const sanitizedQuery = sanitizeFtsQuery(query);

  if (!sanitizedQuery) return [];

  let queryCozo = '';
  // Use single-line query format to avoid parser issues
  if (buckets.length > 0) {
    queryCozo = `?[id, score, content, source, timestamp, buckets, tags, epochs, provenance] := ~memory:content_fts{id | query: $q, k: 500, bind_score: score}, *memory{id, content, source, timestamp, buckets, tags, epochs, provenance}, length(intersection(buckets, $buckets)) > 0`;
  } else {
    queryCozo = `?[id, score, content, source, timestamp, buckets, tags, epochs, provenance] := ~memory:content_fts{id | query: $q, k: 500, bind_score: score}, *memory{id, content, source, timestamp, buckets, tags, epochs, provenance}`;
  }

  try {
    const result = await db.run(queryCozo, { q: sanitizedQuery, buckets });

    if (!result.rows) return [];

    return result.rows.map((row: any[]) => ({
      id: row[0],
      score: row[1],
      content: row[2],
      source: row[3],
      timestamp: row[4],
      buckets: row[5],
      tags: row[6],
      epochs: row[7],
      provenance: row[8]
    }));

  } catch (e) {
    console.error('[Search] FTS failed', e);
    return [];
  }
}

/**
 * Format search results within character budget
 */
function formatResults(results: SearchResult[], maxChars: number): { context: string; results: SearchResult[]; toAgentString: () => string; metadata?: any } {
  // Convert SearchResult to ContextAtom
  const candidates = results.map(r => ({
    id: r.id,
    content: r.content,
    source: r.source,
    timestamp: r.timestamp,
    score: r.score
  }));

  const tokenBudget = Math.floor(maxChars / 4);
  const rollingContext = composeRollingContext("query_placeholder", candidates, tokenBudget);

  const sortedResults = results.sort((a, b) => b.score - a.score);

  return {
    context: rollingContext.prompt || 'No results found.',
    results: sortedResults,
    toAgentString: () => {
      // Safe substring in case content is missing (though our types enforce it)
      return sortedResults.map(r => `[${r.provenance}] ${r.source}: ${(r.content || "").substring(0, 200)}...`).join('\n');
    },
    metadata: rollingContext.stats
  };
}

export function parseQuery(query: string): { phrases: string[]; temporal: string[]; buckets: string[]; keywords: string[]; } {
  const result = { phrases: [] as string[], temporal: [] as string[], buckets: [] as string[], keywords: [] as string[] };
  const phraseRegex = /"([^"]+)"/g;
  let phraseMatch;
  while ((phraseMatch = phraseRegex.exec(query)) !== null) result.phrases.push(phraseMatch[1]);
  let remainingQuery = query.replace(/"[^"]+"/g, '');
  const temporalRegex = /@(\w+)/g;
  let temporalMatch;
  while ((temporalMatch = temporalRegex.exec(remainingQuery)) !== null) result.temporal.push(temporalMatch[1]);
  remainingQuery = remainingQuery.replace(/@\w+/g, '');
  const bucketRegex = /#(\w+)/g;
  let bucketMatch;
  while ((bucketMatch = bucketRegex.exec(remainingQuery)) !== null) result.buckets.push(bucketMatch[1]);
  remainingQuery = remainingQuery.replace(/#\w+/g, '');
  result.keywords = remainingQuery.split(/\s+/).filter(kw => kw.length > 0);
  return result;
}