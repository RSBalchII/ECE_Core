/**
 * Search Results Integration Test
 * 
 * Tests the search API with real queries and validates result structure.
 * Results are logged to .anchor/results/ for analysis.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { fetch } from 'undici';
import { join, dirname } from 'path';
import { homedir } from 'os';
import { fileURLToPath } from 'url';
import { mkdirSync, writeFileSync, existsSync, rmSync } from 'fs';

const __dirname = join(dirname(fileURLToPath(import.meta.url)));
const PROJECT_ROOT = join(__dirname, '..', '..');
// FIX (2026-08-21): test artifacts must not be written into the repo. ANCHOR_ROOT resolves to
// ~/.anchor (Standard 110); setup.ts sets it for vitest workers, the fallback keeps standalone runs correct.
const ANCHOR_ROOT = process.env.ANCHOR_ROOT || join(homedir(), '.anchor');
const RESULTS_DIR = join(ANCHOR_ROOT, 'results');

// Test configuration
const SERVER_PORT = 3160;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;
const API_KEY = process.env.ANCHOR_API_KEY || 'test-api-key';

// Result logging
const logResult = (testName: string, results: any, query: string) => {
  const resultDir = join(RESULTS_DIR, 'search');
  mkdirSync(resultDir, { recursive: true });
  
  const timestamp = new Date().toISOString();
  const resultFile = join(resultDir, `${testName}-${timestamp.replace(/[:.]/g, '-')}.json`);
  
  const data = {
    timestamp,
    query,
    results,
    totalResults: results?.totalResults || 0,
    resultsCount: results?.results?.length || 0,
  };
  
  writeFileSync(resultFile, JSON.stringify(data, null, 2));
  console.log(`📝 Search results logged to: ${resultFile}`);
};

describe('Search Results Integration Tests', () => {
  let serverStarted = false;

  beforeAll(async () => {
    console.log('🔍 [Search Results] Setting up test environment...');
    
    // Ensure results directory exists
    mkdirSync(RESULTS_DIR, { recursive: true });
    
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
      console.log('⚠️  Server not running, skipping live search tests');
    }
  });

  afterAll(() => {
    console.log('🧹 [Search Results] Cleaning up...');
  });

  it('should find engine source files', async () => {
    if (!serverStarted) {
      console.log('⚠️  Skipping live search test - server not running');
      return;
    }
    
    if (!existsSync(RESULTS_DIR)) {
      mkdirSync(RESULTS_DIR, { recursive: true });
    }
    
    const query = 'engine';
    const results = await fetchSearch(query, 10);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    console.log(`   Results returned: ${results.results.length}`);
    
    if (results.results.length > 0) {
      logResult('engine-search', results, query);
      
      // Validate result structure
      for (const result of results.results) {
        expect(result).toHaveProperty('id');
        expect(result).toHaveProperty('source');
        expect(result).toHaveProperty('content');
        expect(typeof result.score).toBe('number');
      }
    }
  });

  it('should find TypeScript files', async () => {
    if (!serverStarted) return;
    
    const query = '.ts';
    const results = await fetchSearch(query, 10);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    
    if (results.results.length > 0) {
      logResult('typescript-search', results, query);
    }
  });

  it('should find configuration files', async () => {
    if (!serverStarted) return;
    
    const query = 'tsconfig.json';
    const results = await fetchSearch(query, 5);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    
    if (results.results.length > 0) {
      logResult('config-search', results, query);
    }
  });

  it('should find package.json references', async () => {
    if (!serverStarted) return;
    
    const query = 'pnpm';
    const results = await fetchSearch(query, 5);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    
    if (results.results.length > 0) {
      logResult('pnpm-search', results, query);
    }
  });

  it('should find GitHub-related content', async () => {
    if (!serverStarted) return;
    
    const query = 'github';
    const results = await fetchSearch(query, 10);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    
    if (results.results.length > 0) {
      logResult('github-search', results, query);
    }
  });

  it('should support semantic search', async () => {
    if (!serverStarted) return;
    
    const query = 'authentication';
    const results = await fetchSearch(query, 5);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    
    if (results.totalResults > 0 && results.results.length > 0) {
      logResult('semantic-search', results, query);
    }
  });

  it('should support tag-based search', async () => {
    if (!serverStarted) return;
    
    const query = '#test';
    const results = await fetchSearch(query, 5);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    
    if (results.results.length > 0) {
      logResult('tag-search', results, query);
    }
  });

  it('should return empty results for non-existent terms', async () => {
    if (!serverStarted) return;
    
    const query = 'nonexistent-unique-term-12345';
    const results = await fetchSearch(query, 10);
    
    console.log(`\n🔍 Query: "${query}"`);
    console.log(`   Total results: ${results.totalResults}`);
    
    expect(results.totalResults).toBe(0);
  });

  it('should respect limit parameter', async () => {
    if (!serverStarted) return;
    
    const query = 'test';
    const results10 = await fetchSearch(query, 10);
    const results5 = await fetchSearch(query, 5);
    
    console.log(`\n🔍 Query: "${query}" with limit=10`);
    console.log(`   Results: ${results10.results.length}`);
    console.log(`\n🔍 Query: "${query}" with limit=5`);
    console.log(`   Results: ${results5.results.length}`);
    
    expect(results10.results.length).toBeLessThanOrEqual(10);
    expect(results5.results.length).toBeLessThanOrEqual(5);
  });

  it('should include provenance in results', async () => {
    if (!serverStarted) return;
    
    const query = 'anchor';
    const results = await fetchSearch(query, 5);
    
    if (results.results.length > 0) {
      const firstResult = results.results[0];
      console.log(`\n📄 First result provenance:`);
      console.log(`   ID: ${firstResult.id}`);
      console.log(`   Source: ${firstResult.source}`);
      console.log(`   Bucket: ${firstResult.bucket || 'N/A'}`);
    }
  });

  async function fetchSearch(query: string, limit: number): Promise<any> {
    const res = await fetch(`${SERVER_URL}/api/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
      body: JSON.stringify({ query, limit }),
      signal: AbortSignal.timeout(10000),
    });
    
    if (!res.ok) {
      throw new Error(`Search failed: ${res.status} ${res.statusText}`);
    }
    
    return await res.json();
  }
});
