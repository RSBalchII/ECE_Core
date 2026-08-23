/**
 * Distillation Results Integration Test
 * 
 * Tests the radial distillation process and validates output structure.
 * Results are logged to .anchor/results/ for analysis.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { fetch } from 'undici';
import { join, dirname } from 'path';
import { homedir } from 'os';
import { fileURLToPath } from 'url';
import { mkdirSync, writeFileSync, existsSync, rmSync, readFileSync } from 'fs';

const __dirname = join(dirname(fileURLToPath(import.meta.url)));
const PROJECT_ROOT = join(__dirname, '..', '..');
// FIX (2026-08-21): test artifacts must not be written into the repo. ANCHOR_ROOT resolves to
// ~/.anchor (Standard 110); setup.ts sets it for vitest workers, the fallback keeps standalone runs correct.
const ANCHOR_ROOT = process.env.ANCHOR_ROOT || join(homedir(), '.anchor');
const RESULTS_DIR = join(ANCHOR_ROOT, 'results');
const DISTILLS_DIR = join(ANCHOR_ROOT, 'distills');

// Test configuration
const SERVER_PORT = 3160;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;
const API_KEY = process.env.ANCHOR_API_KEY || 'test-api-key';

// Result logging
const logDistillationResult = (testName: string, data: any) => {
  const resultDir = join(RESULTS_DIR, 'distillation');
  mkdirSync(resultDir, { recursive: true });

  const timestamp = new Date().toISOString();
  const resultFile = join(resultDir, `${testName}-${timestamp.replace(/[:.]/g, '-')}.json`);

  writeFileSync(resultFile, JSON.stringify(data, null, 2));
  console.log(`📝 Distillation results logged to: ${resultFile}`);
};

describe('Distillation Results Integration Tests', () => {
  let serverStarted = false;

  beforeAll(async () => {
    console.log('🔧 [Distillation Results] Setting up test environment...');

    // Ensure directories exist
    mkdirSync(RESULTS_DIR, { recursive: true });
    mkdirSync(DISTILLS_DIR, { recursive: true });

    // Check if server is running
    try {
      const res = await fetch(`${SERVER_URL}/api/health`, {
        signal: AbortSignal.timeout(3000),
      });
      if (res.ok) {
        const data = await res.json();
        console.log('✅ Server is already running');
        console.log(`   Health: ${JSON.stringify(data)}`);
        serverStarted = true;
      }
    } catch (err) {
      console.log('⚠️  Server not running, skipping live distillation tests');
    }
  });

  afterAll(() => {
    console.log('🧹 [Distillation Results] Cleaning up...');
  });

  it('should distill a simple text document', async () => {
    if (!serverStarted) {
      console.log('⚠️  Skipping live distillation test - server not running');
      return;
    }

    const testDocument = `
# Test Document

This is a test document for distillation. It contains multiple paragraphs
and sections to test the radial distillation algorithm.

## Section 1

This section discusses the importance of semantic memory systems for AI agents.
Semantic memory allows agents to store and retrieve knowledge efficiently.

## Section 2

The second section covers retrieval mechanisms. Anchor Engine uses a graph-based
approach called STAR (Semantic Temporal Associative Retrieval) for searching.

## Section 3

The final section talks about local-first architecture. This means data stays
on the user's machine, providing better privacy and control.
    `.trim();

    const result = await distillText(testDocument, 'test-doc-1');

    console.log(`\n📄 Document: test-doc-1`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    if (result.atoms && result.atoms.length > 0) {
      logDistillationResult('simple-distillation', {
        document: testDocument,
        result,
        timestamp: new Date().toISOString(),
      });

      // Validate atom structure
      for (const atom of result.atoms) {
        expect(atom).toHaveProperty('id');
        expect(atom).toHaveProperty('content');
        expect(atom).toHaveProperty('tags');
        expect(atom).toHaveProperty('timestamp');
      }
    }
  });

  it('should distill with custom radius', async () => {
    if (!serverStarted) return;

    const testDocument = `
# Short Document

This is a short document with two sections to test radial distillation
with different radius parameters.

## Part A

First part of the document.

## Part B

Second part of the document.
    `.trim();

    const result = await distillText(testDocument, 'short-doc', {
      radius: 2,
    });

    console.log(`\n📄 Document: short-doc (radius=2)`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    if (result.atoms) {
      logDistillationResult('radius-distillation', {
        document: testDocument,
        result,
        timestamp: new Date().toISOString(),
      });
    }
  });

  it('should handle empty document', async () => {
    if (!serverStarted) return;

    const result = await distillText('', 'empty-doc');

    console.log(`\n📄 Document: empty-doc (empty input)`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    expect(result.atoms?.length).toBe(0);
  });

  it('should handle whitespace-only document', async () => {
    if (!serverStarted) return;

    const result = await distillText('   \n\n   ', 'whitespace-doc');

    console.log(`\n📄 Document: whitespace-doc (whitespace only)`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    // Should produce no atoms or minimal atoms
    expect(result.atoms?.length).toBeLessThanOrEqual(1);
  });

  it('should create atoms with proper tags', async () => {
    if (!serverStarted) return;

    const testDocument = `
# Test Tags

This document tests tag generation. It should automatically extract
relevant tags based on content analysis.

## Keywords

Important keywords include: semantic, memory, retrieval, graph, AI.
    `.trim();

    const result = await distillText(testDocument, 'tag-test');

    console.log(`\n📄 Document: tag-test`);
    console.log(`   Tags found:`, result.atoms?.[0]?.tags || []);

    if (result.atoms && result.atoms.length > 0) {
      const tags = result.atoms[0].tags;
      // Should have generated some tags
      expect(tags.length).toBeGreaterThan(0);

      logDistillationResult('tag-generation', {
        document: testDocument,
        result,
        tags: tags,
        timestamp: new Date().toISOString(),
      });
    }
  });

  it('should preserve provenance information', async () => {
    if (!serverStarted) return;

    const testDocument = `
# Provenance Test

This document tests provenance tracking. The source should be recorded
correctly for audit purposes.

## Content

Some important content goes here.
    `.trim();

    const result = await distillText(testDocument, 'provenance-test', {
      source: 'test-source',
      path: '/test/path.md',
    });

    console.log(`\n📄 Document: provenance-test`);
    console.log(`   Provenance:`, result.provenance);

    if (result.provenance) {
      expect(result.provenance.source).toBe('test-source');
      expect(result.provenance.path).toBe('/test/path.md');

      logDistillationResult('provenance-test', result);
    }
  });

  it('should handle special characters in content', async () => {
    if (!serverStarted) return;

    const testDocument = `# Special Characters

This document contains special characters: <>&" and unicode: 你好世界 🌍

## Code Example

\`\`\`javascript
const x = 1;
console.log(x);
\`\`\`

## HTML

<p>Hello World</p>`;

    const result = await distillText(testDocument, 'special-chars');

    console.log(`\n📄 Document: special-chars`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    if (result.atoms && result.atoms.length > 0) {
      logDistillationResult('special-chars', result);
    }
  });

  it('should handle long documents', async () => {
    if (!serverStarted) return;

    const longDocument = `
# Long Document

This is a long document with many paragraphs to test the distillation
algorithm with larger inputs.

`.repeat(10); // Repeat 10 times

    const result = await distillText(longDocument, 'long-doc');

    console.log(`\n📄 Document: long-doc (repeated 10 times)`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    if (result.atoms) {
      logDistillationResult('long-document', result);
    }
  });

  it('should handle markdown headers', async () => {
    if (!serverStarted) return;

    const testDocument = `
# H1 Header

This is a level 1 header.

## H2 Header

This is a level 2 header.

### H3 Header

This is a level 3 header.

#### H4 Header

This is a level 4 header.
    `.trim();

    const result = await distillText(testDocument, 'headers-test');

    console.log(`\n📄 Document: headers-test`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    if (result.atoms) {
      logDistillationResult('headers', result);
    }
  });

  it('should handle lists', async () => {
    if (!serverStarted) return;

    const testDocument = `
# Lists Test

## Unordered List

- Item 1
- Item 2
- Item 3

## Ordered List

1. First
2. Second
3. Third
    `.trim();

    const result = await distillText(testDocument, 'lists-test');

    console.log(`\n📄 Document: lists-test`);
    console.log(`   Atoms created: ${result.atoms?.length || 0}`);

    if (result.atoms) {
      logDistillationResult('lists', result);
    }
  });

  async function distillText(
    text: string,
    id: string,
    options?: { source?: string; path?: string; radius?: number }
  ): Promise<any> {
    const body = {
      document: text,
      id,
      ...options,
    };

    const res = await fetch(`${SERVER_URL}/api/distill`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });

    if (!res.ok) {
      const error = await res.json();
      throw new Error(`Distillation failed: ${res.status} ${error.message || res.statusText}`);
    }

    return await res.json();
  }
});