/**
 * Database Module for Sovereign Context Engine
 *
 * This module manages the PGlite database connection and provides
 * database operations for the context engine.
 */

import { config } from '../config/index.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { PGlite } from '@electric-sql/pglite';

const __filename = fileURLToPath(import.meta.url);

import { pathManager } from '../utils/path-manager.js';
import { dbSerializer } from '../utils/db-connection-serializer.js';

export class Database {
  private dbInstance: any = null;
  private _isInitialized: boolean = false;
  private inTransaction: boolean = false;
  private preparedStatements: Map<string, any> = new Map();

  constructor() {
    // Database connection is now established in init()
  }

  get isInitialized(): boolean {
    return this._isInitialized;
  }

  /**
   * Begin a transaction
   *
   * NOTE: Nested transactions are not supported. If a transaction is already
   * open, this call is a no-op. PGlite does not support SAVEPOINTs via this
   * wrapper. For nested transactional logic, use raw SQL SAVEPOINTs:
   *   await db.run('SAVEPOINT my_save');
   *   ...on error... await db.run('ROLLBACK TO SAVEPOINT my_save');
   */
  async beginTransaction(): Promise<void> {
    if (!this.inTransaction) {
      await this.run('BEGIN');
      this.inTransaction = true;
    }
  }

  /**
   * Commit a transaction
   */
  async commit(): Promise<void> {
    if (this.inTransaction) {
      await this.run('COMMIT');
      this.inTransaction = false;
    }
  }

  /**
   * Rollback a transaction
   */
  async rollback(): Promise<void> {
    if (this.inTransaction) {
      await this.run('ROLLBACK');
      this.inTransaction = false;
    }
  }

  /**
   * Execute a function within a transaction
   */
  async transaction<T>(fn: () => Promise<T>): Promise<T> {
    await this.beginTransaction();
    try {
      const result = await fn();
      await this.commit();
      return result;
    } catch (error) {
      await this.rollback();
      throw error;
    }
  }

  /**
   * Initialize the database with required schemas
   * Wipes existing database on startup to prevent corruption
   */
  async init(): Promise<void> {
    // 0. Initialize the database connection
    if (this.dbInstance === null) {
      // Use pathManager for consistent absolute path (Standard 051)
      const dbPath = process.env.PGLITE_DB_PATH || pathManager.getDatabasePath();

      // Wipe and recreate the database directory on every startup (Standard 051 - Ephemeral Index)
      // Controlled by user_settings.json: database.wipe_on_startup (default: true)
      const shouldWipe = config.DATABASE?.WIPE_ON_STARTUP !== false;
      try {
        console.log(`[DB] Using database directory: ${dbPath}`);

        if (shouldWipe) {
          // Remove existing database directory to prevent corruption from unclean shutdowns
          if (fs.existsSync(dbPath)) {
            console.log(`[DB] Removing existing database directory (preventing corruption): ${dbPath}`);
            try {
              fs.rmSync(dbPath, { recursive: true, force: true });
              console.log('[DB] Old database directory removed successfully');
            } catch (rmError: any) {
              console.warn(`[DB] Warning: Could not remove old database directory: ${rmError.message}`);
              console.warn('[DB] Will attempt to overwrite on init');
            }
          }

          // Also wipe mirrored_brain to prevent corrupted files from accumulating
          const mirroredBrainPath = path.join(path.dirname(dbPath), 'mirrored_brain');
          if (fs.existsSync(mirroredBrainPath)) {
            console.log('[DB] Clearing mirrored_brain directory (regenerated from inbox on start)');
            try {
              const entries = fs.readdirSync(mirroredBrainPath);
              for (const entry of entries) {
                const entryPath = path.join(mirroredBrainPath, entry);
                fs.rmSync(entryPath, { recursive: true, force: true });
              }
              console.log(`[DB] mirrored_brain cleared (${entries.length} entries removed)`);
            } catch (mirrorError: any) {
              console.warn(`[DB] Warning: Could not clear mirrored_brain: ${mirrorError.message}`);
            }
          }
        } else {
          console.log('[DB] Retaining existing database (wipe_on_startup=false). Index may be stale.');
        }

        console.log(`[DB] Database directory ready: ${dbPath}`);
      } catch (cleanupError: any) {
        console.error('[DB] Error during database directory preparation:', cleanupError);
        // Don't crash if wipe fails, just try to continue
      }

      try {
        console.log(`[DB] Initializing PGlite at: ${dbPath}`);
        
        // Read memory settings from config (with safe defaults)
        const sharedBuffers = `${config.DATABASE?.SHARED_BUFFERS_MB || 64}MB`;
        const effectiveCache = `${config.DATABASE?.EFFECTIVE_CACHE_SIZE_MB || 128}MB`;
        const workMem = `${config.DATABASE?.WORK_MEM_MB || 8}MB`;
        const maintWorkMem = `${config.DATABASE?.MAINTENANCE_WORK_MEM_MB || 32}MB`;

        // Initialize PGlite with optimized memory settings (Standard 127)
        // Memory reduction tactics for embedded deployment (phones + laptops)
        this.dbInstance = await new PGlite(dbPath, {
          // Don't set maxMemory limit - let Node.js GC manage heap (6GB from --max-old-space-size)
          // OOM prevention is handled by:
          // 1. Search serialization (one search at a time)
          // 2. Memory pressure detection (downgrade max-recall if heap >3.2GB)
          // 3. Forced GC after ingestion and search completion
          relaxedDurability: true, // Skip fsync during ingestion (Standard 059)
          settings: {
            // Reduce PGlite WASM buffer cache from default 1GB
            'shared_buffers': sharedBuffers,
            // Bound planner's estimate to prevent unbounded CTE memory
            'effective_cache_size': effectiveCache,
            // Per-operation memory for sorts/hashes (physics walker CTEs)
            'work_mem': workMem,
            // Memory for VACUUM, CREATE INDEX, etc.
            'maintenance_work_mem': maintWorkMem,
            // WAL buffer size
            'wal_buffers': '4MB',
            // Spread checkpoint writes over 90% of checkpoint interval
            'checkpoint_completion_target': 0.9,
            // Random page access cost estimate (helps planner choose seq scans)
            'random_page_cost': 1.1,
            // Sequential scan cost estimate
            'seq_page_cost': 1.0,
          },
        });

        console.log(`[DB] PGlite initialized successfully: ${dbPath}`);
        console.log(`[DB] Memory settings: shared_buffers=${sharedBuffers}, effective_cache_size=${effectiveCache}, work_mem=${workMem}`);

        // Additional runtime memory bounds (applied after init)
        // These complement the constructor settings above
        await this.dbInstance.exec(`SET effective_cache_size = '${effectiveCache}'`);
        await this.dbInstance.exec(`SET work_mem = '${workMem}'`);
        await this.dbInstance.exec(`SET maintenance_work_mem = '${maintWorkMem}'`);
      } catch (e: any) {
        console.error(`[DB] Failed to initialize PGlite: ${e.message}`);
        throw e;
      }
    }

    // Create Synonyms table for automatic query expansion
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS synonyms (
          term TEXT PRIMARY KEY,
          synonyms TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
      `);
      console.log("[DB] 'synonyms' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating synonyms table:', e);
      throw e;
    }

    // Create atoms table schema - simplified for PGlite compatibility
    try {
      // Create sequence for vector_ids
      await this.run('CREATE SEQUENCE IF NOT EXISTS vector_id_seq START 1;');

      await this.run(`
        CREATE TABLE IF NOT EXISTS atoms (
          id TEXT PRIMARY KEY,
          source_path TEXT,
          timestamp REAL,
          simhash TEXT,
          embedding TEXT,
          vector_id BIGINT,
          provenance TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
      `);

      console.log("[DB] 'atoms' table initialized.");

      // Add missing columns if they don't exist (for existing databases)
      const columnsToAdd = [
        { name: 'vector_id', type: 'BIGINT' },
        { name: 'buckets', type: 'TEXT[]' },
        { name: 'tags', type: 'TEXT[]' },
        { name: 'epochs', type: 'TEXT[]' },
        { name: 'sequence', type: 'INTEGER' },
        { name: 'type', type: 'TEXT' },
        { name: 'hash', type: 'TEXT' },
        { name: 'molecular_signature', type: 'TEXT' },
        { name: 'compound_id', type: 'TEXT' },
        { name: 'start_byte', type: 'INTEGER' },
        { name: 'end_byte', type: 'INTEGER' },
        { name: 'numeric_value', type: 'REAL' },
        { name: 'numeric_unit', type: 'TEXT' },
        { name: 'source_id', type: 'TEXT' },
        { name: 'tags', type: 'JSONB' },
        { name: 'entities', type: 'JSONB' },
        { name: 'payload', type: 'JSONB' }, // Crystal Atom Structure (Hybrid Architecture)
        { name: 'content', type: 'TEXT' }, // Atom content (Standard 051)
      ];

      for (const col of columnsToAdd) {
        try {
          await this.run(`ALTER TABLE atoms ADD COLUMN IF NOT EXISTS ${col.name} ${col.type};`);
        } catch (alterErr: any) {
          // Column might already exist, which is fine
          console.debug(`[DB] Column ${col.name} addition:`, alterErr.message);
        }
      }

      // Add index for compound_id (CRITICAL for Physics Walker)
      try {
        await this.run('CREATE INDEX IF NOT EXISTS idx_atoms_compound_id ON atoms(compound_id);');
      } catch (idxErr: any) {
        console.warn('[DB] Could not create compound_id index:', idxErr.message);
      }
    } catch (e: any) {
      console.error('[DB] Error initializing atoms table:', e);
      throw e;
    }

    // Create the tags table (The "Nervous System")
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS tags (
          atom_id TEXT,
          tag TEXT,
          bucket TEXT,
          PRIMARY KEY (atom_id, tag, bucket)
        );
      `);

      // Create indexes - optimized for PhysicsWalker queries
      try {
        await this.run('CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);');
      } catch (indexErr: any) {
        console.warn('[DB] Could not create tag index:', indexErr.message);
      }
      try {
        await this.run('CREATE INDEX IF NOT EXISTS idx_tags_bucket ON tags(bucket);');
      } catch (indexErr: any) {
        console.warn('[DB] Could not create bucket index:', indexErr.message);
      }
      // NEW INDEX (2026-02-23): For fast atom_id lookups in PhysicsWalker
      try {
        await this.run('CREATE INDEX IF NOT EXISTS idx_tags_atom_id ON tags(atom_id);');
      } catch (indexErr: any) {
        console.warn('[DB] Could not create atom_id index:', indexErr.message);
      }

      console.log("[DB] 'tags' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating tags table:', e);
      throw e;
    }

    // Create Edges table (The Graph Connections)
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS edges (
          source_id TEXT,
          target_id TEXT,
          relation TEXT,
          weight REAL,
          PRIMARY KEY (source_id, target_id, relation)
        );
      `);

      console.log("[DB] 'edges' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating edges table:', e);
      throw e;
    }

    // Create Source Table (Container)
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS sources (
          path TEXT PRIMARY KEY,
          hash TEXT,
          total_atoms INTEGER,
          last_ingest REAL
        );
      `);

      console.log("[DB] 'sources' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating sources table:', e);
      throw e;
    }

    // Create molecules table (The Document Sentences)
    try {
      await this.run(`
          CREATE TABLE IF NOT EXISTS molecules (
            id TEXT PRIMARY KEY,
            content TEXT,
            compound_id TEXT,
            sequence INTEGER,
            start_byte INTEGER,
            end_byte INTEGER,
            type TEXT,
            numeric_value REAL,
            numeric_unit TEXT,
            molecular_signature TEXT,
            embedding TEXT,
            timestamp REAL,
            tags JSONB,
            entities JSONB,
            source_path TEXT,
            provenance TEXT
          );
        `);

      // Add indices for molecules
      try {
        await this.run('CREATE INDEX IF NOT EXISTS idx_molecules_compound ON molecules(compound_id);');
      } catch (idxErr: any) {
        console.warn('[DB] Could not create molecule compound index:', idxErr.message);
      }

      // Ensure new columns exist for existing databases
      const molColumnsToAdd = [
        { name: 'content', type: 'TEXT' },
        { name: 'tags', type: 'JSONB' },
        { name: 'entities', type: 'JSONB' },
        { name: 'source_path', type: 'TEXT' },
        { name: 'provenance', type: 'TEXT' },
      ];

      for (const col of molColumnsToAdd) {
        try {
          await this.run(`ALTER TABLE molecules ADD COLUMN IF NOT EXISTS ${col.name} ${col.type};`);
        } catch (alterErr: any) {
          // Column might already exist
        }
      }

      console.log("[DB] 'molecules' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating molecules table:', e);
      throw e;
    }

    // Compounds table REMOVED - Standard 051 Migration
    // The deprecated compounds table has been removed.
    // All data now flows through atoms/molecules tables with provenance tracking.

    console.log("[DB] ✅ Compounds table creation skipped (Standard 051: Pointer-only storage)");

    // Create Engrams table (Lexical Sidecar)
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS engrams (
          key TEXT PRIMARY KEY,
          value TEXT
        );
      `);

      console.log("[DB] 'engrams' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating engrams table:', e);
      throw e;
    }

    // Create App Settings table (v5.2.0+ Database-Backed Configuration)
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          type TEXT DEFAULT 'string',
          description TEXT,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
      `);
      
      // Index for fast lookups by key prefix
      await this.run('CREATE INDEX IF NOT EXISTS idx_app_settings_key ON app_settings(key)');
      
      console.log("[DB] 'app_settings' table initialized (v5.2.0+).");
    } catch (e: any) {
      console.error('[DB] Error creating app_settings table:', e);
      throw e;
    }

    // Create Atom Positions table (Lazy Molecule Inflation)
    // Tracks where atoms (keywords) appear in compounds for radial inflation
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS atom_positions (
          compound_id TEXT NOT NULL,
          atom_label TEXT NOT NULL,
          byte_offset INTEGER NOT NULL,
          PRIMARY KEY (compound_id, atom_label, byte_offset)
        );
      `);
      await this.run(`
        CREATE INDEX IF NOT EXISTS idx_atom_positions_label 
        ON atom_positions(atom_label);
      `);

      console.log("[DB] 'atom_positions' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating atom_positions table:', e);
      throw e;
    }

    // Create Summary Nodes Table (Dreamer Abstractions)
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS summary_nodes (
          id TEXT PRIMARY KEY,
          type TEXT,
          span_start REAL,
          span_end REAL,
          embedding TEXT
        );
      `);
      console.log("[DB] 'summary_nodes' table initialized.");
    } catch (e: any) {
      console.error('[DB] Error creating summary_nodes table:', e);
      throw e;
    }

    // Create GitHub Repos Table (Standard 115: GitHub Repository Ingestion)
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS github_repos (
          id TEXT PRIMARY KEY,
          owner TEXT NOT NULL,
          repo TEXT NOT NULL,
          branch TEXT DEFAULT 'main',
          bucket TEXT NOT NULL,
          github_url TEXT NOT NULL,
          last_synced_at TIMESTAMP,
          last_sync_status TEXT,
          last_error TEXT,
          total_files INTEGER DEFAULT 0,
          total_atoms INTEGER DEFAULT 0,
          total_size_bytes INTEGER DEFAULT 0,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
      `);
      console.log("[DB] 'github_repos' table initialized.");

      // Create index for owner/repo lookup
      await this.run(`
        CREATE INDEX IF NOT EXISTS idx_github_repos_owner_repo
        ON github_repos(owner, repo);
      `);
    } catch (e: any) {
      console.error('[DB] Error creating github_repos table:', e);
      throw e;
    }

    // Create Distills Table (Standard 016: Distill Versioning)
    // Stores metadata pointers to distill files on disk
    try {
      await this.run(`
        CREATE TABLE IF NOT EXISTS distills (
          id TEXT PRIMARY KEY,
          timestamp TEXT NOT NULL,
          filename TEXT NOT NULL,
          file_path TEXT NOT NULL,
          line_count INTEGER NOT NULL,
          lines_unique INTEGER NOT NULL,
          compression_ratio REAL,
          source_sessions TEXT[],
          source_files TEXT[],
          parameters JSONB,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
      `);
      console.log("[DB] 'distills' table initialized.");

      // Create indexes for common queries
      await this.run(`
        CREATE INDEX IF NOT EXISTS idx_distills_timestamp
        ON distills(timestamp DESC);
      `);
      await this.run(`
        CREATE INDEX IF NOT EXISTS idx_distills_filename
        ON distills(filename);
      `);
      await this.run(`
        CREATE INDEX IF NOT EXISTS idx_distills_source_sessions
        ON distills USING GIN(source_sessions);
      `);
    } catch (e: any) {
      console.error('[DB] Error creating distills table:', e);
      throw e;
    }

    // Create JSONB GIN Index (Crystal Atom Optimization)
    try {
      await this.run(`
        CREATE INDEX IF NOT EXISTS idx_atoms_payload_gin
        ON atoms
        USING GIN (payload);
      `);
      console.log('[DB] GIN index created for payload (Crystal Atom).');
    } catch (e: any) {
      console.warn('[DB] Could not create payload GIN index:', e.message);
    }

    // Mark as initialized after all setup is complete
    this._isInitialized = true;
    console.log('Database initialized successfully');
  }

  /**
   * Close the database connection
   */
  async close() {
    // Close the database connection
    if (this.dbInstance) {
      await this.dbInstance.close();
    }
  }

  /**
   * Run a query against the database (v5.2.0+ serialized)
   *
   * All queries are routed through DbConnectionSerializer to prevent PGlite
   * connection corruption ("cannot drop active portal", deadlocks).
   * Queries execute FIFO — only one runs at a time.
   */
  async run(query: string, params?: any[]) {
    const { config } = await import('../config/index.js');
    if (config.LOG_LEVEL === 'DEBUG') {
      console.log(`[DB] Executing Query: ${query.substring(0, 80)}...`);
      if (params && params.length > 0) console.log('[DB] Params:', params);
    }

    try {
      if (this.dbInstance === null) {
        throw new Error('Database not initialized');
      }

      // Route through serializer — ensures single-connection safety with PGlite WASM
      const result = await dbSerializer.execute(this.dbInstance, query, params);
      return result;
    } catch (e: any) {
      // Don't log transaction control statements as errors
      if (!query.trim().match(/^(BEGIN|COMMIT|ROLLBACK)/i)) {
        console.error(`[DB] Query Failed: ${e.message}`);
        console.error(`[DB] Query: ${query}`);
      }
      throw e;
    }
  }

  /**
   * Run a FTS search query (v5.2.0+ serialized)
   */
  async search(query: string) {
    if (this.dbInstance === null) {
      throw new Error('Database not initialized');
    }

    // For now, use a simple LIKE query since full-text search may not be available
    const result = await dbSerializer.execute(
      this.dbInstance,
      'SELECT * FROM atoms WHERE content LIKE ?',
      [`%${query}%`],
    );
    return result;
  }

  // Helper methods for file system operations
  private existsSync = fs.existsSync;
  private rmdirSync = fs.rmSync;
  private mkdirSync = fs.mkdirSync;
}

// Export a singleton instance
export const db = new Database();