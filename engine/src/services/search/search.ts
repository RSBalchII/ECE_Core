/**
 * Search Service with Engram Layer and Provenance Boosting
 *
 * Implements:
 * 1. Engram Layer (Fast Lookup) - O(1) lookup for known entities
 * 2. Provenance Boosting - Sovereign content gets boost
 * 3. Tag-Walker Protocol - Graph-based associative retrieval (Replacing Vector Search)
 * 4. Intelligent Query Expansion - GLM-assisted decomposition (Standard 069)
 */

import { db } from '../../core/db.js';
import { createHash } from 'crypto';
import { composeRollingContext } from '../../core/inference/context_manager.js';
import wink from 'wink-nlp';
import model from 'wink-eng-lite-web-model';

// Initialize NLP (Fast CPU-based)
const nlp = wink(model);

interface SearchResult {
  id: string;
  content: string;
  source: string;
  timestamp: number;
  buckets: string[];
  tags: string[];
  epochs: string;
  provenance: string;
  score: number;
}

/**
 * Fetch top tags from the system to ground the LLM's query expansion
 */
export async function getGlobalTags(limit: number = 50): Promise<string[]> {
  try {
    // CozoDB aggregation syntax is restrictive in this environment.
    // We fetch unique tags and rely on the list for grounding.
    const query = `
            ?[tag] := *memory{tags}, tag in tags :limit 500
        `;
    const result = await db.run(query);
    if (!result.rows) return [];

    const uniqueTags = [...new Set((result.rows as string[][]).map((r: string[]) => r[0]))];
    return uniqueTags.slice(0, limit) as string[];
  } catch (e) {
    console.error('[Search] Failed to fetch global tags:', e);
    return [];
  }
}

/**
 * Use LLM to expand query into semantically similar system tags
 */
import { getMasterTags } from '../tags/discovery.js';

/**
 * Deterministic Query Expansion (No LLM)
 * Scans the user query for known tags from the master list.
 */
export async function expandQuery(originalQuery: string): Promise<string[]> {
  try {
    const globalTags = getMasterTags(); // This is synchronous file read
    const queryLower = originalQuery.toLowerCase();

    // Find tags specifically mentioned in the query or that substring match
    // Simple heuristic: if query contains the tag, we boost it.
    const foundTags = globalTags.filter(tag => {
      const tagLower = tag.toLowerCase();
      // Check for boundary matches or direct inclusion
      return queryLower.includes(tagLower);
    });

    if (foundTags.length > 0) {
      console.log(`[Search] Deterministically matched tags: ${foundTags.join(', ')}`);
    }
    return foundTags;
  } catch (e) {
    console.error('[Search] Expansion failed:', e);
    return [];
  }
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
 * Natural Language Parser (Standard 070)
 * Uses NLP to extract "Meaningful Tags" (Nouns, Proper Nouns, Important Verbs).
 * This prevents common words ("lately", "been", "working") from killing FTS recall.
 */
function parseNaturalLanguage(query: string): string {
  const doc = nlp.readDoc(query);

  // Extract Nouns and Proper Nouns (The "Subjects")
  // We treat these as the core search tags.
  const nouns = doc.tokens().filter((t: any) => {
    const tag = t.out(nlp.its.pos);
    return tag === 'NOUN' || tag === 'PROPN' || tag === 'ADJ';
  }).out((nlp as any).its.text);

  // If we extracted valid tags, use them. 
  // Otherwise fallback to the original query (sanitized).
  if (nouns.length > 0) {
    // Deduplicate and join
    return [...new Set(nouns)].join(' ').toLowerCase();
  }

  return sanitizeFtsQuery(query);
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
 * Tag-Walker Associative Search (Replaces Vector Search)
 */
export async function tagWalkerSearch(
  query: string,
  buckets: string[] = [],
  tags: string[] = [],
  _maxChars: number = 524288
): Promise<SearchResult[]> {
  try {
    const sanitizedQuery = sanitizeFtsQuery(query);
    if (!sanitizedQuery) return [];

    // 1. Direct Search (The Anchor)
    const anchorQuery = `
            ?[id, content, source, timestamp, buckets, tags, epochs, provenance, score] := 
            ~memory:content_fts{id | query: $query, k: 50, bind_score: fts_score},
            *memory{id, content, source, timestamp, buckets, tags, epochs, provenance},
            score = 70.0 * fts_score
            ${buckets.length > 0 ? ', length(intersection(buckets, $buckets)) > 0' : ''}
            ${tags.length > 0 ? ', length(intersection(tags, $tags)) > 0' : ''}
            :limit 20
        `;

    const anchorResult = await db.run(anchorQuery, { query: sanitizedQuery, buckets, tags });
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

    const walkQuery = `
            ?[id, content, source, timestamp, buckets, tags, epochs, provenance, score] := 
            *memory{id: anchor_id, tags: anchor_tags},
            anchor_id in $anchorIds,
            tag in anchor_tags,
            *memory{id, content, source, timestamp, buckets, tags, epochs, provenance},
            tag in tags,
            id != anchor_id,
            ${tags.length > 0 ? 'length(intersection(tags, $tags)) > 0,' : ''} 
            score = 30.0
            :limit 10
        `;

    const walkResult = await db.run(walkQuery, { anchorIds, tags });
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
 * Execute search with Intelligent Expansion and Tag-Walker Protocol
 */
export async function executeSearch(
  query: string,
  _bucket?: string,
  buckets?: string[],
  maxChars: number = 524288,
  _deep: boolean = false,
  provenance: 'sovereign' | 'external' | 'all' = 'all'
): Promise<{ context: string; results: SearchResult[]; toAgentString: () => string; metadata?: any }> {
  console.log(`[Search] executeSearch (Expanded Tag-Walker) called with provenance: ${provenance}`);

  // 0. PRE-PROCESS: Extract Scope Tags (e.g., #code, #doc)
  // We manually extract them because NLP strips them as noise.
  const scopeTags: string[] = [];
  const queryParts = query.split(/\s+/);
  const cleanQueryParts: string[] = [];

  for (const part of queryParts) {
    if (part.startsWith('#')) {
      scopeTags.push(part); // Keep the hash!
    } else {
      cleanQueryParts.push(part);
    }
  }
  const cleanQuery = cleanQueryParts.join(' ');

  // Separate actual Buckets (folders) from Tags (hashtags)
  const realBuckets = buckets || [];

  // Log the split
  console.log(`[Search] Query: "${cleanQuery}", Tags: [${scopeTags.join(', ')}], Buckets: [${realBuckets.join(', ')}]`);

  // 0. NATURAL LANGUAGE PARSING (Standard 070)
  // Strip stop words from the query for better FTS performance
  // Use the CLEANED query (without tags)
  const parsedQuery = parseNaturalLanguage(cleanQuery);
  if (parsedQuery !== cleanQuery) {
    console.log(`[Search] NLP Parsed Query: "${cleanQuery}" -> "${parsedQuery}"`);
  }

  // 0.5. QUERY EXPANSION (Phase 0 - Standard 069)
  const expansionTags = await expandQuery(cleanQuery);
  const expandedQuery = expansionTags.length > 0 ? `${parsedQuery} ${expansionTags.join(' ')}` : parsedQuery;
  console.log(`[Search] Optimized Query: ${expandedQuery}`);

  // 1. ENGRAM LOOKUP
  const engramResults = await lookupByEngram(cleanQuery);
  let finalResults: SearchResult[] = [];
  const includedIds = new Set<string>();

  if (engramResults.length > 0) {
    // ... (logic remains same)
    console.log(`[Search] Found ${engramResults.length} via Engram: ${cleanQuery}`);
    const engramContextQuery = `?[id, content, source, timestamp, buckets, tags, epochs, provenance] := *memory{id, content, source, timestamp, buckets, tags, epochs, provenance}, id in $ids`;
    const engramContentResult = await db.run(engramContextQuery, { ids: engramResults });
    if (engramContentResult.rows) {
      engramContentResult.rows.forEach((row: any[]) => {
        if (!includedIds.has(row[0])) {
          // Basic check: Does this engram result match the tags?
          const rowTags = row[5] as string[];
          const rowBuckets = row[4] as string[];

          const matchesTags = scopeTags.every(t => rowTags.includes(t));
          const matchesBuckets = realBuckets.every(b => rowBuckets.includes(b));

          if ((scopeTags.length === 0 || matchesTags) && (realBuckets.length === 0 || matchesBuckets)) {
            finalResults.push({
              id: row[0], content: row[1], source: row[2], timestamp: row[3], buckets: row[4], tags: row[5], epochs: row[6], provenance: row[7], score: 200
            });
            includedIds.add(row[0]);
          }
        }
      });
    }
  }

  // 2. TAG-WALKER SEARCH (Hybrid FTS + Graph)
  // Pass both buckets and tags explicitely
  const walkerResults = await tagWalkerSearch(expandedQuery, realBuckets, scopeTags, maxChars);

  // Merge and Apply Provenance Boosting
  walkerResults.forEach(r => {
    let score = r.score;

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

/**
 * Traditional FTS fallback
 */
export async function runTraditionalSearch(query: string, buckets: string[]): Promise<SearchResult[]> {
  const sanitizedQuery = sanitizeFtsQuery(query);
  if (!sanitizedQuery) return [];

  let queryCozo = '';
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