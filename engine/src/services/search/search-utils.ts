/**
 * Search Utilities Module — "The Tools"
 *
 * Types, interfaces, Hamming distance calculation, result formatting,
 * and display helpers used across the search subsystem.
 * Extracted from search.ts for clean separation of concerns.
 */

import { config } from '../../config/index.js';
import { composeRollingContext } from '../../core/inference/context_manager.js';
import { wasmModuleLoader } from '../../utils/wasm-module-loader.js';
import type { SemanticCategory } from '../../types/taxonomy.js';
import { ContextInflator } from './context-inflator.js';
import { getSetting } from '../settings.js';
import * as fs from 'fs';
import * as path from 'path';
import { getMirrorPath, MIRRORED_BRAIN_PATH } from '../mirror/mirror.js';
import { PATHS } from '../../config/paths.js';

/**
 * Remove inline hashtag tokens from content (Standard 123).
 * Tags are stored separately in result.tags; they add noise when embedded in text.
 */
export function stripInlineTags(content: string): string {
  if (!content) return content;
  let s = content.replace(/\\?"#[^"\\]+\\?"/g, '');
  s = s.replace(/##?[A-Za-z0-9_\u0080-\uFFFF]+/g, '');
  // Only strip " - " list separators (space-hyphen-space), not bare hyphens
  // in kebab-case identifiers like p-6, text-xl, font-bold, etc.
  s = s.replace(/[ \t]+-[ \t]+/g, ' ');
  // Collapse any extra whitespace left after tag removal
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

/**
 * Remove tag footers from truncated snippets (Standard 123 extension).
 * When YAML session records are truncated mid-record, structural metadata
 * footers appear (e.g., ##19864Residen ##1Okay ##3am ##ABQLo).
 * These are serialization artifacts, not content.
 */
export function stripTagFooters(content: string): string {
  if (!content) return '';
  const lines = content.split('\n');
  // Remove trailing lines that are predominantly tag tokens (##*)
  while (lines.length > 0) {
    const lastLine = lines[lines.length - 1].trim();
    // Pattern: one or more "##Token" separated by spaces (structural footer)
    if (/^(##[A-Za-z0-9_]*\s*)+$/.test(lastLine)) {
      lines.pop();
    } else {
      break;
    }
  }
  return lines.join('\n').trim();
}

/**
 * Coalesced Snippet - Merged atoms from same file within proximity threshold
 */
export interface CoalescedSnippet {
  source: string;
  compoundId: string;
  startByte: number;
  endByte: number;
  timestamp: number;
  content: string;
  sourceAtoms: SearchResult[];  // Track which atoms were merged
  relevanceScore: number;
  provenance: string;
  tags: string[];
}

export interface SearchResult {
    id: string;
    content: string;
    source: string;
    timestamp: number;
    buckets: string[];
    tags: string[];
    epochs: string;
    provenance: string;
    score: number;
    sequence?: number; // Added for Bright Node continuity
    molecular_signature?: string;  // V4 Nomenclature (formerly simhash)
    frequency?: number; // Number of times this content was found (for deduplication)
    temporal_state?: { // Information about temporal aspects of duplicates
        first_seen: number;
        last_seen: number;
        occurrence_count: number;
        timestamps: number[]; // Array of all timestamps when this content or similar was found
    };
    // Atomic Fields
    compound_id?: string;
    start_byte?: number;
    end_byte?: number;
    type?: string;
    numeric_value?: number;
    numeric_unit?: string;
    is_inflated?: boolean;
    // Semantic Fields
    semanticCategories?: SemanticCategory[];
    relatedEntities?: string[];
    // Context Provenance (Standard 107)
    temporal_weight?: number; // Exponential decay factor e^(-λΔt)
    decay_factor?: number; // Lambda * age in seconds
    simhash_distance?: number; // Hamming distance from query (0-64)
    structural_similarity?: number; // 1 - (distance/64)
    association_path?: string[]; // Tags that connected this result to query
    retrieved_at?: number; // When this result was retrieved (for caching)
}

/**
 * Helper: Calculate Hamming Distance between two hex strings
 * Uses the native module or fallback if available
 */
export function getHammingDistance(hashA: string, hashB: string): number {
    try {
        // Validate inputs before processing
        if (!hashA || !hashB) {
            console.warn('[Search] Invalid hash inputs for Hamming distance calculation:', { hashA, hashB });
            return 64; // Max distance on error (assume different)
        }

        // Ensure valid hex strings (strip 0x prefix if present)
        const cleanA = hashA.replace(/^0x/i, '');
        const cleanB = hashB.replace(/^0x/i, '');
        if (!/^[0-9a-fA-F]+$/.test(cleanA) || !/^[0-9a-fA-F]+$/.test(cleanB)) {
            console.warn('[Search] Invalid hex string format for Hamming distance:', { hashA, hashB });
            return 64; // Max distance on error (assume different)
        }

        const a = BigInt(`0x${cleanA}`);
        const b = BigInt(`0x${cleanB}`);

        // Use WASM module for distance calculation (Standard 074 - WASM Edition)
        try {
          return wasmModuleLoader.distance(a, b);
        } catch (wasmError) {
          console.warn('[Search] WASM distance function failed, using JS fallback:', wasmError);
        }
        
        // JavaScript fallback implementation
        let xor = a ^ b;
        let count = 0;
        while (xor > 0n) {
            xor &= (xor - 1n);
            count++;
        }
        return count;

    } catch (e) {
        console.error('[Search] Hamming distance calculation failed:', e);
        return 64; // Max distance on error (assume different)
    }
}

/**
 * Helper: safely extract array from possibly undefined input
 */
export function getItems(input: string[] | undefined): string[] {
    return Array.isArray(input) ? input : [];
}

/**
 * Coalesce atoms by proximity - merges nearby atoms from same source file
 * into coherent snippets for better LLM consumption
 *
 * @param results - Search results to coalesce
 * @param proximityThreshold - Bytes within which to merge atoms (default 500)
 * @returns Coalesced snippets with expanded content
 */
export async function coalesceByProximity(
  results: SearchResult[],
  proximityThreshold: number = 500,
  maxSnippets: number = 500,
): Promise<CoalescedSnippet[]> {
  // Group by compound_id (source file)
  const byCompound = new Map<string, SearchResult[]>();
  results.forEach(r => {
    if (!r.compound_id || !r.source) return;
    if (!byCompound.has(r.compound_id)) byCompound.set(r.compound_id, []);
    byCompound.get(r.compound_id)!.push(r);
  });

  const coalesced: CoalescedSnippet[] = [];
  let mergedCount = 0;

  for (const [compoundId, atoms] of byCompound.entries()) {
    if (atoms.length === 0) continue;

    // Sort by byte offset
    atoms.sort((a, b) => (a.start_byte || 0) - (b.start_byte || 0));

    // Merge atoms within proximity threshold
    const merged: CoalescedSnippet[] = [];
    let current: CoalescedSnippet | null = null;

    for (const atom of atoms) {
      const atomStart = atom.start_byte || 0;
      const atomEnd = atom.end_byte || 0;

      if (!current) {
        current = {
          source: atom.source,
          compoundId,
          startByte: atomStart,
          endByte: atomEnd,
          timestamp: atom.timestamp,
          content: atom.content,
          sourceAtoms: [atom],
          relevanceScore: atom.score,
          provenance: atom.provenance || 'internal',
          tags: (atom.tags || []).slice(0, 10), // Limit to top 10 tags initially
        };
      } else {
        const gap = atomStart - current.endByte;

        // Merge if overlapping or within proximity threshold
        if (gap <= proximityThreshold) {
          // Extend window
          current.endByte = Math.max(current.endByte, atomEnd);
          current.sourceAtoms.push(atom);
          current.relevanceScore = Math.max(current.relevanceScore, atom.score);
          current.timestamp = Math.min(current.timestamp, atom.timestamp); // Use earliest timestamp
          // Merge tags but limit to top 10 most relevant
          const mergedTags = Array.from(new Set([...current.tags, ...(atom.tags || [])]));
          current.tags = mergedTags.slice(0, 15); // Allow slightly more during merge, final limit applied later
          mergedCount++;
        } else {
          // Push current and start new
          merged.push(current);
          current = {
            source: atom.source,
            compoundId,
            startByte: atomStart,
            endByte: atomEnd,
            timestamp: atom.timestamp,
            content: atom.content,
            sourceAtoms: [atom],
            relevanceScore: atom.score,
            provenance: atom.provenance || 'internal',
            tags: (atom.tags || []).slice(0, 10), // Limit to top 10 tags for new snippets
          };
        }
      }
    }
    if (current) merged.push(current);

    // Per-source cap: prevent a single file from dominating the results.
    // Keep the top-scoring snippets per source before the global maxSnippets cap.
    // maxPerSource scales with budget: 3 for small budgets, up to 8 for large.
    const maxPerSource = Math.max(3, Math.min(8, Math.ceil(maxSnippets / 15)));
    const perSourceCapped = merged
      .sort((a, b) => b.relevanceScore - a.relevanceScore)
      .slice(0, maxPerSource);
    coalesced.push(...perSourceCapped);
  }

  // Sort all snippets by relevance score DESC, keep only top-maxSnippets before
  // inflating from disk. This prevents inflating 200+ snippets when only 20-30
  // will fit in the token budget.
  coalesced.sort((a, b) => b.relevanceScore - a.relevanceScore);
  const cappedCoalesced = coalesced.slice(0, maxSnippets);

  // Re-inflate content from disk only for the snippets we're keeping
  for (const snippet of cappedCoalesced) {
    try {
      const inflatedContent = await inflateSnippetFromDisk(snippet);
      if (inflatedContent) {
        snippet.content = inflatedContent;
      }
    } catch (e) {
      console.warn(`[Coalesce] Failed to inflate snippet from ${snippet.source}`, e);
    }
  }

  console.log(`[Coalesce] Merged ${results.length} atoms -> ${coalesced.length} snippets (${mergedCount} merges), inflating top ${cappedCoalesced.length}`);
  return cappedCoalesced;
}

/**
 * Inflate a coalesced snippet from disk
 */
// Hard limit per snippet to prevent OOM when coalesced byte ranges span large files.
// With 800px proximity threshold in max-recall, merged windows can be multi-MB.
// 100KB is ample for any single context snippet (≈25k tokens).
const MAX_SNIPPET_BYTES = 100_000;

async function inflateSnippetFromDisk(snippet: CoalescedSnippet): Promise<string | null> {
  try {
    // Resolve file path - try mirrored first
    const mirrorPath = getMirrorPath(snippet.source, snippet.provenance);
    let absolutePath = mirrorPath;

    if (!fs.existsSync(mirrorPath)) {
      absolutePath = path.isAbsolute(snippet.source)
        ? snippet.source
        : path.join(MIRRORED_BRAIN_PATH, snippet.source);
    }

    if (!fs.existsSync(absolutePath)) return null;

    const stats = fs.statSync(absolutePath);
    const fileSize = stats.size;

    // Clamp to file bounds
    const start = Math.max(0, snippet.startByte);
    const rawEnd = Math.min(fileSize, snippet.endByte);

    if (start >= rawEnd) return null;

    // Cap read size: if the merged window is huge, read from the start of the window
    // up to MAX_SNIPPET_BYTES only.  Content is truncated, not silently dropped.
    const readLength = Math.min(rawEnd - start, MAX_SNIPPET_BYTES);
    const end = start + readLength;
    const truncated = end < rawEnd;

    // Read content
    const buffer = Buffer.alloc(readLength);
    const fd = fs.openSync(absolutePath, 'r');
    try {
      fs.readSync(fd, buffer, 0, readLength, start);
    } finally {
      fs.closeSync(fd);
    }

    let content = buffer.toString('utf-8');

    // Snap to sentence boundaries for coherence
    content = snapToSentenceBoundaries(content, 0, content.length).text;

    // Strip tag footers (##19864Residen, ##1Okay, etc.) that appear when truncating YAML records
    content = stripTagFooters(content);

    // Add ellipsis to indicate truncation
    if (start > 0) content = '...' + content;
    if (truncated || end < fileSize) content += '...';

    return content.trim();
  } catch (e) {
    console.warn('[Coalesce] inflateSnippetFromDisk failed:', e);
    return null;
  }
}

/**
 * Snap to sentence boundaries for cleaner snippets
 */
function snapToSentenceBoundaries(content: string, targetStart: number, targetEnd: number): { start: number, end: number, text: string } {
  // Snap start: find previous sentence end
  const preceding = content.substring(0, targetStart);
  const matchStart = preceding.match(/([.!?]\s|\n\s*\n)(?=[^.!?\n]*$)/);
  const snappedStart = matchStart && matchStart.index !== undefined
    ? matchStart.index + matchStart[0].length
    : 0;

  // Snap end: find next sentence end
  const succeeding = content.substring(targetEnd);
  const matchEnd = succeeding.match(/([.!?]\s|\n\s*\n)/);
  const snappedEnd = matchEnd && matchEnd.index !== undefined
    ? targetEnd + matchEnd.index + 1
    : content.length;

  return {
    start: snappedStart,
    end: snappedEnd,
    text: content.substring(snappedStart, snappedEnd).trim(),
  };
}

/**
 * Format search results within character budget
 * Uses molecular coordinates (start_byte/end_byte) for precise content slicing
 *
 * Features:
 * - Coalesces nearby atoms into coherent snippets (500-1000 chars)
 * - Adds metadata headers with file, range, timestamp, atom count
 * - Sorts chronologically for causal narrative
 * - Wraps in XML with relevance scores for LLM prioritization
 */
export async function formatResults(
  results: SearchResult[],
  maxChars: number,
  options?: { enableCoalescing?: boolean; proximityThreshold?: number; },
): Promise<{ context: string; results: SearchResult[]; toAgentString: () => string; metadata?: any }> {
  try {
    const enableCoalescing = options?.enableCoalescing ?? true;
    const proximityThreshold = options?.proximityThreshold ?? 500;

    // Step 1: Coalesce atoms into coherent snippets
    let snippets: CoalescedSnippet[];
    let coalescingStats = { 
      original_atoms: results.length, 
      coalesced_snippets: results.length, 
      compression_ratio: 1.0, 
    };

    if (enableCoalescing) {
      // Cap snippets to inflate based on budget: minimum 50, max one per 500 chars of budget
      // (reduced from 300 to prevent OOM when processing large result sets)
      const maxSnippetsForBudget = Math.max(50, Math.ceil(maxChars / 500));
      snippets = await coalesceByProximity(results, proximityThreshold, maxSnippetsForBudget);
      coalescingStats = {
        original_atoms: results.length,
        coalesced_snippets: snippets.length,
        compression_ratio: results.length > 0 ? (results.length / snippets.length) : 1.0,
      };
    } else {
      // Convert SearchResult[] to CoalescedSnippet[] for uniform handling
      snippets = results.map(r => ({
        source: r.source,
        compoundId: r.compound_id || '',
        startByte: r.start_byte || 0,
        endByte: r.end_byte || 0,
        timestamp: r.timestamp,
        content: r.content,
        sourceAtoms: [r],
        relevanceScore: r.score,
        provenance: r.provenance || 'internal',
        tags: (r.tags || []).slice(0, 10), // Limit to top 10 most relevant tags per molecule
      }));
    }

    // Step 2: Sort chronologically (causal narrative)
    snippets.sort((a, b) => a.timestamp - b.timestamp);

    // Step 3: Calculate temporal weights
    const now = Date.now();
    const lambda = 0.00001;  // h⁻¹ - 7.9 year half-life (matches paper.md line 69)

    const enrichedSnippets = snippets.map(s => {
      const ageMs = now - s.timestamp;
      const ageHours = ageMs / (1000 * 60 * 60);  // Convert ms to hours for λ in h⁻¹
      const decayFactor = lambda * ageHours;
      const temporalWeight = Math.exp(-decayFactor);
      const relevanceScore = (s.relevanceScore * temporalWeight).toFixed(3);

      return {
        ...s,
        content: stripInlineTags(s.content),   // Standard 123: strip inline #Tag tokens
        temporal_weight: temporalWeight,
        decay_factor: decayFactor,
        weighted_score: relevanceScore,
      };
    });

    // Step 3.5: Semantic word-overlap deduplication.
    // Drop snippets whose significant words are already well-covered by a higher-scored snippet.
    // "Significant words" = >4 chars, not stopwords. Overlap threshold = 60%.
    const OVERLAP_THRESHOLD = 0.60;
    const STOPWORDS = new Set(['this','that','with','from','they','were','have','been','their','which','when','will','also','what','your','more','some','than','then','into','there','about','would','could','should','other','after','these','those','just','over','such','even','like','much','well','also','here','very','only','its']);
    const sigWords = (text: string): Set<string> => {
      const words = text.toLowerCase().match(/\b[a-z]{5,}\b/g) || [];
      return new Set(words.filter(w => !STOPWORDS.has(w)));
    };
    const jaccardOverlap = (a: Set<string>, b: Set<string>): number => {
      if (a.size === 0 || b.size === 0) return 0;
      let intersection = 0;
      for (const w of a) if (b.has(w)) intersection++;
      return intersection / Math.min(a.size, b.size);
    };

    const deduped: typeof enrichedSnippets = [];
    const acceptedWordSets: Set<string>[] = [];
    // Sort by weighted_score DESC for dedup pass (best snippets win), then re-sort chronologically below
    const scoreOrdered = [...enrichedSnippets].sort((a, b) => parseFloat(b.weighted_score) - parseFloat(a.weighted_score));
    for (const s of scoreOrdered) {
      const words = sigWords(s.content);
      const isDuplicate = acceptedWordSets.some(accepted => jaccardOverlap(words, accepted) >= OVERLAP_THRESHOLD);
      if (!isDuplicate) {
        deduped.push(s);
        acceptedWordSets.push(words);
      }
    }
    // Restore chronological order for causal narrative
    deduped.sort((a, b) => a.timestamp - b.timestamp);
    const deduplicatedSnippets = deduped;
    const dedupRemovedCount = enrichedSnippets.length - deduplicatedSnippets.length;
    if (dedupRemovedCount > 0) {
      console.log(`[Dedup] Removed ${dedupRemovedCount} semantically overlapping snippets (${enrichedSnippets.length} → ${deduplicatedSnippets.length})`);
    }

    // Force garbage collection after dedup to free memory from enrichedSnippets
    if (global.gc) {
      global.gc();
    }

    // Step 4: Build XML-wrapped context with metadata headers
    const xmlContext = deduplicatedSnippets.map((s, idx) => {
      const timestamp = new Date(s.timestamp).toISOString();
      const persona = s.tags[0] || s.provenance || 'unknown';
      const atomCount = s.sourceAtoms.length;
      const charCount = s.content.length;
      const startHex = s.startByte.toString(16).toUpperCase().padStart(4, '0');
      const endHex = s.endByte.toString(16).toUpperCase().padStart(4, '0');
      const fileName = path.basename(s.source);

      // Metadata header for each snippet
      const header = `[GROUP:${idx + 1}] [File:${fileName}] [Range: 0x${startHex}-0x${endHex}] [Time: ${timestamp}] [Atoms: ${atomCount}] [Chars: ${charCount}]`;

      return `${header}
<atom id="${s.sourceAtoms.map(a => a.id.substring(0, 8)).join(',')}" relevance="${s.weighted_score}" timestamp="${timestamp}" persona="${persona}" source="${s.source}">
${s.content}
</atom>`;
    }).join('\n\n');

    // Force garbage collection after building XML context to free dedup arrays
    if (global.gc) {
      global.gc();
    }

    // Step 5: Calculate budget allocation
    const totalContentChars = deduplicatedSnippets.reduce((sum, s) => sum + s.content.length, 0);
    const overheadChars = xmlContext.length - totalContentChars;
    const budgetUtilization = maxChars > 0 ? ((totalContentChars + overheadChars) / maxChars * 100).toFixed(1) : 'N/A';

    // Step 6: Convert snippets back to SearchResult[] for API compatibility
    const enrichedResults: SearchResult[] = deduplicatedSnippets.map(s => ({
      id: s.sourceAtoms.map(a => a.id).join('+'),
      content: s.content,
      source: s.source,
      timestamp: s.timestamp,
      buckets: [],
      tags: s.tags,
      epochs: '',
      provenance: s.provenance,
      score: s.relevanceScore,
      compound_id: s.compoundId,
      start_byte: s.startByte,
      end_byte: s.endByte,
      temporal_weight: s.temporal_weight,
      decay_factor: s.decay_factor,
      is_inflated: true,
    }));

    return {
      context: xmlContext || 'No results found.',
      results: enrichedResults,
      toAgentString: () => {
        return deduplicatedSnippets.map(s =>
          `[${s.provenance}] ${s.source} (t=${s.temporal_weight.toFixed(3)}, atoms=${s.sourceAtoms.length}): ${s.content.substring(0, 200)}...`,
        ).join('\n');
      },
      metadata: {
        coalescing: coalescingStats,
        deduplication: { removed: dedupRemovedCount, remaining: deduplicatedSnippets.length },
        budget_allocation: {
          total_chars: totalContentChars + overheadChars,
          content_chars: totalContentChars,
          overhead_chars: overheadChars,
          utilization_percent: parseFloat(budgetUtilization),
        },
        provenance_enabled: true,
        temporal_decay_lambda: lambda,
        xml_wrapped: true,
        chronological_sort: true,
      },
    };
  } catch (error) {
    console.error('[Search] formatResults failed:', error);
    return {
      context: 'Error occurred during result formatting.',
      results: [],
      toAgentString: () => 'Error occurred during result formatting.',
      metadata: { error: true, message: 'Failed to format search results' },
    };
  }
}

/**
 * Helper to filter tags for display (User Request: Hide Year Numbers)
 */
export async function filterDisplayTags(tags: string[]): Promise<string[]> {
  const hideYears = await getSetting('search.hide_years_in_tags', false);
  if (!hideYears) return tags;
  // Remove if exactly 4 digits (approx year check)
  return tags.filter(t => !/^\d{4}$/.test(t));
}
