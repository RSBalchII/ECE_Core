/**
 * Ingest Service - Memory Ingestion with Provenance Tracking
 *
 * Implements the Data Provenance feature by adding a 'provenance' column
 * to distinguish between "Sovereign" (User-Created) and "Ancillary" (External) data.
 */

import { db } from '../../core/db.js';
import crypto from 'crypto';
import { config } from '../../config/index.js';

interface IngestOptions {
  atomize?: boolean;
}





/**
 * Determines the provenance of content based on its source
 */
function determineProvenance(source: string, type?: string): 'sovereign' | 'external' | 'system' {
  // If source comes from context/inbox/ or API with type 'user', it's sovereign
  if (source.includes('context/inbox/') || type === 'user') {
    return 'sovereign';
  }

  // If source is from web scraping or bulk import, it's external
  if (source.includes('web_scrape') || source.includes('bulk_import')) {
    return 'external';
  }

  // Default to external for most cases
  return 'external';
}

/**
 * Ingest content into the memory database with provenance tracking
 */
export async function ingestContent(
  content: string,
  source: string,
  type: string = 'text',
  buckets: string[] = ['core'],
  tags: string[] = [],
  _options: IngestOptions = {}
): Promise<{ status: string; id?: string; message?: string }> {

  if (!content) {
    throw new Error('Content is required for ingestion');
  }

  // Auto-assign provenance based on source
  const provenance = determineProvenance(source, type);

  // Generate hash for content deduplication
  const hash = crypto.createHash('md5').update(content).digest('hex');

  // Check if content with same hash already exists
  const existingQuery = `?[id] := *memory{id, hash}, hash = $hash`;
  const existingResult = await db.run(existingQuery, { hash });

  if (existingResult.rows && existingResult.rows.length > 0) {
    return {
      status: 'skipped',
      id: existingResult.rows[0][0],
      message: 'Content with same hash already exists'
    };
  }

  // Generate unique ID
  const id = `mem_${Date.now()}_${crypto.randomBytes(8).toString('hex').substring(0, 16)}`;
  const timestamp = Date.now();
  const tagsJson = tags; // Pass as array, Cozo Napi handles it
  const bucketsArray = Array.isArray(buckets) ? buckets : [buckets];
  const epochsJson: string[] = []; // Pass as array

  // Insert the memory with provenance information
  // Schema: id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding
  const insertQuery = `?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding] <- $data :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding}`;

  await db.run(insertQuery, {
    data: [[id, timestamp, content, source, source, 0, type, hash, bucketsArray, epochsJson, tagsJson, provenance, new Array(config.MODELS.EMBEDDING_DIM).fill(0.1)]]
  });

  // Strict Read-After-Write Verification (Standard 059)
  const verify = await db.run(`?[id] := *memory{id}, id = $id`, { id });
  if (!verify.rows || verify.rows.length === 0) {
    throw new Error(`Ingestion Verification Failed: ID ${id} not found after write.`);
  }

  return {
    status: 'success',
    id,
    message: 'Content ingested successfully with provenance tracking'
  };
}

export interface IngestAtom {
  id: string;
  content: string;
  sourceId: string;
  sequence: number;
  timestamp: number;
  provenance: 'sovereign' | 'external';
  embedding?: number[];
  hash?: string; // Explicit hash to avoid ID-based guessing
}

/**
 * Ingest pre-processed atoms
 */
export async function ingestAtoms(
  atoms: IngestAtom[],
  source: string,
  buckets: string[] = ['core'],
  tags: string[] = []
): Promise<number> {

  if (atoms.length === 0) return 0;

  const rows = atoms.map(atom => {
    // Schema: id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding
    return [
      atom.id,
      atom.timestamp,
      atom.content,
      source,
      atom.sourceId,
      atom.sequence,
      'text', // Type
      atom.hash || atom.id.replace('atom_', ''), // Use explicit hash or fallback
      buckets,
      [], // epochs
      tags,
      atom.provenance,
      atom.embedding || new Array(config.MODELS.EMBEDDING_DIM).fill(0.1)
    ];
  });

  // Chunked Insert
  const chunkSize = 50;
  let inserted = 0;
  const totalBatches = Math.ceil(rows.length / chunkSize);

  console.log(`[Ingest] Starting DB Write for ${rows.length} atoms (${totalBatches} batches)...`);

  for (let i = 0; i < rows.length; i += chunkSize) {
    const batchNum = Math.floor(i / chunkSize) + 1;
    if (batchNum % 10 === 0 || batchNum === 1 || batchNum === totalBatches) {
      console.log(`[Ingest] Writing batch ${batchNum}/${totalBatches}...`);
    }
    const chunk = rows.slice(i, i + chunkSize);
    try {
      if (chunk.length > 0) {
        const sampleEmbedding = chunk[0][12] as number[];
        if (sampleEmbedding.length !== config.MODELS.EMBEDDING_DIM) {
          console.warn(`[Ingest] WARNING: Embedding dimension mismatch! Schema: ${config.MODELS.EMBEDDING_DIM}, Actual: ${sampleEmbedding.length}`);
        }
      }
      await db.run(`
                ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding] <- $data
                :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding}
             `, { data: chunk });
    } catch (e: any) {
      console.error(`[Ingest] Batch insert failed: ${e.message}`);
      throw e; // RETHROW to abort Watchdog update
    }

    // Standard 059: Batch Read-After-Write Verification
    try {
      const chunkIds = chunk.map(row => row[0]); // row[0] is id
      const chunkIdsStr = JSON.stringify(chunkIds);
      const verifyQuery = `?[id] := *memory{id}, id in ${chunkIdsStr}`;
      const verifyResult = await db.run(verifyQuery);

      const count = verifyResult.rows ? verifyResult.rows.length : 0;

      if (count !== chunk.length) {
        const errorMsg = `[Ingest] CRITICAL: Batch Verification Failed! Inserted: ${chunk.length}, Verified: ${count}. Potential Ghost Data.`;
        console.error(errorMsg);
        throw new Error(errorMsg); // STRICT MODE: Fail fast.
      } else {
        inserted += count;
      }
    } catch (verifyError: any) {
      console.error(`[Ingest] Verification Query Failed: ${verifyError.message}`);
      throw verifyError; // RETHROW
    }
  }

  return inserted;
}

/**
 * Bulk import YAML content with provenance tracking
 */
export async function importYamlContent(yamlContent: any[]): Promise<{ imported: number; skipped: number; errors: number }> {
  let imported = 0;
  let skipped = 0;
  let errors = 0;

  for (const record of yamlContent) {
    try {
      if (!record.content) {
        errors++;
        continue;
      }

      const result = await ingestContent(
        record.content,
        record.source || 'yaml_import',
        record.type || 'text',
        record.buckets || ['imported'],
        record.tags || []
      );

      if (result.status === 'success') {
        imported++;
      } else if (result.status === 'skipped') {
        skipped++;
      }
    } catch (error) {
      console.error('YAML import error for record:', record, error);
      errors++;
    }
  }

  return { imported, skipped, errors };
}