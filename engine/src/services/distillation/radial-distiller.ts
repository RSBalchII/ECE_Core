/**
 * Radial Distiller — Standard 133 Implementation
 *
 * Three-phase pipeline for lossless corpus compression:
 * 1. COLLECT: Radially inflate all compounds
 * 2. DEDUPLICATE: Line-level hash-based deduplication
 * 3. REASSEMBLE: Build coherent output compounds
 *
 * Memory-conscious: streaming mode for mobile, batch mode for desktop
 */

import { db } from '../../core/db.js';
import { ContextInflator } from '../search/context-inflator.js';
import { StructuredLogger } from '../../utils/structured-logger.js';
import { getMirrorPath } from '../mirror/mirror.js';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';

// Configuration from Standard 133
const PGLITE_CHUNK_IDS = 100;
const MOBILE_MEMORY_THRESHOLD = 500 * 1024 * 1024; // 500MB

// Memory safety constants
const MAX_LINES_IN_MEMORY = 100000; // Hard ceiling: ~50MB for line objects
const MAX_HEAP_BEFORE_STREAM = 800 * 1024 * 1024; // 800MB heap threshold
const STREAMING_CHUNK_SIZE = 50; // Process compounds in chunks of 50

export interface RadialDistillRequest {
  seed?: {
    query?: string;
    compound_ids?: string[];
    buckets?: string[];
  };
  radius?: number;
  max_radius?: number;
  normalization?: 'strict' | 'lenient';
  preserve_formatting?: boolean;
  streaming?: boolean;
  chunk_size?: number;
  output_format?: 'yaml' | 'json' | 'compound';
  output_path?: string;
  export_to_inbox?: boolean;
}

export interface DistillLine {
  content: string;
  normalizedHash: string;
  originalHash: string;
  provenance: string[];
  timestamps: number[];
  compoundId: string;
  lineNumber: number;
}

export interface RadialDistillResult {
  stats: {
    compounds_processed: number;
    lines_total: number;
    lines_unique: number;
    lines_duplicate: number;
    compression_ratio: string;
    duration_ms: number;
    memory_peak_mb: number;
  };
  output: {
    format: string;
    path?: string;
    size_bytes: number;
    compounds_created: number;
  };
  provenance: {
    source_compounds: string[];
    distilled_at: string;
    parameters: RadialDistillRequest;
  };
}

/**
 * Detect if running in mobile/memory-constrained environment
 * Reuses logic from Standard 134
 */
function isMobileEnvironment(): boolean {
  if (process.platform === 'android') return true;
  if (process.env.ANCHOR_MOBILE_MODE === '1') return true;

  try {
    const os = require('os');
    const totalMem = os.totalmem();
    const freeMem = os.freemem();

    if (totalMem < 2 * 1024 * 1024 * 1024) return true;
    if (freeMem < MOBILE_MEMORY_THRESHOLD) return true;
  } catch {
    return false;
  }

  return false;
}

/**
 * Auto-detect if streaming mode should be enabled
 * Based on heap usage and environment
 */
function shouldEnableStreaming(): boolean {
  // Always stream in mobile environments
  if (isMobileEnvironment()) return true;
  
  // Stream if heap is already under pressure
  const heapUsed = process.memoryUsage().heapUsed;
  if (heapUsed > MAX_HEAP_BEFORE_STREAM) return true;
  
  return false;
}

/**
 * Check memory safety before processing
 * Throws error if operation would exceed safe limits
 */
function checkMemorySafety(currentLines: number, estimatedNewLines: number): void {
  const projectedTotal = currentLines + estimatedNewLines;
  
  if (projectedTotal > MAX_LINES_IN_MEMORY) {
    throw new Error(
      `Memory safety limit exceeded: ${projectedTotal.toLocaleString()} lines would exceed ` +
      `maximum of ${MAX_LINES_IN_MEMORY.toLocaleString()} lines. ` +
      `Consider using a smaller radius, filtering by compound_ids, or running in streaming mode.`
    );
  }
  
  // Check heap usage
  const heapUsed = process.memoryUsage().heapUsed;
  if (heapUsed > MAX_HEAP_BEFORE_STREAM) {
    throw new Error(
      `Heap memory too high (${Math.round(heapUsed / 1024 / 1024)}MB). ` +
      `Please run GC or reduce workload. Threshold: ${Math.round(MAX_HEAP_BEFORE_STREAM / 1024 / 1024)}MB`
    );
  }
}

/**
 * Normalize a line for deduplication
 * Standard 133: strict vs lenient normalization
 */
function normalizeLine(line: string, mode: 'strict' | 'lenient'): string {
  if (mode === 'lenient') {
    // Lenient: just trim
    return line.trim();
  }

  // Strict: aggressive normalization
  let normalized = line.trim();

  // Collapse whitespace
  normalized = normalized.replace(/\s+/g, ' ');

  // Lowercase
  normalized = normalized.toLowerCase();

  // Remove common boilerplate patterns
  normalized = normalized.replace(/^user:\s*/i, '');
  normalized = normalized.replace(/^assistant:\s*/i, '');
  normalized = normalized.replace(/^\[?\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}\]?\s*/, '');
  normalized = normalized.replace(/^\[?\d{2}:\d{2}:\d{2}\]?\s*/, '');

  return normalized;
}

/**
 * Calculate hash for a line
 */
function hashLine(line: string): string {
  return crypto.createHash('sha256').update(line).digest('hex');
}

/**
 * PHASE 1: COLLECT
 * Stream compounds and radially inflate each
 */
async function* collectCompounds(
  request: RadialDistillRequest
): AsyncGenerator<{ compoundId: string; content: string; source: string; timestamp: number }> {
  const radius = request.radius || 2000;
  const maxRadius = request.max_radius || 10000;
  const effectiveRadius = Math.min(radius, maxRadius);

  // Build compound query
  let query = `SELECT id, path, timestamp, provenance FROM compounds`;
  const params: any[] = [];
  const conditions: string[] = [];

  if (request.seed?.compound_ids?.length) {
    conditions.push(`id = ANY($${params.length + 1})`);
    params.push(request.seed.compound_ids);
  }

  if (request.seed?.buckets?.length) {
    // Join with atoms to filter by buckets
    query = `
      SELECT DISTINCT c.id, c.path, c.timestamp, c.provenance
      FROM compounds c
      JOIN atoms a ON a.compound_id = c.id
      WHERE EXISTS(
        SELECT 1 FROM unnest(a.buckets) as bucket
        WHERE bucket = ANY($1)
      )
    `;
    params.push(request.seed.buckets);
  }

  if (request.seed?.query) {
    // FTS-based seed selection
    const tsQuery = request.seed.query.split(/\s+/).filter(t => t.length > 0).join(' | ');
    query = `
      SELECT DISTINCT c.id, c.path, c.timestamp, c.provenance
      FROM compounds c
      JOIN atoms a ON a.compound_id = c.id
      WHERE to_tsvector('simple', a.content) @@ to_tsquery('simple', $1)
    `;
    params.push(tsQuery);
  }

  query += ` ORDER BY timestamp DESC`;

  const result = await db.run(query, params);
  const compounds = result.rows as any[];

  StructuredLogger.info('DISTILL_COLLECT_START', {
    compounds_found: compounds.length,
    radius: effectiveRadius
  });

  // Process each compound with radial inflation
  for (let i = 0; i < compounds.length; i++) {
    const compound = compounds[i];

    try {
      // Create a minimal SearchResult for inflation
      const searchResult = {
        id: compound.id,
        content: '',
        source: compound.path,
        timestamp: compound.timestamp,
        buckets: [],
        tags: [],
        epochs: '',
        provenance: compound.provenance || 'internal',
        score: 1.0,
        compound_id: compound.id,
        start_byte: 0,
        end_byte: 0,
        is_inflated: false
      };

      // Radially inflate from disk
      const inflated = await ContextInflator.inflate([searchResult], effectiveRadius * 2, effectiveRadius);

      if (inflated.length > 0 && inflated[0].content) {
        yield {
          compoundId: compound.id,
          content: inflated[0].content,
          source: compound.path,
          timestamp: compound.timestamp
        };
      }

      // GC hint every N compounds on mobile
      if (isMobileEnvironment() && i % 5 === 0 && global.gc) {
        global.gc();
      }
    } catch (e) {
      StructuredLogger.error('DISTILL_INFLATE_ERROR', e instanceof Error ? e : new Error(String(e)), {
        compound_id: compound.id
      });
    }
  }
}

/**
 * PHASE 1 (Streaming): Collect compounds in chunks with memory monitoring
 * Yields compounds in batches to allow GC between chunks
 */
async function* collectCompoundsChunked(
  request: RadialDistillRequest
): AsyncGenerator<{ compoundId: string; content: string; source: string; timestamp: number }> {
  const radius = request.radius || 2000;
  const maxRadius = request.max_radius || 10000;
  const effectiveRadius = Math.min(radius, maxRadius);

  // Get all compounds first (lightweight query)
  let query = `SELECT id, path, timestamp, provenance FROM compounds`;
  const params: any[] = [];
  const conditions: string[] = [];

  if (request.seed?.compound_ids?.length) {
    conditions.push(`id = ANY($${params.length + 1})`);
    params.push(request.seed.compound_ids);
  }

  if (request.seed?.buckets?.length) {
    query = `
      SELECT DISTINCT c.id, c.path, c.timestamp, c.provenance
      FROM compounds c
      JOIN atoms a ON a.compound_id = c.id
      WHERE EXISTS(
        SELECT 1 FROM unnest(a.buckets) as bucket
        WHERE bucket = ANY($${params.length + 1})
      )
    `;
    params.push(request.seed.buckets);
  }

  if (conditions.length > 0) {
    query += ` WHERE ` + conditions.join(' AND ');
  }

  query += ` ORDER BY timestamp DESC`;

  const result = await db.run(query, params);
  const compounds = result.rows as any[];

  StructuredLogger.info('DISTILL_COLLECT_CHUNKED_START', {
    compounds_found: compounds.length,
    chunk_size: STREAMING_CHUNK_SIZE,
    radius: effectiveRadius
  });

  // Process in chunks to allow GC
  for (let chunkStart = 0; chunkStart < compounds.length; chunkStart += STREAMING_CHUNK_SIZE) {
    const chunk = compounds.slice(chunkStart, chunkStart + STREAMING_CHUNK_SIZE);
    
    StructuredLogger.debug('DISTILL_CHUNK_PROCESSING', {
      chunk_start: chunkStart,
      chunk_size: chunk.length,
      total: compounds.length
    });

    for (const compound of chunk) {
      try {
        const searchResult = {
          id: compound.id,
          content: '',
          source: compound.path,
          timestamp: compound.timestamp,
          buckets: [],
          tags: [],
          epochs: '',
          provenance: compound.provenance || 'internal',
          score: 1.0,
          compound_id: compound.id,
          start_byte: 0,
          end_byte: 0,
          is_inflated: false
        };

        const inflated = await ContextInflator.inflate([searchResult], effectiveRadius * 2, effectiveRadius);

        if (inflated.length > 0 && inflated[0].content) {
          yield {
            compoundId: compound.id,
            content: inflated[0].content,
            source: compound.path,
            timestamp: compound.timestamp
          };
        }
      } catch (e) {
        StructuredLogger.error('DISTILL_INFLATE_ERROR', e instanceof Error ? e : new Error(String(e)), {
          compound_id: compound.id
        });
      }
    }

    // GC hint between chunks in streaming mode
    if (global.gc) {
      global.gc();
    }
    
    // Yield control to event loop
    await new Promise(resolve => setTimeout(resolve, 0));
  }
}

/**
 * PHASE 2 (With Monitoring): Deduplicate with memory monitoring and periodic GC
 */
async function deduplicateLinesWithMonitoring(
  compoundGenerator: AsyncGenerator<{ compoundId: string; content: string; source: string; timestamp: number }>,
  request: RadialDistillRequest
): Promise<{
  uniqueLines: Map<string, DistillLine>;
  stats: { total: number; unique: number; duplicate: number };
}> {
  const normalization = request.normalization || 'strict';
  const uniqueLines = new Map<string, DistillLine>();
  let totalLines = 0;
  let duplicateLines = 0;
  let lastMemoryCheck = 0;

  StructuredLogger.info('DISTILL_DEDUP_STREAMING_START', { 
    normalization,
    streaming: true 
  });

  for await (const compound of compoundGenerator) {
    const lines = compound.content.split('\n');

    for (let lineNum = 0; lineNum < lines.length; lineNum++) {
      const line = lines[lineNum];
      totalLines++;

      if (!line.trim()) continue;

      const normalized = normalizeLine(line, normalization);
      const normalizedHash = hashLine(normalized);
      const originalHash = hashLine(line);

      // Memory safety check every 1000 lines
      if (totalLines % 1000 === 0) {
        checkMemorySafety(uniqueLines.size, lines.length - lineNum);
        
        // Additional heap check every 10000 lines
        if (totalLines % 10000 === 0) {
          const heapUsed = process.memoryUsage().heapUsed;
          if (heapUsed > MAX_HEAP_BEFORE_STREAM) {
            StructuredLogger.warn('DISTILL_HEAP_PRESSURE', {
              heap_used_mb: Math.round(heapUsed / 1024 / 1024),
              threshold_mb: Math.round(MAX_HEAP_BEFORE_STREAM / 1024 / 1024),
              lines_processed: totalLines
            });
          }
        }
      }

      if (uniqueLines.has(normalizedHash)) {
        const existing = uniqueLines.get(normalizedHash)!;
        if (!existing.provenance.includes(compound.source)) {
          existing.provenance.push(compound.source);
        }
        existing.timestamps.push(compound.timestamp);
        duplicateLines++;
      } else {
        uniqueLines.set(normalizedHash, {
          content: line.trim(),
          normalizedHash,
          originalHash,
          provenance: [compound.source],
          timestamps: [compound.timestamp],
          compoundId: compound.compoundId,
          lineNumber: lineNum
        });
      }
    }

    // GC hint every 10 compounds in streaming mode
    if (totalLines % 10000 === 0 && global.gc) {
      global.gc();
    }
  }

  StructuredLogger.info('DISTILL_DEDUP_COMPLETE', {
    total_lines: totalLines,
    unique_lines: uniqueLines.size,
    duplicate_lines: duplicateLines,
    dedup_ratio: totalLines > 0 ? ((duplicateLines / totalLines) * 100).toFixed(1) + '%' : '0%'
  });

  return {
    uniqueLines,
    stats: {
      total: totalLines,
      unique: uniqueLines.size,
      duplicate: duplicateLines
    }
  };
}

/**
 * PHASE 2: DEDUPLICATE
 * Line-level deduplication with bounded memory
 */
async function deduplicateLines(
  compoundGenerator: AsyncGenerator<{ compoundId: string; content: string; source: string; timestamp: number }>,
  request: RadialDistillRequest
): Promise<{
  uniqueLines: Map<string, DistillLine>;
  stats: { total: number; unique: number; duplicate: number };
}> {
  const normalization = request.normalization || 'strict';
  const uniqueLines = new Map<string, DistillLine>(); // normalizedHash -> DistillLine
  let totalLines = 0;
  let duplicateLines = 0;

  StructuredLogger.info('DISTILL_DEDUP_START', { normalization });

  for await (const compound of compoundGenerator) {
    const lines = compound.content.split('\n');

    for (let lineNum = 0; lineNum < lines.length; lineNum++) {
      const line = lines[lineNum];
      totalLines++;

      // Skip empty lines
      if (!line.trim()) continue;

      const normalized = normalizeLine(line, normalization);
      const normalizedHash = hashLine(normalized);
      const originalHash = hashLine(line);

      // Memory safety check every 1000 lines
      if (totalLines % 1000 === 0) {
        checkMemorySafety(uniqueLines.size, lines.length - lineNum);
      }

      if (uniqueLines.has(normalizedHash)) {
        // Duplicate: update provenance
        const existing = uniqueLines.get(normalizedHash)!;
        if (!existing.provenance.includes(compound.source)) {
          existing.provenance.push(compound.source);
        }
        existing.timestamps.push(compound.timestamp);
        duplicateLines++;
      } else {
        // New unique line
        uniqueLines.set(normalizedHash, {
          content: line.trim(),
          normalizedHash,
          originalHash,
          provenance: [compound.source],
          timestamps: [compound.timestamp],
          compoundId: compound.compoundId,
          lineNumber: lineNum
        });
      }
    }

    // Memory check on mobile
    if (isMobileEnvironment() && totalLines % 1000 === 0) {
      const memUsage = process.memoryUsage();
      if (memUsage.heapUsed > MOBILE_MEMORY_THRESHOLD) {
        StructuredLogger.warn('DISTILL_MEMORY_PRESSURE', {
          heap_used_mb: Math.floor(memUsage.heapUsed / 1024 / 1024)
        });
        if (global.gc) global.gc();
      }
    }
  }

  return {
    uniqueLines,
    stats: {
      total: totalLines,
      unique: uniqueLines.size,
      duplicate: duplicateLines
    }
  };
}

/**
 * PHASE 3: REASSEMBLE
 * Group lines into coherent output compounds
 */
async function reassembleCompounds(
  uniqueLines: Map<string, DistillLine>,
  request: RadialDistillRequest
): Promise<{ outputPath: string; sizeBytes: number; compoundsCreated: number }> {
  const lines = Array.from(uniqueLines.values());

  // Sort by timestamp (chronological order)
  lines.sort((a, b) => {
    const timeA = Math.min(...a.timestamps);
    const timeB = Math.min(...b.timestamps);
    return timeA - timeB;
  });

  // Determine output path
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  let outputPath: string;
  let compoundsCreated = 0;

  if (request.output_path) {
    outputPath = request.output_path;
  } else if (request.output_format === 'compound') {
    outputPath = path.join(process.cwd(), 'mirrored_brain', 'distilled', `distilled_${timestamp}.md`);
  } else {
    outputPath = path.join(process.cwd(), 'inbox', 'distilled', `distilled_${timestamp}.${request.output_format || 'yaml'}`);
  }

  // Ensure directory exists
  const outputDir = path.dirname(outputPath);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Write output based on format
  if (request.output_format === 'yaml') {
    const yamlContent = yaml.dump({
      metadata: {
        source: 'Anchor Engine Radial Distiller',
        distilled_at: new Date().toISOString(),
        line_count: lines.length,
        parameters: {
          radius: request.radius,
          normalization: request.normalization
        }
      },
      lines: lines.map(l => ({
        content: l.content,
        provenance: l.provenance,
        first_seen: new Date(Math.min(...l.timestamps)).toISOString()
      }))
    });
    fs.writeFileSync(outputPath, yamlContent, 'utf-8');
    compoundsCreated = 1;
  } else if (request.output_format === 'json') {
    const jsonContent = JSON.stringify({
      metadata: {
        source: 'Anchor Engine Radial Distiller',
        distilled_at: new Date().toISOString(),
        line_count: lines.length
      },
      lines: lines.map(l => ({
        content: l.content,
        provenance: l.provenance,
        first_seen: new Date(Math.min(...l.timestamps)).toISOString()
      }))
    }, null, 2);
    fs.writeFileSync(outputPath, jsonContent, 'utf-8');
    compoundsCreated = 1;
  } else {
    // Compound format: write as markdown with provenance headers
    const chunks: string[] = [];
    let currentChunk: string[] = [];
    const CHUNK_SIZE = 1000; // lines per compound

    for (const line of lines) {
      if (currentChunk.length >= CHUNK_SIZE) {
        chunks.push(currentChunk.join('\n'));
        currentChunk = [];
      }

      // Add provenance comment every 10 lines
      if (currentChunk.length % 10 === 0) {
        currentChunk.push(`<!-- Source: ${line.provenance.join(', ')} -->`);
      }
      currentChunk.push(line.content);
    }

    if (currentChunk.length > 0) {
      chunks.push(currentChunk.join('\n'));
    }

    // Write chunks as separate files or single file
    if (chunks.length === 1) {
      fs.writeFileSync(outputPath, chunks[0], 'utf-8');
      compoundsCreated = 1;
    } else {
      // Multiple compounds
      for (let i = 0; i < chunks.length; i++) {
        const chunkPath = outputPath.replace('.md', `_${i + 1}.md`);
        fs.writeFileSync(chunkPath, chunks[i], 'utf-8');
      }
      compoundsCreated = chunks.length;
    }
  }

  const stats = fs.statSync(outputPath);

  StructuredLogger.info('DISTILL_REASSEMBLE_COMPLETE', {
    output_path: outputPath,
    lines_written: lines.length,
    compounds_created: compoundsCreated
  });

  return { outputPath, sizeBytes: stats.size, compoundsCreated };
}

/**
 * Main entry point: Radial Distillation
 * Standard 133 implementation with memory safety
 */
export async function radialDistill(
  request: RadialDistillRequest
): Promise<RadialDistillResult> {
  const startTime = Date.now();
  const memBefore = process.memoryUsage();

  // Auto-enable streaming mode if not explicitly set
  const effectiveRequest = {
    ...request,
    streaming: request.streaming ?? shouldEnableStreaming()
  };

  StructuredLogger.info('RADIAL_DISTILL_START', {
    seed: request.seed,
    radius: request.radius,
    normalization: request.normalization,
    is_mobile: isMobileEnvironment(),
    streaming_enabled: effectiveRequest.streaming,
    heap_used_mb: Math.round(memBefore.heapUsed / 1024 / 1024)
  });

  try {
    // Memory safety check before starting
    checkMemorySafety(0, MAX_LINES_IN_MEMORY); // Initial check

    // Phase 1: Collect (with streaming support)
    const compoundGenerator = effectiveRequest.streaming
      ? collectCompoundsChunked(effectiveRequest)
      : collectCompounds(effectiveRequest);

    // Phase 2: Deduplicate (with memory monitoring)
    const { uniqueLines, stats: dedupStats } = await deduplicateLinesWithMonitoring(
      compoundGenerator,
      effectiveRequest
    );

    // Final memory safety check before reassembly
    checkMemorySafety(uniqueLines.size, 0);

    // Phase 3: Reassemble
    const { outputPath, sizeBytes, compoundsCreated } = await reassembleCompounds(uniqueLines, request);

    const duration = Date.now() - startTime;
    const memAfter = process.memoryUsage();
    const memPeak = Math.max(memAfter.heapUsed, memBefore.heapUsed);

    const compressionRatio = dedupStats.unique > 0
      ? (dedupStats.total / dedupStats.unique).toFixed(2)
      : '1.00';

    const result: RadialDistillResult = {
      stats: {
        compounds_processed: dedupStats.total, // Approximate
        lines_total: dedupStats.total,
        lines_unique: dedupStats.unique,
        lines_duplicate: dedupStats.duplicate,
        compression_ratio: `${compressionRatio}:1`,
        duration_ms: duration,
        memory_peak_mb: Math.floor(memPeak / 1024 / 1024)
      },
      output: {
        format: request.output_format || 'compound',
        path: outputPath,
        size_bytes: sizeBytes,
        compounds_created: compoundsCreated
      },
      provenance: {
        source_compounds: [], // TODO: track actual sources
        distilled_at: new Date().toISOString(),
        parameters: request
      }
    };

    StructuredLogger.info('RADIAL_DISTILL_COMPLETE', {
      duration_ms: duration,
      compression_ratio: compressionRatio,
      lines_unique: dedupStats.unique,
      lines_total: dedupStats.total,
      heap_used_mb: Math.round(memAfter.heapUsed / 1024 / 1024)
    });

    return result;
  } catch (error) {
    StructuredLogger.error('RADIAL_DISTILL_ERROR', error instanceof Error ? error : new Error(String(error)));
    throw error;
  }
}
