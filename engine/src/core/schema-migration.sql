-- ============================================================================
-- Anchor Engine Database Schema Migration
-- ============================================================================
-- This file contains all CREATE TABLE statements for the current schema.
-- Run this script to initialize a fresh database or migrate from an empty state.
-- 
-- VERSION: 5.0.0 (Post-Compounds Removal)
-- DATE: 2026-05-21
-- ============================================================================

-- ------------------------------------------------------------------------------
-- TERMINOLOGY
-- ------------------------------------------------------------------------------
-- 
-- Compound (BEING REMOVED): A file/document reference (path, hash, metadata).
--   This table is deprecated and will be removed in this migration.
--
-- Molecule: A semantic chunk within a compound (or standalone file).
--   - Stores byte offsets (start_byte, end_byte) for content extraction
--   - Contains semantic content chunks
--   - Has tags, entities, and embeddings
--
-- Atom: A tagged concept extracted from molecules.
--   - Stores individual keywords/concepts with their provenance
--   - Does NOT store content (content lives in ~/.anchor/mirrored_brain/)
--   - Used for search indexing and tag-based retrieval

-- ------------------------------------------------------------------------------
-- TABLES
-- ------------------------------------------------------------------------------

-- --------------------------------------------------------------------------
-- atoms: Individual concepts/keywords extracted from text
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS atoms (
  id TEXT PRIMARY KEY,                    -- UUID v4, unique identifier
  source_path TEXT,                       -- File path where this atom was found
  timestamp REAL,                         -- Ingestion timestamp (Unix epoch)
  simhash TEXT,                          -- SimHash for deduplication
  embedding TEXT,                        -- Vector embedding (JSON array or null)
  vector_id BIGINT,                      -- Auto-increment ID for vector DB
  provenance TEXT,                       -- Source origin: 'internal' | 'external' | 'github'
  
  -- Legacy/compatibility columns (for existing databases)
  compound_id TEXT,                     -- FK reference to compounds table (deprecated)
  sequence INTEGER,                     -- Sequence number within source
  type TEXT,                            -- Atom type classification
  hash TEXT,                           -- Content hash for dedup
  
  -- Molecular-level attributes (moved from compounds)
  molecular_signature TEXT,             -- 64-bit Hamming SimHash of parent molecule
  start_byte INTEGER,                   -- Byte offset start in source file
  end_byte INTEGER,                    -- Byte offset end in source file
  numeric_value REAL,                  -- Numeric value if present
  numeric_unit TEXT,                   -- Unit for numeric values
  
  -- Content storage (Standard 051: Pointer-only architecture)
  content TEXT,                        -- Atom's extracted text content
  
  -- JSONB columns for flexible metadata
  tags JSONB,                          -- Array of tag strings
  entities JSONB,                      -- Named entity extraction results
  payload JSONB                       -- Additional structured data (Crystal Atom)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for atoms table
CREATE INDEX IF NOT EXISTS idx_atoms_source_path ON atoms(source_path);
CREATE INDEX IF NOT EXISTS idx_atoms_provenance ON atoms(provenance);
CREATE INDEX IF NOT EXISTS idx_atoms_simhash ON atoms(simhash);
CREATE INDEX IF NOT EXISTS idx_atoms_timestamp ON atoms(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_atoms_compound_id ON atoms(compound_id);
CREATE INDEX IF NOT EXISTS idx_atoms_payload_gin ON atoms USING GIN (payload);

-- --------------------------------------------------------------------------
-- molecules: Semantic text chunks with byte offsets
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS molecules (
  id TEXT PRIMARY KEY,                    -- UUID v4, unique identifier
  content TEXT,                         -- Semantic chunk content
  compound_id TEXT,                     -- FK reference to compounds table (deprecated)
  sequence INTEGER,                     -- Sequence number within source
  start_byte INTEGER,                   -- Byte offset start in source file
  end_byte INTEGER,                    -- Byte offset end in source file
  
  -- Type classification for numeric literals
  type TEXT,                            -- 'number' | 'percentage' | etc.
  numeric_value REAL,                  -- Parsed numeric value
  numeric_unit TEXT,                   -- Unit (e.g., 'kg', 'm/s²')
  
  molecular_signature TEXT,             -- 64-bit Hamming SimHash for molecule
  
  embedding TEXT,                       -- Vector embedding (JSON array)
  timestamp REAL,                       -- Ingestion timestamp
  tags JSONB,                          -- Array of tag strings
  entities JSONB,                      -- Named entity extraction results
  
  source_path TEXT,                    -- Direct file path reference
  provenance TEXT                     -- Source origin metadata
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for molecules table
CREATE INDEX IF NOT EXISTS idx_molecules_source_path ON molecules(source_path);
CREATE INDEX IF NOT EXISTS idx_molecules_provenance ON molecules(provenance);
CREATE INDEX IF NOT EXISTS idx_molecules_compound_id ON molecules(compound_id);
CREATE INDEX IF NOT EXISTS idx_molecules_timestamp ON molecules(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_molecules_signature ON molecules(molecular_signature);

-- --------------------------------------------------------------------------
-- compounds: REMOVED (v5.2 milestone) — deprecated table dropped from schema
-- --------------------------------------------------------------------------
-- The compounds table was the pre-removal reference layer. All provenance and
-- signature data now lives in atoms/molecules; the ingestion pipeline no longer
-- writes compounds rows. Dropped here so fresh stores boot without it.

-- --------------------------------------------------------------------------
-- tags: Tag-atom relationships (The "Nervous System")
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
  atom_id TEXT NOT NULL,                 -- Reference to atoms.id
  tag TEXT NOT NULL,                    -- Tag name/concept
  bucket TEXT NOT NULL,                  -- Bucket for grouping (e.g., 'physics', 'ml')
  PRIMARY KEY (atom_id, tag, bucket)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for tags table
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_tags_bucket ON tags(bucket);
CREATE INDEX IF NOT EXISTS idx_tags_atom_id ON tags(atom_id);

-- --------------------------------------------------------------------------
-- edges: Graph relationships between atoms (The "Graph Connections")
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edges (
  source_id TEXT NOT NULL,               -- Reference to atoms.id
  target_id TEXT NOT NULL,              -- Reference to atoms.id
  relation TEXT NOT NULL,               -- Relationship type
  weight REAL,                          -- Edge weight for ranking
  PRIMARY KEY (source_id, target_id, relation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for edges table
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);

-- --------------------------------------------------------------------------
-- sources: Container for source tracking (The "Source Registry")
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
  path TEXT PRIMARY KEY,                -- File path as unique key
  hash TEXT,                           -- Content hash for dedup
  total_atoms INTEGER,                 -- Count of atoms in this source
  last_ingest REAL                    -- Last ingestion timestamp
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------------------------
-- engrams: Lexical sidecar (keyword-value store)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS engrams (
  key TEXT PRIMARY KEY,                -- Lookup key
  value TEXT                           -- Associated value
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------------------------
-- atom_positions: Lazy molecule inflation positions
-- Tracks where atoms appear in compounds for radial inflation
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS atom_positions (
  compound_id TEXT NOT NULL,           -- Reference to compounds.id
  atom_label TEXT NOT NULL,            -- Atom/keyword label
  byte_offset INTEGER NOT NULL,        -- Position in source text
  PRIMARY KEY (compound_id, atom_label, byte_offset)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for atom_positions table
CREATE INDEX IF NOT EXISTS idx_atom_positions_label ON atom_positions(atom_label);

-- --------------------------------------------------------------------------
-- summary_nodes: Dreamer abstractions (high-level summaries)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS summary_nodes (
  id TEXT PRIMARY KEY,                 -- UUID identifier
  type TEXT,                          -- Node type classification
  span_start REAL,                   -- Start position in context
  span_end REAL,                     -- End position in context
  embedding TEXT                    -- Vector embedding for semantic search
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------------------------
-- github_repos: GitHub repository ingestion tracking (Standard 115)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS github_repos (
  id TEXT PRIMARY KEY,                 -- UUID identifier
  owner TEXT NOT NULL,                -- GitHub username/organization
  repo TEXT NOT NULL,                 -- Repository name
  branch TEXT DEFAULT 'main',         -- Git branch
  bucket TEXT NOT NULL,               -- Storage bucket reference
  github_url TEXT NOT NULL,           -- Full GitHub URL
  
  last_synced_at TIMESTAMP,           -- Last sync timestamp
  last_sync_status TEXT,              -- Sync status ('success' | 'error')
  last_error TEXT,                    -- Error message if failed
  
  total_files INTEGER DEFAULT 0,      -- Total files indexed
  total_atoms INTEGER DEFAULT 0,      -- Total atoms extracted
  total_size_bytes INTEGER DEFAULT 0, -- Total size in bytes
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for github_repos table
CREATE INDEX IF NOT EXISTS idx_github_repos_owner_repo 
    ON github_repos(owner, repo);
CREATE INDEX IF NOT EXISTS idx_github_repos_synced ON github_repos(last_synced_at DESC);

-- --------------------------------------------------------------------------
-- distills: Distillation output tracking (Standard 016)
-- Stores metadata pointers to distill files on disk
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS distills (
  id TEXT PRIMARY KEY,                 -- UUID identifier
  timestamp TEXT NOT NULL,             -- ISO timestamp of distillation
  filename TEXT NOT NULL,              -- Base filename
  file_path TEXT NOT NULL,            -- Full path to distill file
  
  line_count INTEGER NOT NULL,        -- Total lines in output
  lines_unique INTEGER NOT NULL,      -- Unique lines (deduplicated)
  compression_ratio REAL,             -- Compression efficiency metric
  
  source_sessions TEXT[],            -- Array of session IDs that produced this
  source_files TEXT[],              -- Array of file paths processed
  parameters JSONB,                 -- Processing parameters used
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for distills table
CREATE INDEX IF NOT EXISTS idx_distills_timestamp 
    ON distills(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_distills_filename 
    ON distills(filename);
CREATE INDEX IF NOT EXISTS idx_distills_source_sessions 
    ON distills USING GIN(source_sessions);

-- --------------------------------------------------------------------------
-- synonyms: Query expansion terms (for search enhancement)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS synonyms (
  term TEXT PRIMARY KEY,              -- Base search term
  synonyms TEXT,                     -- Comma-separated synonym list
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- SEQUENCE DEFINITIONS
-- ------------------------------------------------------------------------------

-- Auto-increment sequence for vector IDs (used by embedding service)
CREATE SEQUENCE IF NOT EXISTS vector_id_seq START 1 INCREMENT BY 1;

-- ------------------------------------------------------------------------------
-- MIGRATION NOTES — v5.2 milestone (compounds removal complete)
-- ------------------------------------------------------------------------------
--
-- This schema represents the post-compounds-removal state. The deprecated
-- compounds table has been dropped from this file; fresh stores boot without it,
-- and the ingestion pipeline no longer writes compounds rows. All provenance and
-- signature data now lives in atoms/molecules.
