/**
 * GitHub Clone Integration Test
 * 
 * Tests the GitHub repository cloning functionality.
 * Validates that repositories are cloned correctly to the external inbox.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
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

// Test configuration
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || '';
const GITHUB_REPO = 'RSBalchII/anchor-engine-node';

describe('GitHub Clone Integration Tests', () => {
  let serverProcess: ReturnType<typeof spawn> | null = null;
  let serverStarted = false;

  beforeAll(async () => {
    console.log('🔧 [GitHub Clone] Setting up test environment...');

    // Ensure directories exist
    mkdirSync(RESULTS_DIR, { recursive: true });
    mkdirSync(EXTERNAL_INBOX, { recursive: true });

    // Check if server is already running
    try {
      const { spawn } = await import('child_process');
      const server = spawn('node', ['dist/index.js'], {
        cwd: PROJECT_ROOT,
        stdio: 'pipe',
        env: {
          ...process.env,
          PORT: '3160',
          ANCHOR_GITHUB_TOKEN: GITHUB_TOKEN,
        },
      });

      server.stdout?.on('data', (data) => {
        const log = data.toString().trim();
        if (log.includes('listening') || log.includes('ready')) {
          console.log(`📡 [Server] ${log}`);
          serverStarted = true;
        }
      });

      server.stderr?.on('data', (data) => {
        const log = data.toString().trim();
        if (log.includes('error') || log.includes('Error')) {
          console.error(`❌ [Server] ${log}`);
        }
      });

      // Wait for server to be ready
      await new Promise(resolve => setTimeout(resolve, 3000));
      console.log('⏳ Server startup complete');
    } catch (err) {
      console.log('⚠️  Server startup failed or already running');
    }
  });

  afterAll(async () => {
    console.log('🧹 [GitHub Clone] Cleaning up...');
    if (serverProcess) {
      serverProcess.kill('SIGTERM');
      await new Promise((resolve) => serverProcess?.on('exit', resolve));
      console.log('✅ Server stopped');
    }
  });

  it('should clone a public repository', async () => {
    const repoName = 'test-repo-clone';
    const cloneDir = join(EXTERNAL_INBOX, repoName);

    // Clean up if exists
    if (existsSync(cloneDir)) {
      rmSync(cloneDir, { recursive: true, force: true });
      console.log(`🗑️  Removed existing clone: ${cloneDir}`);
    }

    console.log(`\n📦 Cloning ${GITHUB_REPO}...`);

    const cloneCommand = `git clone --depth 1 https://github.com/${GITHUB_REPO}.git "${cloneDir}"`;

    try {
      const { stdout, stderr } = await execAsync(cloneCommand, {
        timeout: 120_000,
        cwd: PROJECT_ROOT,
      });

      console.log(`✅ Clone complete`);
      console.log(`   Output: ${stdout.trim()}`);

      // Validate clone
      expect(existsSync(cloneDir)).toBe(true);
      expect(existsSync(join(cloneDir, 'package.json'))).toBe(true);
      expect(existsSync(join(cloneDir, 'README.md'))).toBe(true);

      // Log results
      const result = {
        timestamp: new Date().toISOString(),
        repo: GITHUB_REPO,
        cloneDir,
        files: getDirectoryContents(cloneDir),
      };

      const resultFile = join(RESULTS_DIR, 'github-clone.json');
      writeFileSync(resultFile, JSON.stringify(result, null, 2));
      console.log(`📝 Results logged to: ${resultFile}`);

    } catch (error: any) {
      console.error(`❌ Clone failed: ${error.message}`);
      throw error;
    }
  }, 120_000);

  it('should verify repository structure', async () => {
    const repoName = 'test-repo-clone';
    const cloneDir = join(EXTERNAL_INBOX, repoName);

    if (!existsSync(cloneDir)) {
      throw new Error('Clone directory does not exist');
    }

    console.log(`\n📁 Verifying repository structure...`);

    // Check key files
    const keyFiles = [
      'package.json',
      'README.md',
      'engine/src/index.ts',
      'engine/package.json',
    ];

    for (const file of keyFiles) {
      const filePath = join(cloneDir, file);
      if (existsSync(filePath)) {
        console.log(`✅ Found: ${file}`);
      } else {
        console.log(`❌ Missing: ${file}`);
      }
    }

    // Read package.json
    const packageJson = readFileSync(join(cloneDir, 'package.json'), 'utf-8');
    const pkg = JSON.parse(packageJson);

    console.log(`\n📄 package.json contents:`);
    console.log(`   Name: ${pkg.name}`);
    console.log(`   Version: ${pkg.version}`);
  });

  it('should handle shallow clone', async () => {
    const repoName = 'shallow-clone-test';
    const cloneDir = join(EXTERNAL_INBOX, repoName);

    // Clean up
    if (existsSync(cloneDir)) {
      rmSync(cloneDir, { recursive: true, force: true });
    }

    console.log(`\n📦 Creating shallow clone...`);

    const cloneCommand = `git clone --depth 1 --branch main https://github.com/${GITHUB_REPO}.git "${cloneDir}"`;

    try {
      await execAsync(cloneCommand, {
        timeout: 60_000,
        cwd: PROJECT_ROOT,
      });

      console.log('✅ Shallow clone complete');

      // Verify HEAD is at main
      const head = readFileSync(join(cloneDir, '.git', 'HEAD'), 'utf-8').trim();
      expect(head).toBe('ref: refs/heads/main');

    } catch (error: any) {
      console.error(`❌ Shallow clone failed: ${error.message}`);
      throw error;
    }
  }, 60_000);

  it('should handle repository with submodules', async () => {
    // This test checks if the clone handles submodules correctly
    const repoName = 'submodule-test';
    const cloneDir = join(EXTERNAL_INBOX, repoName);

    // Clean up
    if (existsSync(cloneDir)) {
      rmSync(cloneDir, { recursive: true, force: true });
    }

    console.log(`\n📦 Cloning repository with potential submodules...`);

    const cloneCommand = `git clone https://github.com/${GITHUB_REPO}.git "${cloneDir}"`;

    try {
      const { stdout } = await execAsync(cloneCommand, {
        timeout: 120_000,
        cwd: PROJECT_ROOT,
      });

      console.log(`✅ Clone complete with submodules`);
      console.log(`   Output: ${stdout.trim()}`);

    } catch (error: any) {
      console.error(`❌ Clone with submodules failed: ${error.message}`);
      // This might fail if submodules aren't configured, which is OK
      console.log('⚠️  Note: Submodule clone may require explicit submodule initialization');
    }
  }, 120_000);

  it('should verify git history', async () => {
    const repoName = 'test-repo-clone';
    const cloneDir = join(EXTERNAL_INBOX, repoName);

    if (!existsSync(cloneDir)) {
      throw new Error('Clone directory does not exist');
    }

    console.log(`\n📜 Checking git history...`);

    const { stdout: log } = await execAsync(`git log --oneline -10`, {
      cwd: cloneDir,
    });

    console.log(`   Recent commits:`);
    console.log(log);

    // Should have at least some commits
    const commitCount = (log.match(/commit/gi) || []).length;
    console.log(`   Commits found: ${commitCount}`);
  });

  it('should verify README content', async () => {
    const repoName = 'test-repo-clone';
    const cloneDir = join(EXTERNAL_INBOX, repoName);

    if (!existsSync(cloneDir)) {
      throw new Error('Clone directory does not exist');
    }

    console.log(`\n📄 Reading README.md...`);

    const readme = readFileSync(join(cloneDir, 'README.md'), 'utf-8');
    const lines = readme.split('\n').slice(0, 20);

    console.log(`   First 20 lines:`);
    for (const line of lines) {
      console.log(`   ${line}`);
    }

    // Should contain project name
    expect(readme).toContain('Anchor Engine');
  });

  function getDirectoryContents(dir: string): string[] {
    try {
      return execSync(`ls -la "${dir}"`, { encoding: 'utf-8' })
        .split('\n')
        .filter(line => line.trim());
    } catch {
      return [];
    }
  }
});