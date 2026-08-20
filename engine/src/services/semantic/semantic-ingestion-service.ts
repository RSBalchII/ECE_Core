/**
 * Semantic Ingestion Service for ECE (Semantic Shift Refactor)
 * 
 * Replaces the old atomizer with semantic molecule processing
 * that creates high-level semantic tags and atomic entities.
 */

import { SemanticMoleculeProcessor } from './semantic-molecule-processor.js';
import type { SemanticMolecule } from './types/semantic.js';
import { db } from '../../core/db.js';
import * as crypto from 'crypto';
import { NlpService } from '../../services/nlp/nlp-service.js';
import { Timer } from '../../utils/timer.js';
import { executor } from '../../utils/memory-aware-executor.js';

export class SemanticIngestionService {
  private moleculeProcessor: SemanticMoleculeProcessor;

  constructor() {
    this.moleculeProcessor = new SemanticMoleculeProcessor();
  }

  /**
   * Ingest content using the new semantic architecture
   * Creates molecules with high-level semantic tags and atomic entities
   */
  public async ingestContent(
    content: string,
    source: string,
    type: string = 'text',
    bucket: string = 'default',
    buckets: string[] = [],
    tags: string[] = [], // These will be high-level semantic categories
  ): Promise<{ status: string; id: string; message: string }> {
    const timer = new Timer('IngestionService');

    try {
      console.log(`[IngestionService] Starting ingestion for source: ${source}, type: ${type}, length: ${content.length} chars`);

      // Handle legacy single-bucket param
      const allBuckets = bucket ? [...buckets, bucket] : buckets;
      console.log(`[IngestionService] Processing with buckets: [${allBuckets.join(', ')}], tags: [${tags.join(', ')}]`);

      // Ensure explicit metadata tags exist (Fix for missing UI toggles when NER fails)
      // This ensures 'indexTags' never receives an empty list, so buckets are always indexed.
      const metadataTags = [`source:${source}`, `type:${type}`];
      const effectiveTags = [...new Set([...tags, ...metadataTags])];
      console.log(`[IngestionService] Effective tags after adding metadata: [${effectiveTags.join(', ')}]`);

      // Validate content length to prevent oversized atoms
      const MAX_CONTENT_LENGTH = 500 * 1024; // 500KB limit
      if (content.length > MAX_CONTENT_LENGTH) {
        console.warn(`[SemanticIngestionService] Content exceeds maximum length (${content.length} chars), performing automatic chunking...`);
        // Split the content into smaller chunks and process each separately
        timer.log('Starting large content ingestion');
        const result = await this.ingestLargeContent(content, source, type, bucket, buckets, effectiveTags);
        timer.logTotalAndReset(`Completed large content ingestion for ${source}`);
        return result;
      }

      timer.log('Starting content splitting');
      // Split content into text chunks (molecules)
      const textChunks = this.splitIntoMolecules(content);
      console.log(`[IngestionService] Content split into ${textChunks.length} chunks`);
      timer.logLap(`Split content into ${textChunks.length} chunks`);

      timer.log('Starting molecule processing');
      // Process each chunk into semantic molecules - OPTIMIZED FOR PARALLEL PROCESSING
      const chunksWithMetadata = textChunks.map((chunk, index) => ({
        content: chunk,
        source: `${source}_chunk_${index}`,
        timestamp: Date.now() + index, // Slightly offset timestamps
        provenance: 'external',
      }));

      console.log(`[IngestionService] Processing ${chunksWithMetadata.length} chunks through molecule processor...`);
      // Process chunks with memory-aware bounded concurrency (v5.2.0+) — prevents heap spikes
      const semanticMolecules = await executor.process(
        chunksWithMetadata,
        async chunk => this.moleculeProcessor.processTextChunk(
          chunk.content,
          chunk.source,
          chunk.timestamp,
          chunk.provenance,
        ),
        { maxConcurrency: 3 }, // NLP is CPU-bound; bounded parallelism prevents OOM
      );
      console.log(`[IngestionService] Processed ${semanticMolecules.length} semantic molecules with a total of ${semanticMolecules.reduce((sum, mol) => sum + mol.containedEntities.length, 0)} atomic entities`);
      timer.logLap(`Processed ${semanticMolecules.length} semantic molecules`);

      // Refactored to use the shared helper method
      const result = await this.saveMoleculesBatched([semanticMolecules], source, type, allBuckets, effectiveTags);

      // Construct the compatible return object
      return {
        status: result.status,
        id: semanticMolecules[0]?.id || 'unknown',
        message: result.message,
      };
    } catch (e: any) {
      console.error('[SemanticIngestionService] Ingest Error:', e);
      return { status: 'error', id: 'unknown', message: e.message };
    }
  }

  /**
   * Helper to validate and save a batch of molecules to the database
   * Handles the transaction, deduplication, and bulk insertion
   */
  private async saveMoleculesBatched(
    moleculeBatches: SemanticMolecule[][],
    source: string,
    type: string,
    buckets: string[],
    tags: string[],
  ): Promise<{ status: 'success' | 'error', message: string }> {
    const timer = new Timer('SaveMoleculesBatched');

    // Flatten the batches for this transaction (or we could process per batch)
    // For ingestContent (single file), it's one batch.
    // For ingestLargeContent, we might call this iteratively.
    const molecules = moleculeBatches.flat();

    if (molecules.length === 0) {
      return { status: 'success', message: 'No molecules to save' };
    }

    // SHARED ZERO VECTOR OPTIMIZATION
    const ZERO_VECTOR_STR = JSON.stringify(new Array(768).fill(0.1));
    const allAtomsToInsert: any[] = [];

    // Prepare atoms
    for (const molecule of molecules) {
      // Use the ID from the molecule if it exists (it was generated by the processor)
      // or generate a new one if strictly necessary. 
      // The processor should be the source of truth, but the original code overrode it.
      // Let's respect the processor's ID to keep the object consistent.
      const id = molecule.id || `mol_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const { timestamp } = molecule;
      const hash = crypto.createHash('sha256').update(molecule.content).digest('hex');

      // Prepare molecule atom
      allAtomsToInsert.push({
        id,
        timestamp,
        content: molecule.content,
        source_path: source,
        source_id: source,
        sequence: 0,
        type: type || 'semantic_molecule',
        hash,
        buckets: buckets,
        tags: [...tags, ...molecule.semanticTags.map((tag: string) => tag.replace('#', ''))],
        epochs: [],
        provenance: molecule.provenance,
        simhash: '0',
        embedding: ZERO_VECTOR_STR,
      });

      // Prepare atomic entities
      for (const entity of molecule.containedEntities) {
        const entityHash = crypto.createHash('sha256').update(entity).digest('hex').substring(0, 16);
        const atomId = `atom_${id}_${entityHash}`;
        const atomHash = crypto.createHash('sha256').update(entity).digest('hex');

        // Truncate entity tag
        const entityTagRaw = `entity:${entity.toLowerCase()}`;
        const entityTag = entityTagRaw.length > 255 ? entityTagRaw.substring(0, 255) : entityTagRaw;

        allAtomsToInsert.push({
          id: atomId,
          timestamp,
          content: entity,
          source_path: `${source}_entities`,
          source_id: id,
          sequence: 0,
          type: 'atomic_entity',
          hash: atomHash,
          buckets: [...buckets, 'entities'],
          tags: [entityTag, ...molecule.semanticTags.map((tag: string) => tag.replace('#', ''))],
          epochs: [],
          provenance: 'internal',
          simhash: '0',
          embedding: ZERO_VECTOR_STR,
        });
      }
    }

    // Database Transaction
    await db.run('BEGIN');

    try {
      // Bulk Insert Atoms
      if (allAtomsToInsert.length > 0) {
        // Deduplicate by ID
        const uniqueAtomsMap = new Map<string, any>();
        for (const atom of allAtomsToInsert) {
          if (!uniqueAtomsMap.has(atom.id)) {
            uniqueAtomsMap.set(atom.id, atom);
          }
        }
        const uniqueAtoms = Array.from(uniqueAtomsMap.values());

        const ATOM_BATCH_SIZE = 100; // Smaller batch size to be safe
        for (let i = 0; i < uniqueAtoms.length; i += ATOM_BATCH_SIZE) {
          const batch = uniqueAtoms.slice(i, i + ATOM_BATCH_SIZE);
          const atomValues: any[] = [];
          const atomPlaceholders: string[] = [];
          let pIdx = 1;

          for (const atom of batch) {
            atomPlaceholders.push(`($${pIdx}, $${pIdx + 1}, $${pIdx + 2}, $${pIdx + 3}, $${pIdx + 4}, $${pIdx + 5}, $${pIdx + 6}, $${pIdx + 7}, $${pIdx + 8}, $${pIdx + 9}, $${pIdx + 10}, $${pIdx + 11}, $${pIdx + 12}, $${pIdx + 13})`);
            atomValues.push(
              atom.id, atom.timestamp, atom.content, atom.source_path, atom.source_id,
              atom.sequence, atom.type, atom.hash, atom.buckets, atom.tags,
              atom.epochs, atom.provenance, atom.simhash, atom.embedding,
            );
            pIdx += 14;
          }

          const atomQuery = `
            INSERT INTO atoms (id, timestamp, content, source_path, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding)
            VALUES ${atomPlaceholders.join(', ')}
            ON CONFLICT (id) DO UPDATE SET
              content = EXCLUDED.content,
              timestamp = EXCLUDED.timestamp,
              source_path = EXCLUDED.source_path,
              source_id = EXCLUDED.source_id,
              sequence = EXCLUDED.sequence,
              type = EXCLUDED.type,
              hash = EXCLUDED.hash,
              buckets = EXCLUDED.buckets,
              tags = EXCLUDED.tags,
              epochs = EXCLUDED.epochs,
              provenance = EXCLUDED.provenance,
              simhash = EXCLUDED.simhash,
              embedding = EXCLUDED.embedding
          `;

          await db.run(atomQuery, atomValues);
        }
      }

      // Bulk Insert Tags
      const allTagEntries: any[] = [];
      const tagEntrySet = new Set<string>();

      for (const atom of allAtomsToInsert) {
        for (const bucket of atom.buckets) {
          for (const tag of atom.tags) {
            if (!tag || tag.length > 255) continue;
            const entryKey = `${atom.id}-${tag}-${bucket}`;
            if (!tagEntrySet.has(entryKey)) {
              tagEntrySet.add(entryKey);
              allTagEntries.push({ atomId: atom.id, tag, bucket });
            }
          }
        }
      }

      if (allTagEntries.length > 0) {
        const TAG_BATCH_SIZE = 500;
        for (let i = 0; i < allTagEntries.length; i += TAG_BATCH_SIZE) {
          const batch = allTagEntries.slice(i, i + TAG_BATCH_SIZE);
          const tagValues: any[] = [];
          const tagPlaceholders: string[] = [];
          let pIdx = 1;

          for (const entry of batch) {
            tagPlaceholders.push(`($${pIdx}, $${pIdx + 1}, $${pIdx + 2})`);
            tagValues.push(entry.atomId, entry.tag, entry.bucket);
            pIdx += 3;
          }

          const tagQuery = `
            INSERT INTO tags (atom_id, tag, bucket)
            VALUES ${tagPlaceholders.join(', ')}
            ON CONFLICT (atom_id, tag, bucket) DO NOTHING
          `;

          await db.run(tagQuery, tagValues);
        }
      }

      await db.run('COMMIT');
      timer.logTotalAndReset(`Saved batch of ${molecules.length} molecules`);
      return {
        status: 'success',
        message: `Saved ${molecules.length} molecules with ${molecules.reduce((sum, m) => sum + m.containedEntities.length, 0)} entities`,
      };

    } catch (error) {
      console.error('[IngestionService] Database transaction error:', error);
      await db.run('ROLLBACK');
      throw error;
    }
  }

  /**
   * Split content into semantic molecules (text chunks)
   * This replaces the old atomizer logic
   */
  private splitIntoMolecules(content: string): string[] {
    // Split by paragraphs or sentences, preserving semantic meaning
    // This is a simplified version - could be enhanced with more sophisticated NLP

    // First, try to split by paragraphs
    const paragraphs = content.split(/\n\s*\n/).filter(p => p.trim().length > 0);

    // If paragraphs are too long, split further by sentences
    const chunks: string[] = [];
    for (const paragraph of paragraphs) {
      if (paragraph.length <= 500) { // Max length for a semantic molecule
        chunks.push(paragraph.trim());
      } else {
        // Split long paragraphs into sentences
        const sentences = this.splitIntoSentences(paragraph);
        let currentChunk = '';

        for (const sentence of sentences) {
          if ((currentChunk + ' ' + sentence).length > 500) {
            if (currentChunk) {
              chunks.push(currentChunk.trim());
            }
            currentChunk = sentence;
          } else {
            currentChunk += (currentChunk ? ' ' : '') + sentence;
          }
        }

        if (currentChunk) {
          chunks.push(currentChunk.trim());
        }
      }
    }

    return chunks.filter(chunk => chunk.length > 10); // Filter out very short chunks
  }

  /**
   * Split text into sentences
   */
  private splitIntoSentences(text: string): string[] {
    // Simple sentence splitting - could be enhanced with NLP
    return text
      .split(/(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s+/g)
      .map(s => s.trim())
      .filter(s => s.length > 0);
  }

  /**
   * Process a single text chunk into a semantic molecule
   */
  public async processSingleChunk(
    content: string,
    source: string,
    timestamp: number = Date.now(),
  ): Promise<SemanticMolecule> {
    return await this.moleculeProcessor.processTextChunk(content, source, timestamp);
  }

  /**
   * Ingest large content by automatically chunking it into smaller pieces
   * HEAVILY OPTIMIZED: Process all chunks in parallel with maximum concurrency and use single bulk database operation
   */
  private async ingestLargeContent(
    content: string,
    source: string,
    type: string = 'text',
    bucket: string = 'default',
    buckets: string[] = [],
    tags: string[] = [],
  ): Promise<{ status: string; id: string; message: string }> {
    const allBuckets = bucket ? [...buckets, bucket] : buckets;
    const chunkSize = 100 * 1024; // Reduced to 100KB to prevent memory issues with PGlite while maintaining reasonable performance
    const overlapSize = 1 * 1024; // Reduced overlap to 1KB to minimize redundancy

    const chunks: string[] = [];
    let start = 0;

    while (start < content.length) {
      let end = start + chunkSize;

      // If we're near the end, just take the remainder
      if (end >= content.length) {
        end = content.length;
      } else {
        // Try to find a good break point (sentence or paragraph boundary)
        let breakPoint = end;
        const searchWindow = content.substring(end, Math.min(end + 5000, content.length));

        // Look for a good break point
        const paragraphBreak = searchWindow.lastIndexOf('\n\n');
        const sentenceBreak = searchWindow.lastIndexOf('. ');
        const newlineBreak = searchWindow.lastIndexOf('\n');

        // Choose the closest appropriate break point
        if (paragraphBreak !== -1) {
          breakPoint = end + paragraphBreak + 2; // +2 for \n\n
        } else if (sentenceBreak !== -1) {
          breakPoint = end + sentenceBreak + 2; // +2 for '. '
        } else if (newlineBreak !== -1) {
          breakPoint = end + newlineBreak + 1; // +1 for '\n'
        } else {
          // If no good break point found, just break at chunkSize
          breakPoint = end;
        }

        // Ensure we don't go beyond the content length
        breakPoint = Math.min(breakPoint, content.length);

        // If the break point is too close to start, just break at chunkSize
        if (breakPoint - start < chunkSize * 0.5) {
          breakPoint = Math.min(start + chunkSize, content.length);
        }

        end = breakPoint;
      }

      // Add overlap from previous chunk if not the first chunk
      const overlapStart = start > 0 ? Math.max(0, start - overlapSize) : start;
      const chunk = content.substring(overlapStart, end);

      chunks.push(chunk);
      start = end;
    }

    console.log(`[IngestionService] Split large content (${content.length} chars) into ${chunks.length} chunks of ~${Math.round(chunkSize / 1024)}KB each`);

    // STREAMING BATCH IMPLEMENTATION

    // We process chunks in groups (Strides) to avoid OOM and CPU starvation
    // Since NLP is CPU-bound, parallel processing of batches doesn't help throughput and only hurts RAM/GC.
    // Process 1 chunk (100KB) at a time to ensure maximum stability and lowest memory footprint.
    const BATCH_SIZE = 1; // Reduced from 50 to 1 for serial processing of large chunks
    let totalMolecules = 0;
    let totalEntities = 0;

    console.log(`[IngestionService] Split large content (${content.length} chars) into ${chunks.length} chunks. Processing in batches of ${BATCH_SIZE}...`);

    for (let i = 0; i < chunks.length; i += BATCH_SIZE) {
      const batchChunks = chunks.slice(i, i + BATCH_SIZE);
      console.log(`[IngestionService] Processing batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(chunks.length / BATCH_SIZE)} (${batchChunks.length} chunks)...`);

      // 1. Process text chunks into molecules (Parallel within the batch)
      const batchPromptResults = await Promise.all(
        batchChunks.map(async (chunk, batchIndex) => {
          const globalIndex = i + batchIndex;
          const chunkSource = `${source}_chunk_${globalIndex + 1}_of_${chunks.length}`;

          const textChunks = this.splitIntoMolecules(chunk);
          const chunksWithMetadata = textChunks.map((textChunk, idx) => ({
            content: textChunk,
            source: `${chunkSource}_molecule_${idx}`,
            timestamp: Date.now() + globalIndex * 1000 + idx,
            provenance: 'external',
          }));

          return await this.moleculeProcessor.processTextChunks(chunksWithMetadata);
        }),
      );

      // Flatten the batch results
      const batchMolecules = batchPromptResults.flat();

      if (batchMolecules.length > 0) {
        // 2. Save this batch immediately to releasing memory
        await this.saveMoleculesBatched([batchMolecules], source, type, allBuckets, tags);

        totalMolecules += batchMolecules.length;
        totalEntities += batchMolecules.reduce((sum, m) => sum + m.containedEntities.length, 0);

        // Optional: Hint at GC (not available in standard JS, but ensuring scope clear helps)
      }
    }

    return {
      status: 'success',
      id: `multi_chunk_${Date.now()}`,
      message: `Processed large content in ${chunks.length} chunks (streaming), ingested ${totalMolecules} semantic molecules with ${totalEntities} atomic entities`,
    };
  }

  /**
   * Internal method to ingest a single chunk without length validation
   * Optimized for Big O performance using Batched Transactions
   */
  private async ingestSingleChunk(
    content: string,
    source: string,
    type: string = 'text',
    bucket: string = 'default',
    buckets: string[] = [],
    tags: string[] = [],
  ): Promise<{ status: string; id: string; message: string }> {
    // This method bypasses the length validation to avoid recursion
    try {
      // Handle legacy single-bucket param
      const allBuckets = bucket ? [...buckets, bucket] : buckets;

      // Split content into text chunks (molecules)
      const textChunks = this.splitIntoMolecules(content);

      // Process each chunk into semantic molecules - OPTIMIZED FOR PARALLEL PROCESSING
      const chunksWithMetadata = textChunks.map((chunk, index) => ({
        content: chunk,
        source: `${source}_chunk_${index}`,
        timestamp: Date.now() + index, // Slightly offset timestamps
        provenance: 'external',
      }));

      // Process chunks in parallel to reduce serial processing time
      const semanticMolecules = await Promise.all(
        chunksWithMetadata.map(chunk => this.moleculeProcessor.processTextChunk(
          chunk.content,
          chunk.source,
          chunk.timestamp,
          chunk.provenance,
        )),
      );

      // Batched Ingestion Logic
      // Use Map for deduplication (Fixes "ON CONFLICT... cannot affect row a second time")
      const atomsToInsert = new Map<string, any>();
      const tagsToInsert: { atomId: string, tags: string[], buckets: string[] }[] = [];
      const edgesToInsert: any[] = []; // For variant relationships

      // Optimize: Reuse zero vector string to save RAM
      const ZERO_VECTOR_STR = JSON.stringify(new Array(768).fill(0.1));

      for (const molecule of semanticMolecules) {
        const id = `mol_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        const { timestamp } = molecule;
        const hash = crypto.createHash('sha256').update(molecule.content).digest('hex');

        // Prepare Payload (always happens regardless of vector processing)
        const atomType = type || 'semantic_molecule';
        const embeddingStr = ZERO_VECTOR_STR; // Use pre-computed zero vector string

        atomsToInsert.set(id, {
          id,
          timestamp,
          content: molecule.content,
          source_path: source,
          source_id: source,
          sequence: 0,
          type: atomType,
          hash,
          buckets: allBuckets,
          tags: [...tags, ...molecule.semanticTags.map((tag: string) => tag.replace('#', ''))],
          epochs: [],
          provenance: molecule.provenance,
          simhash: '0',
          embedding: embeddingStr,
          vector_id: null, // No vector ID when not using vectors
        });

        // Prepare Tags for Molecule
        tagsToInsert.push({
          atomId: id,
          tags: [...tags, ...molecule.semanticTags.map((tag: string) => tag.replace('#', ''))],
          buckets: allBuckets,
        });

        // Also store the atomic entities separately if needed
        for (const entity of molecule.containedEntities) {
          // Fix for index size limit: Hash the entity for the ID
          const entityHash = crypto.createHash('sha256').update(entity).digest('hex').substring(0, 16);
          const atomId = `atom_${id}_${entityHash}`;
          const atomHash = crypto.createHash('sha256').update(entity).digest('hex');

          // Truncate entity tag
          const entityTagRaw = `entity:${entity.toLowerCase()}`;
          const entityTag = entityTagRaw.length > 255 ? entityTagRaw.substring(0, 255) : entityTagRaw;

          const entityTags = [entityTag, ...molecule.semanticTags.map((tag: string) => tag.replace('#', ''))];
          const entityBuckets = [...allBuckets, 'entities'];

          // Prepare Payload for Entity
          // DEDUP CHECK: If this entity already exists in the map (from another sentence), ignore duplicate push
          if (!atomsToInsert.has(atomId)) {
            atomsToInsert.set(atomId, {
              id: atomId,
              timestamp,
              content: entity,
              source_path: `${source}_entities`,
              source_id: id,
              sequence: 0,
              type: 'atomic_entity',
              hash: atomHash,
              buckets: entityBuckets,
              tags: entityTags,
              epochs: [],
              provenance: 'internal',
              simhash: '0',
              embedding: ZERO_VECTOR_STR, // Use shared zero vector string
              vector_id: null,
            });

            // Prepare Tags for Entity
            tagsToInsert.push({
              atomId: atomId,
              tags: entityTags,
              buckets: entityBuckets,
            });
          }
        }
      }

      // Execute Batch Transaction
      if (atomsToInsert.size > 0) {
        await db.run('BEGIN');

        try {
          // 1. Bulk Insert Atoms (Optimized batch size)
          const atomList = Array.from(atomsToInsert.values());
          const ATOM_BATCH_SIZE = 500; // Increased batch size for better performance

          for (let i = 0; i < atomList.length; i += ATOM_BATCH_SIZE) {
            const batch = atomList.slice(i, i + ATOM_BATCH_SIZE);
            const atomValues: any[] = [];
            const atomPlaceholders: string[] = [];
            let pIdx = 1;

            for (const atom of batch) {
              atomPlaceholders.push(`($${pIdx}, $${pIdx + 1}, $${pIdx + 2}, $${pIdx + 3}, $${pIdx + 4}, $${pIdx + 5}, $${pIdx + 6}, $${pIdx + 7}, $${pIdx + 8}, $${pIdx + 9}, $${pIdx + 10}, $${pIdx + 11}, $${pIdx + 12}, $${pIdx + 13})`);
              atomValues.push(
                atom.id, atom.timestamp, atom.content, atom.source_path, atom.source_id,
                atom.sequence, atom.type, atom.hash, atom.buckets, atom.tags,
                atom.epochs, atom.provenance, atom.simhash, atom.embedding,
              );
              pIdx += 14;
            }

            const atomQuery = `
              INSERT INTO atoms (id, timestamp, content, source_path, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding)
              VALUES ${atomPlaceholders.join(', ')}
              ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                timestamp = EXCLUDED.timestamp,
                source_path = EXCLUDED.source_path,
                source_id = EXCLUDED.source_id,
                sequence = EXCLUDED.sequence,
                type = EXCLUDED.type,
                hash = EXCLUDED.hash,
                buckets = EXCLUDED.buckets,
                tags = EXCLUDED.tags,
                epochs = EXCLUDED.epochs,
                provenance = EXCLUDED.provenance,
                simhash = EXCLUDED.simhash,
                embedding = EXCLUDED.embedding
            `;

            await db.run(atomQuery, atomValues);
          }

          // 2. Bulk Insert Tags (Optimized batch size)
          const allTagEntries: any[] = [];
          for (const item of tagsToInsert) {
            for (const bucket of item.buckets) {
              for (const tag of item.tags) {
                if (!tag || tag.length > 255) continue;
                allTagEntries.push({ atomId: item.atomId, tag, bucket });
              }
            }
          }

          const TAG_BATCH_SIZE = 1000; // Increased batch size for better performance
          for (let i = 0; i < allTagEntries.length; i += TAG_BATCH_SIZE) {
            const batch = allTagEntries.slice(i, i + TAG_BATCH_SIZE);
            const batchValues: any[] = [];
            const placeholders: string[] = [];
            let pIdx = 1;

            for (const entry of batch) {
              placeholders.push(`($${pIdx}, $${pIdx + 1}, $${pIdx + 2})`);
              batchValues.push(entry.atomId, entry.tag, entry.bucket);
              pIdx += 3;
            }

            if (batchValues.length > 0) {
              const tagQuery = `
                INSERT INTO tags (atom_id, tag, bucket)
                VALUES ${placeholders.join(', ')}
                ON CONFLICT (atom_id, tag, bucket) DO NOTHING
              `;
              await db.run(tagQuery, batchValues);
            }
          }

          // 3. Bulk Insert Edges (Sub-batched)
          if (edgesToInsert.length > 0) {
            const EDGE_BATCH_SIZE = 100; // Increased batch size for better performance
            for (let i = 0; i < edgesToInsert.length; i += EDGE_BATCH_SIZE) {
              const batch = edgesToInsert.slice(i, i + EDGE_BATCH_SIZE);
              const batchValues: any[] = [];
              const placeholders: string[] = [];
              let pIdx = 1;

              for (const edge of batch) {
                placeholders.push(`($${pIdx}, $${pIdx + 1}, $${pIdx + 2}, $${pIdx + 3})`);
                batchValues.push(edge.source, edge.target, edge.relation, edge.weight);
                pIdx += 4;
              }

              const edgeQuery = `
                  INSERT INTO edges (source_id, target_id, relation, weight)
                  VALUES ${placeholders.join(', ')}
                  ON CONFLICT (source_id, target_id, relation) DO NOTHING
              `;
              await db.run(edgeQuery, batchValues);
            }
          }

          await db.run('COMMIT');
        } catch (error) {
          await db.run('ROLLBACK');
          throw error;
        }
      }

      return {
        status: 'success',
        id: semanticMolecules[0]?.id || 'unknown',
        message: `Ingested ${semanticMolecules.length} semantic molecules with ${semanticMolecules.reduce((sum, mol) => sum + mol.containedEntities.length, 0)} atomic entities`,
      };
    } catch (e: any) {
      console.error('[SemanticIngestionService] Single Chunk Ingest Error:', e);
      return { status: 'error', id: 'unknown', message: e.message };
    }
  }


  /**
   * Index tags in the separate tags table for efficient retrieval/filtering
   */
  private async indexTags(atomId: string, tags: string[], buckets: string[]): Promise<void> {
    if (!tags.length || !buckets.length) return;

    // Use a simple Set to deduplicate quickly
    const uniqueEntries = new Set<string>();
    const values: any[] = [];
    const placeholders: string[] = [];
    let i = 1;

    for (const bucket of buckets) {
      for (const tag of tags) {
        if (!tag) continue;
        if (tag.length > 255) continue; // Skip tags that are too long for the index

        const key = `${atomId}:${tag}:${bucket}`;
        if (uniqueEntries.has(key)) continue;
        uniqueEntries.add(key);

        placeholders.push(`($${i}, $${i + 1}, $${i + 2})`);
        values.push(atomId, tag, bucket);
        i += 3;
      }
    }

    if (values.length === 0) return;

    try {
      await db.run(
        `INSERT INTO tags (atom_id, tag, bucket) VALUES ${placeholders.join(', ')}
           ON CONFLICT (atom_id, tag, bucket) DO NOTHING`,
        values,
      );
    } catch (e) {
      // Warn but don't fail ingestion
      console.warn('[SemanticIngestionService] Failed to index tags', e);
    }
  }
}