/**
 * Database Module for Sovereign Context Engine
 * 
 * This module manages the CozoDB database connection and provides
 * database operations for the context engine.
 */

import { CozoDb } from 'cozo-node';
import { config } from '../config/index.js';

export class Database {
  private db: CozoDb;

  constructor() {
    // Initialize the database with RocksDB persistent backend
    this.db = new CozoDb('rocksdb', './context.db');
    console.log('[DB] Initialized with RocksDB backend: ./context.db');
  }

  /**
   * Initialize the database with required schemas
   */
  async init() {
    // Create the memory table schema
    // We check for existing columns to determine if migration is needed
    try {
      const result = await this.db.run('::columns memory');
      const columns = result.rows.map((r: any) => r[0]);

      // Check for Level 1 Atomizer fields
      const hasSequence = columns.includes('sequence');
      const hasEmbedding = columns.includes('embedding');
      const hasSourceId = columns.includes('source_id');

      if (!hasSequence || !hasEmbedding || !hasSourceId) {
        console.log('Migrating memory schema: Adding Atomizer columns...');

        // 1. Fetch old data into memory (Safe subset of columns)
        // We only fallback to what we know existed in v2
        const oldDataResult = await this.db.run(`
          ?[id, timestamp, content, source, provenance] := 
          *memory{id, timestamp, content, source, provenance}
        `);

        console.log(`[DB] Migrating ${oldDataResult.rows.length} rows...`);

        // 2. Drop old indices and table
        try {
          console.log('[DB] Removing indices...');
          try { await this.db.run('::remove memory:knn'); } catch (e) { }
          try { await this.db.run('::remove memory:vec_idx'); } catch (e) { } // Legacy
          try { await this.db.run('::remove memory:content_fts'); } catch (e) { }
        } catch (e: any) {
          console.log(`[DB] Index removal warning: ${e.message}`);
        }

        console.log('[DB] Removing old table...');
        await this.db.run('::remove memory');

        // 3. Create new table
        await this.db.run(`
          :create memory {
            id: String
            =>
            timestamp: Float,
            content: String,
            source: String,
            source_id: String,
            sequence: Int,
            type: String,
            hash: String,
            buckets: [String],
            epochs: [String],
            tags: [String],
            provenance: String,
            embedding: <F32; ${config.MODELS.EMBEDDING_DIM}>
          }
        `);

        // 4. Re-insert data with defaults
        if (oldDataResult.rows.length > 0) {
          const crypto = await import('crypto'); // Dynamic import for hash generation

          const newData = oldDataResult.rows.map((row: any) => {
            // row: [id, timestamp, content, source, provenance]
            const content = row[2] || "";
            const hash = crypto.createHash('md5').update(content).digest('hex');

            return [
              row[0], // id
              row[1] || Date.now(), // timestamp
              content, // content
              row[3] || "unknown", // source
              row[3] || "unknown", // source_id (default to source path)
              0,      // sequence
              'fragment', // type (default)
              hash, // hash (calculated)
              [], // buckets
              [], // tags
              [], // epochs
              row[4] || "{}", // provenance
              new Array(config.MODELS.EMBEDDING_DIM).fill(0.0) // embedding (reset to zero to force re-embed)
            ];
          });

          // Batch insert
          const chunkSize = 100;
          for (let i = 0; i < newData.length; i += chunkSize) {
            const chunk = newData.slice(i, i + chunkSize);
            await this.db.run(`
               ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, embedding] <- $data
               :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, embedding}
             `, { data: chunk });
          }
        }
        console.log('[DB] Migration complete.');
      }
    } catch (e: any) {
      // Create fresh if not exists
      if (e.message && (e.message.includes('RelNotFound') || e.message.includes('not found') || e.message.includes('Cannot find'))) {
        console.log('[DB] Creating memory table from scratch...');
        // Create Memory Table
        try {
          await this.db.run(`
            :create memory {
                id: String
                =>
                timestamp: Float,
                content: String,
                source: String,
                source_id: String,
                sequence: Int,
                type: String,
                hash: String,
                buckets: [String],
                epochs: [String],
                tags: [String],
                provenance: String,
                embedding: <F32; ${config.MODELS.EMBEDDING_DIM}>
            }
        `);
          console.log('Memory table initialized');

          // REMOVED: Vector index (HNSW) is no longer used. Tag-Walker is the primary retrieval method.
          // Explicitly remove it if it exists to save resources and prevent zero-vector errors.
          try {
            await this.db.run('::remove memory:knn');
            console.log('[DB] Legacy vector index (memory:knn) removed.');
          } catch (e) {
            // Ignore if index doesn't exist
          }

        } catch (createError: any) {
          console.error(`[DB] Failed to create memory table: ${createError.message}`);

          // Check if table already exists (not an error technically, but we might want schema check)
          if (!createError.message?.includes('Duplicate') && !createError.display?.includes('Duplicate')) {
            throw createError;
          }
        }
      } else {
        console.log(`[DB] Schema check/migration failed: ${e.message}`);
        if (e.message.includes('indices attached') || e.message.includes('Index lock')) {
          console.log('[DB] Index lock detected. Automatically purging corrupted database...');

          // Close existing connection
          try { this.db.close(); } catch (c) { }

          // Give OS time to release file locks (Windows is slow)
          await new Promise(resolve => setTimeout(resolve, 1000));

          const fs = await import('fs');
          try {
            // RocksDB creates a DIRECTORY, not a file. unlinkSync fails on dirs.
            if (fs.existsSync('./context.db')) fs.rmSync('./context.db', { recursive: true, force: true });
            if (fs.existsSync('./context.db-log')) fs.rmSync('./context.db-log', { force: true });
            if (fs.existsSync('./context.db-lock')) fs.rmSync('./context.db-lock', { force: true });
          } catch (err: any) {
            console.error('[DB] Failed to auto-purge:', err.message);
            console.error('[DB] Please MANUALLY delete the "context.db" folder and restart.');
            process.exit(1); // Do not recurse if FS fails, just exit.
          }

          // Re-initialize fresh
          console.log('[DB] Re-initializing fresh database...');
          this.db = new CozoDb('rocksdb', './context.db');
          await this.init(); // Recursive retry
          return;
        }
        throw e;
      }
    }

    // Create Source Table (Container)
    try {
      await this.db.run(`
        :create source {
           path: String,
           hash: String,
           total_atoms: Int,
           last_ingest: Float
        }
      `);
    } catch (e: any) { if (!e.message?.includes('conflict') && !e.message?.includes('Duplicate')) throw e; }

    // Create Summary Node Table (Level 2/3: Episodes/Epochs)
    try {
      await this.db.run(`
        :create summary_node {
           id: String,
           type: String,
           content: String,
           span_start: Float,
           span_end: Float,
           embedding: <F32; 384>
        }
      `);
    } catch (e: any) { if (!e.message?.includes('conflict') && !e.message?.includes('Duplicate')) throw e; }

    // Create Parent_Of Edge Table (Hierarchy)
    try {
      await this.db.run(`
        :create parent_of {
           parent_id: String,
           child_id: String,
           weight: Float
        }
      `);
    } catch (e: any) { if (!e.message?.includes('conflict') && !e.message?.includes('Duplicate')) throw e; }

    // Create Engram table (Lexical Sidecar)
    try {
      await this.db.run(`
        :create engrams {
          key: String,
          value: String
        }
      `);
    } catch (e: any) {
      if (!e.message?.includes('conflict') && !e.message?.includes('Duplicate')) throw e;
    }

    // Create FTS index for content
    try {
      await this.db.run(`
        ::fts create memory:content_fts {
          extractor: content,
          tokenizer: Simple,
          filters: [Lowercase]
        }
      `);
    } catch (e: any) {
      if (!e.message?.includes('conflict') && !e.message?.includes('Duplicate') && !e.message?.includes('already exists')) throw e;
    }

    console.log('Database initialized successfully');
  }

  /**
   * Close the database connection
   */
  async close() {
    // Close the database connection
    this.db.close();
  }

  /**
   * Run a query against the database
   */
  async run(query: string, params?: any) {
    const { config } = await import('../config/index.js');
    if (config.LOG_LEVEL === 'DEBUG') {
      if (query.includes(':put') || query.includes(':insert')) {
        console.log(`[DB] Executing Write: ${query.substring(0, 50)}... Params keys: ${params ? Object.keys(params) : 'none'}`);
        if (params && params.data) console.log(`[DB] Data rows: ${params.data.length}`);
      }
    }

    try {
      const result = await this.db.run(query, params);
      return result;
    } catch (e: any) {
      console.error(`[DB] Query Failed: ${e.message}`);
      console.error(`[DB] Query: ${query}`);
      throw e;
    }
  }

  /**
   * Run a FTS search query
   */
  async search(query: string) {
    return await this.db.run(query);
  }
}

// Export a singleton instance
export const db = new Database();