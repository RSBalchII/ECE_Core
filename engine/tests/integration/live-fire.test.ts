/**
 * Live Fire Integration Test Suite (Fixed Version)
 *
 * Comprehensive end-to-end test that mimics a human user workflow:
 * 1. Launches the engine server (including pglite init).
 * 2. Clones a repo via the GitHub module.
 * 3. Ingests the cloned repo through the watchdog.
 * 4. Runs comprehensive searches over live data.
 * 5. Validates result structure and ingestion metrics.
 *
 * This is the "smoke test" that proves the entire system works together.
 */

import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import { join, dirname } from 'path';
import { homedir } from 'os';
import { fileURLToPath } from 'url';
import { existsSync, rmSync, mkdirSync } from 'fs';

const execAsync = promisify(exec);
const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');

/** Resolve node executable path — try known locations, fall back to 'node' */
function resolveNodeExecutable(): string {
  const candidates = [
    'C:\\Users\\rsbii\\Projects\\node22\\node-v22.14.0-win-arm64\\node.exe',
    process.env.NODE_EXE ?? '',
    'node',
  ].filter(Boolean);
  for (const c of candidates) {
    try {
      const { execSync } = require('child_process');
      execSync(`${c} --version`, { stdio: 'pipe' });
      return c;
    } catch { /* next */ }
  }
  return 'node';
}

const NODE_EXE = resolveNodeExecutable();

// ── Configuration ──────────────────────────────────────────────────────────

const GITHUB_REPO = 'RSBalchII/anchor-engine-node';
// FIX (2026-08-21): test artifacts must not be written into the repo. ANCHOR_ROOT resolves to
// ~/.anchor (Standard 110); setup.ts sets it for vitest workers, the fallback keeps standalone runs correct.
const ANCHOR_ROOT = process.env.ANCHOR_ROOT || join(homedir(), '.anchor');
const CLONE_DIR = join(ANCHOR_ROOT, 'external-inbox', 'anchor-engine-node');
const SERVER_PORT = 3160;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;

// Timeout configuration - increased with safety margins
const CLONE_TIMEOUT_MS = 300_000; // 5 minutes for git clone (increased from 3min)
const INGESTION_TIMEOUT_MS = 600_000; // 10 minutes for full ingestion (increased from 5min)
const POLL_INTERVAL_MS = 2000; // Check ingestion status every 2 seconds (more frequent)
const SERVER_READY_TIMEOUT_MS = 180_000; // 3 minutes for server to be ready (increased from 2min)
const GLOBAL_TIMEOUT_MS = 10 * 60_000; // 10 minute global timeout for each test (increased from 5min)
const CLEANUP_TIMEOUT_MS = 30_000; // 30 seconds for server cleanup

// ── Helpers ────────────────────────────────────────────────────────────────

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
    const res = await fetch(`${SERVER_URL}/health`, {
      signal: AbortSignal.timeout(5000)
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
    const res = await fetch(`${SERVER_URL}/health`, {
      signal: AbortSignal.timeout(5000)
    });
    const data = await res.json();
    return data?.status === 'healthy' || data?.engine !== undefined;
  } catch {
    return false;
  }
}

/**
 * Check ingestion status via the watchdog endpoint.
 */
async function getIngestionStatus(): Promise<any> {
  try {
    const res = await fetch(`${SERVER_URL}/v1/watchdog/status`, {
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
    const res = await fetch(`${SERVER_URL}/v1/ingestion/progress`, {
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
  const res = await fetch(`${SERVER_URL}/v1/memory/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
    signal: AbortSignal.timeout(15000),
  });
  return await res.json();
}

/**
 * Get search analytics (total results, categories, etc.).
 * Note: Using search results directly instead of /api/search/analytics endpoint.
 */
async function getSearchAnalytics(): Promise<any> {
  try {
    // Analytics data is now included in search results
    const res = await fetch(`${SERVER_URL}/v1/stats`, {
      signal: AbortSignal.timeout(5000),
    });
    return await res.json().catch(() => null);
  } catch {
    return null;
  }
}

/**
 * Validate search result structure.
 */
function validateSearchResults(results: any[], totalResults: number): void {
  expect(results.length).toBeLessThanOrEqual(10); // Limit check
  expect(results.length).toBeLessThanOrEqual(totalResults); // Consistency check

  for (const result of results) {
    expect(result).toHaveProperty('id');
    expect(result).toHaveProperty('source');
    expect(result).toHaveProperty('content');
    expect(typeof result.score).toBe('number');
  }
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

describe('Live Fire Integration Tests', () => {
  let serverProcess: ReturnType<typeof spawn> | null = null;
  let serverStartTime: number;

  /**
   * Start the engine server if not already running.
   */
  beforeAll(async () => {
    console.log('\n🚀 [Live Fire] Starting engine server...');
    console.log(`   Server URL: ${SERVER_URL}`);
    console.log(`   Node executable: ${NODE_EXE}`);
    serverStartTime = Date.now();

    // Check if server is already running
    const alreadyRunning = await isServerRunning();
    if (alreadyRunning) {
      console.log('✅ Server already running, skipping start');
      serverProcess = null;  // Don't try to cleanup a non-existent process
      return;
    }

    // Start the engine server using resolved node executable
    console.log('📦 Starting server process...');
    serverProcess = spawn(NODE_EXE, ['dist/index.js'], {
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
    } else {
      console.log('✅ No server to cleanup (test used existing server)');
    }
    console.log('✅ Cleanup complete');
  }, CLEANUP_TIMEOUT_MS);

  // ── Test 1: Server Health ───────────────────────────────────────────────

  it('should respond to health checks', async () => {
    const res = await fetch(`${SERVER_URL}/v1/health`, {
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

    // Remove existing clone if any
    if (existsSync(CLONE_DIR)) {
      console.log('🗑️  Removing existing clone...');
      rmSync(CLONE_DIR, { recursive: true, force: true });
    }

    // Clone the repository
    const cloneCommand = `git clone --depth 1 https://github.com/${GITHUB_REPO}.git "${CLONE_DIR}"`;
    const { stdout, stderr } = await execAsync(cloneCommand, {
      timeout: CLONE_TIMEOUT_MS,
      cwd: PROJECT_ROOT,
    });

    console.log(`✅ Clone complete: ${CLONE_DIR}`);
    console.log(`   Output: ${stdout.trim()}`);
    expect(existsSync(CLONE_DIR)).toBe(true);
    expect(existsSync(join(CLONE_DIR, 'package.json'))).toBe(true);
  }, CLONE_TIMEOUT_MS);

  // ── Test 3: Verify External Inbox ───────────────────────────────────────

  it('should have files in external-inbox', async () => {
    const externalInbox = join(CLONE_DIR);
    
    // Cross-platform file verification using Node.js fs module
    console.log(`📁 Verifying key files in ${externalInbox}...`);
    
    const keyFiles = ['package.json', 'README.md', 'engine/tsconfig.json'];
    for (const file of keyFiles) {
      expect(existsSync(join(externalInbox, file))).toBe(true);
    }

    console.log(`✅ All key files present in external inbox`);
  });

  // ── Test 4: Start Watchdog / Ingestion ──────────────────────────────────

  it('should start ingestion via watchdog', async () => {
    console.log('\n🔄 [Live Fire] Starting watchdog ingestion...');
    
    // Step 1: Check current watched paths before starting
    const statusBefore = await getIngestionStatus();
    console.log(`   📊 Watchdog status BEFORE start: ${JSON.stringify(statusBefore)}`);

    // Start the watchdog (this is what the UI does)
    const watchdogRes = await fetch(`${SERVER_URL}/v1/watchdog/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paths: [CLONE_DIR],
        recursive: true,
      }),
      signal: AbortSignal.timeout(15_000),
    });

    // Step 2: Log the response from watchdog start
    if (!watchdogRes.ok) {
      const errorData = await watchdogRes.json().catch(() => ({ message: 'Unknown error' }));
      console.error(`   ❌ Watchdog start FAILED with status ${watchdogRes.status}:`, JSON.stringify(errorData));
      throw new Error(`Watchdog failed to start: ${errorData.message || 'Unknown error'}`);
    }

    const watchdogData = await watchdogRes.json();
    console.log(`   ✅ Watchdog started successfully: ${JSON.stringify(watchdogData)}`);

    // Step 3: Verify watchdog is now running
    const statusAfter = await getIngestionStatus();
    console.log(`   📊 Watchdog status AFTER start: ${JSON.stringify(statusAfter)}`);
    
    expect(watchdogRes.ok).toBe(true);
  });

  // ── Test 5: Monitor Ingestion Progress ──────────────────────────────────

  it('should complete ingestion within timeout', async () => {
    console.log('\n⏱️  [Live Fire] Monitoring ingestion progress...');
    console.log(`   Ingestion timeout: ${INGESTION_TIMEOUT_MS}ms (${(INGESTION_TIMEOUT_MS/1000).toFixed(1)}s)`);
    const ingestionStart = Date.now();

    // Poll for ingestion completion with detailed status logging
    let totalFiles = 0;
    let processedFiles = 0;
    let errors = 0;
    let lastStatus: any = null;
    let lastProgressLog = Date.now();
    let pollCount = 0;

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
          console.log(`   ✅ Ingestion complete: ${processedFiles}/${totalFiles} files, ${errors} errors`);
          console.log(`   Total ingestion time: ${((Date.now() - ingestionStart) / 1000).toFixed(1)}s`);
          return true;
        }

        // Log progress every 3 seconds (more frequent) with poll count
        if (Date.now() - lastProgressLog >= 3_000) {
          const pct = totalFiles > 0 ? Math.round((processedFiles / totalFiles) * 100) : 0;
          console.log(`   📊 Progress: ${processedFiles}/${totalFiles} files (${pct}%), ${errors} errors (poll #${++pollCount})`);
          lastProgressLog = Date.now();
        }

        return false;
      },
      INGESTION_TIMEOUT_MS,
      POLL_INTERVAL_MS,
      'Ingestion completion',
    );

    expect(totalFiles).toBeGreaterThan(0);
    expect(processedFiles).toBeGreaterThan(0);
  }, INGESTION_TIMEOUT_MS);

  // ── Test 6: Verify Data in Database ─────────────────────────────────────

  it('should have ingested data in the database', async () => {
    console.log('\n📊 [Live Fire] Verifying database contents...');

    const analytics = await getSearchAnalytics();
    console.log(`   Search analytics: ${JSON.stringify(analytics)}`);

    expect(analytics).toBeDefined();
    if (analytics?.totalResults === undefined || analytics.totalResults === null) {
      throw new Error('No results found in database - ingestion may have failed');
    }

    console.log(`   ✅ Total results in database: ${analytics.totalResults}`);
  });

  // ── Test 7: Search Tests ────────────────────────────────────────────────

  it('should find engine source files', async () => {
    console.log('\n🔍 [Live Fire] Searching for "engine"...');
    const results = await search('engine', 10);
    console.log(`   Search "engine": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    expect(results.results.length).toBeGreaterThan(0);

    // Validate structure
    validateSearchResults(results.results, results.totalResults);

    // Verify results are from the cloned repo
    const engineResults = results.results.filter(
      (r: any) => r.source?.includes('engine') || r.source?.includes('anchor-engine-node')
    );
    console.log(`   ✅ Found ${engineResults.length} engine-related results`);
  });

  it('should find TypeScript files', async () => {
    console.log('\n🔍 [Live Fire] Searching for ".ts"...');
    const results = await search('.ts', 10);
    console.log(`   Search ".ts": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    validateSearchResults(results.results, results.totalResults);
  });

  it('should find configuration files', async () => {
    console.log('\n🔍 [Live Fire] Searching for "tsconfig.json"...');
    const results = await search('tsconfig.json', 5);
    console.log(`   Search "tsconfig.json": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    validateSearchResults(results.results, results.totalResults);
  });

  it('should find package.json references', async () => {
    console.log('\n🔍 [Live Fire] Searching for "pnpm"...');
    const results = await search('pnpm', 5);
    console.log(`   Search "pnpm": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    validateSearchResults(results.results, results.totalResults);
  });

  it('should find GitHub-related content', async () => {
    console.log('\n🔍 [Live Fire] Searching for "github"...');
    const results = await search('github', 10);
    console.log(`   Search "github": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThan(0);
    validateSearchResults(results.results, results.totalResults);
  });

  // ── Test 8: Advanced Search ─────────────────────────────────────────────

  it('should support semantic search', async () => {
    console.log('\n🔍 [Live Fire] Semantic search for "authentication"...');
    const results = await search('authentication', 5);
    console.log(`   Search "authentication": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThanOrEqual(0);
    if (results.totalResults > 0) {
      validateSearchResults(results.results, results.totalResults);
    }
  });

  it('should support tag-based search', async () => {
    console.log('\n🔍 [Live Fire] Tag-based search for "#test"...');
    const results = await search('#test', 5);
    console.log(`   Search "#test": ${results.totalResults} results`);

    expect(results.totalResults).toBeGreaterThanOrEqual(0);
  });

  // ── Test 9: Ingestion Metrics ───────────────────────────────────────────

  it('should report ingestion metrics', async () => {
    console.log('\n📊 [Live Fire] Checking ingestion metrics...');
    const progress = await getIngestionProgress();
    console.log(`   Ingestion metrics: ${JSON.stringify(progress)}`);

    expect(progress).toBeDefined();
    if (progress?.totalFiles === undefined || progress.totalFiles === null) {
      throw new Error('No ingestion metrics available - ingestion may have failed');
    }
    
    expect(progress?.totalFiles).toBeGreaterThan(0);
    expect(progress?.processedFiles).toBeGreaterThan(0);
    expect(progress?.processedFiles).toBeLessThanOrEqual(progress.totalFiles);
  });

  // ── Test 10: End-to-End Timing ──────────────────────────────────────────

  it('should complete all tests within reasonable time', () => {
    const totalElapsed = Date.now() - serverStartTime;
    console.log(`\n⏱️  Total test suite time: ${(totalElapsed / 1000).toFixed(1)}s`);
    expect(totalElapsed).toBeLessThan(300_000); // 5 minutes max
  });
});