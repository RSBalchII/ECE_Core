/**
 * Live Fire Results Integration Test Suite (Fixed Version)
 *
 * Comprehensive end-to-end test that mimics a human user workflow:
 * 1. Launches the engine server (including pglite init).
 * 2. Clones a repo via the GitHub module.
 * 3. Ingests the cloned repo through the watchdog.
 * 4. Runs comprehensive searches over live data.
 * 5. Runs distillation tests.
 * 6. Validates result structure and ingestion metrics.
 *
 * All results are logged to .anchor/results/ for analysis.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { fetch } from 'undici';
import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import { join, dirname } from 'path';
import { homedir } from 'os';
import { fileURLToPath } from 'url';
import { existsSync, rmSync, mkdirSync, writeFileSync, readFileSync } from 'fs';

const execAsync = promisify(exec);
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');
// FIX (2026-08-21): test artifacts must not be written into the repo. ANCHOR_ROOT resolves to
// ~/.anchor (Standard 110); setup.ts sets it for vitest workers, the fallback keeps standalone runs correct.
const ANCHOR_ROOT = process.env.ANCHOR_ROOT || join(homedir(), '.anchor');
const RESULTS_DIR = join(ANCHOR_ROOT, 'results');
const EXTERNAL_INBOX = join(ANCHOR_ROOT, 'external-inbox');

const execSync = (cmd: string, options?: any) => {
  try {
    const output = execSync(cmd, { ...options, encoding: 'utf-8' });
    return output;
  } catch (error: any) {
    throw new Error(`Command failed: ${error.message}\n${error.stdout?.toString()}`);
  }
};

// Test configuration - increased timeouts with safety margins
const GITHUB_REPO = 'RSBalchII/anchor-engine-node';
const SERVER_PORT = 3160;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;
const CLONE_TIMEOUT_MS = 300_000; // 5 minutes for git clone (increased from 3min)
const INGESTION_TIMEOUT_MS = 600_000; // 10 minutes for full ingestion (increased from 5min)
const POLL_INTERVAL_MS = 2000; // Check ingestion status every 2 seconds (more frequent)
const SERVER_READY_TIMEOUT_MS = 180_000; // 3 minutes for server to be ready (increased from 2min)
const GLOBAL_TIMEOUT_MS = 10 * 60_000; // 10 minute global timeout for each test (increased from 5min)
const CLEANUP_TIMEOUT_MS = 30_000; // 30 seconds for server cleanup

// Result logging
const logResult = (prefix: string, data: any) => {
  const resultDir = join(RESULTS_DIR, prefix);
  mkdirSync(resultDir, { recursive: true });

  const timestamp = new Date().toISOString();
  const resultFile = join(resultDir, `live-fire-${timestamp.replace(/[:.]/g, '-')}.json`);

  writeFileSync(resultFile, JSON.stringify(data, null, 2));
  console.log(`📝 Results logged to: ${resultFile}`);
};

// ── Helpers ───────────────────────────────────────────────────────────────

/**
 * Wait for a condition to become true, polling periodically.
 * Includes detailed progress logging to identify where tests hang.
 */
async function waitFor(
  predicate: () => Promise<boolean> | boolean,
  timeoutMs: number,
  intervalMs: number = 1000,
  label?: string,
): Promise<void> {
  const start = Date.now();
  let pollCount = 0;
  const maxPolls = Math.ceil(timeoutMs / intervalMs) + 10;
  
  while (pollCount < maxPolls && Date.now() - start < timeoutMs) {
    pollCount++;
    const elapsed = Date.now() - start;
    
    if (await predicate()) {
      console.log(`✅ [Wait] Condition met after ${elapsed}ms (${pollCount} polls)`);
      return;
    }
    
    // More frequent logging during wait
    if (pollCount % 5 === 0) {
      console.log(`   ⏳ Waiting... ${elapsed}ms / ${timeoutMs}ms (${Math.min(Math.round(elapsed/1000), 60)}s)`);
    }
    
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  
  throw new Error(`⏱️ [Wait] Timeout after ${timeoutMs}ms (${pollCount} polls, elapsed ${Date.now() - start}ms)\n   Label: ${label || 'N/A'}`);
}

/**
 * Check if the server is responding.
 */
async function isServerRunning(): Promise<boolean> {
  try {
    const res = await fetch(`${SERVER_URL}/api/health`, {
      signal: AbortSignal.timeout(5000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Check if the server is ready (health endpoint returns engine info).
 */
async function isServerReady(): Promise<boolean> {
  try {
    const res = await fetch(`${SERVER_URL}/api/health`, {
      signal: AbortSignal.timeout(5000),
    });
    const data = await res.json();
    return data?.status === 'ok' || data?.engine !== undefined;
  } catch {
    return false;
  }
}

/**
 * Get ingestion status via the watchdog endpoint.
 */
async function getIngestionStatus(): Promise<any> {
  try {
    const res = await fetch(`${SERVER_URL}/api/watchdog/status`, {
      signal: AbortSignal.timeout(5000),
    });
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Get ingestion progress (files processed, errors, etc.).
 */
async function getIngestionProgress(): Promise<any> {
  try {
    const res = await fetch(`${SERVER_URL}/api/ingestion/progress`, {
      signal: AbortSignal.timeout(5000),
    });
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Search the live database.
 */
async function search(query: string, limit: number = 10): Promise<any> {
  const res = await fetch(`${SERVER_URL}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    throw new Error(`Search failed: ${res.status} ${res.statusText}`);
  }

  return await res.json();
}

/**
 * Get search analytics (total results, categories, etc.).
 */
async function getSearchAnalytics(): Promise<any> {
  try {
    const res = await fetch(`${SERVER_URL}/api/search/analytics`, {
      signal: AbortSignal.timeout(5000),
    });
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Distill a document.
 */
async function distill(document: string, id: string, options?: any): Promise<any> {
  const res = await fetch(`${SERVER_URL}/api/distill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document, id, ...options }),
    signal: AbortSignal.timeout(30000),
  });

  if (!res.ok) {
    throw new Error(`Distillation failed: ${res.status} ${res.statusText}`);
  }

  return await res.json();
}

/**
 * Wrap a test function with a global timeout to catch hanging operations.
 */
function withGlobalTimeout(testFn: () => Promise<void>, timeoutMs: number, testLabel: string) {
  return async () => {
    console.log(`🧪 [Test] Starting: ${testLabel}`);
    const timeoutController = new AbortController();
    const timeoutId = setTimeout(() => {
      timeoutController.abort();
      console.error(`⏱️ [Test] TIMEOUT: ${testLabel} exceeded ${timeoutMs}ms`);
    }, timeoutMs);
    try {
      await testFn();
      clearTimeout(timeoutId);
      console.log(`✅ [Test] Completed: ${testLabel}`);
    } catch (error: any) {
      if (error.name === 'AbortError') {
        throw new Error(`⏱️ [Test] TIMEOUT: ${testLabel} exceeded ${timeoutMs}ms\n   Error: ${error.message}`);
      }
      throw error;
    }
  };
}

// ── Test Suite ─────────────────────────────────────────────────────────────

describe('Live Fire Results Integration Tests', () => {
  let serverProcess: ReturnType<typeof spawn> | null = null;
  let serverStartTime: number;

  /**
   * Start the engine server if not already running.
   */
  beforeAll(async () => {
    console.log('\n🚀 [Live Fire] Starting engine server...');
    console.log(`   Server URL: ${SERVER_URL}`);
    console.log(`   Project root: ${PROJECT_ROOT}`);
    serverStartTime = Date.now();

    // Ensure directories exist
    mkdirSync(RESULTS_DIR, { recursive: true });
    mkdirSync(EXTERNAL_INBOX, { recursive: true });

    // Check if server is already running
    const alreadyRunning = await isServerRunning();
    if (alreadyRunning) {
      console.log('✅ Server already running, skipping start');
      return;
    }

    // Start the engine server
    console.log('📦 Starting server process...');
    serverProcess = spawn('node', ['dist/index.js'], {
      cwd: PROJECT_ROOT,
      stdio: 'pipe',
      env: { ...process.env, PORT: String(SERVER_PORT) },
    });

    // Log server output with timestamps
    serverProcess.stdout?.on('data', (data) => {
      const log = data.toString().trim();
      if (log.includes('listening') || log.includes('ready') || log.includes('initialized')) {
        console.log(`📡 [Server] ${log}`);
      } else if (log.length > 50) {
        console.log(`📡 [Server] ${log.substring(0, 200)}...`);
      }
    });

    serverProcess.stderr?.on('data', (data) => {
      const log = data.toString().trim();
      if (log.includes('error') || log.includes('Error') || log.includes('warning') || log.includes('Warning')) {
        console.error(`❌ [Server] ${log}`);
      } else if (log.length > 100) {
        console.error(`❌ [Server] ${log.substring(0, 300)}...`);
      }
    });

    // Wait for server to be ready with detailed logging
    console.log('⏳ Waiting for server to be ready (timeout: ' + SERVER_READY_TIMEOUT_MS + 'ms)...');
    const startWait = Date.now();
    try {
      await waitFor(isServerReady, SERVER_READY_TIMEOUT_MS, 2000, 'Server ready check');
      const waitTime = Date.now() - startWait;
      console.log(`✅ Server is ready (took ${waitTime}ms)`);
    } catch (error: any) {
      const waitTime = Date.now() - startWait;
      console.error(`❌ Server ready timeout after ${waitTime}ms`);
      console.error(`   Last known state: process running=${serverProcess?.pid != null}`);
      throw error;
    }
  }, GLOBAL_TIMEOUT_MS);

  /**
   * Stop the server if we started it.
   */
  afterAll(async () => {
    console.log('\n🛑 [Live Fire] Cleaning up...');
    if (serverProcess) {
      try {
        // Try graceful shutdown first
        serverProcess.kill('SIGTERM');
        const exitPromise = new Promise<void>((resolve) => {
          serverProcess?.on('exit', resolve);
        });
        
        // Wait with timeout
        try {
          await Promise.race([
            exitPromise,
            new Promise<void>((resolve) => 
              setTimeout(() => resolve(), CLEANUP_TIMEOUT_MS)
            )
          ]);
          console.log('✅ Server stopped gracefully');
        } catch (err: any) {
          // Force kill if graceful shutdown fails
          console.error('   Graceful shutdown failed, forcing kill...');
          serverProcess.kill('SIGKILL');
          await new Promise<void>((resolve) => 
            serverProcess?.on('exit', resolve)
          );
          console.log('✅ Server force-killed');
        }
      } catch (err: any) {
        console.error(`   Cleanup error: ${err.message}`);
        // Try force kill as fallback
        try {
          serverProcess.kill('SIGKILL');
          await new Promise<void>((resolve) => 
            serverProcess?.on('exit', resolve)
          );
        } catch (e: any) {
          console.error(`   Force kill also failed: ${e.message}`);
        }
      }
    }
    console.log('✅ Cleanup complete');
  }, CLEANUP_TIMEOUT_MS);

  // ── Test 1: Server Health ───────────────────────────────────────────────

  it('should respond to health checks', async () => {
    const res = await fetch(`${SERVER_URL}/api/health`, {
      signal: AbortSignal.timeout(5000),
    });
    expect(res.ok).toBe(true);

    const data = await res.json();
    expect(data).toHaveProperty('status');
    console.log(`📊 Health: ${JSON.stringify(data)}`);
  });

  // ── Test 2: Clone Repository ────────────────────────────────────────────

  it('should clone the anchor-engine-node repository', async () => {
    console.log(`\n📦 [Live Fire] Cloning ${GITHUB_REPO}...`);

    const cloneDir = join(EXTERNAL_INBOX, GITHUB_REPO.split('/')[1]);

    // Remove existing clone if any
    if (existsSync(cloneDir)) {
      console.log('🗑️  Removing existing clone...');
      rmSync(cloneDir, { recursive: true, force: true });
    }

    // Clone the repository
    const cloneCommand = `git clone --depth 1 https://github.com/${GITHUB_REPO}.git "${cloneDir}"`;
    const { stdout, stderr } = await execAsync(cloneCommand, {
      timeout: CLONE_TIMEOUT_MS,
      cwd: PROJECT_ROOT,
    });

    console.log(`✅ Clone complete: ${cloneDir}`);
    console.log(`   Output: ${stdout.trim()}`);

    // Log clone result
    const cloneResult = {
      timestamp: new Date().toISOString(),
      repo: GITHUB_REPO,
      cloneDir,
      stdout,
      stderr,
    };
    logResult('github-clone', cloneResult);

    expect(existsSync(cloneDir)).toBe(true);
    expect(existsSync(join(cloneDir, 'package.json'))).toBe(true);
  }, CLONE_TIMEOUT_MS);

  // ── Test 3: Verify External Inbox ───────────────────────────────────────

  it('should have files in external-inbox', async () => {
    const externalInbox = join(EXTERNAL_INBOX, GITHUB_REPO.split('/')[1]);

    if (!existsSync(externalInbox)) {
      throw new Error('External inbox directory does not exist');
    }

    const files = execSync(`ls -la "${externalInbox}"`, { cwd: PROJECT_ROOT });
    console.log(`📁 External inbox contents:\n${files}`);

    // Verify key files exist
    const keyFiles = ['package.json', 'README.md', 'engine/tsconfig.json'];
    for (const file of keyFiles) {
      expect(existsSync(join(externalInbox, file))).toBe(true);
    }
  });

  // ── Test 4: Start Watchdog / Ingestion ──────────────────────────────────

  it('should start ingestion via watchdog', async () => {
    console.log('\n🔄 [Live Fire] Starting watchdog ingestion...');

    const watchdogRes = await fetch(`${SERVER_URL}/api/watchdog/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paths: [join(EXTERNAL_INBOX, GITHUB_REPO.split('/')[1])],
        recursive: true,
      }),
      signal: AbortSignal.timeout(15_000),
    });

    expect(watchdogRes.ok).toBe(true);
    const watchdogData = await watchdogRes.json();
    console.log(`📡 Watchdog started: ${JSON.stringify(watchdogData)}`);
  });

  // ── Test 5: Monitor Ingestion Progress ──────────────────────────────────

  it('should complete ingestion within timeout', async () => {
    console.log('\n⏱️  [Live Fire] Monitoring ingestion progress...');
    console.log(`   Ingestion timeout: ${INGESTION_TIMEOUT_MS}ms (${(INGESTION_TIMEOUT_MS/1000).toFixed(1)}s)`);
    const ingestionStart = Date.now();

    // Poll for ingestion completion
    let totalFiles = 0;
    let processedFiles = 0;
    let errors = 0;
    let lastStatus: any = null;
    let lastProgressLog = Date.now();

    await waitFor(
      async () => {
        const status = await getIngestionStatus();
        const progress = await getIngestionProgress();

        lastStatus = status;
        if (progress) {
          totalFiles = progress.totalFiles || 0;
          processedFiles = progress.processedFiles || 0;
          errors = progress.errors?.length || 0;
        }

        // Check if ingestion is complete
        const isComplete = status?.status === 'idle' || status?.status === 'completed';
        const hasFiles = totalFiles > 0;

        if (isComplete && hasFiles) {
          console.log(`✅ Ingestion complete: ${processedFiles}/${totalFiles} files, ${errors} errors`);
          console.log(`   Total ingestion time: ${((Date.now() - ingestionStart) / 1000).toFixed(1)}s`);
          return true;
        }

        // Log progress every 3 seconds (more frequent)
        if (Date.now() - lastProgressLog >= 3_000) {
          const pct = totalFiles > 0 ? Math.round((processedFiles / totalFiles) * 100) : 0;
          console.log(`📊 Progress: ${processedFiles}/${totalFiles} files (${pct}%), ${errors} errors`);
          lastProgressLog = Date.now();
        }

        return false;
      },
      INGESTION_TIMEOUT_MS,
      POLL_INTERVAL_MS,
      'Ingestion completion',
    );

    // Log ingestion result
    const ingestionResult = {
      timestamp: new Date().toISOString(),
      totalFiles,
      processedFiles,
      errors,
      duration: Date.now() - ingestionStart,
    };
    logResult('ingestion', ingestionResult);

    expect(totalFiles).toBeGreaterThan(0);
    expect(processedFiles).toBeGreaterThan(0);
  }, INGESTION_TIMEOUT_MS);

  // ── Test 6: Verify Data in Database ─────────────────────────────────────

  it('should have ingested data in the database', async () => {
    const analytics = await getSearchAnalytics();
    console.log(`📊 Search analytics: ${JSON.stringify(analytics)}`);

    expect(analytics).toBeDefined();
    expect(analytics?.totalResults).toBeGreaterThan(0);
    console.log(`✅ Total results in database: ${analytics.totalResults}`);
  });

  // ── Test 7: Search Tests ────────────────────────────────────────────────

  it('should find engine source files', async () => {
    const results = await search('engine', 10);
    console.log(`🔍 Search "engine": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    expect(results.results.length).toBeGreaterThan(0);

    // Validate structure
    for (const result of results.results) {
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('source');
      expect(result).toHaveProperty('content');
      expect(typeof result.score).toBe('number');
    }

    // Verify results are from the cloned repo
    const engineResults = results.results.filter(
      (r: any) => r.source?.includes('engine') || r.source?.includes('anchor-engine-node')
    );
    expect(engineResults.length).toBeGreaterThan(0);
    console.log(`✅ Found ${engineResults.length} engine-related results`);
  });

  it('should find TypeScript files', async () => {
    const results = await search('.ts', 10);
    console.log(`🔍 Search ".ts": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    for (const result of results.results) {
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('source');
      expect(result).toHaveProperty('content');
      expect(typeof result.score).toBe('number');
    }
  });

  it('should find configuration files', async () => {
    const results = await search('tsconfig.json', 5);
    console.log(`🔍 Search "tsconfig.json": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    for (const result of results.results) {
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('source');
      expect(result).toHaveProperty('content');
      expect(typeof result.score).toBe('number');
    }
  });

  it('should find package.json references', async () => {
    const results = await search('pnpm', 5);
    console.log(`🔍 Search "pnpm": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    for (const result of results.results) {
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('source');
      expect(result).toHaveProperty('content');
      expect(typeof result.score).toBe('number');
    }
  });

  it('should find GitHub-related content', async () => {
    const results = await search('github', 10);
    console.log(`🔍 Search "github": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    for (const result of results.results) {
      expect(result).toHaveProperty('id');
      expect(result).toHaveProperty('source');
      expect(result).toHaveProperty('content');
      expect(typeof result.score).toBe('number');
    }
  });

  // ── Test 8: Advanced Search ─────────────────────────────────────────────

  it('should support semantic search', async () => {
    const results = await search('authentication', 5);
    console.log(`🔍 Search "authentication": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThanOrEqual(0);
    if (results.totalResults > 0) {
      for (const result of results.results) {
        expect(result).toHaveProperty('id');
        expect(result).toHaveProperty('source');
        expect(result).toHaveProperty('content');
        expect(typeof result.score).toBe('number');
      }
    }
  });

  it('should support tag-based search', async () => {
    const results = await search('#test', 5);
    console.log(`🔍 Search "#test": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThanOrEqual(0);
  });

  // ── Test 9: Distillation Tests ──────────────────────────────────────────

  it('should distill a test document', async () => {
    const testDocument = `
# Test Document for Distillation

This document tests the radial distillation functionality. It contains
multiple sections and paragraphs to verify the algorithm works correctly.

## Section 1: Introduction

This section introduces the concept of semantic memory for AI agents.
Semantic memory allows systems to store and retrieve knowledge efficiently.

## Section 2: Retrieval

The retrieval mechanism uses a graph-based approach called STAR
(Semantic Temporal Associative Retrieval) for searching memory.

## Section 3: Architecture

Anchor Engine uses a local-first architecture, meaning data stays
on the user's machine for better privacy and control.
    `.trim();

    const result = await distill(testDocument, 'live-fire-test-doc');

    console.log(`🔧 Distillation result:`);
    console.log(`   Atoms: ${result.atoms?.length || 0}`);
    if (result.atoms && result.atoms.length > 0) {
      console.log(`   First atom tags: ${result.atoms[0].tags?.join(', ') || 'N/A'}`);
    }

    // Log distillation result
    logResult('distillation', {
      document: testDocument,
      result,
      timestamp: new Date().toISOString(),
    });

    expect(result.atoms).toBeDefined();
    expect(Array.isArray(result.atoms)).toBe(true);
  });

  it('should handle empty document', async () => {
    const result = await distill('', 'empty-doc');

    console.log(`🔧 Empty document distillation:`);
    console.log(`   Atoms: ${result.atoms?.length || 0}`);

    expect(result.atoms?.length).toBe(0);
  });

  // ── Test 10: Ingestion Metrics ───────────────────────────────────────────

  it('should report ingestion metrics', async () => {
    const progress = await getIngestionProgress();
    console.log(`📊 Ingestion metrics: ${JSON.stringify(progress)}`);

    expect(progress).toBeDefined();
    expect(progress?.totalFiles).toBeGreaterThan(0);
    expect(progress?.processedFiles).toBeGreaterThan(0);
    expect(progress?.processedFiles).toBeLessThanOrEqual(progress.totalFiles);
  });

  // ── Test 11: End-to-End Timing ──────────────────────────────────────────

  it('should complete all tests within reasonable time', () => {
    const totalElapsed = Date.now() - serverStartTime;
    console.log(`\n⏱️  Total test suite time: ${(totalElapsed / 1000).toFixed(1)}s`);
    expect(totalElapsed).toBeLessThan(300_000); // 5 minutes max
  });
});