/**
 * Database Module for Sovereign Context Engine
 *
 * This module manages the CozoDB database connection and provides
 * database operations for the context engine.
 */

console.log('[DB] Loading Config...');
import { config } from '../config/index.js';
console.log('[DB] Creating Require...');
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
console.log('[DB] Requiring cozo-node...');
let cozoNode: any;
try {
  cozoNode = require('cozo-node');
  // cozoNode = require('cozo-node');
  console.log('[DB] cozo-node loaded (Standard Module).');
} catch (e) {
  try {
    // Fallback: Try loading from project root based on platform
    // This allows placing platform-specific binaries in ECE_Core/engine/
    console.log(`[DB] Standard module load failed. Attempting local binary override for platform: ${process.platform}...`);

    if (process.platform === 'win32') {
      const native = require('../../cozo_node_win32.node');
      cozoNode = {
        open_db: (engine: string, path: string, options: any) => native.open_db(engine || 'mem', path || 'data.db', JSON.stringify(options || {})),
        close_db: (id: number) => native.close_db(id),
        query_db: (id: number, script: string, params: any, immutable?: boolean) => new Promise((resolve, reject) => {
          native.query_db(id, script, params || {}, (err: any, result: any) => {
            if (err) {
              try { reject(JSON.parse(err)); } catch (e) { reject(err); }
            } else {
              resolve(result);
            }
          }, !!immutable);
        })
      };
    } else if (process.platform === 'darwin') {
      const native = require('../../cozo_node_darwin.node');
      cozoNode = {
        open_db: (engine: string, path: string, options: any) => native.open_db(engine || 'mem', path || 'data.db', JSON.stringify(options || {})),
        close_db: (id: number) => native.close_db(id),
        query_db: (id: number, script: string, params: any, immutable?: boolean) => new Promise((resolve, reject) => {
          native.query_db(id, script, params || {}, (err: any, result: any) => {
            if (err) {
              try { reject(JSON.parse(err)); } catch (e) { reject(err); }
            } else {
              resolve(result);
            }
          }, !!immutable);
        })
      };
    } else if (process.platform === 'linux') {
      const native = require('../../cozo_node_linux.node');
      cozoNode = {
        open_db: (engine: string, path: string, options: any) => native.open_db(engine || 'mem', path || 'data.db', JSON.stringify(options || {})),
        close_db: (id: number) => native.close_db(id),
        query_db: (id: number, script: string, params: any, immutable?: boolean) => new Promise((resolve, reject) => {
          native.query_db(id, script, params || {}, (err: any, result: any) => {
            if (err) {
              try { reject(JSON.parse(err)); } catch (e) { reject(err); }
            } else {
              resolve(result);
            }
          }, !!immutable);
        })
      };
    } else {
      throw new Error(`Unsupported platform for local binary override: ${process.platform}`);
    }

    console.log(`[DB] Loaded cozo-node from local binary override (${process.platform}).`);
  } catch (e2: any) {
    console.warn(`[DB] WARNING: cozo-node missing (both standard and local). Engine will run in Stateless Mode. Error: ${e2.message}`);
  }
}

class MockDatabase {
  init() { console.log('[MockDB] Initialized (Stateless).'); return Promise.resolve(); }
  close() { console.log('[MockDB] Closed.'); }
  run(_q: string, _p?: any) {
    console.log('[MockDB] Query executed in stateless mode.');
    return Promise.resolve({ rows: [], headers: [] });
  }
  search(_q: string) { return Promise.resolve({ rows: [] }); }
}

export class Database {
  private dbId: string | null = null;

  constructor() {
    // Database connection is now established in init()
  }

  /**
   * Initialize the database with required schemas
   */
  async init() {
    // 0. Initialize the database connection (moved from constructor to prevent import-time crashes)
    if (this.dbId === null) {
      try {
        console.log('[DB] Attempting to open RocksDB backend: ./context.db');
        this.dbId = cozoNode.open_db('rocksdb', './context.db', {});  // Options object for RocksDB
        console.log('[DB] Initialized with RocksDB backend: ./context.db');
      } catch (e: any) {
        const errStr = String(e) + (e.message || '');
        if (errStr.includes('lock file') || errStr.includes('IO error') || errStr.includes('Invalid argument') || errStr.includes('does not exist') || errStr.includes('rocksdb')) {
          console.error('\n[DB] Database corruption or lock detected. Auto-purging...');
          console.error(`[DB] Reason: ${errStr}`);

          try {
            // Close just in case
            try { this.close(); } catch (c) { }

            const fs = await import('fs');
            if (fs.existsSync('./context.db')) fs.rmSync('./context.db', { recursive: true, force: true });
            if (fs.existsSync('./context.db-log')) fs.rmSync('./context.db-log', { force: true });

            console.log('[DB] Purge complete. Retrying initialization...');
            this.dbId = cozoNode.open_db('rocksdb', './context.db', {});
            console.log('[DB] Re-initialization successful.');
            return; // Continue to schema init
          } catch (recoveryError: any) {
            console.error('[DB] CRITICAL: Auto-recovery failed.', recoveryError);
            throw new Error('Database Corrupted & Recovery Failed: ' + errStr);
          }
        }
        throw e;
      }
    }

    // Create the memory table schema
    // We check for existing columns to determine if migration is needed
    try {
      const result = await this.run('::columns memory');
      const columns = result.rows.map((r: any) => r[0]);

      // Check for Level 1 Atomizer fields
      const hasSequence = columns.includes('sequence');
      const hasEmbedding = columns.includes('embedding');
      const hasSourceId = columns.includes('source_id');
      const hasSimhash = columns.includes('simhash');

      if (!hasSequence || !hasEmbedding || !hasSourceId || !hasSimhash) {
        console.log('Migrating memory schema: Adding Atomizer columns...');

        // 1. Fetch old data into memory (Safe subset of columns)
        // We dynamic build the query to avoid requesting missing columns
        const simhashField = hasSimhash ? ", simhash" : "";

        const oldDataResult = await this.run(`
          ?[id, timestamp, content, source, provenance${simhashField}] :=
          *memory{id, timestamp, content, source, provenance${simhashField}}
        `);

        console.log(`[DB] Migrating ${oldDataResult.rows.length} rows...`);

        // 2. Drop old indices and table
        try {
          console.log('[DB] Removing indices...');
          try { await this.run('::remove memory:knn'); } catch (e) { }
          try { await this.run('::remove memory:vec_idx'); } catch (e) { } // Legacy
          try { await this.run('::remove memory:content_fts'); } catch (e) { }
        } catch (e: any) {
          console.log(`[DB] Index removal warning: ${e.message}`);
        }

        console.log('[DB] Removing old table...');
        await this.run('::remove memory');

        // 3. Create new table
        await this.run(`
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
            simhash: String,
            embedding: <F32; ${config.MODELS.EMBEDDING_DIM}>
          }
        `);

        // 4. Re-insert data with defaults
        if (oldDataResult.rows.length > 0) {
          const crypto = await import('crypto'); // Dynamic import for hash generation

          const newData = oldDataResult.rows.map((row: any) => {
            // row: [id, timestamp, content, source, provenance, simhash]
            // Note: Handling old rows without simhash -> default "0"
            const content = row[2] || "";
            const hash = crypto.createHash('md5').update(content).digest('hex');
            // If simhash was fetched, it's at index 5. If not, it's undefined -> "0"
            const oldSimhash = hasSimhash ? row[5] : "0";
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
              oldSimhash, // simhash
              new Array(config.MODELS.EMBEDDING_DIM).fill(0.0) // embedding (reset to zero to force re-embed)
            ];
          });

          // Batch insert
          const chunkSize = 100;
          for (let i = 0; i < newData.length; i += chunkSize) {
            const chunk = newData.slice(i, i + chunkSize);
            await this.run(`
               ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding] <- $data
               :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding}
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
          await this.run(`
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
                simhash: String,
                embedding: <F32; ${config.MODELS.EMBEDDING_DIM}>
            }
        `);
          console.log('Memory table initialized');

          // REMOVED: Vector index is no longer used. Tag-Walker is the primary retrieval method.
          // Explicitly remove it if it exists to save resources and prevent zero-vector errors.
          try {
            await this.run('::remove memory:knn');
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
          try { this.close(); } catch (c) { }

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
          this.dbId = cozoNode.open_db('rocksdb', './context.db', {});
          await this.init(); // Recursive retry
          return;
        }
        throw e;
      }
    }

    // Create Source Table (Container)
    try {
      await this.run(`
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
      await this.run(`
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
      await this.run(`
        :create parent_of {
           parent_id: String,
           child_id: String,
           weight: Float
        }
      `);
    } catch (e: any) { if (!e.message?.includes('conflict') && !e.message?.includes('Duplicate')) throw e; }

    // Create Engram table (Lexical Sidecar)
    try {
      await this.run(`
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
      await this.run(`
        ::fts create memory:content_fts {
          extractor: content,
          tokenizer: Simple,
          filters: [Lowercase]
        }
      `);
    } catch (e: any) {
      if (!e.message?.includes('conflict') && !e.message?.includes('Duplicate') && !e.message?.includes('already exists')) throw e;
    }

    // ----------------------------------------------------
    // CRITICAL: Performance Indices (Tags, Buckets, Epochs)
    // ----------------------------------------------------
    // We attempt to create HNSW or basic indices for these list columns if supported,
    // or standard indices for scalar columns.
    // Since CozoDB 0.7+ supports list indexing via JSON ops or specific index types,
    // we will start with basic covering indices if possible, or skip if complex.
    //
    // Update: CozoDB `::index create` works on specific columns.
    // For List columns, it indexes the list AS A VALUE unless we use specific techniques.
    // However, filtering `tag in tags` usually triggers a scan.
    // A better approach for specific performance is ensuring we rely on the `::index` if supported.
    // We will just try to create them. If it fails (due to list type), we log warning.

    const indices = ['buckets', 'tags', 'epochs'];
    for (const idx of indices) {
      try {
        // Create a standard index (non-unique). 
        // Note: Indexing a List column in RocksDB backend might just index the JSON string.
        // Effectively this speeds up exact match of the WHOLE list, but maybe not `contains`.
        // BUT, it's better than nothing for equality checks.
        await this.run(`::index create memory:${idx} { keys: [${idx}] }`);
        console.log(`[DB] Index created: memory:${idx}`);
      } catch (e: any) {
        // Ignore "already exists"
        if (!e.message?.includes('Duplicate') && !e.message?.includes('already exists')) {
          // console.warn(`[DB] Could not create index for ${idx} (might be expected for Lists): ${e.message}`);
        }
      }
    }

    console.log('Database initialized successfully');
  }

  /**
   * Close the database connection
   */
  async close() {
    // Close the database connection
    if (this.dbId) {
      cozoNode.close_db(this.dbId);
    }
  }

  /**
   * Run a query against the database
   */
  async run(q: string, p?: any) {
    const { config } = await import('../config/index.js');
    if (config.LOG_LEVEL === 'DEBUG') {
      if (q.includes(':put') || q.includes(':insert')) {
        console.log(`[DB] Executing Write: ${q.substring(0, 50)}... Params keys: ${p ? Object.keys(p) : 'none'}`);
        if (p && p.data) console.log(`[DB] Data rows: ${p.data.length}`);
      }
    }

    try {
      if (this.dbId === null) {
        throw new Error('Database not initialized');
      }
      const result = cozoNode.query_db(this.dbId, q, p !== undefined ? p : {});
      return result;
    } catch (e: any) {
      console.error(`[DB] Query Failed: ${e.message}`);
      console.error(`[DB] Query: ${q}`);
      throw e;
    }
  }

  /**
   * Run a FTS search query
   */
  async search(query: string) {
    if (this.dbId === null) {
      throw new Error('Database not initialized');
    }
    return cozoNode.query_db(this.dbId, query, {});
  }
}

// Export a singleton instance
export const db = cozoNode ? new Database() : new MockDatabase() as unknown as Database;