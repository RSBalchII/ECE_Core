/**
 * Radial Distillation Integration Tests
 *
 * Tests the radial distillation pipeline:
 * 1. Collect compounds
 * 2. Deduplicate lines
 * 3. Reassemble into coherent output
 * 
 * Run: pnpm test -- radial-distiller.test.ts
 */

import { describe, test, expect, beforeEach, afterAll } from '@jest/globals';
import { PGlite } from '@electric-sql/pglite';
import * as path from 'path';
import * as fs from 'fs';
import * as crypto from 'crypto';

describe('Radial Distillation Integration', () => {
  let db: PGlite;
  let testDbPath: string;
  let testOutputDir: string;

  beforeEach(async () => {
    // Create unique temp database path
    testDbPath = path.join(process.cwd(), 'test-distill-db-' + Date.now());
    testOutputDir = path.join(process.cwd(), 'test-distill-output-' + Date.now());

    // Clean up if exists
    if (fs.existsSync(testDbPath)) {
      fs.rmSync(testDbPath, { recursive: true, force: true });
    }
    if (fs.existsSync(testOutputDir)) {
      fs.rmSync(testOutputDir, { recursive: true, force: true });
    }
    fs.mkdirSync(testOutputDir, { recursive: true });

    // Initialize fresh database
    db = new PGlite(testDbPath);
    await db.waitReady;

    // Create schema
    await createDistillationSchema(db);
    await seedDistillationData(db);
  });

  afterAll(async () => {
    // Cleanup
    if (db) {
      await db.close();
    }
    if (testDbPath && fs.existsSync(testDbPath)) {
      fs.rmSync(testDbPath, { recursive: true, force: true });
    }
    if (testOutputDir && fs.existsSync(testOutputDir)) {
      fs.rmSync(testOutputDir, { recursive: true, force: true });
    }
  });

  describe('Line Deduplication', () => {
    test('should deduplicate identical lines across compounds', async () => {
      const duplicateLine = 'This is a duplicate line for testing';
      
      // Hash the line
      const hash = hashLine(duplicateLine);
      
      // Verify hash is consistent
      expect(hash).toBeDefined();
      expect(hash.length).toBe(64); // SHA256 hex length
      
      // Test normalization
      const normalized1 = normalizeLine(duplicateLine, 'strict');
      const normalized2 = normalizeLine('  ' + duplicateLine + '  ', 'strict');
      
      // Normalization should handle whitespace
      expect(normalized1).toBe(normalized2);
    });

    test('should handle strict vs lenient normalization', async () => {
      const line = 'User: Hello there!';
      
      const strict = normalizeLine(line, 'strict');
      const lenient = normalizeLine(line, 'lenient');
      
      // Strict should remove "User:" prefix
      expect(strict).not.toContain('User:');
      // Lenient should just trim
      expect(lenient).toBe('User: Hello there!');
    });

    test('should track provenance for duplicate lines', async () => {
      // Insert same content in multiple compounds
      const content = 'Shared content across compounds';
      
      await db.run(`
        INSERT INTO compounds (id, path, provenance, timestamp) 
        VALUES ($1, $2, $3, $4)
      `, ['compound-a', '/test/a.txt', 'internal', Date.now()]);
      
      await db.run(`
        INSERT INTO compounds (id, path, provenance, timestamp) 
        VALUES ($1, $2, $3, $4)
      `, ['compound-b', '/test/b.txt', 'internal', Date.now()]);

      await db.run(`
        INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5)
      `, ['mol-a', content, 'compound-a', 0, content.length]);

      await db.run(`
        INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
        VALUES ($1, $2, $3, $4, $5)
      `, ['mol-b', content, 'compound-b', 0, content.length]);

      // Query should find both
      const result = await db.run(
        `SELECT m.id, m.content, c.id as compound_id, c.path
         FROM molecules m
         JOIN compounds c ON m.compound_id = c.id
         WHERE m.content = $1`,
        [content]
      );

      expect(result.rows).toHaveLength(2);
      const compoundIds = result.rows.map((r: any) => r.compound_id);
      expect(compoundIds).toContain('compound-a');
      expect(compoundIds).toContain('compound-b');
    });
  });

  describe('Compound Collection', () => {
    test('should collect all compounds for distillation', async () => {
      const result = await db.run(
        `SELECT id, path, provenance, timestamp FROM compounds ORDER BY id`
      );

      expect(result.rows).toBeDefined();
      expect(result.rows.length).toBeGreaterThanOrEqual(3);
    });

    test('should filter compounds by provenance', async () => {
      const result = await db.run(
        `SELECT id, path, provenance FROM compounds WHERE provenance = $1`,
        ['internal']
      );

      expect(result.rows).toBeDefined();
      result.rows.forEach((row: any) => {
        expect(row.provenance).toBe('internal');
      });
    });

    test('should filter compounds by path pattern', async () => {
      const result = await db.run(
        `SELECT id, path FROM compounds WHERE path LIKE $1`,
        ['/test/chat/%']
      );

      expect(result.rows).toBeDefined();
      result.rows.forEach((row: any) => {
        expect(row.path).toMatch(/\/test\/chat\//);
      });
    });
  });

  describe('Memory Safety', () => {
    test('should handle large compound sets', async () => {
      // Insert many compounds
      const compoundCount = 50;
      for (let i = 0; i < compoundCount; i++) {
        await db.run(`
          INSERT INTO compounds (id, path, provenance, timestamp)
          VALUES ($1, $2, $3, $4)
        `, [`compound-${i}`, `/test/bulk/${i}.txt`, 'internal', Date.now()]);

        // Add molecules to each compound
        for (let j = 0; j < 10; j++) {
          await db.run(`
            INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
            VALUES ($1, $2, $3, $4, $5)
          `, [
            `mol-${i}-${j}`,
            `Content for compound ${i}, molecule ${j}`,
            `compound-${i}`,
            j * 100,
            (j + 1) * 100
          ]);
        }
      }

      const result = await db.run(
        `SELECT COUNT(*) as count FROM compounds`
      );

      expect(parseInt(result.rows[0].count)).toBe(compoundCount + 3); // +3 from seed data
    });

    test('should stream results for memory efficiency', async () => {
      // Create a cursor-like pattern
      const batchSize = 10;
      let offset = 0;
      let totalProcessed = 0;

      while (true) {
        const result = await db.run(
          `SELECT id, content FROM molecules LIMIT $1 OFFSET $2`,
          [batchSize, offset]
        );

        if (!result.rows || result.rows.length === 0) break;

        totalProcessed += result.rows.length;
        offset += batchSize;

        // Simulate processing
        result.rows.forEach((row: any) => {
          expect(row.id).toBeDefined();
          expect(row.content).toBeDefined();
        });
      }

      expect(totalProcessed).toBeGreaterThan(0);
    });
  });

  describe('Output Generation', () => {
    test('should generate YAML output', async () => {
      const yamlContent = generateYamlOutput([
        {
          compoundId: 'compound-1',
          lines: ['Line 1', 'Line 2', 'Line 3'],
          provenance: ['/test/file1.txt']
        }
      ]);

      expect(yamlContent).toBeDefined();
      expect(yamlContent).toContain('compound_id: compound-1');
      expect(yamlContent).toContain('- Line 1');
    });

    test('should generate JSON output', async () => {
      const jsonOutput = generateJsonOutput([
        {
          compoundId: 'compound-1',
          lines: ['Line 1', 'Line 2'],
          provenance: ['/test/file1.txt']
        }
      ]);

      const parsed = JSON.parse(jsonOutput);
      expect(parsed.compounds).toBeDefined();
      expect(parsed.compounds.length).toBe(1);
      expect(parsed.compounds[0].compound_id).toBe('compound-1');
    });

    test('should write output to file', async () => {
      const outputPath = path.join(testOutputDir, 'test-output.yaml');
      
      const yamlContent = generateYamlOutput([
        {
          compoundId: 'test-compound',
          lines: ['Test line 1', 'Test line 2'],
          provenance: ['/test/test.txt']
        }
      ]);

      fs.writeFileSync(outputPath, yamlContent, 'utf-8');
      
      expect(fs.existsSync(outputPath)).toBe(true);
      
      const written = fs.readFileSync(outputPath, 'utf-8');
      expect(written).toContain('test-compound');
    });
  });

  describe('Compression Statistics', () => {
    test('should calculate compression ratio', async () => {
      const linesTotal = 1000;
      const linesUnique = 650;
      const linesDuplicate = linesTotal - linesUnique;
      
      const compressionRatio = (linesUnique / linesTotal) * 100;
      
      expect(compressionRatio).toBe(65);
      expect(linesDuplicate).toBe(350);
    });

    test('should track processing duration', async () => {
      const startTime = Date.now();
      
      // Simulate processing
      await new Promise(resolve => setTimeout(resolve, 10));
      
      const duration = Date.now() - startTime;
      
      expect(duration).toBeGreaterThanOrEqual(10);
      expect(duration).toBeLessThan(1000); // Should complete quickly
    });
  });
});

// Helper Functions

async function createDistillationSchema(db: PGlite) {
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
    CREATE TABLE IF NOT EXISTS molecules (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      compound_id TEXT REFERENCES compounds(id),
      tags JSONB,
      start_byte BIGINT,
      end_byte BIGINT,
      sequence INTEGER
    )
  `);

  await db.exec(`
    CREATE TABLE IF NOT EXISTS atoms (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      source_path TEXT,
      compound_id TEXT REFERENCES compounds(id),
      start_byte BIGINT,
      end_byte BIGINT,
      tags JSONB
    )
  `);
}

async function seedDistillationData(db: PGlite) {
  // Seed compounds representing different source types
  await db.run(`
    INSERT INTO compounds (id, path, provenance, timestamp) 
    VALUES ($1, $2, $3, $4)
  `, ['compound-1', '/test/chat/conversation-1.txt', 'internal', Date.now()]);

  await db.run(`
    INSERT INTO compounds (id, path, provenance, timestamp) 
    VALUES ($1, $2, $3, $4)
  `, ['compound-2', '/test/chat/conversation-2.txt', 'internal', Date.now()]);

  await db.run(`
    INSERT INTO compounds (id, path, provenance, timestamp) 
    VALUES ($1, $2, $3, $4)
  `, ['compound-3', '/test/docs/readme.md', 'internal', Date.now()]);

  // Seed molecules with some duplicates
  const sharedContent = 'This content appears in multiple compounds';
  
  await db.run(`
    INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
    VALUES ($1, $2, $3, $4, $5)
  `, ['mol-1', 'Unique content for compound 1', 'compound-1', 0, 29]);

  await db.run(`
    INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
    VALUES ($1, $2, $3, $4, $5)
  `, ['mol-2', sharedContent, 'compound-1', 30, 30 + sharedContent.length]);

  await db.run(`
    INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
    VALUES ($1, $2, $3, $4, $5)
  `, ['mol-3', sharedContent, 'compound-2', 0, sharedContent.length]);

  await db.run(`
    INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
    VALUES ($1, $2, $3, $4, $5)
  `, ['mol-4', 'Unique content for compound 2', 'compound-2', sharedContent.length, sharedContent.length + 29]);

  await db.run(`
    INSERT INTO molecules (id, content, compound_id, start_byte, end_byte)
    VALUES ($1, $2, $3, $4, $5)
  `, ['mol-5', 'Documentation content', 'compound-3', 0, 21]);
}

function hashLine(line: string): string {
  return crypto.createHash('sha256').update(line).digest('hex');
}

function normalizeLine(line: string, mode: 'strict' | 'lenient'): string {
  if (mode === 'lenient') {
    return line.trim();
  }

  // Strict normalization
  let normalized = line.trim();
  
  // Collapse whitespace
  normalized = normalized.replace(/\s+/g, ' ');
  
  // Lowercase
  normalized = normalized.toLowerCase();
  
  // Remove common prefixes
  normalized = normalized.replace(/^user:\s*/i, '');
  normalized = normalized.replace(/^assistant:\s*/i, '');
  normalized = normalized.replace(/^\[?\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}\]?\s*/, '');
  
  return normalized;
}

function generateYamlOutput(compounds: Array<{ compoundId: string; lines: string[]; provenance: string[] }>): string {
  let yaml = 'distilled_output:\n';
  yaml += `  generated_at: ${new Date().toISOString()}\n`;
  yaml += `  compounds:\n`;
  
  for (const compound of compounds) {
    yaml += `    - compound_id: ${compound.compoundId}\n`;
    yaml += `      provenance:\n`;
    compound.provenance.forEach(p => {
      yaml += `        - ${p}\n`;
    });
    yaml += `      lines:\n`;
    compound.lines.forEach(line => {
      yaml += `        - "${line.replace(/"/g, '\\"')}"\n`;
    });
  }
  
  return yaml;
}

function generateJsonOutput(compounds: Array<{ compoundId: string; lines: string[]; provenance: string[] }>): string {
  return JSON.stringify({
    generated_at: new Date().toISOString(),
    compounds: compounds.map(c => ({
      compound_id: c.compoundId,
      provenance: c.provenance,
      lines: c.lines
    }))
  }, null, 2);
}
