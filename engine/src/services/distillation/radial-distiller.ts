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

import { db } from '../../core/db.js'
import { ContextInflator } from '../search/context-inflator.js'
import { StructuredLogger } from '../../utils/structured-logger.js'
import { getMirrorPath, MIRRORED_BRAIN_PATH } from '../mirror/mirror.js'
import { PATHS, DEFAULT_PROVENANCE } from '../../config/paths.js'
import { recordDistill } from './distill-manager.js'
import crypto from 'crypto'
import fs from 'fs'
import path from 'path'
import yaml from 'js-yaml'

// Import batch fetch for compounds
import { batchFetchCompounds } from '../../utils/db-batch.js'

export interface RadialDistillRequest {
  seed?: {
    query?: string;
    compound_ids?: string[];
    buckets?: string[];
  }
  radius?: number;
  max_radius?: number;
  normalization?: 'strict' | 'lenient'
  preserve_formatting?: boolean
  streaming?: boolean
  chunk_size?: number
  output_format?: 'yaml' | 'json' | 'compound' | 'decision-records'
  output_path?: string
}

export interface DistillLine {
  content: string
  normalizedHash: string
  originalHash: string
  provenance: string[]
  timestamps: number[]
  compoundId: string
  lineNumber: number
}

export interface RadialDistillResult {
  stats: {
    compounds_processed: number
    lines_total: number
    lines_unique: number
    lines_duplicate: number
    compression_ratio: string
    duration_ms: number
    memory_peak_mb: number
  }
  output: {
    format: string
    path?: string
    size_bytes: number
    compounds_created: number
  }
  provenance: {
    source_compounds: string[]
    unique_sources: number
    distilled_at: string
    parameters: RadialDistillRequest
  }
}

const MOBILE_MEMORY_THRESHOLD = 500 * 1024 * 1024

function isMobileEnvironment(): boolean {
  if (process.platform === 'android') return true
  if (process.env.ANCHOR_MOBILE_MODE === '1') return true
  try {
    const os = require('os')
    const totalMem = os.totalmem()
    const freeMem = os.freemem()
    if (totalMem < 2 * 1024 * 1024 * 1024) return true
    if (freeMem < MOBILE_MEMORY_THRESHOLD) return true
  } catch {
    return false
  }
  return false
}

function normalizeLine(line: string, mode: 'strict' | 'lenient'): string {
  if (mode === 'lenient') {
    return line.trim()
  }
  let normalized = line.trim()
  normalized = normalized.replace(/\s+/g, ' ')
  normalized = normalized.toLowerCase()
  normalized = normalized.replace(/^user:\s*/i, '')
  normalized = normalized.replace(/^assistant:\s*/i, '')
  normalized = normalized.replace(/^\[?\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}\]?\s*/, '')
  normalized = normalized.replace(/^\[?\d{2}:\d{2}:\d{2}\]?\s*/, '')
  return normalized
}

function hashLine(line: string): string {
  return crypto.createHash('sha256').update(line).digest('hex')
}

async function* collectCompounds(
  request: RadialDistillRequest,
): AsyncGenerator<{ compoundId: string; content: string; source: string; timestamp: number }> {
  const radius = request.radius || 2000
  const maxRadius = request.max_radius || 10000
  const effectiveRadius = Math.min(radius, maxRadius)

  let conditions: string[] = []
  let queryBase = ``

  // Query molecules directly (Phase 2B: compounds table is now an index layer)
  queryBase += `
    SELECT DISTINCT
      m.compound_id AS compound_id,
      m.id AS molecule_id,
      m.source_path AS source_path,
      m.timestamp,
      m.provenance,
      m.start_byte,
      m.end_byte,
      m.content as content_preview
    FROM molecules m
  `

  const params: any[] = [DEFAULT_PROVENANCE]

  // Remove DEFAULT_PROVENance from params when no seed is provided - return ALL compounds
  const effectiveParams = request.seed ? [...params] : []

  if (request.seed?.compound_ids?.length) {
    conditions.push(`m.compound_id = $${effectiveParams.length + 1}`)
    effectiveParams.push(request.seed.compound_ids)
  }

  if (request.seed?.query) {
    const tsQuery = request.seed.query.split(/\s+/).filter(t => t.length > 0).join(' | ')
    queryBase += ` JOIN atoms a ON m.compound_id = a.compound_id WHERE to_tsvector('simple', a.content) @@ to_tsquery('simple', $${effectiveParams.length + 1})`
    effectiveParams.push(tsQuery)
  }

  if (conditions.length > 0) {
    queryBase += ' AND (' + conditions.join(' OR ') + ')'
  }

  queryBase += ' ORDER BY m.timestamp DESC, m.start_byte ASC'

  const result = await db.run(queryBase, effectiveParams)
  const rows = result.rows as any[]

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]
    
    try {
      let content = ''
      let source: string = 'unknown'
      let timestamp: number = Date.now()
      
      if (row.molecule_id !== null && row.start_byte !== undefined) {
        // Use molecule coordinates - we have the actual byte range!
        content = row.content_preview || ''
        source = row.source_path
        timestamp = row.timestamp || Date.now()
        
        StructuredLogger.info('[Distill] Processing molecule', { 
          id: row.molecule_id, 
          start_byte: row.start_byte, 
          end_byte: row.end_byte 
        })
      } else if (row.compound_id && row.source_path) {
        // Compound-level - try to inflate using ContextInflator
        const searchResult = {
          id: row.compound_id,
          content: '',
          source: row.source_path,
          timestamp: row.timestamp || Date.now(),
          buckets: [],
          tags: [],
          epochs: '',
          provenance: row.provenance || 'internal',
          score: 1.0,
          compound_id: row.compound_id,
          start_byte: 0,
          end_byte: 0,
          is_inflated: false,
        }

        const inflated = await ContextInflator.inflate([searchResult], effectiveRadius * 2, effectiveRadius)

        if (inflated.length > 0 && inflated[0].content) {
          content = inflated[0].content
          source = inflated[0].source
          timestamp = row.timestamp || Date.now()
        } else {
          // Fallback: try reading from disk directly using getMirrorPath
          const mirrorPath = getMirrorPath(row.source_path, row.provenance)
          if (mirrorPath && fs.existsSync(mirrorPath)) {
            content = fs.readFileSync(mirrorPath, 'utf-8')
            source = row.source_path
            timestamp = row.timestamp || Date.now()
          } else {
            StructuredLogger.warn('[Distill] Cannot find file for compound', { path: row.source_path })
            continue // Skip this compound if file not found
          }
        }
      }

      if (content) {
        yield {
          compoundId: row.compound_id || 'unknown',
          content,
          source,
          timestamp,
        }
      }

      if (isMobileEnvironment() && i % 5 === 0 && global.gc) {
        global.gc()
      }
    } catch (e) {
      const error = e as Error
      StructuredLogger.error('[Distill] Error processing row', error)
      continue // Skip failed rows but keep going
    }
  }
}

async function deduplicateLines(
  compoundGenerator: AsyncGenerator<{ compoundId: string; content: string; source: string; timestamp: number }>,
  request: RadialDistillRequest,
): Promise<{ uniqueLines: Map<string, DistillLine>; stats: { total: number; unique: number; duplicate: number; compoundsSkipped: number; compoundsTotal: number } }> {
  const normalization = request.normalization || 'strict'
  const uniqueLines = new Map<string, DistillLine>()
  const MAX_DEDUP_CACHE = 10000
  const seenCompoundHashes = new Set<string>()
  let totalLines = 0
  let duplicateLines = 0
  let duplicateCompoundsSkipped = 0
  let compoundsTotal = 0

  for await (const compound of compoundGenerator) {
    compoundsTotal++

    const compoundHash = hashLine(compound.content)
    if (seenCompoundHashes.has(compoundHash)) {
      duplicateCompoundsSkipped++
      if (duplicateCompoundsSkipped % 100 === 0) {
        // Aggregate debug logging
      }
      continue
    }

    if (seenCompoundHashes.size >= MAX_DEDUP_CACHE) {
      const hashes = Array.from(seenCompoundHashes)
      const toRemove = Math.floor(hashes.length * 0.1)
      hashes.splice(0, toRemove)
      seenCompoundHashes.clear()
      hashes.forEach(h => seenCompoundHashes.add(h))
    }

    seenCompoundHashes.add(compoundHash)

    const lines = compound.content.split('\n')

    for (let lineNum = 0; lineNum < lines.length; lineNum++) {
      const line = lines[lineNum]
      totalLines++

      if (!line.trim()) continue

      const normalized = normalizeLine(line, normalization)
      const normalizedHash = hashLine(normalized)
      const originalHash = hashLine(line)

      if (uniqueLines.has(normalizedHash)) {
        const existing = uniqueLines.get(normalizedHash)!
        if (!existing.provenance.includes(compound.source)) {
          existing.provenance.push(compound.source)
        }
        existing.timestamps.push(compound.timestamp)
        duplicateLines++
      } else {
        uniqueLines.set(normalizedHash, {
          content: line.trim(),
          normalizedHash,
          originalHash,
          provenance: [compound.source],
          timestamps: [compound.timestamp],
          compoundId: compound.compoundId,
          lineNumber: lineNum,
        })
      }
    }
  }

  return { uniqueLines, stats: { total: totalLines, unique: uniqueLines.size, duplicate: duplicateLines, compoundsSkipped: duplicateCompoundsSkipped, compoundsTotal } }
}

async function reassembleCompounds(
  uniqueLines: Map<string, DistillLine>,
  request: RadialDistillRequest,
): Promise<{ outputPath: string; sizeBytes: number; compoundsCreated: number }> {
  const lines = Array.from(uniqueLines.values())

  lines.sort((a, b) => {
    const timeA = Math.min(...a.timestamps)
    const timeB = Math.min(...b.timestamps)
    return timeA - timeB
  })

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  let outputPath: string

  if (request.output_path) {
    outputPath = request.output_path
  } else if (request.output_format === 'compound') {
    outputPath = path.join(PATHS.MIRRORED_BRAIN_DIR, 'distilled', `distilled_${timestamp}.md`)
  } else {
    outputPath = path.join(PATHS.DISTILLS_DIR, `distilled_${timestamp}.${request.output_format || 'json'}`)
  }

  const outputDir = path.dirname(outputPath)
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true })
  }

  if (request.output_format === 'yaml') {
    const yamlContent = yaml.dump({
      metadata: {
        source: 'Anchor Engine Radial Distiller',
        distilled_at: new Date().toISOString(),
        line_count: lines.length,
      },
      lines: lines.map(l => ({ content: l.content, provenance: l.provenance })),
    })
    fs.writeFileSync(outputPath, yamlContent, 'utf-8')
  } else if (request.output_format === 'json') {
    const jsonContent = JSON.stringify({
      metadata: { source: 'Anchor Engine Radial Distiller', distilled_at: new Date().toISOString() },
      lines: lines.map(l => ({ content: l.content, provenance: l.provenance })),
    }, null, 2)
    fs.writeFileSync(outputPath, jsonContent, 'utf-8')
  } else {
    const chunks: string[] = []
    let currentChunk: string[] = []
    for (const line of lines) {
      if (currentChunk.length >= 1000) {
        chunks.push(currentChunk.join('\n'))
        currentChunk = []
      }
      currentChunk.push(line.content)
    }
    if (currentChunk.length > 0) {
      chunks.push(currentChunk.join('\n'))
    }

    if (chunks.length === 0) {
      fs.writeFileSync(outputPath, '', 'utf-8')
    } else if (chunks.length === 1) {
      fs.writeFileSync(outputPath, chunks[0], 'utf-8')
    } else {
      for (let i = 0; i < chunks.length; i++) {
        const chunkPath = outputPath.replace('.md', `_${i + 1}.md`)
        fs.writeFileSync(chunkPath, chunks[i], 'utf-8')
      }
    }
  }

  const stats = fs.statSync(outputPath)
  return { outputPath, sizeBytes: stats.size, compoundsCreated: 1 }
}

export async function radialDistill(
  request: RadialDistillRequest,
): Promise<RadialDistillResult> {
  const startTime = Date.now()
  const memBefore = process.memoryUsage()

  try {
    const compoundGenerator = collectCompounds(request)
    const { uniqueLines, stats: dedupStats } = await deduplicateLines(compoundGenerator, request)
    const { outputPath, sizeBytes, compoundsCreated } = await reassembleCompounds(uniqueLines, request)
  const duration = Date.now() - startTime
    const memAfter = process.memoryUsage()
    const memPeak = Math.max(memAfter.heapUsed, memBefore.heapUsed)

    const compressionRatio = dedupStats.unique > 0
      ? (dedupStats.total / dedupStats.unique).toFixed(2)
      : '1.00'

    const sourceCompounds = Array.from(uniqueLines.values())
      .flatMap(line => line.provenance)
      .filter((source, index, arr) => arr.indexOf(source) === index)
      .sort()

    const result: RadialDistillResult = {
      stats: {
        compounds_processed: dedupStats.compoundsTotal,
        lines_total: dedupStats.total,
        lines_unique: dedupStats.unique,
        lines_duplicate: dedupStats.duplicate,
        compression_ratio: `${compressionRatio}:1`,
        duration_ms: duration,
        memory_peak_mb: Math.floor(memPeak / 1024 / 1024),
      },
      output: { format: request.output_format || 'compound', path: outputPath, size_bytes: sizeBytes, compounds_created: compoundsCreated },
      provenance: { source_compounds: sourceCompounds, unique_sources: sourceCompounds.length, distilled_at: new Date().toISOString(), parameters: request },
    }

    return result
  } catch (error) {
    throw error
  }
}