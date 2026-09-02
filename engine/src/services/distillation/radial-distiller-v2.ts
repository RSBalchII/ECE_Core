/**
 * Radial Distiller v2.0 — Decision Record Output
 *
 * Three-phase pipeline for semantic corpus compression:
 * 1. COLLECT: Extract semantic blocks (headings, sections)
 * 2. DEDUPLICATE: Block-level deduplication with SimHash (using @rbalchii/anchor-fingerprint-wasm)
 * 3. REASSEMBLE: Build Decision Record JSON output
 *
 * Prevents self-contamination by filtering distilled_* files
 */

import { db } from '../../core/db.js';
import { ContextInflator } from '../search/context-inflator.js';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { pathManager } from '../../utils/path-manager.js';
import { getMirrorPath } from '../mirror/mirror.js';
import { recordDistill } from './distill-manager.js';
import { wasmModuleLoader } from '../../utils/wasm-module-loader.js';
import { config, PATHS } from '../../config/index.js';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { execSync } from 'child_process';

// Configuration
const PGLITE_CHUNK_IDS = 100;
const MOBILE_MEMORY_THRESHOLD = 500 * 1024 * 1024;

/**
 * Guard for paths that are interpolated into shell commands (e.g. the git call in
 * extractTemporalMetadata). Only allow a conservative path charset so a hostile
 * source_path cannot break out of the quotes and inject arbitrary shell code.
 * Returns true when the path is safe to interpolate; false otherwise.
 */
function isShellSafePath(p: string): boolean {
  return /^[A-Za-z0-9/._\-]+$/.test(p) && p.length > 0 && !p.includes('..');
}

// Filtering patterns to prevent self-contamination
const DISTILLATION_OUTPUT_PATTERNS = [
  /distilled_.*\.(yaml|json|md)$/i,
  /MASTER_DISTILLED_.*\.(yaml|json|md)$/i,
  /_distilled_.*\.(yaml|json|md)$/i,
];

/**
 * Check if a file should be excluded (distillation output)
 */
function isDistillationOutput(filePath: string): boolean {
  const fileName = path.basename(filePath);
  return DISTILLATION_OUTPUT_PATTERNS.some(pattern => pattern.test(fileName));
}

/**
 * Semantic Block interface
 */
export interface SemanticBlock {
  id: string;
  type: 'heading1' | 'heading2' | 'heading3' | 'problem' | 'solution' | 'rationale' | 'status' | 'content';
  content: string;
  heading?: string;
  level: number;
  provenance: string[];
  mtime: number;
  simhash: string;
  tags?: string[];
}

/**
 * Decision Record interface (final output)
 */
export interface DecisionRecord {
  id: string;
  title: string;
  problem?: string;
  solution?: string[];
  rationale?: string;
  supersedes?: string[];
  status: 'active' | 'deprecated' | 'archived';
  timestamp: string;
  provenance: string[];
  tags: string[];
}

/**
 * Temporal metadata extracted via cascade
 */
export interface TemporalMetadata {
  primary: string;           // YYYY-MM-DD
  fallback_source: 'content' | 'git' | 'filename' | 'mtime';
}

/**
 * Memory type classification
 */
export type MemoryType = 'episodic' | 'procedural' | 'semantic' | 'metacognitive';

/**
 * Enriched decision record with temporal and memory type metadata
 */
export interface EnrichedDecisionRecord extends DecisionRecord {
  temporal: TemporalMetadata;
  memory_type: MemoryType;
  frequency?: number;
  source_files?: string[];
  related_entries?: string[];
}

/**
 * Universal Digital Object Metadata
 * Captures file-agnostic metadata for any digital object
 */
export interface DigitalObjectMetadata {
  // Core identity (always present)
  id: string;                   // Unique identifier (hash or UUID)
  source_path: string;          // Original file path
  source_type: string;          // File extension or format hint (jsonl, md, ts, etc.)
  
  // Temporal (always present for filesystem objects)
  created_at?: string;          // File creation time (ISO)
  modified_at: string;          // File mtime (ISO)
  ingested_at: string;          // When added to Anchor Engine (ISO)
  
  // Provenance (always present)
  bucket: string;               // Source bucket (inbox, external-inbox, etc.)
  compound_id: string;          // Database compound ID
  
  // Content metadata (always calculable)
  size_bytes: number;           // File size
  line_count?: number;          // Line count (for text files)
  char_count?: number;          // Character count
  
  // Semantic metadata (extracted during distillation)
  topics?: string[];            // Extracted topics/themes
  entities?: string[];          // Named entities found
  tags?: string[];              // Assigned tags
}

/**
 * Chat Session Metadata (extends digital object with session-specific data)
 * Only populated when source_type === 'jsonl' and bucket === 'inbox'
 */
export interface ChatSessionMetadata extends DigitalObjectMetadata {
  session_id: string;           // UUID from JSONL filename
  session_start: string;        // First message timestamp
  session_end: string;          // Last message timestamp
  commands: string[];           // Slash commands run (/auth, /model, etc.)
  message_count: number;        // Total messages
  participants: string[];       // Roles observed (user, assistant, system)
  models_used?: string[];       // LLM models referenced
}

/**
 * Session Index Entry (for query routing)
 * Derived from ChatSessionMetadata, optimized for search
 */
export interface SessionIndexEntry {
  session_id: string;           // UUID for targeted queries
  date: string;                 // Session start date
  commands: string[];           // Commands for command-based queries
  topics: string[];             // Topics for semantic queries
  full_log_path: string;        // Path for direct file access
  message_count: number;        // For filtering by session size
  participants: string[];       // For filtering by interaction type
}

export interface RadialDistillRequest {
  seed?: {
    query?: string;
    compound_ids?: string[];
    buckets?: string[];
    tags?: string[];  // New: tag-based distillation mode
  };
  radius?: number;
  max_radius?: number;
  output_format?: 'yaml' | 'json' | 'decision-records' | 'json-full' | 'nested-yaml';
  output_path?: string;
  export_to_inbox?: boolean;
  auto_save?: boolean;
  mode?: 'standard' | 'tag-based' | 'full-corpus';  // New: distillation mode
  dry_run?: boolean;                 // New: preview without writing
  similarity_threshold?: number;     // New: aggregation aggressiveness (0.0-1.0, default 0.85)
  page_size?: number;                // full-corpus: atoms per DB page (default 500)
  inflate_radius?: number;           // full-corpus: bytes each side of pointer to inflate (default 500, max 1000)
  max_record_bytes?: number;         // full-corpus: hard cap on inflated content per record (default 8192)
}

export interface RadialDistillResult {
  stats: {
    compounds_processed: number;
    blocks_total: number;
    blocks_unique: number;
    decision_records: number;
    compression_ratio: string;
    duration_ms: number;
    memory_peak_mb: number;
  };
  output: {
    format: string;
    path?: string;
    size_bytes: number;
    records_created?: number;
  };
  provenance: {
    source_compounds: string[];
    distilled_at: string;
    parameters: RadialDistillRequest;
  };
  // Decision records (the actual distilled content)
  records?: DecisionRecord[];
  // NEW: Enriched records with temporal, memory_type, and aggregation metadata
  enriched_records?: EnrichedDecisionRecord[];
  // Digital object metadata for all processed compounds
  digital_objects?: DigitalObjectMetadata[];
  // Session index (subset of digital_objects for chat sessions)
  session_index?: SessionIndexEntry[];
  // Inflated content for tag-based mode (full atom content)
  inflated_content?: { content: string; source: string; tags: string[]; timestamp: number; }[];
  // Distillation metrics tracking (NEW)
  metrics?: {
    totalAtoms: number;
    successfulReads: number;
    provenanceMismatches: number;
    fallbackReads: number;
    failedReads: number;
    skippedByContent: number;
  };
}

/**
 * Extract semantic blocks from markdown text
 * Splits on headings and detects section types
 */
function extractSemanticBlocks(content: string, sourcePath: string, mtime: number): SemanticBlock[] {
  const blocks: SemanticBlock[] = [];
  const lines = content.split('\n');

  // DEBUG: Log first few lines for debugging
  console.log(`[DEBUG] extractSemanticBlocks: source=${sourcePath}, lines=${lines.length}`);
  if (lines.length > 0) {
    console.log(`[DEBUG] First line: ${JSON.stringify(lines[0])}`);
  }

  let currentBlock: string[] = [];
  let currentType: SemanticBlock['type'] = 'content';
  let currentLevel = 0;
  let currentHeading = '';

  const headingPattern = /^(#{1,6})\s+(.+)$/;
  const typeKeywords: Record<string, SemanticBlock['type']> = {
    'problem': 'problem',
    'issue': 'problem',
    'challenge': 'problem',
    'solution': 'solution',
    'approach': 'solution',
    'implementation': 'solution',
    'rationale': 'rationale',
    'why': 'rationale',
    'reason': 'rationale',
    'status': 'status',
    'state': 'status',
  };
  
  function saveBlock() {
    if (currentBlock.length > 0) {
      const blockContent = currentBlock.join('\n').trim();
      if (blockContent) {
        const simhash = computeSimHash(blockContent);
        blocks.push({
          id: crypto.createHash('sha256').update(blockContent).digest('hex').substring(0, 16),
          type: currentType,
          content: blockContent,
          heading: currentHeading || undefined,
          level: currentLevel,
          provenance: [sourcePath],
          mtime,
          simhash,
          tags: extractTags(blockContent),
        });
      }
    }
  }
  
  for (const line of lines) {
    const headingMatch = line.match(headingPattern);
    
    if (headingMatch) {
      // Save previous block
      saveBlock();
      
      // Start new block
      currentLevel = headingMatch[1].length;
      currentHeading = headingMatch[2].trim();
      currentBlock = [line];
      
      // Detect type from heading
      const headingLower = currentHeading.toLowerCase();
      currentType = 'content';
      for (const [keyword, type] of Object.entries(typeKeywords)) {
        if (headingLower.includes(keyword)) {
          currentType = type;
          break;
        }
      }
      
      // Override for heading levels
      if (currentLevel === 1) currentType = 'heading1';
      else if (currentLevel === 2) currentType = 'heading2';
      else if (currentLevel === 3) currentType = 'heading3';
    } else {
      currentBlock.push(line);
    }
  }
  
  // Save last block
  saveBlock();
  
  return blocks;
}

/**
 * Compute SimHash for a block using WASM module (Rust-compiled)
 */
function computeSimHash(text: string): string {
  // Use WASM fingerprint module (Rust-compiled, works on all platforms)
  try {
    const hash = wasmModuleLoader.fingerprint(text);
    // Convert bigint to hex string (16 chars = 64 bits)
    if (hash && typeof hash === 'bigint') {
      return hash.toString(16).padStart(16, '0').substring(0, 16);
    }
  } catch (e: any) {
    // Silent fallback - WASM not available on all platforms
  }
  
  // Fallback: deterministic hash using crypto
  const hash = crypto.createHash('sha256').update(text.toLowerCase().replace(/\s+/g, ' ')).digest('hex');
  return hash.substring(0, 16);
}

/**
 * Extract tags from content
 */
function extractTags(content: string): string[] {
  const tagPattern = /#(\w+)/g;
  const tags: string[] = [];
  let match;
  
  while ((match = tagPattern.exec(content)) !== null) {
    tags.push(match[1].toLowerCase());
  }
  
  return tags;
}

/**
 * Deduplicate blocks by SimHash within same type
 */
function deduplicateBlocks(blocks: SemanticBlock[]): SemanticBlock[] {
  const uniqueBlocks = new Map<string, SemanticBlock>();
  
  for (const block of blocks) {
    const key = `${block.type}:${block.simhash}`;
    
    if (!uniqueBlocks.has(key)) {
      uniqueBlocks.set(key, block);
    } else {
      // Merge provenance
      const existing = uniqueBlocks.get(key)!;
      for (const prov of block.provenance) {
        if (!existing.provenance.includes(prov)) {
          existing.provenance.push(prov);
        }
      }
      // Use earliest mtime
      if (block.mtime < existing.mtime) {
        existing.mtime = block.mtime;
      }
    }
  }
  
  return Array.from(uniqueBlocks.values());
}

/**
 * Assemble Decision Records from blocks
 * Groups by SIMHASH (content similarity) not by file - enables cross-file dedup
 */
function assembleDecisionRecords(blocks: SemanticBlock[]): DecisionRecord[] {
  const records: DecisionRecord[] = [];
  
  // Group blocks by SIMHASH + TYPE (same concept across files)
  const blocksByConcept = new Map<string, SemanticBlock[]>();
  
  for (const block of blocks) {
    // Key by simhash + type to group identical concepts across files
    const conceptKey = `${block.type}:${block.simhash}`;
    
    if (!blocksByConcept.has(conceptKey)) {
      blocksByConcept.set(conceptKey, []);
    }
    blocksByConcept.get(conceptKey)!.push(block);
  }
  
  // Create ONE decision record per unique concept (not per file!)
  for (const [conceptKey, conceptBlocks] of blocksByConcept.entries()) {
    // Merge ALL provenance from all files that share this concept
    const allProvenance = Array.from(
      new Set(conceptBlocks.flatMap(b => b.provenance))
    );
    
    // Merge ALL tags
    const allTags = Array.from(
      new Set(conceptBlocks.flatMap(b => b.tags || []))
    );
    
    // Use earliest mtime
    const earliestMtime = Math.min(...conceptBlocks.map(b => b.mtime));
    
    // Find best title (prefer heading1/2, fallback to first block's heading)
    const titleBlock = conceptBlocks.find(b => b.type === 'heading1' || b.type === 'heading2');
    const title = titleBlock?.heading || conceptBlocks[0]?.heading || 'Untitled Concept';
    
    // Extract problem (merge from all blocks that have it)
    const problemBlocks = conceptBlocks.filter(b => b.type === 'problem');
    const problem = problemBlocks.length > 0 
      ? problemBlocks.map(b => b.content).join('\n\n')
      : undefined;
    
    // Extract solutions (merge from all blocks)
    const solutionBlocks = conceptBlocks.filter(b => b.type === 'solution');
    const solution = solutionBlocks.length > 0
      ? solutionBlocks.flatMap(b => {
          // Try to extract numbered lists, fallback to full content
          const lines = b.content.split('\n');
          const numbered = lines.filter(l => /^\d+\./.test(l.trim()));
          return numbered.length > 0 ? numbered : [b.content];
        })
      : undefined;
    
    // Extract rationale (merge from all blocks)
    const rationaleBlocks = conceptBlocks.filter(b => b.type === 'rationale');
    const rationale = rationaleBlocks.length > 0
      ? rationaleBlocks.map(b => b.content).join('\n\n')
      : undefined;
    
    // Extract status
    const statusBlock = conceptBlocks.find(b => b.type === 'status');
    let status: DecisionRecord['status'] = 'active';
    if (statusBlock) {
      const statusText = statusBlock.content.toLowerCase();
      if (statusText.includes('deprecated') || statusText.includes('superseded')) {
        status = 'deprecated';
      } else if (statusText.includes('archived') || statusText.includes('legacy')) {
        status = 'archived';
      }
    }
    
    // Build unified content from all blocks
    const content = conceptBlocks
      .map(b => b.content)
      .filter(Boolean)
      .join('\n\n');
    
    // Generate ID from simhash (same concept = same ID)
    const simhash = conceptBlocks[0]?.simhash || '';
    const id = `concept-${simhash.substring(0, 16)}`;
    
    records.push({
      id,
      title,
      problem,
      solution: solution && solution.length > 0 ? solution : undefined,
      rationale,
      supersedes: undefined,
      status,
      timestamp: new Date(earliestMtime).toISOString(),
      provenance: allProvenance,  // ALL files that share this concept
      tags: allTags,
    });
  }
  
  return records;
}

// ============================================================================
// NEW: Temporal Metadata Cascade (content → git → filename → mtime)
// ============================================================================

/**
 * Extract temporal metadata via cascade fallback
 * 1. Content-internal dates (ISO 8601, frontmatter)
 * 2. Git history (if .git exists and file is tracked)
 * 3. Filename patterns (2025-07-04_session.md, 20251119_notes.txt)
 * 4. File mtime (fallback)
 */
function extractTemporalMetadata(content: string, sourcePath: string, mtime: number): TemporalMetadata {
  // 1. Content-internal dates
  const isoDateMatch = content.match(/\b(20\d{2}-\d{2}-\d{2})\b/);
  if (isoDateMatch) {
    return { primary: isoDateMatch[1], fallback_source: 'content' };
  }

  // Frontmatter date
  const frontmatterDateMatch = content.match(/^date:\s*"?(\d{4}-\d{2}-\d{2})"?/m);
  if (frontmatterDateMatch) {
    return { primary: frontmatterDateMatch[1], fallback_source: 'content' };
  }

  // 2. Git history (graceful degradation — skip if git unavailable)
  try {
    // ISSUE-21: sourcePath is interpolated into a shell command below; validate it
    // first so a hostile path cannot inject arbitrary code through the quotes.
    if (!isShellSafePath(sourcePath)) {
      return { primary: new Date(mtime).toISOString().split('T')[0], fallback_source: 'mtime' };
    }
    const gitLog = execSync(`git log -1 --format="%ai" -- "${sourcePath}"`, {
      cwd: path.join(PATHS.INBOX_DIR, '..'),
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 3000,
    });
    const gitDateMatch = gitLog.match(/(\d{4}-\d{2}-\d{2})/);
    if (gitDateMatch) {
      return { primary: gitDateMatch[1], fallback_source: 'git' };
    }
  } catch {
    // Git unavailable or file not tracked — proceed to filename fallback
    StructuredLogger.debug('[Distill] Git log unavailable, proceeding to filename fallback', { sourcePath });
  }

  // 3. Filename patterns
  const fileName = path.basename(sourcePath);
  const fileNameDateMatch = fileName.match(/(\d{4})[-_]?(\d{2})[-_]?(\d{2})/);
  if (fileNameDateMatch) {
    const date = `${fileNameDateMatch[1]}-${fileNameDateMatch[2]}-${fileNameDateMatch[3]}`;
    return { primary: date, fallback_source: 'filename' };
  }

  // 4. File mtime (fallback)
  const mtimeDate = new Date(mtime).toISOString().split('T')[0];
  return { primary: mtimeDate, fallback_source: 'mtime' };
}

// ============================================================================
// NEW: Memory Type Inference
// ============================================================================

/**
 * Infer memory type from content and source path
 */
function inferMemoryType(content: string, sourcePath: string): MemoryType {
  const text = (content + ' ' + sourcePath).toLowerCase();

  // Episodic: time-bound events, meetings, tasks, people
  if (/\b(meeting|call|deadline|today|tomorrow|yesterday|this week|next week)\b/.test(text)) {
    return 'episodic';
  }
  // Check for person names in conversational context
  if (/\b(meeting with|talked to|asked|Carmen|Katie|Caitlin|Dory|Rob)\b/.test(text)) {
    return 'episodic';
  }
  // Check for date-bound work logs
  if (/\b(\d{4}-\d{2}-\d{2}.*said|noted|assigned|agreed)\b/.test(text)) {
    return 'episodic';
  }

  // Procedural: how-to, workflows, code patterns, protocols
  if (/\b(fix|workflow|protocol|step|implement|setup|install|configure|deploy|script)\b/.test(text)) {
    return 'procedural';
  }

  // Metacognitive: self-reflection, learning, strategy
  if (/\b(reflection|learned|realized|strategy|approach|thinking about|should have)\b/.test(text)) {
    return 'metacognitive';
  }

  // Default: semantic (concepts, architecture, decisions)
  return 'semantic';
}

// ============================================================================
// NEW: Semantic Deduplication Across Sources (Enhanced)
// ============================================================================

/**
 * Create a semantic key for grouping related concepts
 * Uses content fingerprint + topic extraction for fuzzy matching
 */
function createSemanticKey(content: string): string {
  // Extract topics from tags and headings
  const topics = extractTags(content).join('_');
  
  // Compute SimHash of normalized content (64-bit)
  const simhash = computeSimHash(content);
  
  // Combine into semantic key: topics + hash prefix for grouping
  return `${topics || 'general'}:${simhash.substring(0, 8)}`;
}

/**
 * Format aggregated content from multiple records
 */
function formatAggregatedContent(records: DecisionRecord[]): string {
  // Merge problem statements (prefer longest/most detailed)
  const problems = records.map(r => r.problem).filter(Boolean);
  const bestProblem = problems.length > 1 
    ? problems.sort((a, b) => (b?.length || 0) - (a?.length || 0))[0]
    : problems[0];

  // Merge solutions with deduplication
  const allSolutions = records.flatMap(r => r.solution || []);
  const uniqueSolutions = Array.from(new Set(allSolutions));

  // Merge rationales
  const rationales = records.map(r => r.rationale).filter(Boolean);
  
  return [
    bestProblem ? `PROBLEM:\n${bestProblem}` : '',
    uniqueSolutions.length > 0 ? `SOLUTION (${records.length} sources):\n` + uniqueSolutions.join('\n') : '',
    rationales.length > 0 ? `RATIONALE:\n${rationales.join('\n\n')}` : ''
  ].filter(Boolean).join('\n\n');
}

/**
 * Calculate aggregate score based on source diversity and content quality
 */
function calculateGroupScore(records: DecisionRecord[]): number {
  // Base score from frequency (more sources = higher confidence)
  const freqScore = Math.min(1.0, records.length / 5);
  
  // Boost for diverse provenance (different files vs same file repeated)
  const uniqueSources = new Set(records.flatMap(r => r.provenance)).size;
  const diversityScore = uniqueSources > 1 ? 0.2 : 0;
  
  return freqScore + diversityScore;
}

/**
 * Generate unified tags from multiple records
 */
function generateTags(records: DecisionRecord[]): string[] {
  return Array.from(
    new Set(records.flatMap(r => r.tags || []))
  );
}

/**
 * Infer memory type from aggregated content
 */
function inferMemoryTypeFromGroup(records: DecisionRecord[]): MemoryType {
  // Use majority vote with fallback to most detailed record
  const types = records.map(r => inferMemoryType(
    [r.problem, ...(r.solution || []), r.rationale].filter(Boolean).join('\n'),
    r.provenance[0] || ''
  ));
  
  // Find mode (most common type)
  const counts = new Map<MemoryType, number>();
  for (const t of types) {
    counts.set(t, (counts.get(t) || 0) + 1);
  }
  
  let bestType: MemoryType = 'semantic';
  let maxCount = 0;
  for (const [type, count] of counts) {
    if (count > maxCount) {
      maxCount = count;
      bestType = type;
    }
  }
  
  return bestType;
}

/**
 * Deduplicate decision records across source files using enhanced semantic aggregation
 */
function deduplicateAcrossSources(
  records: DecisionRecord[],
  similarityThreshold?: number,
): EnrichedDecisionRecord[] {
  const grouped = new Map<string, DecisionRecord[]>();
  
  // Group by semantic key (content fingerprint + topics)
  for (const r of records) {
    const content = [r.problem, ...(r.solution || []), r.rationale].filter(Boolean).join('\n') || r.title;
    const key = createSemanticKey(content);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(r);
  }
  
  // Transform groups into enriched records
  return Array.from(grouped.entries()).map(([key, group]) => {
    // ISSUE-18: filter invalid timestamps before min — a single bad row would make the
    // whole Math.min NaN and crash `new Date(NaN).toISOString()` below. Fall back to now().
    const validTimes = group.map(r => new Date(r.timestamp).getTime()).filter(t => !isNaN(t));
    const earliestMtime = validTimes.length > 0 ? Math.min(...validTimes) : Date.now();
    const allProvenance = Array.from(new Set(group.flatMap(r => r.provenance)));
    
    return {
      id: `agg_${hash(key)}`,
      title: group[0].title, // Keep first record's title as anchor
      problem: formatAggregatedContent(group).split('\n')[1]?.replace('PROBLEM:\n', '') || undefined,
      solution: formatAggregatedContent(group).includes('SOLUTION')
        ? [formatAggregatedContent(group).match(/SOLUTION \([^)]\):\s*(.+)/)?.[1] || ''].filter(Boolean) : undefined,
      rationale: formatAggregatedContent(group).split('\n')[2]?.replace('RATIONALE:\n', '') || undefined,
      supersedes: group.flatMap(r => r.supersedes || []).filter(Boolean),
      status: inferStatusFromGroup(group),
      timestamp: new Date(earliestMtime).toISOString(),
      provenance: allProvenance,
      tags: generateTags(group),
      temporal: extractTemporalMetadata(
        formatAggregatedContent(group),
        group[0].provenance[0] || '',
        earliestMtime
      ),
      memory_type: inferMemoryTypeFromGroup(group),
      frequency: group.length,
      source_files: Array.from(new Set(allProvenance.map(p => path.basename(p)))),
      related_entries: group.length > 1 ? group.map(r => r.id) : undefined,
    };
  });
}

/**
 * Hash helper for semantic keys
 */
function hash(str: string): string {
  return crypto.createHash('sha256').update(str).digest('hex').substring(0, 16);
}

/**
 * Infer status from aggregated records (prefer deprecated/archived over active)
 */
function inferStatusFromGroup(records: DecisionRecord[]): 'active' | 'deprecated' | 'archived' {
  if (records.some(r => r.status === 'archived')) return 'archived';
  if (records.some(r => r.status === 'deprecated')) return 'deprecated';
  return 'active';
}

// ============================================================================
// NEW: Nested YAML v2 Emitter
// ============================================================================

/**
 * Emit nested YAML v2 format grouped by source → temporal → semantic
 */
function emitNestedYaml(
  enrichedRecords: EnrichedDecisionRecord[],
  stats: RadialDistillResult['stats'],
): string {
  // Group by source file
  const bySource = new Map<string, EnrichedDecisionRecord[]>();
  for (const rec of enrichedRecords) {
    const sourceFile = rec.source_files?.[0] || path.basename(rec.provenance[0] || 'unknown');
    if (!bySource.has(sourceFile)) bySource.set(sourceFile, []);
    bySource.get(sourceFile)!.push(rec);
  }

  const yamlObj = {
    version: '2.0',
    generated_at: new Date().toISOString(),
    summary: {
      compression_ratio: stats.compression_ratio,
      blocks_total: stats.blocks_total,
      blocks_unique: stats.blocks_unique,
      distilled_entries: enrichedRecords.length,
      duration_ms: stats.duration_ms,
    },
    sources: Array.from(bySource.entries()).map(([sourceFile, records]) => ({
      file: sourceFile,
      temporal_hint: records[0]?.temporal?.primary || 'unknown',
      entries: records.map(rec => ({
        id: rec.id,
        title: rec.title,
        frequency: rec.frequency || 1,
        source_files: rec.source_files || [],
        content: [
          rec.problem ? `Problem: ${rec.problem}` : '',
          rec.solution?.length ? `Solution:\n${rec.solution.join('\n')}` : '',
          rec.rationale ? `Why: ${rec.rationale}` : '',
        ].filter(Boolean).join('\n\n') || rec.title,
        score: 1.0,
        tags: rec.tags,
        memory_type: rec.memory_type,
        temporal: rec.temporal,
      })),
    })),
  };

  return yaml.dump(yamlObj, { lineWidth: -1, noRefs: true });
}

// ============================================================================
// NEW: JSON-Full Emitter (full content preservation)
// ============================================================================

/**
 * Emit JSON with full inflated content from tag-based mode
 */
function emitJsonFull(
  enrichedRecords: EnrichedDecisionRecord[],
  inflatedContent: { content: string; source: string; tags: string[]; timestamp: number; }[],
  stats: RadialDistillResult['stats'],
): Record<string, unknown> {
  return {
    version: '2.0',
    generated_at: new Date().toISOString(),
    summary: {
      compression_ratio: stats.compression_ratio,
      blocks_total: stats.blocks_total,
      blocks_unique: stats.blocks_unique,
      distilled_entries: enrichedRecords.length,
      full_content_entries: inflatedContent.length,
      duration_ms: stats.duration_ms,
    },
    records: enrichedRecords,
    inflated_content: inflatedContent.map(item => ({
      source: item.source,
      tags: item.tags,
      timestamp: new Date(item.timestamp).toISOString(),
      content: item.content,
    })),
  };
}

/**
 * Extract digital object metadata from a compound
 * Works for any file type, with special handling for chat JSONL files
 */
function extractDigitalObjectMetadata(
  compound: any,
  content: string,
  mtime: number,
  ingestedAt: string,
): DigitalObjectMetadata | null {
  // Rows may be molecule rows (source_path / compound_id) or legacy atom
  // rows (path / id). The compounds table was removed (Standard 051), so
  // molecule rows are the common case — resolve both field spellings.
  const resolvedPath: string | undefined = compound.path || compound.source_path;
  if (!resolvedPath) return null;
  const resolvedId: string | undefined = compound.id || compound.compound_id;

  const pathExt = path.extname(resolvedPath).toLowerCase();
  const sourceType = pathExt.slice(1) || 'unknown';
  
  // Base metadata (always present)
  const metadata: DigitalObjectMetadata = {
    id: crypto.createHash('sha256').update(resolvedPath).digest('hex').substring(0, 16),
    source_path: resolvedPath,
    source_type: sourceType,
    modified_at: new Date(mtime).toISOString(),
    ingested_at: ingestedAt,
    bucket: compound.provenance || 'unknown',
    compound_id: resolvedId || '',
    size_bytes: Buffer.byteLength(content, 'utf-8'),
    line_count: content.split('\n').length,
    char_count: content.length,
    topics: [],
    entities: [],
    tags: [],
  };
  
  // Extract topics from content (simple keyword extraction)
  const topicKeywords = content.match(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g) || [];
  metadata.topics = Array.from(new Set(topicKeywords.slice(0, 10)));
  
  // Extract tags (hashtag pattern)
  const tagMatches = content.match(/#(\w+)/g) || [];
  metadata.tags = Array.from(new Set(tagMatches.map(t => t.slice(1).toLowerCase())));
  
  return metadata;
}

/**
 * Extract chat session metadata from JSONL content
 * Returns ChatSessionMetadata if valid chat session, null otherwise
 */
function extractChatSessionMetadata(
  baseMetadata: DigitalObjectMetadata,
  content: string,
  compound: any,
): ChatSessionMetadata | null {
  // Only process JSONL files from inbox
  if (baseMetadata.source_type !== 'jsonl' || !baseMetadata.bucket.includes('inbox')) {
    return null;
  }
  
  // Extract session_id from filename (UUID pattern).
  // Use the resolved source_path (baseMetadata) — molecule rows carry source_path,
  // not compound.path (compounds table removed, Standard 051).
  const filename = path.basename(baseMetadata.source_path, '.jsonl');
  const sessionUuidMatch = filename.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
  if (!sessionUuidMatch) {
    return null;
  }
  
  const lines = content.split('\n').filter(line => line.trim());
  if (lines.length === 0) {
    return null;
  }
  
  // Parse messages
  const messages: any[] = [];
  const commands: string[] = [];
  const participants = new Set<string>();
  const modelsUsed = new Set<string>();
  let firstTimestamp: string | null = null;
  let lastTimestamp: string | null = null;
  
  for (const line of lines) {
    try {
      const msg = JSON.parse(line);
      messages.push(msg);
      
      // Track timestamps
      if (msg.timestamp) {
        if (!firstTimestamp) firstTimestamp = msg.timestamp;
        lastTimestamp = msg.timestamp;
      }
      
      // Track participants
      if (msg.type) participants.add(msg.type);
      if (msg.role) participants.add(msg.role);
      
      // Track commands
      if (msg.subtype === 'slash_command' && msg.systemPayload?.rawCommand) {
        const cmd = msg.systemPayload.rawCommand;
        if (!commands.includes(cmd)) {
          commands.push(cmd);
        }
      }
      
      // Track models
      if (msg.model) {
        modelsUsed.add(msg.model);
      }
    } catch {
      // Skip malformed lines
    }
  }
  
  return {
    ...baseMetadata,
    session_id: filename,
    session_start: firstTimestamp || baseMetadata.modified_at,
    session_end: lastTimestamp || baseMetadata.modified_at,
    commands,
    message_count: messages.length,
    participants: Array.from(participants),
    models_used: Array.from(modelsUsed),
  };
}

/**
 * Build session index from chat session metadata
 */
function buildSessionIndex(chatSessions: ChatSessionMetadata[]): SessionIndexEntry[] {
  return chatSessions.map(session => ({
    session_id: session.session_id,
    date: session.session_start,
    commands: session.commands,
    topics: session.topics || [],
    full_log_path: session.source_path,
    message_count: session.message_count,
    participants: session.participants,
  }));
}

/**
 * Fetch all unique tags from the database
 */
export async function fetchAllTags(): Promise<string[]> {
  try {
    // Source A: tags junction table
    const tagsTableResult = await db.run('SELECT DISTINCT tag FROM tags WHERE tag IS NOT NULL ORDER BY tag');
    const tagsTableCount = tagsTableResult.rows?.length || 0;

    // Source B: atoms.tags[] array (TEXT[])
    const atomsTagsResult = await db.run('SELECT DISTINCT UNNEST(tags) as tag FROM atoms WHERE tags IS NOT NULL AND tags != \'{}\' ORDER BY tag');
    const atomsTagsCount = atomsTagsResult.rows?.length || 0;

    // Legacy A/B test logging (can be enabled via LOG_LEVEL for debugging)
    if (config.LOG_LEVEL === 'debug') {
      console.log(`[A/B Test][fetchAllTags] Source A (tags table): ${tagsTableCount} | Source B (atoms.tags[]): ${atomsTagsCount}`);
    }

    // Use whichever source has data (prefer atoms.tags[] as primary)
    if (atomsTagsCount > 0) {
      const allTags = new Set<string>();
      if (atomsTagsResult.rows) {
        for (const row of atomsTagsResult.rows) {
          if (row.tag) allTags.add(row.tag as string);
        }
      }
      return [...allTags].sort();
    }

    // Fallback to tags table
    if (tagsTableCount > 0) {
      const allTags = new Set<string>();
      if (tagsTableResult.rows) {
        for (const row of tagsTableResult.rows) {
          if (row.tag) allTags.add(row.tag as string);
        }
      }
      return [...allTags].sort();
    }

    return [];
  } catch (error) {
    console.error('[fetchAllTags] Error:', error);
    return [];
  }
}

/**
 * Fetch all atoms for a specific tag with full content
 */
export async function fetchAtomsByTag(tag: string): Promise<any[]> {
  try {
    // Source A: tags junction table
    const tagsTableResult = await db.run(
      'SELECT atom_id FROM tags WHERE tag = $1',
      [tag]
    );
    const tagsTableCount = tagsTableResult.rows?.length || 0;

    // Source B: atoms.tags[] array containment
    const atomsTagsResult = await db.run(
      'SELECT id FROM atoms WHERE $1 = ANY(tags)',
      [tag]
    );
    const atomsTagsCount = atomsTagsResult.rows?.length || 0;

    // Legacy A/B test logging (sample every 10th call to reduce noise)
    if (config.LOG_LEVEL === 'debug' && Math.random() < 0.1) {
      console.log(`[A/B Test][fetchAtomsByTag][${tag}] Source A (tags table): ${tagsTableCount} | Source B (atoms.tags[]): ${atomsTagsCount}`);
    }

    // Collect atom IDs from both sources
    const atomIds = new Set<string>();

    if (tagsTableResult.rows) {
      for (const row of tagsTableResult.rows) {
        if (row.atom_id) atomIds.add(row.atom_id);
      }
    }

    if (atomsTagsResult.rows) {
      for (const row of atomsTagsResult.rows) {
        if (row.id) atomIds.add(row.id);
      }
    }

    if (atomIds.size === 0) {
      return [];
    }

    // Fetch atoms with their content - use 'buckets' (plural) not 'bucket'
    const atomsResult = await db.run(
      'SELECT id, content, source_path, tags, buckets, provenance FROM atoms WHERE id = ANY($1)',
      [Array.from(atomIds)]
    );

    return atomsResult.rows || [];
  } catch (error) {
    console.error(`[fetchAtomsByTag] Error for tag ${tag}:`, error);
    return [];
  }
}

/**
 * Distillation metrics tracking
 */
interface DistillationMetrics {
  totalAtoms: number;
  successfulReads: number;
  provenanceMismatches: number;
  fallbackReads: number;
  failedReads: number;
  skippedByContent: number;
}

/**
 * Tag-based distillation mode
 * Iterates through all tags, fetches all content for each tag, and deduplicates
 * Uses ContextInflator.inflate() to get full atom content (like v5.0.0)
 */
async function tagBasedDistill(request: RadialDistillRequest): Promise<{
  blocks: SemanticBlock[];
  digitalObjects: DigitalObjectMetadata[];
  compoundsProcessed: number;
  inflatedContent: { content: string; source: string; tags: string[]; timestamp: number; }[];
  metrics: DistillationMetrics;
}> {
  const allBlocks: SemanticBlock[] = [];
  const digitalObjects: DigitalObjectMetadata[] = [];
  const inflatedContent: { content: string; source: string; tags: string[]; timestamp: number; }[] = [];
  let compoundsProcessed = 0;
  const ingestedAt = new Date().toISOString();

  // Initialize metrics tracking
  const metrics: DistillationMetrics = {
    totalAtoms: 0,
    successfulReads: 0,
    provenanceMismatches: 0,
    fallbackReads: 0,
    failedReads: 0,
    skippedByContent: 0,
  };

  // Get tags to process (all tags or specified subset)
  let tagsToProcess = request.seed?.tags;

  if (!tagsToProcess || tagsToProcess.length === 0) {
    // Fetch all tags if not specified
    tagsToProcess = await fetchAllTags();
    StructuredLogger.info('[TagBasedDistill] Processing all tags', { count: tagsToProcess.length });
  } else {
    StructuredLogger.info('[TagBasedDistill] Processing specified tags', { count: tagsToProcess.length });
  }

  // Track processed atoms to avoid duplicates across tags
  const processedAtomIds = new Set<string>();

  // Process each tag
  for (const tag of tagsToProcess) {
    const atoms = await fetchAtomsByTag(tag);

    for (const atom of atoms) {
      // Skip if already processed (dedup across tags)
      if (processedAtomIds.has(atom.id)) {
        continue;
      }
      processedAtomIds.add(atom.id);

      metrics.totalAtoms++;

      // Skip distillation outputs
      if (isDistillationOutput(atom.source_path)) {
        continue;
      }

      compoundsProcessed++;

      // Get content from mirrored_brain filesystem (Standard 051 - Pointer Only)
      // This is the v5.0.0 approach that works reliably
      let content = '';

      // Normalize provenance for getMirrorPath - prefer provenance field over bucket
      let prov: 'internal' | 'external' | 'quarantine' = 'internal';
      if (atom.provenance) {
        const provStr = String(atom.provenance).toLowerCase();
        if (provStr === 'internal' || provStr.includes('internal')) {
          prov = 'internal';
        } else if (provStr === 'quarantine') {
          prov = 'quarantine';
        } else if (provStr === 'external' || !provStr) {
          prov = 'external';
        }
      } else {
        // Fallback to bucket if provenance not available
        const bucketStr = String(atom.bucket || '').toLowerCase();
        if (bucketStr === 'quarantine') {
          prov = 'quarantine';
        } else if (bucketStr === 'external' || !bucketStr) {
          prov = 'external';
        }
      }

      const sourcePath = atom.source_path || '';

      // Handle GitHub URL format: github:user/repo/path/to/file.md
      // These are URLs, not filesystem paths - skip them for local distillation
      if (sourcePath.startsWith('github:')) {
        console.warn(`[TagBasedDistill] Skipping GitHub URL: ${sourcePath}`);
        metrics.failedReads++;
        continue;
      }

      // Build fallback attempts list with provenance tracking
      const attempts: Array<{ name: string; path: string; isFallback: boolean }> = [
        { name: `Mirrored (${prov})`, path: getMirrorPath(sourcePath, prov), isFallback: false },
      ];

      // Add fallback attempts for other provenance types
      if (prov !== 'internal') {
        attempts.push({ name: 'Mirrored (internal)', path: getMirrorPath(sourcePath, 'internal'), isFallback: true });
      }
      if (prov !== 'external') {
        attempts.push({ name: 'Mirrored (external)', path: getMirrorPath(sourcePath, 'external'), isFallback: true });
      }
      if (prov !== 'quarantine') {
        attempts.push({ name: 'Mirrored (quarantine)', path: getMirrorPath(sourcePath, 'quarantine'), isFallback: true });
      }

      // Try original source_path if it's a valid filesystem path
      if (path.isAbsolute(sourcePath) || sourcePath.includes('\\') || sourcePath.includes('/')) {
        attempts.push({ name: 'Original path', path: sourcePath, isFallback: true });
      }

      // Try notebook directory with relative path
      const notebookDir = path.join(PATHS.FALLBACK_DATA_DIR, 'notebook');
      const localPath = path.join(notebookDir, sourcePath);
      attempts.push({ name: 'Notebook path', path: localPath, isFallback: true });

      // Attempt to read content from each location
      let foundAtPath = '';
      let usedFallback = false;

      for (const attempt of attempts) {
        if (fs.existsSync(attempt.path)) {
          try {
            content = fs.readFileSync(attempt.path, 'utf-8');
            foundAtPath = attempt.name;
            usedFallback = attempt.isFallback;
            
            if (attempt.isFallback) {
              metrics.fallbackReads++;
              StructuredLogger.info('[TagBasedDistill] Using fallback path', {
                atomId: atom.id,
                tag: tag,
                expected: prov,
                found: attempt.name,
              });
            }
            break;
          } catch (err: any) {
            console.warn(`[TagBasedDistill] Failed to read ${attempt.name}: ${err.message}`);
          }
        }
      }

      // Track provenance mismatch if fallback was used
      if (usedFallback && foundAtPath !== `Mirrored (${prov})`) {
        metrics.provenanceMismatches++;
        StructuredLogger.warn('[TagBasedDistill] Provenance mismatch detected', {
          atomId: atom.id,
          tag: tag,
          expected: prov,
          found: foundAtPath,
        });
      }

      // Skip if no content found
      if (!content || content.trim() === '') {
        console.warn(`[TagBasedDistill] No content found for atom ${atom.id} at ${sourcePath}`);
        metrics.failedReads++;
        continue;
      }

      metrics.successfulReads++;

      // Add to inflated content
      inflatedContent.push({
        content,
        source: atom.source_path || `atom:${atom.id}`,
        tags: atom.tags || [],
        timestamp: atom.timestamp || Date.now()
      });

      // Extract semantic blocks
      const mtime = atom.timestamp || Date.now();
      const blocks = extractSemanticBlocks(content, atom.source_path || `atom:${atom.id}`, mtime);

      for (const block of blocks) {
        if (!block.tags) block.tags = [];
        if (!block.tags.includes(tag)) {
          block.tags.push(tag);
        }
      }

      allBlocks.push(...blocks);

      // Extract digital object metadata
      const baseMetadata = extractDigitalObjectMetadata(
        { id: atom.id, path: atom.source_path, provenance: atom.bucket },
        content,
        mtime,
        ingestedAt
      );
      if (baseMetadata) {
        digitalObjects.push(baseMetadata);
      }
    }
  }

  return {
    blocks: allBlocks,
    digitalObjects,
    compoundsProcessed,
    inflatedContent,
    metrics,
  };
}

/**
 * Finalize distillation - common pipeline for both standard and tag-based modes
 */
async function finalizeDistillation(
  request: RadialDistillRequest,
  allBlocks: SemanticBlock[],
  digitalObjects: DigitalObjectMetadata[],
  chatSessions: ChatSessionMetadata[],
  compoundsProcessed: number,
  startTime: number,
  ingestedAt: string,
  inflatedContent?: { content: string; source: string; tags: string[]; timestamp: number; }[],
  distillationMetrics?: DistillationMetrics,
): Promise<RadialDistillResult> {
  // Build session index from chat sessions
  const sessionIndex = buildSessionIndex(chatSessions);

  // Phase 2: DEDUPLICATE - Block-level deduplication
  const uniqueBlocks = deduplicateBlocks(allBlocks);

  // Phase 3: REASSEMBLE - Build Decision Records
  const decisionRecords = assembleDecisionRecords(uniqueBlocks);

  // Phase 3.5: SEMANTIC DEDUPLICATION (NEW) - Cross-source aggregation
  const similarityThreshold = request.similarity_threshold ?? config.DISTILLER.SIMILARITY_THRESHOLD ?? 0.85;
  const enrichedRecords = deduplicateAcrossSources(decisionRecords, similarityThreshold);

  StructuredLogger.info('DISTILL_AGGREGATION', {
    before: decisionRecords.length,
    after: enrichedRecords.length,
    reduction: `${((1 - enrichedRecords.length / Math.max(1, decisionRecords.length)) * 100).toFixed(1)}%`,
    similarity_threshold: similarityThreshold,
  });

  // Dry-run mode: return preview without writing
  if (request.dry_run) {
    StructuredLogger.info('DISTILL_DRY_RUN', { records: enrichedRecords.length });
    return {
      stats: {
        compounds_processed: compoundsProcessed,
        blocks_total: allBlocks.length,
        blocks_unique: uniqueBlocks.length,
        decision_records: enrichedRecords.length,
        compression_ratio: `${(allBlocks.length / Math.max(1, enrichedRecords.length)).toFixed(1)}:1`,
        duration_ms: Date.now() - startTime,
        memory_peak_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
      },
      output: {
        format: request.output_format || 'decision-records',
        size_bytes: 0,
        records_created: enrichedRecords.length,
      },
      provenance: {
        source_compounds: digitalObjects.map(d => d.source_path),
        distilled_at: new Date().toISOString(),
        parameters: request,
      },
      records: enrichedRecords as DecisionRecord[],
      digital_objects: digitalObjects,
      session_index: sessionIndex,
      inflated_content: inflatedContent || [],
      enriched_records: enrichedRecords,
      metrics: distillationMetrics || { totalAtoms: 0, successfulReads: 0, provenanceMismatches: 0, fallbackReads: 0, failedReads: 0, skippedByContent: 0 },
    };
  }

  // Generate output
  const outputFormat = request.output_format || 'decision-records';
  let outputPath: string | undefined;
  let outputSize = 0;

  // Determine if we should save to file
  const shouldSaveToFile = request.output_path || request.auto_save;

  if (outputFormat === 'nested-yaml') {
    // NEW: Nested YAML v2 format
    const yamlOutput = emitNestedYaml(enrichedRecords, {
      compounds_processed: compoundsProcessed,
      blocks_total: allBlocks.length,
      blocks_unique: uniqueBlocks.length,
      decision_records: enrichedRecords.length,
      compression_ratio: `${(allBlocks.length / Math.max(1, enrichedRecords.length)).toFixed(1)}:1`,
      duration_ms: Date.now() - startTime,
      memory_peak_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
    });
    outputSize = yamlOutput.length;

    if (shouldSaveToFile) {
      const distillsDir = path.join(PATHS.DISTILLS_DIR);
      if (!fs.existsSync(distillsDir)) fs.mkdirSync(distillsDir, { recursive: true });
      const outputPath = path.join(
        distillsDir,
        `distilled_nested_${new Date().toISOString().replace(/[:.]/g, '-')}.yaml`,
      );
      fs.writeFileSync(outputPath, yamlOutput);
    }
  } else if (outputFormat === 'json-full') {
    // NEW: JSON with full inflated content
    const jsonFullOutput = emitJsonFull(enrichedRecords, inflatedContent || [], {
      compounds_processed: compoundsProcessed,
      blocks_total: allBlocks.length,
      blocks_unique: uniqueBlocks.length,
      decision_records: enrichedRecords.length,
      compression_ratio: `${(allBlocks.length / Math.max(1, enrichedRecords.length)).toFixed(1)}:1`,
      duration_ms: Date.now() - startTime,
      memory_peak_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
    });
    const jsonOutput = JSON.stringify(jsonFullOutput, null, 2);
    outputSize = jsonOutput.length;

    if (shouldSaveToFile) {
      const distillsDir = path.join(PATHS.DISTILLS_DIR);
      if (!fs.existsSync(distillsDir)) fs.mkdirSync(distillsDir, { recursive: true });
      const outputPath = path.join(
        distillsDir,
        `distilled_full_${new Date().toISOString().replace(/[:.]/g, '-')}.json`,
      );
      fs.writeFileSync(outputPath, jsonOutput);
    }
  } else if (outputFormat === 'json' || outputFormat === 'decision-records') {
    // Include digital objects and session index in JSON output
    const fullOutput = {
      metadata: {
        source: 'Anchor Engine Radial Distiller v2.0',
        distilled_at: new Date().toISOString(),
        decision_records: enrichedRecords.length,
        digital_objects_count: digitalObjects.length,
        session_index_count: sessionIndex.length,
      },
      records: enrichedRecords,
      digital_objects: digitalObjects,
      session_index: sessionIndex,
    };
    const jsonOutput = JSON.stringify(fullOutput, null, 2);
    outputSize = jsonOutput.length;

    if (shouldSaveToFile) {
      const distillsDir = path.join(PATHS.DISTILLS_DIR);
      if (!fs.existsSync(distillsDir)) fs.mkdirSync(distillsDir, { recursive: true });
      const outputPath = path.join(
        distillsDir,
        `distilled_standards_${new Date().toISOString().replace(/[:.]/g, '-')}.json`,
      );
      fs.writeFileSync(outputPath, jsonOutput);
    }
  } else if (outputFormat === 'yaml') {
    // Backward compatibility - legacy YAML format
    const yamlOutput = yaml.dump({
      metadata: {
        source: 'Anchor Engine Radial Distiller v2.0',
        distilled_at: new Date().toISOString(),
        decision_records: enrichedRecords.length,
        digital_objects_count: digitalObjects.length,
        session_index_count: sessionIndex.length,
      },
      records: enrichedRecords,
      digital_objects: digitalObjects,
      session_index: sessionIndex,
    });

    outputSize = yamlOutput.length;

    if (shouldSaveToFile) {
      const distillsDir = path.join(PATHS.DISTILLS_DIR);
      if (!fs.existsSync(distillsDir)) fs.mkdirSync(distillsDir, { recursive: true });
      const outputPath = path.join(
        distillsDir,
        `distilled_${new Date().toISOString().replace(/[:.]/g, '-')}.yaml`,
      );
      fs.writeFileSync(outputPath, yamlOutput);
    }
  }

  const duration = Date.now() - startTime;

  const result: RadialDistillResult = {
    stats: {
      compounds_processed: compoundsProcessed,
      blocks_total: allBlocks.length,
      blocks_unique: uniqueBlocks.length,
      decision_records: enrichedRecords.length,
      compression_ratio: `${(allBlocks.length / Math.max(1, enrichedRecords.length)).toFixed(1)}:1`,
      duration_ms: duration,
      memory_peak_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
    },
    output: {
      format: outputFormat,
      path: outputPath,
      size_bytes: outputSize,
      records_created: enrichedRecords.length,
    },
    provenance: {
      source_compounds: digitalObjects.map(d => d.source_path),
      distilled_at: new Date().toISOString(),
      parameters: request,
    },
    // Return enriched decision records with temporal and memory type metadata
    records: enrichedRecords as DecisionRecord[],
    // Digital object metadata for all processed compounds
    digital_objects: digitalObjects,
    // Session index for chat sessions
    session_index: sessionIndex,
    // Inflated content for tag-based mode (full atom content)
    inflated_content: inflatedContent || [],
    // NEW: Enriched records with full metadata
    enriched_records: enrichedRecords,
  };

  StructuredLogger.info('RADIAL_DISTILL_V2_COMPLETE', {
    records: result.stats.decision_records,
    compression: result.stats.compression_ratio,
    aggregation_reduction: `${((1 - enrichedRecords.length / Math.max(1, decisionRecords.length)) * 100).toFixed(1)}%`,
    duration_ms: duration,
  });

  // Standard 016: Record distill in database with pointers to file
  try {
    if (outputPath) {
      const sourceSessions = sessionIndex.map((s: any) => s.session_id || s.id).filter(Boolean);
      const sourceFiles = digitalObjects.map(d => d.source_path);

      await recordDistill({
        timestamp: new Date().toISOString(),
        filename: path.basename(outputPath),
        file_path: outputPath,
        line_count: allBlocks.length,
        lines_unique: uniqueBlocks.length,
        compression_ratio: parseFloat(result.stats.compression_ratio.replace(':1', '')),
        source_sessions: sourceSessions,
        source_files: sourceFiles,
        parameters: {
          radius: request.radius,
          output_format: outputFormat,
          decision_records: enrichedRecords.length,
          digital_objects: digitalObjects.length,
          session_index: sessionIndex.length,
        },
      });
      console.log('[Distill] ✅ Distill recorded in database');
    }
  } catch (dbError: any) {
    console.warn('[Distill] Could not record distill in database:', dbError.message);
    // Don't fail the distill if DB recording fails
  }

  return result;
}

/**
 * Read a bounded byte range from a mirrored file (pointer-based inflation).
 * Content lives at its pointer location on disk — never in the DB. Returns
 * { content:'', inflated:false } when the mirror file is missing or unreadable.
 */
function readRangeFromMirror(
  sourcePath: string,
  provenance: string | undefined,
  startByte: number,
  endByte: number,
  radius: number,
  maxBytes: number,
): { content: string; inflated: boolean } {
  try {
    const mirrorPath = getMirrorPath(sourcePath, provenance || 'internal');
    if (!fs.existsSync(mirrorPath)) return { content: '', inflated: false };
    const fileSize = fs.statSync(mirrorPath).size;
    const start = Math.max(0, (startByte ?? 0) - radius);
    const rawEnd = Math.min(fileSize, (endByte ?? startByte ?? 0) + radius);
    if (rawEnd <= start) return { content: '', inflated: false };
    const readLength = Math.min(rawEnd - start, maxBytes);
    const buffer = Buffer.alloc(readLength);
    const fd = fs.openSync(mirrorPath, 'r');
    try {
      fs.readSync(fd, buffer, 0, readLength, start);
    } finally {
      fs.closeSync(fd);
    }
    return { content: buffer.toString('utf-8'), inflated: true };
  } catch (e) {
    console.warn(`[FullCorpusDistill] Range read failed for ${sourcePath}:`, e);
    return { content: '', inflated: false };
  }
}

/** A single pointer into a mirrored source file (Standard 051). */
interface Occurrence {
  source_path: string;
  start_byte: number;
  end_byte: number;
}

/**
 * Find the widest real occurrence of a record — the one Pass 2 actually reads
 * from. The record's own start_byte/end_byte is often a compound-level (0,0)
 * marker, so the widest occurrence in occurrences[] points at the true atom
 * range. Returns { occ: null, span: 0 } when there are no real byte ranges.
 */
function widestOccurrence(rec: FullCorpusRecord): { occ: Occurrence | null; span: number } {
  if (!rec.occurrences || rec.occurrences.length === 0) return { occ: null, span: 0 };
  let best = rec.occurrences[0];
  let bestSpan = Math.max(0, best.end_byte - best.start_byte);
  for (const o of rec.occurrences) {
    const span = Math.max(0, o.end_byte - o.start_byte);
    if (span > bestSpan) { bestSpan = span; best = o; }
  }
  return { occ: best, span: bestSpan };
}

/** The source file a record's content is read from (widest occurrence). */
function readFileFor(rec: FullCorpusRecord): string {
  const { occ } = widestOccurrence(rec);
  return (occ && occ.source_path) || rec.source_path;
}

/** A single unique atom record streamed to the full-corpus distill JSONL. */
interface FullCorpusRecord {
  id: string;
  type: string;
  content: string;
  source_path: string;
  start_byte: number;
  end_byte: number;
  compound_id?: string;
  provenance?: string;
  timestamp?: number;
  molecular_signature?: string;
  occurrences: Occurrence[];
  content_inflated: boolean;
}

/**
 * Full-corpus distillation — seedless mode.
 *
 * Expands and dedups EVERY unique atom in the corpus and streams them to a
 * JSONL file under PATHS.DISTILLS_DIR. Pointer-driven by design (Standard 051):
 *   Pass 1: keyset-paginate atoms (pointers only — content is never read from
 *           the DB), dedup by molecular_signature → simhash → id, merging
 *           duplicate pointers into occurrences[].
 *   Pass 2: for each unique atom, inflate a bounded byte range around its
 *           primary pointer from the mirrored file on disk and stream one
 *           JSONL line per record. Memory stays flat regardless of corpus size;
 *           the HTTP response carries only counts + output.path (never records).
 */
export async function radialDistillFullCorpus(request: RadialDistillRequest): Promise<RadialDistillResult> {
  const startTime = Date.now();
  const pageSize = Math.max(50, request.page_size ?? 500);
  const radius = Math.min(Math.max(0, request.inflate_radius ?? 500), 1000);
  const maxRecordBytes = Math.max(256, request.max_record_bytes ?? 8192);

  StructuredLogger.info('FULL_CORPUS_DISTILL_START', { page_size: pageSize, inflate_radius: radius, max_record_bytes: maxRecordBytes });

  const unique = new Map<string, FullCorpusRecord>();
  const uniqueOrder: string[] = [];
  const filesSeen = new Set<string>();
  let totalAtoms = 0;

  // ---- Pass 1: enumerate (pointers only) + dedup -------------------------
  try {
    let lastId = '';
    for (;;) {
      const res = await db.run(
        `SELECT id, compound_id, source_path, start_byte, end_byte, timestamp, type, molecular_signature, simhash, provenance
         FROM atoms WHERE id > $1 ORDER BY id LIMIT $2`,
        [lastId, pageSize],
      );
      const rows: any[] = res.rows || [];
      if (rows.length === 0) break;

      for (const row of rows) {
        totalAtoms++;
        lastId = row.id as string;
        const sourcePath = (row.source_path as string) || '';
        if (!sourcePath) continue; // pointerless atom — nothing to distill
        filesSeen.add(sourcePath);

        const sb = (row.start_byte as number) ?? 0;
        const eb = (row.end_byte as number) ?? 0;
        const key: string = (row.molecular_signature as string) || (row.simhash as string) || `id:${row.id}`;
        let rec = unique.get(key);
        if (!rec) {
          rec = {
            id: row.id as string,
            type: (row.type as string) || 'content',
            content: '', // inflated in pass 2 from the pointer location on disk
            source_path: sourcePath,
            start_byte: sb,
            end_byte: eb,
            compound_id: row.compound_id as string | undefined,
            provenance: row.provenance as string | undefined,
            timestamp: row.timestamp as number | undefined,
            molecular_signature: (row.molecular_signature as string) || undefined,
            occurrences: [],
            content_inflated: false,
          };
          unique.set(key, rec);
          uniqueOrder.push(key);
        }
        // Collect EVERY pointer (including the group's first row) so Pass 2 can
        // inflate from the widest real range. The first row is often a
        // compound-level atom at (0,0); the true atom byte ranges live here.
        const occ: Occurrence = { source_path: sourcePath, start_byte: sb, end_byte: eb };
        if (!rec.occurrences.some(o => o.source_path === occ.source_path && o.start_byte === occ.start_byte)) {
          rec.occurrences.push(occ);
        }
      }

      // Yield to the event loop between pages (keeps the API responsive).
      await new Promise(r => setImmediate(r));
    }
  } catch (error: any) {
    StructuredLogger.error('FULL_CORPUS_DISTILL_PASS1_ERROR', error);
    throw error;
  }

  // ---- Pass 2: inflate from pointer locations on disk + stream JSONL -----
  const distillsDir = PATHS.DISTILLS_DIR;
  if (!fs.existsSync(distillsDir)) fs.mkdirSync(distillsDir, { recursive: true });
  const outputPath = path.join(
    distillsDir,
    `distilled_fullcorpus_${new Date().toISOString().replace(/[:.]/g, '-')}.jsonl`,
  );

  let sizeBytes = 0;
  let inflatedCount = 0;
  let streamError: any = null;

  // Group records by source file so records from the same file stream
  // contiguously (Standard 051 locality). We only reorder string keys — build a
  // sorted index array keyed by (readFileFor, start_byte) and stream in that
  // order. Content windows are still read one bounded window at a time, so
  // memory stays flat regardless of corpus size; this is purely a reordering of
  // the existing uniqueOrder keys, not an accumulation of content.
  const groupOrder = uniqueOrder.slice().sort((a, b) => {
    const ra = readFileFor(unique.get(a)!);
    const rb = readFileFor(unique.get(b)!);
    if (ra !== rb) return ra < rb ? -1 : 1;
    const sa = widestOccurrence(unique.get(a)!).span || unique.get(a)!.start_byte;
    const sb = widestOccurrence(unique.get(b)!).span || unique.get(b)!.start_byte;
    return sa - sb;
  });

  await new Promise<void>((resolve) => {
    const out = fs.createWriteStream(outputPath);
    let i = 0;

    const writeNext = () => {
      if (streamError) return resolve();
      while (i < groupOrder.length) {
        const rec = unique.get(groupOrder[i])!;
        i++;
        // Inflate a bounded range from disk. Prefer the WIDEST real pointer in
        // occurrences[] — the record's own start_byte/end_byte is often a
        // compound-level (0,0) marker, so it would inflate the wrong region on
        // large files. Fall back to the record pointer when no real range exists.
        const { occ } = widestOccurrence(rec);
        const inflStart = (occ && occ.start_byte > 0) ? occ.start_byte : rec.start_byte;
        const inflEnd = (occ && occ.end_byte > 0) ? occ.end_byte : rec.end_byte;
        const { content, inflated } = readRangeFromMirror(
          rec.source_path, rec.provenance, inflStart, inflEnd, radius, maxRecordBytes,
        );
        rec.content = content;
        rec.content_inflated = inflated && content.length > 0;
        if (rec.content_inflated) inflatedCount++;

        const line = JSON.stringify(rec) + '\n';
        sizeBytes += Buffer.byteLength(line, 'utf-8');
        const ok = out.write(line);
        if (!ok) {
          // Backpressure: wait for drain before continuing.
          out.once('drain', writeNext);
          return;
        }
      }
      out.end(() => resolve());
    };

    out.on('error', (err) => { streamError = err; try { out.destroy(); } catch {} resolve(); });
    writeNext();
  });

  if (streamError) {
    StructuredLogger.error('FULL_CORPUS_DISTILL_STREAM_ERROR', streamError);
    throw streamError;
  }

  const duration = Date.now() - startTime;
  const uniqueCount = uniqueOrder.length;

  // Standard 016: record the distill checkpoint (pointer to the file).
  try {
    await recordDistill({
      timestamp: new Date().toISOString(),
      filename: path.basename(outputPath),
      file_path: outputPath,
      line_count: totalAtoms,
      lines_unique: uniqueCount,
      compression_ratio: totalAtoms > 0 ? parseFloat((totalAtoms / Math.max(1, uniqueCount)).toFixed(3)) : null,
      source_sessions: [],
      source_files: Array.from(filesSeen),
      parameters: {
        mode: 'full-corpus',
        page_size: pageSize,
        inflate_radius: radius,
        max_record_bytes: maxRecordBytes,
        total_atoms: totalAtoms,
        unique_atoms: uniqueCount,
        files: filesSeen.size,
        inflated: inflatedCount,
      },
    });
  } catch (dbError: any) {
    console.warn('[FullCorpusDistill] Could not record distill in database:', dbError.message);
  }

  StructuredLogger.info('FULL_CORPUS_DISTILL_COMPLETE', {
    total_atoms: totalAtoms,
    unique_atoms: uniqueCount,
    files: filesSeen.size,
    inflated: inflatedCount,
    size_bytes: sizeBytes,
    duration_ms: duration,
    output_path: outputPath,
  });

  return {
    stats: {
      compounds_processed: filesSeen.size,
      blocks_total: totalAtoms,
      blocks_unique: uniqueCount,
      decision_records: uniqueCount,
      compression_ratio: `${(totalAtoms / Math.max(1, uniqueCount)).toFixed(1)}:1`,
      duration_ms: duration,
      memory_peak_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
    },
    output: {
      format: 'full-corpus-jsonl',
      path: outputPath,
      size_bytes: sizeBytes,
      records_created: uniqueCount,
    },
    provenance: {
      source_compounds: Array.from(filesSeen),
      distilled_at: new Date().toISOString(),
      parameters: request,
    },
    // NOTE: the record array is intentionally NOT returned — it lives in the
    // streamed JSONL file. The HTTP response carries counts + output.path only.
  };
}

/**
 * Main distillation function
 */
export async function radialDistill(request: RadialDistillRequest): Promise<RadialDistillResult> {
  const startTime = Date.now();
  const ingestedAt = new Date().toISOString();

  StructuredLogger.info('RADIAL_DISTILL_V2', {
    endpoint: '/v1/memory/distill',
    format: request.output_format || 'decision-records',
    mode: request.mode || 'standard',
  });

  try {
    // Seedless full-corpus mode (user preference): no query, no compound_ids,
    // no buckets, no tags → expand + dedup EVERY unique atom and stream to file.
    const seed = request.seed;
    const isSeedless = !seed || (!seed.query && !(seed.compound_ids?.length) && !(seed.buckets?.length) && !(seed.tags?.length));
    if (request.mode === 'full-corpus' || (isSeedless && request.mode !== 'standard')) {
      return radialDistillFullCorpus(request);
    }

    // Route to tag-based mode if requested
    if (request.mode === 'tag-based' || (request.seed?.tags && request.seed.tags.length > 0)) {
      const tagResult = await tagBasedDistill(request);

      // Log distillation metrics
      StructuredLogger.info('[Distillation] Metrics', {
        totalAtoms: tagResult.metrics.totalAtoms,
        successfulReads: tagResult.metrics.successfulReads,
        provenanceMismatches: tagResult.metrics.provenanceMismatches,
        fallbackReads: tagResult.metrics.fallbackReads,
        failedReads: tagResult.metrics.failedReads,
        skippedByContent: tagResult.metrics.skippedByContent,
      });

      // Continue with standard pipeline using tag-based results
      return finalizeDistillation(request, tagResult.blocks, tagResult.digitalObjects, [], tagResult.compoundsProcessed, startTime, ingestedAt, tagResult.inflatedContent, tagResult.metrics);
    }

    // Phase 1: COLLECT - Extract semantic blocks and metadata (standard mode)
    const allBlocks: SemanticBlock[] = [];
    const digitalObjects: DigitalObjectMetadata[] = [];
    const chatSessions: ChatSessionMetadata[] = [];
    let compoundsProcessed = 0;

    // Phase 3A: Query molecules directly instead of compounds table
    let moleculeQuery = 'SELECT id AS compound_id, source_path, provenance, timestamp FROM molecules';
    const params: any[] = [];

    if (request.seed?.compound_ids && request.seed.compound_ids.length > 0) {
      // Filter by specific compound IDs. molecules.compound_id holds the mem_…
      // id; molecules.id is a per-molecule PK (mol_…) and must NOT be used here.
      // (The buckets branch below already joins on compound_id correctly.)
      moleculeQuery += ' WHERE compound_id = ANY($1)';
      params.push(request.seed.compound_ids);
    } else if (request.seed?.buckets && request.seed.buckets.length > 0) {
      // Join with atoms to filter by tags (Phase 1D-1)
      moleculeQuery = `
        SELECT DISTINCT ON (m.compound_id) m.id AS compound_id, m.source_path, m.provenance, MAX(m.timestamp)
        FROM molecules m
        JOIN atoms a ON m.compound_id = a.compound_id
        WHERE EXISTS(
          SELECT 1 FROM unnest(a.buckets) as bucket
          WHERE bucket = ANY($1)
        )
      `;
      params.push(request.seed.buckets);
    }

    const molecules = (await db.run(moleculeQuery, params)).rows || [];

    // Count distinct compound_ids from molecules for accurate metrics
    let moleculeCountQuery = 'SELECT COUNT(DISTINCT id) AS cnt FROM molecules';
    const moleculeParams: any[] = [];
    if (request.seed?.buckets && request.seed.buckets.length > 0) {
      moleculeCountQuery += ` WHERE EXISTS(
        SELECT 1 FROM atoms a
        JOIN molecules m ON a.compound_id = m.id
        WHERE EXISTS(
          SELECT 1 FROM unnest(a.buckets) as bucket
          WHERE bucket = ANY($1)
        )
      )`;
      moleculeParams.push(request.seed.buckets);
    }
    const countResult = await db.run(moleculeCountQuery, moleculeParams);
    const totalMolecules = parseInt(countResult.rows?.[0]?.cnt ?? '0', 10);

    // Track metrics for standard mode
    const standardMetrics: DistillationMetrics = {
      totalAtoms: totalMolecules,
      successfulReads: 0,
      provenanceMismatches: 0,
      fallbackReads: 0,
      failedReads: 0,
      skippedByContent: 0,
    };

    // Phase 1D-3: Deduplicate file reads — each unique path is read only once.
    const mirrorDir = PATHS.MIRRORED_BRAIN_DIR;

    type PathEntry = { localPath: string; moleculeIdx: number };
    const seenPaths = new Set<string>();
    const uniqueEntries: PathEntry[] = [];
    for (const [idx, molecule] of molecules.entries()) {
      if (!molecule.source_path) continue;
      const localPath = path.join(mirrorDir, molecule.source_path);
      if (!seenPaths.has(localPath)) {
        seenPaths.add(localPath);
        uniqueEntries.push({ localPath, moleculeIdx: idx });
      }
    }

    // Step 2: Read each unique file once into a cache.
    const contentCache = new Map<string, string>();
    const mtimeCache = new Map<string, number>();
    for (const entry of uniqueEntries) {
      if (!fs.existsSync(entry.localPath)) {
        console.warn(`[RadialDistiller] Skipping molecule ${molecules[entry.moleculeIdx].compound_id}: file not found at ${entry.localPath}`);
        continue;
      }
      try {
        contentCache.set(entry.localPath, fs.readFileSync(entry.localPath, 'utf-8'));
        const stats = fs.statSync(entry.localPath);
        mtimeCache.set(entry.localPath, stats.mtimeMs);
      } catch (err: any) {
        console.warn(`[RadialDistiller] Failed to read ${entry.localPath}: ${err.message}`);
      }
    }

    // Step 3: Process all molecules using cached content.
    for (const molecule of molecules) {
      if (!molecule.source_path) continue;
      if (isDistillationOutput(molecule.source_path)) continue;

      const localPath = path.join(mirrorDir, molecule.source_path);
      const content = contentCache.get(localPath) ?? '';
      const mtime = mtimeCache.get(localPath) ?? Date.now();

      if (!content) {
        standardMetrics.failedReads++;
        continue;
      }

      standardMetrics.totalAtoms++;
      standardMetrics.successfulReads++;

      console.log(`[DEBUG] RadialDistiller: using cached content for ${molecule.source_path}`);

      const blocks = extractSemanticBlocks(content, molecule.source_path, mtime);
      allBlocks.push(...blocks);

      // Extract digital object metadata (NEW)
      const baseMetadata = extractDigitalObjectMetadata(molecule, content, mtime, ingestedAt);
      if (baseMetadata) {
        digitalObjects.push(baseMetadata);

        // Extract chat session metadata if applicable (NEW)
        const chatMetadata = extractChatSessionMetadata(baseMetadata, content, molecule);
        if (chatMetadata) {
          chatSessions.push(chatMetadata);
        }
      }
    }

    // Log metrics for standard mode
    if (standardMetrics.failedReads > 0) {
      StructuredLogger.warn('[Distillation] Standard mode metrics', {
        total: standardMetrics.totalAtoms,
        successful: standardMetrics.successfulReads,
        failed: standardMetrics.failedReads,
      });
    }

    return finalizeDistillation(request, allBlocks, digitalObjects, chatSessions, compoundsProcessed, startTime, ingestedAt, undefined, standardMetrics);

  } catch (error: any) {
    StructuredLogger.error('RADIAL_DISTILL_V2_ERROR', error);
    throw error;
  }
}
