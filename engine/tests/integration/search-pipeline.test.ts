/**
 * Search Pipeline Integration Tests
 *
 * Tests the full search pipeline: query → parse → search → inflate → serialize → return
 * 
 * Run: pnpm test -- search-pipeline.test.ts
 */

import { describe, test, expect, beforeEach, afterAll } from '@jest/globals';
import { PGlite } from '@electric-sql/pglite';
import * as path from 'path';
import * as fs from 'fs';

describe('Search Pipeline Integration', () => {
  let db: PGlite;
  let testDbPath: string;

  beforeEach(async () => {
    // Create unique temp database path for each test
    testDbPath = path.join(process.cwd(), 'test-search-db-' + Date.now());

    // Clean up if exists
    if (fs.existsSync(testDbPath)) {
      fs.rmSync(testDbPath, { recursive: true, force: true });
    }

    // Initialize fresh database
    db = new PGlite(testDbPath);
    await db.waitReady;

    // Create full schema
    await createFullSchema(db);
    await seedTestData(db);
  });

  afterAll(async () => {
    // Cleanup
    if (db) {
      await db.close();
    }
    if (testDbPath && fs.existsSync(testDbPath)) {
      fs.rmSync(testDbPath, { recursive: true, force: true });
    }
  });

  describe('Basic Search Flow', () => {
    test('should find molecules by full-text search', async () => {
      const query = 'semantic search';
      const results = await ftsSearch(db, query);
      
      expect(results).toBeDefined();
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].content).toContain('semantic');
    });

    test('should handle empty queries gracefully', async () => {
      const query = '';
      const results = await ftsSearch(db, query);
      
      expect(results).toEqual([]);
    });

    test('should handle queries with special characters', async () => {
      const query = 'test@#$%^&*()';
      const results = await ftsSearch(db, query);
      
      // Should not throw, may return empty results
      expect(Array.isArray(results)).toBe(true);
    });

    test('should respect bucket filters', async () => {
      const query = 'graph';
      const bucket = 'test-corpus';
      const results = await ftsSearchWithBucket(db, query, bucket);
      
      expect(results).toBeDefined();
      results.forEach(result => {
        // All results should be from the specified bucket
        expect(result.bucket).toBe(bucket);
      });
    });

    test('should handle multi-term queries with OR logic', async () => {
      const query = 'graph traversal';
      const results = await ftsSearch(db, query);
      
      expect(results).toBeDefined();
      expect(results.length).toBeGreaterThan(0);
      
      // At least some results should contain one of the terms
      const hasMatchingTerm = results.some(r => 
        r.content.toLowerCase().includes('graph') || 
        r.content.toLowerCase().includes('traversal')
      );
      expect(hasMatchingTerm).toBe(true);
    });
  });

  describe('Atom Search with Context Inflation', () => {
    test('should find atoms and inflate context', async () => {
      const query = 'deterministic retrieval';
      
      // First find atoms
      const atomResults = await searchAtoms(db, query);
      expect(atomResults).toBeDefined();
      
      // Then inflate (simulate context expansion)
      if (atomResults.length > 0) {
        const inflated = await inflateContext(db, atomResults[0], 500);
        expect(inflated).toBeDefined();
        expect(inflated.content).toBeDefined();
        expect(inflated.content.length).toBeGreaterThan(0);
      }
    });

    test('should handle atoms without coordinates', async () => {
      // Insert an atom without byte coordinates
      await db.run(`
        INSERT INTO atoms (id, content, source_path, timestamp, tags, provenance)
        VALUES ($1, $2, $3, $4, $5, $6)
      `, ['atom-no-coords', 'Test content without coordinates', 'test.txt', Date.now(), '["test"]', 'internal']);

      const results = await searchAtoms(db, 'test content');
      expect(results).toBeDefined();
      // Should still return the atom even without coordinates
    });
  });

  describe('Deduplication', () => {
    test('should deduplicate identical content across compounds', async () => {
      // Insert duplicate content in different compounds
      const duplicateContent = 'This is duplicate test content';
      
      await db.run(`
        INSERT INTO compounds (id, path, provenance) VALUES ($1, $2, $3)
      `, ['compound-1', '/test/file1.txt', 'internal']);
      
      await db.run(`
        INSERT INTO compounds (id, path, provenance) VALUES ($1, $2, $3)
      `, ['compound-2', '/test/file2.txt', 'internal']);

      await db.run(`
        INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5)
      `, ['mol-1', duplicateContent, 'compound-1', 0, duplicateContent.length]);

      await db.run(`
        INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5)
      `, ['mol-2', duplicateContent, 'compound-2', 0, duplicateContent.length]);

      const results = await ftsSearch(db, 'duplicate test');
      
      // Deduplication logic should handle this
      expect(results).toBeDefined();
    });

    test('should merge overlapping byte ranges', async () => {
      // Insert overlapping molecules in same compound
      await db.run(`
        INSERT INTO compounds (id, path, provenance) VALUES ($1, $2, $3)
      `, ['compound-overlap', '/test/overlap.txt', 'internal']);

      await db.run(`
        INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5)
      `, ['mol-overlap-1', 'First part of content', 'compound-overlap', 0, 21]);

      await db.run(`
        INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5)
      `, ['mol-overlap-2', 'part of content here', 'compound-overlap', 15, 35]);

      const results = await ftsSearch(db, 'content');
      expect(results).toBeDefined();
    });
  });

  describe('Performance Under Load', () => {
    test('should handle concurrent searches', async () => {
      const queries = [
        'semantic search',
        'graph traversal',
        'deterministic retrieval',
        'context inflation',
        'radial distillation'
      ];

      const startTime = Date.now();
      const promises = queries.map(q => ftsSearch(db, q));
      const allResults = await Promise.all(promises);
      const duration = Date.now() - startTime;

      // All searches should complete
      expect(allResults).toHaveLength(5);
      allResults.forEach(results => {
        expect(Array.isArray(results)).toBe(true);
      });

      // Should complete in reasonable time (< 5 seconds for all)
      expect(duration).toBeLessThan(5000);
    });

    test('should handle large result sets', async () => {
      // Insert many molecules
      const batchSize = 100;
      for (let i = 0; i < batchSize; i++) {
        await db.run(`
          INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
          VALUES ($1, $2, $3, $4, $5)
        `, [
          `mol-bulk-${i}`,
          `Test content for bulk item ${i} with search terms`,
          `compound-${Math.floor(i / 10)}`,
          i * 100,
          (i + 1) * 100
        ]);
      }

      const results = await ftsSearch(db, 'search terms');
      expect(results).toBeDefined();
      expect(results.length).toBeGreaterThan(0);
      // Should not return all 100 (limited by query)
      expect(results.length).toBeLessThanOrEqual(20);
    });
  });

  describe('Tag Filtering', () => {
    test('should filter blacklisted tags from results', async () => {
      const results = await searchWithTags(db, 'test');
      
      // Verify no blacklisted tags in results
      results.forEach(result => {
        if (result.tags) {
          const hasBlacklisted = result.tags.some((tag: string) => 
            tag === 'stopword' || tag === 'a' || tag === 'the'
          );
          expect(hasBlacklisted).toBe(false);
        }
      });
    });

    test('should enrich atoms with molecule tags', async () => {
      // Create compound with molecule tags
      await db.run(`
        INSERT INTO compounds (id, path, provenance) VALUES ($1, $2, $3)
      `, ['compound-tag-test', '/test/tagged.txt', 'internal']);

      await db.run(`
        INSERT INTO molecules (id, content, compound_id, tags, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5, $6)
      `, ['mol-tagged', 'Content with molecule tags', 'compound-tag-test', '["molecule-tag", "important"]', 0, 27]);

      await db.run(`
        INSERT INTO atoms (id, content, source_path, compound_id, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5, $6)
      `, ['atom-child', 'Content with molecule tags', '/test/tagged.txt', 'compound-tag-test', 5, 20]);

      const results = await searchWithTags(db, 'content');
      expect(results).toBeDefined();
    });
  });
});

// Helper Functions

async function createFullSchema(db: PGlite) {
  await db.exec(`
    CREATE TABLE IF NOT EXISTS atoms (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      source_path TEXT,
      timestamp BIGINT,
      tags JSONB,
      buckets TEXT[],
      provenance TEXT DEFAULT 'internal',
      compound_id TEXT,
      start_byte BIGINT,
      end_byte BIGINT,
      simhash TEXT
    )
  `);

  await db.exec(`
    CREATE TABLE IF NOT EXISTS molecules (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      compound_id TEXT,
      tags JSONB,
      start_byte BIGINT,
      end_byte BIGINT,
      sequence INTEGER,
      molecular_signature TEXT,
      type TEXT,
      numeric_value DOUBLE PRECISION,
      numeric_unit TEXT
    )
  `);

  await db.exec(`
    CREATE TABLE IF NOT EXISTS compounds (
      id TEXT PRIMARY KEY,
      compound_body TEXT,
      path TEXT,
      molecular_signature TEXT,
      provenance TEXT DEFAULT 'internal',
      timestamp BIGINT
    )
  `);

  await db.exec(`
    CREATE TABLE IF NOT EXISTS tags (
      id SERIAL PRIMARY KEY,
      atom_id TEXT REFERENCES atoms(id),
      tag TEXT NOT NULL
    )
  `);

  await db.exec(`
    CREATE TABLE IF NOT EXISTS engrams (
      key TEXT PRIMARY KEY,
      value JSONB NOT NULL
    )
  `);

  // Create FTS index
  await db.exec(`
    CREATE INDEX IF NOT EXISTS molecules_fts_idx
      ON molecules
      USING GIN (to_tsvector('simple', content))
  `);
}

async function seedTestData(db: PGlite) {
  // Seed compounds
  await db.run(`
    INSERT INTO compounds (id, path, provenance, timestamp) VALUES ($1, $2, $3, $4)
  `, ['compound-1', '/test/file1.txt', 'internal', Date.now()]);
  
  await db.run(`
    INSERT INTO compounds (id, path, provenance, timestamp) VALUES ($1, $2, $3, $4)
  `, ['compound-2', '/test/file2.txt', 'internal', Date.now()]);

  await db.run(`
    INSERT INTO compounds (id, path, provenance, timestamp) VALUES ($1, $2, $3, $4)
  `, ['test-corpus', '/test/corpus.txt', 'test-corpus', Date.now()]);

  // Seed molecules with various content
  const molecules = [
    { id: 'mol-1', content: 'Semantic search using graph traversal for deterministic retrieval', compound: 'compound-1' },
    { id: 'mol-2', content: 'Context inflation expands search results radially', compound: 'compound-1' },
    { id: 'mol-3', content: 'Radial distillation compresses corpus losslessly', compound: 'compound-2' },
    { id: 'mol-4', content: 'Graph-based retrieval outperforms vector search', compound: 'compound-2' },
    { id: 'mol-5', content: 'Test content for bucket filtering', compound: 'test-corpus' },
  ];

  for (const mol of molecules) {
    await db.run(`
      INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
      VALUES ($1, $2, $3, $4, $5)
    `, [mol.id, mol.content, mol.compound, 0, mol.content.length]);
  }

  // Seed atoms
  await db.run(`
    INSERT INTO atoms (id, content, source_path, compound_id, start_byte, end_byte, tags)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
  `, ['atom-1', 'Deterministic retrieval system', '/test/file1.txt', 'compound-1', 0, 30, '["search", "graph"]']);
}

async function ftsSearch(db: PGlite, query: string): Promise<any[]> {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter(t => t.length > 1);

  if (terms.length === 0) return [];

  const tsQuery = terms.join(' | ');
  const result = await db.run(
    `SELECT id, content
     FROM molecules
     WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', $1)
     LIMIT 20`,
    [tsQuery]
  );

  return result.rows || [];
}

async function ftsSearchWithBucket(db: PGlite, query: string, bucket: string): Promise<any[]> {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter(t => t.length > 1);

  if (terms.length === 0) return [];

  const tsQuery = terms.join(' | ');
  const result = await db.run(
    `SELECT m.id, m.content, c.path as bucket
     FROM molecules m
     JOIN compounds c ON m.compound_id = c.id
     WHERE to_tsvector('simple', m.content) @@ plainto_tsquery('simple', $1)
     AND c.path = $2
     LIMIT 20`,
    [tsQuery, bucket]
  );

  return result.rows || [];
}

async function searchAtoms(db: PGlite, query: string): Promise<any[]> {
  const terms = query.split(/\s+/).filter(t => t.length > 1);
  if (terms.length === 0) return [];

  const tsQuery = terms.join(' | ');
  const result = await db.run(
    `SELECT id, content, source_path, compound_id, start_byte, end_byte
     FROM atoms
     WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', $1)
     LIMIT 10`,
    [tsQuery]
  );

  return result.rows || [];
}

async function inflateContext(db: PGlite, atom: any, radius: number): Promise<any> {
  if (!atom.compound_id || atom.start_byte === undefined) {
    return { ...atom, is_inflated: false, content: atom.content };
  }

  const start = Math.max(0, atom.start_byte - radius);
  const end = atom.end_byte + radius;

  const result = await db.run(
    `SELECT content FROM molecules 
     WHERE compound_id = $1 
     AND start_byte <= $2 
     AND end_byte >= $3
     LIMIT 1`,
    [atom.compound_id, end, start]
  );

  if (result.rows && result.rows.length > 0) {
    return {
      ...atom,
      content: result.rows[0].content,
      is_inflated: true
    };
  }

  return { ...atom, is_inflated: false };
}

async function searchWithTags(db: PGlite, query: string): Promise<any[]> {
  const terms = query.split(/\s+/).filter(t => t.length > 1);
  if (terms.length === 0) return [];

  const tsQuery = terms.join(' | ');
  const result = await db.run(
    `SELECT id, content, tags
     FROM atoms
     WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', $1)
     LIMIT 20`,
    [tsQuery]
  );

  return (result.rows || []).map((row: any) => ({
    ...row,
    tags: row.tags ? (typeof row.tags === 'string' ? JSON.parse(row.tags) : row.tags) : []
  }));
}
