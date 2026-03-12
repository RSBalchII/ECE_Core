/**
 * Search Orchestrator — "The Brain"
 *
 * Core search orchestration, Tag-Walker physics engine, engram lookup,
 * and result merging. All NLP parsing lives in query-parser.ts ("The Ears"),
 * utilities in search-utils.ts ("The Tools"), and graph reasoning in
 * bright-nodes.ts ("The Illuminator").
 *
 * Standard 086 Compliant.
 * Standard 086 = "Dual-Strategy Search" (internal specification numbering).
 * See specs/standards/STANDARD_086_DUAL_STRATEGY_SEARCH.md for full spec.
 * Two modes: Standard Search (70/30 budget, temporal decay) and Max-Recall
 * (zero decay, 3-hop traversal). Mode auto-selects based on token budget.
 */

import { db } from '../../core/db.js';
import { createHash } from 'crypto';
import { config } from '../../config/index.js';
import { MAX_RECALL_CONFIG } from '../../config/max-recall-config.js';
import { SemanticCategory } from '../../types/taxonomy.js';
import { ContextInflator } from './context-inflator.js';
import { Timer } from '../../utils/timer.js';
import { systemStatus } from '../system-status.js';
import { processWithAdaptiveConcurrency } from '../../utils/adaptive-concurrency.js';

// --- Imports from extracted modules ---
import {
  nlp, isExpansionReady, semanticExpand,
  getGlobalTags, expandQuery, sanitizeFtsQuery, expandCamelCase,
  parseNaturalLanguage, extractKeyTermsFromConversation,
  extractTemporalContext, splitQueryIntoMolecules, parseQuery,
  expandConversationalQuery, getRelatedTagsForQuery
} from './query-parser.js';

import {
  SearchResult,
  getHammingDistance, getItems, formatResults, filterDisplayTags
} from './search-utils.js';

import { KnowledgeCluster, KnowledgeMolecule } from '../../types/api.js';

// Re-export everything that external consumers need
export { getGlobalTags, filterDisplayTags, parseQuery, splitQueryIntoMolecules };
export type { SearchResult };
export type { BrightNode, BrightNodeRelationship } from './bright-nodes.js';
export { getBrightNodes, getStructuredGraph } from './bright-nodes.js';

/**
 * Lightweight semantic scoring for two-pass search (Standard 134)
 * Scores candidates without expensive context inflation
 */
function calculateLightweightScore(
  result: SearchResult,
  queryTerms: string[],
  query: string
): number {
  if (!result.content) return result.score || 0;

  const content = result.content.toLowerCase();
  const contentWords = new Set(content.split(/\s+/).filter(w => w.length > 2));

  // Term overlap score (0-1)
  let termMatches = 0;
  for (const term of queryTerms) {
    const termLower = term.toLowerCase();
    if (content.includes(termLower)) termMatches++;
  }
  const termScore = queryTerms.length > 0 ? termMatches / queryTerms.length : 0;

  // Exact phrase bonus
  const phraseBonus = content.includes(query.toLowerCase()) ? 0.3 : 0;

  // Tag relevance bonus
  const tagBonus = result.tags && result.tags.length > 0
    ? result.tags.filter(t => queryTerms.some(qt => t.toLowerCase().includes(qt.toLowerCase()))).length * 0.1
    : 0;

  // Recency bonus (newer = higher score, decay over 30 days)
  let recencyBonus = 0;
  if (result.timestamp) {
    const ageDays = (Date.now() - result.timestamp) / (1000 * 60 * 60 * 24);
    recencyBonus = Math.max(0, 0.2 * (1 - ageDays / 30));
  }

  // Combine scores (base score + term overlap + bonuses)
  const baseScore = result.score || 0.5;
  return Math.min(1.0, baseScore * 0.3 + termScore * 0.5 + phraseBonus + tagBonus + recencyBonus);
}

/**
 * Create or update an engram (lexical sidecar) for fast entity lookup
 */
export async function createEngram(key: string, memoryIds: string[]): Promise<void> {
  const normalizedKey = key.toLowerCase().trim();
  const engramId = createHash('md5').update(normalizedKey).digest('hex');

  const insertQuery = `INSERT INTO engrams (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`;
  await db.run(insertQuery, [engramId, JSON.stringify(memoryIds)]);
}

/**
 * Lookup memories by engram key (O(1) operation)
 */
export async function lookupByEngram(key: string): Promise<string[]> {
  const normalizedKey = key.toLowerCase().trim();
  const engramId = createHash('md5').update(normalizedKey).digest('hex');

  const query = `SELECT value FROM engrams WHERE key = $1`;
  const result = await db.run(query, [engramId]);

  if (result.rows && result.rows.length > 0) {
    return JSON.parse(result.rows[0].value as string);
  }

  return [];
}

/**
 * Hydrate engram IDs into full SearchResult objects
 */
export async function hydrateEngrams(ids: string[]): Promise<SearchResult[]> {
  if (!ids || ids.length === 0) return [];

  const query = `
    SELECT id, content, source_path, timestamp, buckets, tags, provenance, compound_id, start_byte, end_byte
    FROM atoms
    WHERE id = ANY($1)
  `;

  try {
    const result = await db.run(query, [ids]);

    return result.rows.map((row: any) => ({
      id: row.id,
      content: row.content,
      source: row.source_path, // Map source_path to source
      timestamp: row.timestamp,
      buckets: row.buckets || [],
      tags: row.tags || [],
      epochs: '',
      provenance: row.provenance || 'internal',
      score: 1.0, // High score for direct engram hits
      compound_id: row.compound_id,
      start_byte: row.start_byte,
      end_byte: row.end_byte
    }));
  } catch (e) {
    console.error('[Search] Failed to hydrate engrams:', e);
    return [];
  }
}

/**
 * Enrich atoms with molecule tags for better contextual associations
 * Fetches tags from parent molecules and merges them with atom tags
 * This provides richer semantic context for LLMs viewing search results
 */
async function enrichAtomsWithMoleculeTags(anchors: SearchResult[]): Promise<void> {
  try {
    // Group anchors by compound_id for efficient batch query
    const anchorsByCompound = new Map<string, SearchResult[]>();
    
    for (const anchor of anchors) {
      if (anchor.compound_id) {
        if (!anchorsByCompound.has(anchor.compound_id)) {
          anchorsByCompound.set(anchor.compound_id, []);
        }
        anchorsByCompound.get(anchor.compound_id)!.push(anchor);
      }
    }

    if (anchorsByCompound.size === 0) return;

    const compoundIds = Array.from(anchorsByCompound.keys());

    try {
      // ⚡ Bolt Optimization: Batch fetch molecules for all compounds using ANY() to prevent N+1 queries
      const molQuery = `
        SELECT compound_id, tags
        FROM molecules
        WHERE compound_id = ANY($1) AND tags IS NOT NULL
      `;

      const molResult = await db.run(molQuery, [compoundIds]);

      // Group molecule tags by compound_id
      const tagsByCompound = new Map<string, Set<string>>();

      if (molResult.rows && molResult.rows.length > 0) {
        for (const molRow of molResult.rows) {
          const cId = molRow.compound_id;
          if (!tagsByCompound.has(cId)) {
            tagsByCompound.set(cId, new Set<string>());
          }
          const compoundTags = tagsByCompound.get(cId)!;
          
          if (molRow.tags) {
            let rawTags: unknown = molRow.tags;

            if (typeof rawTags === 'string') {
              try {
                rawTags = JSON.parse(rawTags);
              } catch {
                // Malformed tags JSON for this molecule; skip this row only.
                continue;
              }
            }

            if (Array.isArray(rawTags)) {
              for (const tag of rawTags) {
                if (tag && typeof tag === 'string') {
                  compoundTags.add(tag);
                }
              }
            }
          }
        }
      }

      // Merge molecule tags with each atom's tags
      for (const [compoundId, compoundAnchors] of anchorsByCompound) {
        const moleculeTags = tagsByCompound.get(compoundId);
        if (moleculeTags && moleculeTags.size > 0) {
          for (const anchor of compoundAnchors) {
            const atomTags = anchor.tags || [];
            const mergedTags = Array.from(
              new Set([...atomTags, ...moleculeTags])
            );

            // Sort tags for consistency (atom tags first, then molecule tags alphabetically)
            anchor.tags = mergedTags.sort();
          }
        }
      }
    } catch (molErr) {
      // Silently continue if molecule tag fetch fails, but include compoundId context for debugging
      const sampleCompoundIds = compoundIds.slice(0, 5);
      console.debug(
        '[Search] Could not fetch molecule tags for compounds (count=%d, sample=%o): %o',
        compoundIds.length,
        sampleCompoundIds,
        molErr
      );
    }
  } catch (e) {
    console.warn('[Search] Failed to enrich atoms with molecule tags:', e);
    // Continue without enrichment - this is not a critical failure
  }
}

import { PhysicsTagWalker } from './physics-tag-walker.js';
import { assembleAndSerialize, assembleContextPackage } from './graph-context-serializer.js';
import { UserContext } from '../../types/context.js';

// ---------------------------------------------------------------------------
// Search serialization lock — only one search runs at a time to prevent
// concurrent searches from doubling peak heap usage.
// ---------------------------------------------------------------------------
// Fixed: Use simple boolean flag instead of promise chain to prevent memory leak
let _searchLockHeld = false;
let _searchLockWaiters: Array<() => void> = [];

function acquireSearchLock(): Promise<() => void> {
  return new Promise<() => void>((resolve) => {
    if (!_searchLockHeld) {
      // Lock is free, acquire it immediately
      _searchLockHeld = true;
      resolve(() => {
        _searchLockHeld = false;
        // Release next waiter if any
        const next = _searchLockWaiters.shift();
        if (next) {
          _searchLockHeld = true;
          next();
        }
      });
    } else {
      // Lock is held, queue this waiter
      _searchLockWaiters.push(() => {
        resolve(() => {
          _searchLockHeld = false;
          const next = _searchLockWaiters.shift();
          if (next) {
            _searchLockHeld = true;
            next();
          }
        });
      });
    }
  });
}

// Memory thresholds - loaded from user_settings.json with defaults
// Standard 127/134/135: Configurable memory management
function getMemoryThresholds() {
  const userSettings = (config as any).MEMORY || {};
  return {
    // HEAP_PRESSURE_MB: if V8 heapUsed exceeds this, downgrade max-recall → standard
    HEAP_PRESSURE_MB: userSettings.heap_pressure_mb ?? 500,
    // Throttling thresholds for memory-aware search pacing
    THROTTLE_START_MB: userSettings.throttle_start_mb ?? 800,
    THROTTLE_MAX_MB: userSettings.throttle_max_mb ?? 1200,
    EMERGENCY_STOP_MB: userSettings.emergency_stop_mb ?? 1500,
    // Streaming results configuration
    RESULTS_BATCH_SIZE: userSettings.search_results_batch_size ?? 20,
    ENABLE_STREAMING: userSettings.enable_streaming_results ?? false
  };
}

function heapUsedMB(): number {
  return Math.round(process.memoryUsage().heapUsed / 1024 / 1024);
}

/**
 * Memory-aware throttling: slows down or blocks searches based on memory pressure
 * Returns true if search should proceed, false if it should be rejected
 * Standard 127/134/135: Configurable memory thresholds
 */
async function throttleSearchForMemory(): Promise<{ proceed: boolean; delayMs: number; reason?: string }> {
  const heapMB = heapUsedMB();
  const thresholds = getMemoryThresholds();

  // Emergency stop - reject search
  if (heapMB >= thresholds.EMERGENCY_STOP_MB) {
    console.warn(`[Throttle] EMERGENCY: Heap at ${heapMB}MB >= ${thresholds.EMERGENCY_STOP_MB}MB. Rejecting search.`);
    return { proceed: false, delayMs: 0, reason: `Memory too high (${heapMB}MB)` };
  }

  // Throttle zone - reject if too high
  if (heapMB >= thresholds.THROTTLE_MAX_MB) {
    console.warn(`[Throttle] Heap at ${heapMB}MB >= ${thresholds.THROTTLE_MAX_MB}MB. Rejecting search temporarily.`);
    return { proceed: false, delayMs: 0, reason: `Memory pressure (${heapMB}MB)` };
  }

  // Throttle zone - add delay based on memory pressure
  if (heapMB >= thresholds.THROTTLE_START_MB) {
    const pressureRatio = (heapMB - thresholds.THROTTLE_START_MB) / (thresholds.THROTTLE_MAX_MB - thresholds.THROTTLE_START_MB);
    const delayMs = Math.round(pressureRatio * 10000); // Up to 10 second delay
    console.log(`[Throttle] Heap at ${heapMB}MB. Delaying search by ${delayMs}ms (pressure: ${(pressureRatio * 100).toFixed(0)}%)`);
    await new Promise(resolve => setTimeout(resolve, delayMs));
    return { proceed: true, delayMs, reason: `Throttled (${heapMB}MB)` };
  }

  // Normal operation - no delay
  return { proceed: true, delayMs: 0 };
}

/**
 * Find Anchors (Direct Hits) - Formerly part of tagWalkerSearch
 * Executes Strategy A (Atom positions) and Strategy B (Molecules FTS)
 */
export async function findAnchors(
  query: string,
  buckets: string[] = [],
  tags: string[] = [],
  _maxChars: number = config.SEARCH.max_chars_default,
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  filters?: { type?: string; minVal?: number; maxVal?: number; },
  fuzzy: boolean = false
): Promise<SearchResult[]> {
  try {
    const sanitizedQuery = sanitizeFtsQuery(query);
    if (!sanitizedQuery) return [];

    // 0. Dynamic Atom Scaling
    const tokenBudget = Math.floor(_maxChars / 4);
    const avgTokensPerAtom = 60; // Tuned for better density
    const targetAtomCount = Math.max(10, Math.ceil(tokenBudget / avgTokensPerAtom));

    console.log(`[Search] Dynamic Scaling: Budget=${tokenBudget}t -> Target=${targetAtomCount} atoms`);

    // Construct Query String for FTS
    // Use OR ( | ) by default so multi-word queries find documents containing
    // ANY of the terms, not ALL of them. AND ( & ) is too restrictive for
    // conversational queries like "College Music education" — it requires all
    // three words in the same molecule, which rarely matches.
    // Strip English stop words before building the tsquery — 'simple' config
    // does NOT filter them, so connector words like "and", "the", "or" would
    // match almost every molecule and corrupt ranking.
    const FTS_STOP_WORDS = new Set([
      'a','an','and','are','as','at','be','been','being','but','by',
      'can','could','did','do','does','doing','done','each','for',
      'from','had','has','have','having','he','her','him','his',
      'how','i','if','in','is','it','its','itself','just','me',
      'more','my','no','not','of','off','on','or','our','out',
      'own','same','she','should','so','some','such','than','that',
      'the','their','them','then','there','these','they','this',
      'those','to','too','very','was','we','were','what','when',
      'where','which','while','who','whom','why','will','with',
      'would','you','your','yours'
    ]);
    const queryWords = sanitizedQuery.trim().split(/\s+/).filter(t => t.length > 0);
    const contentWords = queryWords.filter(t => !FTS_STOP_WORDS.has(t));
    // Fall back to full word list if stop-word stripping removed everything
    const baseTerms = contentWords.length > 0 ? contentWords : queryWords;
    // Expand camelCase identifiers (e.g. findAnchors → [findanchors, find, anchors])
    // so FTS can match partial names and prose descriptions of the same concept.
    const tsTerms = expandCamelCase(baseTerms);
    
    // SECURITY FIX: Sanitize FTS query terms to prevent injection attacks
    // Remove PostgreSQL FTS operators and special characters
    const sanitizeFtsTerm = (term: string): string => {
      // Remove FTS operators: &, |, !, ( ), < >
      let sanitized = term.replace(/[&|!()<>]/g, '');
      // Remove quotes and backslashes
      sanitized = sanitized.replace(/["\\]/g, '');
      // Remove control characters
      sanitized = sanitized.replace(/[\x00-\x1F\x7F]/g, '');
      // Escape colons (field search operator)
      sanitized = sanitized.replace(/:/g, '\\:');
      return sanitized;
    };
    
    const sanitizedTerms = tsTerms.map(sanitizeFtsTerm).filter(t => t.length > 0);
    let tsQueryString = sanitizedTerms.join(' | ');

    let anchors: SearchResult[] = [];
    let atomResults: SearchResult[] = [];

    // A. Atom Search (Radial Inflation) via ContextInflator
    // Use stop-word-stripped terms (tsTerms) so we don't inflate around "and", "the", etc.
    const terms = tsTerms.length > 0 ? tsTerms : sanitizedQuery.split(/\s+/).filter(t => t.length > 0);

    if (terms.length > 0) {
      try {
        // [Standard 132] Use adaptive concurrency based on available memory
        const inflations = await processWithAdaptiveConcurrency(
          terms,
          async (term) => ContextInflator.inflateFromAtomPositions(term, 150, 20, undefined, { buckets, provenance })
        );
        let rawAtoms = inflations.flat();

        // [Standard 134] Two-pass scoring: score candidates before expensive processing
        // This avoids inflating low-quality candidates, saving memory and time
        const scoredAtoms = rawAtoms.map(atom => ({
          ...atom,
          score: calculateLightweightScore(atom, terms, sanitizedQuery)
        }));

        // Sort by score and keep only top N (mobile: 5, desktop: 10 per term)
        const isMobile = process.platform === 'android' || (await import('os')).totalmem() < 2 * 1024 * 1024 * 1024;
        const maxResultsPerTerm = isMobile ? 5 : 10;
        const topAtoms = scoredAtoms
          .sort((a, b) => (b.score || 0) - (a.score || 0))
          .slice(0, maxResultsPerTerm * terms.length);

        atomResults.push(...topAtoms);
        console.log(`[Search] Atom search found ${rawAtoms.length} atoms, kept top ${topAtoms.length} after scoring for terms: ${terms.join(', ')}`);
      } catch (e) {
        console.error(`[Search] Atom Search failed:`, e);
      }
    }
    anchors = atomResults;

    // B. Molecule Search (Full-Text with BM25-style ranking)
    let moleculeQuery = `
        SELECT m.id, m.content, c.path as source, m.timestamp,
               '{}'::text[] as buckets, '{}'::text[] as tags, 'epoch_placeholder' as epochs, c.provenance,
               -- Use ts_rank_cd for cover-density ranking (closer to BM25)
               ts_rank_cd(to_tsvector('simple', m.content), to_tsquery('simple', $1)) * 10 as score,
               m.sequence, m.molecular_signature,
               m.start_byte, m.end_byte, m.type, m.numeric_value, m.numeric_unit, m.compound_id
        FROM molecules m
        JOIN compounds c ON m.compound_id = c.id
        WHERE to_tsvector('simple', m.content) @@ to_tsquery('simple', $1)
    `;

    const moleculeParams: any[] = [tsQueryString];

    if (buckets.length > 0) {
      moleculeQuery += ` AND EXISTS (
        SELECT 1 FROM atoms a 
        WHERE a.source_path = c.path 
        AND a.buckets && $${moleculeParams.length + 1}
      )`;
      moleculeParams.push(buckets);
    }

    if (provenance !== 'all' && provenance !== 'quarantine') {
      moleculeQuery += ` AND c.provenance = $${moleculeParams.length + 1}`;
      moleculeParams.push(provenance);
    } else if (provenance === 'all') {
      moleculeQuery += ` AND c.provenance != 'quarantine'`;
    }

    // Replace hardcoded LIMIT 50 with the intended dynamic token budget scalar
    moleculeQuery += ` ORDER BY score DESC LIMIT ${targetAtomCount}`;

    try {
      let molResult = await db.run(moleculeQuery, moleculeParams);

      // Strategy 1.1: If AND fails and query has multiple terms, retry with OR (Fuzzy Fallback)
      if (molResult.rows.length === 0 && tsQueryString.includes('&')) {
        console.log('[Search] Initial AND query yielded 0 results. Retrying with OR-fuzzy logic...');

        // To prevent massive Cartesian product explosions in SQL, we limit the OR fallback
        // to the top 8 longest words (which are statistically more likely to be unique/important).
        const allTerms = sanitizedQuery.split(/\s+/).filter(t => t.length > 3);
        const uniqueTerms = Array.from(new Set(allTerms));
        uniqueTerms.sort((a, b) => b.length - a.length);
        const topTerms = uniqueTerms.slice(0, 8);

        if (topTerms.length > 0) {
          const orQueryString = topTerms.join(' | ');
          console.log(`[Search] OR-fuzzy fallback using terms: ${orQueryString}`);
          const orQuery = moleculeQuery.replace(/\$1/g, '$1'); // Keep same param index
          const orParams = [orQueryString, ...moleculeParams.slice(1)];
          molResult = await db.run(orQuery, orParams);
        }
      }
      const molecules = (molResult.rows || []).map((row: any) => ({
        id: row.id,
        content: row.content,
        source: row.source,
        timestamp: row.timestamp,
        buckets: row.buckets,
        tags: row.tags,
        epochs: row.epochs,
        provenance: row.provenance,
        score: row.score,
        sequence: row.sequence,
        molecular_signature: row.molecular_signature,
        start_byte: row.start_byte,
        end_byte: row.end_byte,
        type: row.type,
        numeric_value: row.numeric_value,
        numeric_unit: row.numeric_unit,
        compound_id: row.compound_id
      }));

      // Merge atom and molecule results
      anchors = [...atomResults, ...molecules];

      // Deduplicate anchors using Range Merging
      // Group by compound_id to find overlaps
      const anchorsByCompound = new Map<string, SearchResult[]>();

      [...atomResults, ...molecules].forEach(a => {
        if (!a.compound_id) return;
        if (!anchorsByCompound.has(a.compound_id)) {
          anchorsByCompound.set(a.compound_id, []);
        }
        anchorsByCompound.get(a.compound_id)!.push(a);
      });

      anchors = [];

      for (const [cId, compoundAnchors] of anchorsByCompound) {
        // Sort by start byte
        compoundAnchors.sort((a, b) => (a.start_byte || 0) - (b.start_byte || 0));

        const merged: SearchResult[] = [];
        if (compoundAnchors.length === 0) continue;

        let current = compoundAnchors[0];

        for (let i = 1; i < compoundAnchors.length; i++) {
          const next = compoundAnchors[i];
          const currentEnd = (current.end_byte || 0);
          const nextStart = (next.start_byte || 0);
          const nextEnd = (next.end_byte || 0);

          // LOGGING FOR DEBUGGING
          // console.log(`[Dedup] Checking ${cId}: [${current.start_byte}-${currentEnd}] vs [${nextStart}-${nextEnd}]`);

          // Check for overlap or adjacency (within 50 bytes)
          if (nextStart <= currentEnd + 50) {
            // If identical start/end, it's a true duplicate (just skip next)
            if (Math.abs(nextStart - (current.start_byte || 0)) < 5 && Math.abs(nextEnd - currentEnd) < 5) {
              // console.log(`[Dedup] Exact/Near match found. Skipping.`);
              continue;
            }

            // If next is contained in current, skip next
            if (nextEnd <= currentEnd) {
              // console.log(`[Dedup] Next contained in Current. Skipping.`);
              continue;
            }

            // If current is contained in next, switch to next
            if ((next.start_byte || 0) <= (current.start_byte || 0) && nextEnd >= currentEnd) {
              // console.log(`[Dedup] Current contained in Next. Swapping.`);
              current = next;
              continue;
            }

            // Strict Dedup: If they overlap by more than 50% (lowered from 80%), suppress the lower scored one.
            const overlap = Math.min(currentEnd, nextEnd) - Math.max((current.start_byte || 0), nextStart);
            const len1 = currentEnd - (current.start_byte || 0);
            const len2 = nextEnd - nextStart;

            if (overlap > 0 && (overlap / len1 > 0.5 || overlap / len2 > 0.5)) {
              // console.log(`[Dedup] Heavy overlap (>50%). Picking better score.`);
              // Keep the one with higher score, or if equal, the current (first)
              if ((next.score || 0) > (current.score || 0)) {
                current = next;
              }
              continue; // Skip the 'loser'
            }

            merged.push(current);
            current = next;

          } else {
            merged.push(current);
            current = next;
          }
        }
        merged.push(current);
        anchors.push(...merged);
      }

      // Final Safety Net: Global Content Similarity Deduplication (O(N^2))
      // Addresses:
      // 1. Cross-Compound Duplicates (different IDs/provenance, same text)
      // 2. Near-Exact Duplicates (whitespace diffs, timestamp diffs)
      // 3. Containment (one result is a subset of another)
      // 4. Overlapping Windows from same compound (NEW FIX)

      const distinctAnchors: SearchResult[] = [];
      // Sort by score desc to prioritize best matches
      anchors.sort((a, b) => (b.score || 0) - (a.score || 0));

      // Helper for normalization: lowercase + remove non-alphanumeric + unescape JSON
      const normalize = (s: string) => {
        // First unescape JSON strings (\\\" → ", \\n → newline, etc.)
        let unescaped = s;
        try {
          // Try to unescape common JSON escape sequences
          unescaped = s
            .replace(/\\"/g, '"')
            .replace(/\\\\/g, '\\')
            .replace(/\\n/g, '\n')
            .replace(/\\r/g, '\r')
            .replace(/\\t/g, '\t');
        } catch (e) {
          // If unescaping fails, use original
        }
        return unescaped.toLowerCase().replace(/[^a-z0-9]/g, '');
      };

      // Helper for content fingerprinting (hash-based dedup across files)
      const crypto = await import('crypto');
      const contentFingerprints = new Map<string, SearchResult>(); // hash -> kept result

      // Track kept ranges per compound to detect sliding window duplicates
      const keptRanges = new Map<string, { start: number, end: number, content: string }[]>();

      for (const candidate of anchors) {
        if (!candidate.content || candidate.content.length < 20) {
          distinctAnchors.push(candidate);
          continue;
        }

        // C. Content Fingerprint Deduplication (ACROSS different files)
        // Hash the normalized content to catch duplicates from different compounds
        const candidateNorm = normalize(candidate.content);
        const contentHash = crypto.createHash('md5').update(candidateNorm.substring(0, 500)).digest('hex');

        if (contentFingerprints.has(contentHash)) {
          // This content already exists from another file - skip it
          continue;
        }
        contentFingerprints.set(contentHash, candidate);

        // A. Geometric Deduplication (if compound_id is available)
        let isGeometricDuplicate = false;
        if (candidate.compound_id && candidate.start_byte !== undefined && candidate.end_byte !== undefined) {
          const ranges = keptRanges.get(candidate.compound_id) || [];
          for (const range of ranges) {
            // Check overlap - LOWERED threshold from 75% to 50% for aggressive dedup
            const overlapStart = Math.max(candidate.start_byte, range.start);
            const overlapEnd = Math.min(candidate.end_byte, range.end);
            const overlapLen = Math.max(0, overlapEnd - overlapStart);

            const candidateLen = candidate.end_byte - candidate.start_byte;
            const rangeLen = range.end - range.start;
            const minLen = Math.min(candidateLen, rangeLen);

            // If overlap is > 50% of either window, it's a duplicate
            if (overlapLen > 0 && (overlapLen >= minLen * 0.5)) {
              isGeometricDuplicate = true;
              break;
            }

            // Check if windows are adjacent or overlapping (within 500 bytes for molecules)
            // Molecules can be large, so use larger threshold
            const gap = Math.max(0, overlapStart - overlapEnd);
            const adjacencyThreshold = Math.max(500, Math.min(candidateLen, rangeLen) * 0.2);
            if (gap >= 0 && gap < adjacencyThreshold) {
              isGeometricDuplicate = true;
              break;
            }
          }

          if (isGeometricDuplicate) continue;
        }

        // B. Content Deduplication (Fallback)
        const candidateFingerprint = candidateNorm.substring(0, 100);

        let isContentDuplicate = false;

        for (const kept of distinctAnchors) {
          const keptNorm = normalize(kept.content);

          // 1. Exact Containment (Candidate is subset of Kept, or vice-versa)
          if (keptNorm.includes(candidateNorm)) {
            isContentDuplicate = true;
            break;
          }
          if (candidateNorm.includes(keptNorm)) {
            isContentDuplicate = true;
            break;
          }

          // 2. Fuzzy Prefix Match - INCREASED check length to 50 for better matching
          const keptFingerprint = keptNorm.substring(0, 100);
          const checkLen = Math.min(candidateFingerprint.length, keptFingerprint.length);
          if (checkLen > 50 && candidateFingerprint.substring(0, checkLen) === keptFingerprint.substring(0, checkLen)) {
            isContentDuplicate = true;
            break;
          }

          // 3. SimHash Distance Check - Cross-file near-duplicates (NEW)
          // Hamming distance < 5 out of 64 bits = near-duplicate content
          if (candidate.molecular_signature && kept.molecular_signature) {
            const simhashDistance = getHammingDistance(candidate.molecular_signature, kept.molecular_signature);
            if (simhashDistance < 5) {
              isContentDuplicate = true;
              break;
            }
          }
        }

        if (!isContentDuplicate) {
          distinctAnchors.push(candidate);

          // Register range
          if (candidate.compound_id && candidate.start_byte !== undefined && candidate.end_byte !== undefined) {
            const ranges = keptRanges.get(candidate.compound_id) || [];
            ranges.push({ start: candidate.start_byte, end: candidate.end_byte, content: candidate.content });
            keptRanges.set(candidate.compound_id, ranges);
          }
        }
      }

      const originalCount = anchors.length;
      anchors = distinctAnchors;
      console.log(`[Search] Final Dedup: ${originalCount} -> ${anchors.length} items. Removed ${originalCount - anchors.length} duplicates.`);

      console.log(`[Search] Anchors found: ${atomResults.length} Atoms, ${molecules.length} Molecules. Final Unique: ${anchors.length}`);

    } catch (e) {
      console.error('[Search] Molecule search failed:', e);
      anchors = atomResults;
    }

    // Intercept: Read content from Mirror (if source_path exists)
    // For atoms without source files (chat history), keep DB content

    const { getMirrorPath } = await import('../mirror/mirror.js');
    const fs = await import('fs');

    // Parallelize mirror reads for performance (non-blocking I/O)
    await Promise.all(anchors.map(async (anchor) => {
      // Skip mirror read if no source_path (chat history atoms)
      if (!anchor.source || anchor.source.trim() === '') {
        return; // Keep DB content
      }

      try {
        // Calculate Mirror Path
        const mirrorPath = getMirrorPath(anchor.source, anchor.provenance);

        // Check if exists and read async
        try {
          const liveContent = await fs.promises.readFile(mirrorPath, 'utf-8');
          if (liveContent && liveContent.length > 0) {
            anchor.content = liveContent;
          }
        } catch (err) {
          // Ignore ENOENT (file missing) or other read errors
        }
      } catch (e: any) {
        // Fail silently -> Keep DB content
      }
    }));

    // === TAG ENRICHMENT: Merge molecule tags with atom tags ===
    // This provides richer contextual associations for LLMs by showing
    // all tags from the parent molecule(s) alongside atom tags
    await enrichAtomsWithMoleculeTags(anchors);

    return anchors;

  } catch (e) {
    console.error('[Search] findAnchors failed:', e);
    return [];
  }
}

/**
 * Execute search with Intelligent Expansion and Physics Tag-Walker Protocol (GCP)
 *
 * @param query - Search query string
 * @param buckets - Array of buckets to search
 * @param maxChars - Maximum characters to return
 * @param provenance - Provenance filter (internal/external/quarantine/all)
 * @param explicitTags - Explicit tags to filter by
 * @param filters - Additional filters
 * @param useMaxRecall - If true, uses MAX_RECALL_CONFIG for comprehensive retrieval
 * @param userContext - User context for personalization
 */
export async function executeSearch(
  query: string,
  buckets?: string[],
  maxChars: number = config.SEARCH.max_chars_default,
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  explicitTags: string[] = [],
  filters?: { type?: string; minVal?: number; maxVal?: number; },
  useMaxRecall: boolean = false,
  userContext?: UserContext
): Promise<{ context: string; results: SearchResult[]; toAgentString: () => string; metadata?: any }> {
  console.log(`[Search] executeSearch (Physics Engine V2) called with provenance: ${provenance}`);
  const startTime = Date.now();

  // Serialize searches — only one at a time to keep peak heap predictable.
  // Concurrent searches on a large corpus (214K+ atoms) double peak memory usage.
  const release = await acquireSearchLock();
  try {
    return await _executeSearchInternal(
      query, buckets, maxChars, provenance,
      explicitTags, filters, useMaxRecall, userContext, startTime
    );
  } finally {
    release();
    if (typeof global.gc === 'function') global.gc();
  }
}

async function _executeSearchInternal(
  query: string,
  buckets?: string[],
  maxChars: number = config.SEARCH.max_chars_default,
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  explicitTags: string[] = [],
  filters?: { type?: string; minVal?: number; maxVal?: number; },
  useMaxRecall: boolean = false,
  userContext?: UserContext,
  startTime: number = Date.now()
): Promise<{ context: string; results: SearchResult[]; toAgentString: () => string; metadata?: any }> {
  // Memory-aware throttling: slow down or reject searches based on memory pressure
  const throttleResult = await throttleSearchForMemory();
  if (!throttleResult.proceed) {
    throw new Error(`Search rejected: ${throttleResult.reason}. Please wait and try again.`);
  }

  // Memory pressure check: if heap is already near the limit, downgrade max-recall
  // to standard search to avoid OOM. Trades result depth for stability.
  const heapMB = heapUsedMB();
  const thresholds = getMemoryThresholds();
  if (useMaxRecall && heapMB > thresholds.HEAP_PRESSURE_MB) {
    console.warn(`[Search] Memory pressure detected (${heapMB}MB heap). Downgrading max-recall → standard search.`);
    useMaxRecall = false;
    maxChars = Math.min(maxChars, config.SEARCH.max_chars_default);
  }

  // Check if system is busy with ingestion
  const status = systemStatus.getStatus();
  if (status.isBusy) {
    // Wait for ingestion to finish before running search.
    // Concurrent search+ingestion causes O(N) memory pressure that can exceed the heap limit
    // (e.g. 207K molecules sharing a compound_id → physics walker cross product crashes at 8GB).
    const maxWaitMs = 180_000; // 3 minutes
    const pollMs = 1_000;
    let waited = 0;
    console.log(`[Search] System busy (${status.state}), waiting for idle before proceeding...`);
    while (systemStatus.getStatus().isBusy && waited < maxWaitMs) {
      await new Promise(r => setTimeout(r, pollMs));
      waited += pollMs;
    }
    if (systemStatus.getStatus().isBusy) {
      console.warn(`[Search] System still busy after ${waited}ms, proceeding with risk.`);
    } else {
      console.log(`[Search] System became idle after ${waited}ms, proceeding with search.`);
    }
  }

  // 1. Parse & Prepare
  const cleanQuery = query; // Simplified for now, real NLP parsing happens in findAnchors/query-parser calls if needed
  const realBuckets = new Set(buckets || []);
  if (explicitTags.length > 0) console.log(`[Search] Explicit tags: ${explicitTags.join(', ')}`);

  // 2. Find Anchors (Planets)
  // Combine Engram Lookup + FTS + Molecule Search
  const engramIds = await lookupByEngram(cleanQuery);
  const engramResults = await hydrateEngrams(engramIds);
  let primaryAnchors = await findAnchors(cleanQuery, Array.from(realBuckets), explicitTags, maxChars, provenance, filters);

  // Tag-Aware Fallback (if low precision/recall on initial anchors)
  if (primaryAnchors.length < 5) {
    console.log(`[Search] Low recall (${primaryAnchors.length} anchors). Attempting Tag-Aware Fallback.`);
    const words = cleanQuery.split(/[\s,]+/);
    // Very naive tag extraction: words > 4 chars, capitalize or check if exists in a tag format.
    // Usually, users type things like "graph nodes consciousness". We can try to use these as tags via LIKE query.
    const fallbackTags = words.filter(w => w.length > 3).map(w => w.toLowerCase());
    if (fallbackTags.length > 0) {
      // Simple programmatic fallback to explicitly look for these terms in the DB tags
      try {
        for (const fbTag of fallbackTags) {
          // PostgreSQL array search - check if tag exists in array
          const tagRes = await db.run(`
                      SELECT id, content, source_path, timestamp, buckets, tags, provenance, simhash, embedding, compound_id, start_byte, end_byte
                      FROM atoms
                      WHERE $1 = ANY(tags)
                      LIMIT 20
                  `, [fbTag]);
          if (tagRes.rows && tagRes.rows.length > 0) {
            tagRes.rows.forEach((row: any) => {
              primaryAnchors.push({
                id: String(row.id),
                content: row.content,
                source: row.source_path,
                timestamp: row.timestamp || Date.now(),
                buckets: typeof row.buckets === 'string' ? JSON.parse(row.buckets) : (row.buckets || []),
                tags: typeof row.tags === 'string' ? JSON.parse(row.tags) : (row.tags || []),
                epochs: '',
                provenance: row.provenance,
                score: 0.8, // fallback constant score
                compound_id: row.compound_id,
                start_byte: row.start_byte,
                end_byte: row.end_byte,
                molecular_signature: String(row.simhash)
              });
            });
          }
        }
        // Enrich fallback results with molecule tags
        if (primaryAnchors.length > 0) {
          await enrichAtomsWithMoleculeTags(primaryAnchors);
        }
      } catch (e: any) {
        console.warn('[Search] Tag-aware fallback failed', e);
      }
    }
  }

  const allAnchors = [...engramResults, ...primaryAnchors];

  // Enrich engram results with molecule tags (findAnchors already does this internally)
  if (engramResults.length > 0) {
    await enrichAtomsWithMoleculeTags(engramResults);
  }

  // Deduplicate
  const seenIds = new Set<string>();
  const uniqueAnchors = allAnchors.filter(r => {
    if (seenIds.has(r.id)) return false;
    seenIds.add(r.id);
    return true;
  });

  // 3. Physics Walker (Moons) - Use TypeScript PhysicsTagWalker
  let walkerResults: any[] = [];
  try {
    // Separate real DB IDs from virtual in-memory molecules created by ContextInflator.
    // Virtual IDs (any prefix starting with 'virtual') have no row in atoms/molecules tables.
    // For each virtual anchor, use its compound_id to find the nearest real molecule.
    const realIds = uniqueAnchors
      .map(a => a.id)
      .filter(id => id && id !== '' && !id.startsWith('virtual'));

    // Collect unique compound_ids from virtual anchors so we can resolve them to real mol_* IDs.
    const virtualCompoundIds = [...new Set(
      uniqueAnchors
        .filter(a => a.id && a.id.startsWith('virtual') && a.compound_id)
        .map(a => a.compound_id as string)
    )];

    let resolvedMolIds: string[] = [];
    if (virtualCompoundIds.length > 0) {
      try {
        const res = await db.run(
          `SELECT id FROM molecules WHERE compound_id = ANY($1) ORDER BY timestamp DESC LIMIT 100`,
          [virtualCompoundIds]
        );
        if (res.rows) resolvedMolIds = res.rows.map((r: any) => String(r.id));
      } catch (e: any) {
        console.warn('[Search] Failed to resolve virtual compound IDs:', e.message);
      }
    }

    const anchorIds = [...new Set([...realIds, ...resolvedMolIds])];

    // Round-robin by compound_id so the walker sees anchors from diverse source
    // documents rather than 30 IDs all from the same file.
    const diverseAnchorIds: string[] = [];
    {
      const byCompound = new Map<string, string[]>();
      for (const a of uniqueAnchors) {
        if (!a.id || (a.id as string).startsWith('virtual')) continue;
        const cid = (a.compound_id as string) || '__unknown__';
        if (!byCompound.has(cid)) byCompound.set(cid, []);
        byCompound.get(cid)!.push(a.id as string);
      }
      // Append resolved mol IDs (from virtual compounds) under their compound bucket
      for (const molId of resolvedMolIds) {
        const cid = '__virtual__';
        if (!byCompound.has(cid)) byCompound.set(cid, []);
        byCompound.get(cid)!.push(molId);
      }
      const groups = [...byCompound.values()];
      const maxRound = Math.max(...groups.map(g => g.length));
      for (let i = 0; i < maxRound; i++) {
        for (const group of groups) {
          if (i < group.length) diverseAnchorIds.push(group[i]);
        }
      }
    }
    const dedupedAnchorIds = [...new Set(diverseAnchorIds)];
    
    if (dedupedAnchorIds.length > 0) {
      // Use TypeScript PhysicsTagWalker for radial inflation
      const walker = new PhysicsTagWalker();
      walkerResults = await walker.performRadialInflation(
        dedupedAnchorIds,
        1,                           // radius (1 hop)
        useMaxRecall ? 300 : 150,    // maxPerHop (results returned; fetches 3x candidates)
        0.2,                         // temperature
        0.001                        // gravityThreshold (lowered from 0.005 for sparser graphs)
      );
      console.log(`[Search] PhysicsTagWalker found ${walkerResults.length} associations`);
    } else {
      console.log(`[Search] No valid anchor IDs for Physics Walker`);
    }
  } catch (e: any) {
    console.log(`[Search] Physics Walker failed, skipping: ${e.message}`);
    walkerResults = [];
  }

  // 4. Graph-Context Serialization (GCP)
  const finalUserContext: UserContext = {
    name: userContext?.name || 'User',
    current_state: userContext?.current_state || 'active'
  };

  const contextPackage = assembleContextPackage({
    user: finalUserContext,
    query: cleanQuery,
    keyTerms: cleanQuery.split(' '),
    scopeTags: explicitTags,
    anchors: uniqueAnchors,
    walkerResults: walkerResults,
    charBudget: maxChars
  });

  const serializedContext = assembleAndSerialize({
    user: finalUserContext,
    query: cleanQuery,
    keyTerms: cleanQuery.split(' '),
    scopeTags: explicitTags,
    anchors: uniqueAnchors,
    walkerResults: walkerResults,
    charBudget: maxChars
  });

  console.log(`[Search] Search completed in ${Date.now() - startTime}ms`);

  // Map back to SearchResult[] for legacy API compatibility
  // Combine Anchors + Walker Results, sorted by score desc
  const combinedResults = [
    ...uniqueAnchors,
    ...walkerResults.map(w => ({
      ...w.result,
      physics: w.physics
    })) as any[]
  ];

  // Cap total results fed to formatResults to prevent OOM.
  // 100KB per snippet cap in inflateSnippetFromDisk bounds memory per snippet,
  // but 900+ snippets * 100KB = still huge. Limit by budget: budget / 200 chars minimum
  // gives a rough upper bound on useful snippets.
  // CRITICAL FIX: Add absolute maximum to prevent resource exhaustion
  const ABSOLUTE_MAX_RESULTS = 200;  // Hard limit regardless of budget
  const maxResultsForBudget = Math.min(
    combinedResults.length,
    ABSOLUTE_MAX_RESULTS,  // Absolute cap
    Math.max(50, Math.ceil(maxChars / 200))  // Budget-based (reduced from 200 to 50 base)
  );
  const cappedResults = combinedResults
    .sort((a: any, b: any) => (b.score || 0) - (a.score || 0))
    .slice(0, maxResultsForBudget);

  // Apply context provenance formatting with coalescing (Standard 108)
  // Enable coalescing for high-budget queries to improve coherence
  const enableCoalescing = maxChars > 16000; // Only coalesce for budgets > 16k chars
  const proximityThreshold = maxChars > 100000 ? 800 : 500; // Larger threshold for max-recall

  console.log(`[Search] Coalescing: ${enableCoalescing ? 'enabled' : 'disabled'} (threshold: ${proximityThreshold}px)`);

  const formatted = await formatResults(cappedResults, maxChars, {
    enableCoalescing,
    proximityThreshold
  });

  return {
    context: serializedContext,
    results: formatted.results,
    toAgentString: () => serializedContext,
    metadata: { ...contextPackage.graphStats, ...formatted.metadata }
  };
}

/**
 * Execute molecule-based search - splits query into sentence-like chunks and searches each separately
 */
export async function executeMoleculeSearch(
  query: string,
  bucket?: string,
  buckets?: string[],
  maxChars: number = config.SEARCH.max_chars_default,
  deep: boolean = false,
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  explicitTags: string[] = [],
  userContext?: UserContext
): Promise<{ context: string; results: SearchResult[]; toAgentString: () => string; metadata?: any }> {
  // Memory-aware throttling
  const throttleResult = await throttleSearchForMemory();
  if (!throttleResult.proceed) {
    throw new Error(`Search rejected: ${throttleResult.reason}. Please wait and try again.`);
  }

  // Split the query into molecules (sentence-like chunks)
  const molecules = splitQueryIntoMolecules(query);
  console.log(`[MoleculeSearch] Split query into ${molecules.length} molecules:`, molecules);

  // Search each molecule separately
  const allResults: SearchResult[] = [];
  const includedIds = new Set<string>();

  for (const [index, molecule] of molecules.entries()) {
    console.log(`[MoleculeSearch] Searching molecule ${index + 1}/${molecules.length}: "${molecule}"`);

    try {
      // Execute search for this specific molecule
      const result = await executeSearch(
        molecule,
        buckets,
        maxChars,
        provenance,
        explicitTags,
        undefined,
        false,
        userContext
      );

      // Add unique results to our collection
      for (const item of result.results) {
        if (!includedIds.has(item.id)) {
          allResults.push(item);
          includedIds.add(item.id);
        }
      }
    } catch (error) {
      console.error(`[MoleculeSearch] Error searching molecule:`, molecule, error);
      // Continue with other molecules even if one fails
    }
  }

  // Sort results by score
  allResults.sort((a, b) => b.score - a.score);

  console.log(`[MoleculeSearch] Combined results from ${molecules.length} molecules: ${allResults.length} total results`);

  return await formatResults(allResults, maxChars); // Use original maxChars to maintain token budget
}

/**
 * Traditional FTS fallback
 */
export async function runTraditionalSearch(query: string, buckets: string[]): Promise<SearchResult[]> {
  const sanitizedQuery = sanitizeFtsQuery(query);
  if (!sanitizedQuery) return [];

  let querySql = `
    SELECT a.id,
           ts_rank(to_tsvector('simple', a.content), plainto_tsquery('simple', $1)) as score,
           a.content, a.source_path as source, a.timestamp,
           a.buckets, a.tags, 'epoch_placeholder' as epochs, a.provenance
    FROM atoms a
    WHERE to_tsvector('simple', a.content) @@ plainto_tsquery('simple', $1)
  `;

  if (buckets.length > 0) {
    querySql += ` AND EXISTS (
      SELECT 1 FROM unnest(a.buckets) as bucket WHERE bucket = ANY($2)
    )`;
  }

  querySql += ` ORDER BY score DESC`;

  try {
    const result = await db.run(querySql, buckets.length > 0 ? [sanitizedQuery, buckets] : [sanitizedQuery]);
    if (!result.rows) return [];

    const mappedResults = result.rows.map((row: any) => ({
      id: row.id,
      score: row.score,
      content: row.content,
      source: row.source,
      timestamp: row.timestamp,
      buckets: row.buckets,
      tags: row.tags,
      epochs: row.epochs,
      provenance: row.provenance
    }));

    await hydrateFromMirror(mappedResults);
    return mappedResults;
  } catch (e) {
    console.error('[Search] FTS failed', e);
    return [];
  }
}

/** 
 * Helper to hydrate results from Mirror (Code Reuse)
 */
async function hydrateFromMirror(results: SearchResult[]) {
  try {
    const { getMirrorPath } = await import('../mirror/mirror.js');
    const fs = await import('fs');

    await Promise.all(results.map(async (res) => {
      try {
        const mirrorPath = getMirrorPath(res.source, res.provenance);
        try {
          const content = await fs.promises.readFile(mirrorPath, 'utf-8');
          if (content) res.content = content;
        } catch (err) {
          // ignore file not found
        }
      } catch (e) { /* ignore */ }
    }));
  } catch (e) { /* ignore */ }
}

/**
 * Iterative Search with Back-off Strategy
 * Attempts to retrieve results by progressively simplifying the query.
 * 
 * @param useMaxRecall - If true, uses MAX_RECALL_CONFIG for comprehensive retrieval
 */
export async function iterativeSearch(
  query: string,
  buckets: string[] = [],
  maxChars: number = config.SEARCH.max_chars_default,
  tags: string[] = [],
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  useMaxRecall: boolean = false,
  userContext?: UserContext
): Promise<{ context: string; results: SearchResult[]; attempt: number; metadata?: any; toAgentString: () => string }> {
  // Memory-aware throttling
  const throttleResult = await throttleSearchForMemory();
  if (!throttleResult.proceed) {
    throw new Error(`Search rejected: ${throttleResult.reason}. Please wait and try again.`);
  }

  // 0. Extract Scope Tags (Hashtags) to preserve them across strategies
  // We want to make sure if user typed "#work", it stays even if we strip adjectives.
  const scopeTags: string[] = [...tags];
  const queryParts = query.split(/\s+/);
  queryParts.forEach(part => {
    if (part.startsWith('#')) scopeTags.push(part);
  });
  const tagsString = scopeTags.join(' ');

  // Strategy 1: Standard Expanded Search (All Nouns, Verbs, Dates + Expansion)
  console.log(`[IterativeSearch] Strategy 1: Standard Execution`);
  let results = await executeSearch(query, buckets, maxChars, provenance, tags, undefined, useMaxRecall, userContext);
  if (results.results.length > 0) return { ...results, attempt: 1 };

  // Strategy 2: Strict "Subjects & Time" (Strip Verbs/Adjectives, keep Nouns + Dates)
  console.log(`[IterativeSearch] Strategy 2: Strict Nouns/Dates`);
  const temporalContext = extractTemporalContext(query);
  const doc = nlp.readDoc(query);
  const nouns = doc.tokens().filter((t: any) => {
    const tag = t.out(nlp.its.pos);
    return tag === 'NOUN' || tag === 'PROPN';
  }).out((nlp as any).its.text);

  const uniqueTokens = new Set([...nouns, ...temporalContext]);
  if (uniqueTokens.size > 0) {
    // Re-inject scope tags
    const strictQuery = Array.from(uniqueTokens).join(' ') + ' ' + tagsString;
    console.log(`[IterativeSearch] Fallback Query 1: "${strictQuery.trim()}"`);
    results = await executeSearch(strictQuery, buckets, maxChars, provenance, tags, undefined, false, userContext);
    if (results.results.length > 0) return { ...results, attempt: 2 };
  }

  // Strategy 3: "Just the Dates" (If query heavily implies time)
  // Sometimes "2025" is the only anchor we have if keywords fail.
  // Or maybe just "Proper Nouns" (Entities).
  const propNouns = doc.tokens().filter((t: any) => t.out(nlp.its.pos) === 'PROPN').out((nlp as any).its.text);

  // Re-inject scope tags
  const entityQuery = [...new Set([...propNouns, ...temporalContext])].join(' ') + ' ' + tagsString;

  if (entityQuery.trim().length > 0 && entityQuery.trim() !== (Array.from(uniqueTokens).join(' ') + ' ' + tagsString).trim()) {
    console.log(`[IterativeSearch] Fallback Query 2: "${entityQuery.trim()}"`);
    results = await executeSearch(entityQuery, buckets, maxChars, provenance, tags, undefined, false, userContext);
    if (results.results.length > 0) return { ...results, attempt: 3 };
  }

  return { ...results, attempt: 4 }; // Return empty result if all fail
}

/**
 * Smart Chat Search (The "Markovian" Context Gatherer)
 * Logic:
 * 1. Try standard Iterative Search.
 * 2. If Recall is Low (< 10 atoms), TRIGGER SPLIT.
 * 3. Split Query into Top Entities (Alice, Bob, etc.).
 * 4. Run Parallel Searches for each entity.
 * 5. Aggregate & Deduplicate.
 * 
 * @param useMaxRecall - If true, uses MAX_RECALL_CONFIG for comprehensive retrieval
 */
export async function smartChatSearch(
  query: string,
  buckets: string[] = [],
  maxChars: number = 20000,
  tags: string[] = [],
  provenance: 'internal' | 'external' | 'quarantine' | 'all' = 'all',
  useMaxRecall: boolean = false,
  userContext?: UserContext
): Promise<{ context: string; results: SearchResult[]; strategy: string; splitQueries?: string[]; metadata?: any; toAgentString: () => string }> {

  const isLongQuery = query.length > 100;
  let initial = { results: [] as SearchResult[], context: '', toAgentString: () => '' };

  // 1. Initial Attempt (Skip if it's a massive max-recall query to force chunking)
  if (!isLongQuery || !useMaxRecall) {
    initial = await iterativeSearch(query, buckets, maxChars, tags, provenance, useMaxRecall, userContext);

    // If we have enough results, returns immediately
    if (initial.results.length >= 10 && !useMaxRecall) {
      return { ...initial, strategy: 'standard' };
    }
    // Max-recall initial search already runs with full budget and 1639-atom target —
    // parallel sub-query split would just run 3 more full-budget searches simultaneously,
    // tripling memory. Return here.
    if (useMaxRecall && initial.results.length > 0) {
      return { ...initial, strategy: 'max-recall' };
    }
  }

  console.log(`[SmartSearch] Triggering Multi-Query Split...`);

  // 2. Extract Entities for Split Search
  let splitQueries: string[] = [];

  if (isLongQuery && useMaxRecall) {
    // Chunk the query into groups of 3-4 words for massive keyword lists
    const words = query.split(/\s+/).filter(w => w.length > 2);
    for (let i = 0; i < words.length; i += 4) {
      splitQueries.push(words.slice(i, i + 4).join(' '));
    }
    // Limit to top 5 chunks to avoid blowing up the DB
    splitQueries = splitQueries.slice(0, 5);
  } else {
    const doc = nlp.readDoc(query);
    // Get Proper Nouns (Entities) and regular Nouns
    // We prioritize PROPN (High Value)
    let entities: string[] = [];
    entities = doc.tokens()
      .filter((t: any) => t.out(nlp.its.pos) === 'PROPN')
      .out(nlp.its.normal, nlp.as.freqTable)
      .map((e: any) => e[0])
      .slice(0, 3); // Top 3 Entities

    // If no entities, try Nouns
    if (entities.length === 0) {
      const nouns = doc.tokens()
        .filter((t: any) => t.out(nlp.its.pos) === 'NOUN')
        .out(nlp.its.normal, nlp.as.freqTable)
        .map((e: any) => e[0])
        .slice(0, 3);
      entities.push(...nouns);
    }
    splitQueries = entities;
  }

  if (splitQueries.length === 0) {
    // No entities to split on, return what we have
    return { ...initial, strategy: 'shallow', splitQueries: [] };
  }

  console.log(`[SmartSearch] Split Entities/Chunks: ${JSON.stringify(splitQueries)}`);

  // 3. Sequential Execution
  // Run each split sub-query one at a time to prevent concurrent heap exhaustion.
  // Parallel Promise.all with max-recall budgets multiplies memory by N sub-queries.
  const budgetPerQuery = useMaxRecall ? maxChars : Math.floor(maxChars / splitQueries.length);
  const parallelResults: Awaited<ReturnType<typeof executeSearch>>[] = [];
  for (const entity of splitQueries) {
    parallelResults.push(
      await executeSearch(entity, buckets, budgetPerQuery, provenance, tags, undefined, useMaxRecall, userContext)
    );
  }

  // 4. Merge & Deduplicate
  const mergedMap = new Map<string, SearchResult>();

  // Add initial results first
  initial.results.forEach(r => mergedMap.set(r.id, r));

  // Add split results
  parallelResults.forEach((res) => {
    res.results.forEach(r => {
      if (!mergedMap.has(r.id)) {
        // Boost score slightly for multi-path discovery?
        // Or keep as is.
        mergedMap.set(r.id, r);
      }
    });
  });

  const mergedResults = Array.from(mergedMap.values());
  console.log(`[SmartSearch] Merged Total: ${mergedResults.length} atoms.`);

  // 4.5. Context Inflation — Expand each atom with surrounding context (n-1, n+1)
  // For max-recall searches, read full context from disk to fill the budget
  if (useMaxRecall && mergedResults.length > 0) {
    // Calculate per-atom budget to fill ~90% of total budget
    const budgetPerAtom = Math.floor(maxChars * 0.9 / mergedResults.length);
    console.log(`[SmartSearch] Inflating ${mergedResults.length} atoms with ${budgetPerAtom} chars each (total budget: ${maxChars})...`);

    const inflatedResults = await ContextInflator.inflate(
      mergedResults,
      maxChars,
      budgetPerAtom  // Dynamic radius based on available budget
    );

    // Replace merged results with inflated versions
    mergedResults.length = 0;
    mergedResults.push(...inflatedResults);

    const avgChars = Math.round(inflatedResults.reduce((sum, a) => sum + a.content.length, 0) / inflatedResults.length);
    console.log(`[SmartSearch] Inflation complete: ${inflatedResults.length} atoms with avg ${avgChars} chars each`);
  }

  // 5. Re-Format using GCP (Standard 086)
  const finalUserContext: UserContext = {
    name: userContext?.name || 'User',
    current_state: userContext?.current_state || 'active'
  };

  const serializedContext = assembleAndSerialize({
    user: finalUserContext,
    query: query,
    keyTerms: splitQueries,
    scopeTags: tags,
    anchors: mergedResults, // Treat all merged results as anchors for now in this aggregate view
    walkerResults: [],
    charBudget: maxChars * 1.5
  });

  return {
    context: serializedContext,
    results: mergedResults,
    toAgentString: () => serializedContext,
    strategy: 'split_merge',
    splitQueries: splitQueries,
    metadata: { strategy: 'split_merge' }
  };
}

/**
 * Cluster SearchResults into KnowledgeClusters for high-density JSON.
 * Groups by source file and sorts by chronological timestamp.
 */
export function clusterMolecules(results: SearchResult[]): KnowledgeCluster[] {
  const bySource = new Map<string, SearchResult[]>();
  for (const res of results) {
    const source = res.source || 'unknown';
    if (!bySource.has(source)) bySource.set(source, []);
    bySource.get(source)!.push(res);
  }

  const clusters: KnowledgeCluster[] = [];

  for (const [source, mols] of bySource) {
    // Sort chronologically
    mols.sort((a, b) => a.timestamp - b.timestamp);

    let currentGroup: SearchResult[] = [];

    for (let i = 0; i < mols.length; i++) {
      if (i === 0) {
        currentGroup.push(mols[i]);
      } else {
        const gapMs = Math.abs(mols[i].timestamp - mols[i - 1].timestamp);
        // If > 1 hour gap, split cluster
        if (gapMs > 60 * 60 * 1000) {
          clusters.push(createCluster(currentGroup, source));
          currentGroup = [mols[i]];
        } else {
          currentGroup.push(mols[i]);
        }
      }
    }

    if (currentGroup.length > 0) {
      clusters.push(createCluster(currentGroup, source));
    }
  }

  return clusters;
}

function createCluster(mols: SearchResult[], source: string): KnowledgeCluster {
  const startTs = new Date(mols[0].timestamp).toISOString();
  const endTs = new Date(mols[mols.length - 1].timestamp).toISOString();

  // Topic extraction based on tag frequency
  const tagCounts = new Map<string, number>();
  mols.forEach(m => {
    (m.tags || []).forEach(t => tagCounts.set(t, (tagCounts.get(t) || 0) + 1));
  });

  const topTags = Array.from(tagCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(e => e[0]);

  const topic = topTags.join(' ');

  // Transform SearchResult to KnowledgeMolecule
  const mappedMolecules: KnowledgeMolecule[] = mols.map(m => {
    const people: string[] = [];
    const concepts: string[] = [];
    const projects: string[] = [];

    if (m.tags) {
      m.tags.forEach(t => {
        const lower = t.toLowerCase();
        if (lower.includes('rob') || lower.includes('coda') || lower.includes('oliver')) {
          people.push(t);
        } else if (lower.includes('agent') || lower.includes('engine') || lower.includes('project') || lower.includes('anchor')) {
          projects.push(t);
        } else if (t.startsWith('#')) {
          concepts.push(t);
        }
      });
    }

    return {
      id: m.id,
      timestamp: new Date(m.timestamp).toISOString(),
      speaker: m.provenance || 'unknown',
      tags: m.tags || [],
      entities: {
        people,
        concepts,
        projects
      },
      content: m.content || '',
      byte_range: {
        start: m.start_byte || 0,
        end: m.end_byte || 0,
        source: m.source || 'unknown'
      }
    };
  });

  const safeId = startTs.replace(/[^0-9]/g, '');
  const basename = source.split(/[/\\]/).pop() || 'unknown';
  const clusterId = `cluster_${basename}_${safeId}`;

  return {
    id: clusterId,
    start_time: startTs,
    end_time: endTs,
    topic: topic,
    molecules: mappedMolecules
  };
}
