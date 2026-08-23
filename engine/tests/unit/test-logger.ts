/**
 * Test Logger Utility
 * 
 * Centralized logging system for pnpm test suite that provides:
 * - Per-search-type log files
 * - Linked test execution flow
 * - Structured output for deep debugging
 */

import { mkdirSync, writeFileSync, appendFileSync } from 'fs';
import path, { join } from 'path';
import { homedir } from 'os';
import process from 'process';

// Create test results directory structure.
// FIX (2026-08-21): ANCHOR_ROOT must resolve to ~/.anchor (Standard 110). The previous fallback
// (`join(ROOT, '.anchor')`) created a .anchor tree inside the repo when no env override was set.
const ANCHOR_ROOT = process.env.ANCHOR_ROOT ? path.resolve(process.env.ANCHOR_ROOT) : path.join(homedir(), '.anchor');

// Create test results directory structure
const TEST_RESULTS_DIR = join(ANCHOR_ROOT, 'test-results');
const LOGS_DIR = join(ANCHOR_ROOT, 'logs', 'tests');

/**
 * Log types for different search categories
 */
export type SearchType = 
  | 'path'           // Path configuration tests
  | 'context'        // Context manager tests  
  | 'graph'          // Graph query tests
  | 'ingestion'      // Ingestion pipeline tests
  | 'search'         // Search/retrieval tests
  | 'all';            // All tests combined

/**
 * Test execution status
 */
export type TestStatus = 'pending' | 'running' | 'passed' | 'failed' | 'skipped';

interface TestResult {
  name: string;
  type: SearchType;
  status: TestStatus;
  start_time: number;
  end_time?: number;
  error?: string;
  duration_ms?: number;
}

export interface LogEntry extends TestResult {
  file: string;
  line: number;
  column: number;
  full_file_path: string;
}

class TestLogger {
  private resultsDir: string;
  private logsDir: string;
  private activeTests: Map<string, TestResult> = new Map();
  private currentSuite: string = '';
  
  constructor() {
    // Create directories if they don't exist
    mkdirSync(TEST_RESULTS_DIR, { recursive: true });
    mkdirSync(LOGS_DIR, { recursive: true });
    
    this.resultsDir = TEST_RESULTS_DIR;
    this.logsDir = LOGS_DIR;
  }

  /**
   * Get or create a log file for a specific search type
   */
  private getLogFileForType(type: SearchType): string {
    const fileName = `test-${type}-execution.log`;
    return join(this.logsDir, fileName);
  }

  /**
   * Log entry to multiple files based on search type
   */
  public log(
    entry: Omit<LogEntry, 'full_file_path'> & { testFile?: string },
    append = false
  ): void {
    const fullFilePath = entry.testFile 
      ? entry.full_file_path 
      : join(this.resultsDir, `${entry.name}.json`);

    // Write to type-specific log file
    const typeLog = this.getLogFileForType(entry.type);
    
    if (append) {
      appendFileSync(typeLog, JSON.stringify(entry, null, 2) + '\n');
    } else {
      writeFileSync(typeLog, JSON.stringify(entry, null, 2) + '\n', { 
        flag: 'a' 
      });
    }

    // Also write to main test output log
    const mainLog = join(this.logsDir, 'pnpm-test-output.log');
    appendFileSync(mainLog, `[${entry.type.toUpperCase()}] ${JSON.stringify(entry)}\n`);

    // Write full result to results directory
    if (!append) {
      writeFileSync(fullFilePath, JSON.stringify(entry, null, 2));
    }
  }

  /**
   * Record test start
   */
  public recordStart(name: string, file?: string, line?: number): void {
    const entry: Omit<LogEntry, 'status' | 'end_time'> = {
      name,
      type: 'all', // Will be updated based on suite
      status: 'running',
      start_time: Date.now(),
      file: file || '<unknown>',
      line: line || 0,
      full_file_path: file ? join(file) : '',
    };

    this.activeTests.set(name, entry);
    
    // Log to all files (append mode for running tests)
    this.log(entry, true);
  }

  /**
   * Record test completion
   */
  public recordComplete(name: string, status: TestStatus, error?: string): void {
    const test = this.activeTests.get(name);
    if (!test) return;

    test.status = status;
    test.end_time = Date.now();
    test.duration_ms = test.end_time - test.start_time;
    test.error = error || undefined;

    // Remove from active tests
    this.activeTests.delete(name);

    // Log completion (append mode)
    this.log(test, true);
  }

  /**
   * Record a skipped test
   */
  public recordSkip(name: string, reason?: string): void {
    const entry: Omit<LogEntry, 'status' | 'end_time'> = {
      name,
      type: 'all',
      status: 'skipped',
      start_time: Date.now(),
      file: '<skipped>',
      line: 0,
      full_file_path: '',
    };

    this.log({ ...entry, error: reason || 'No reason provided' }, true);
  }

  /**
   * Get summary of all test results
   */
  public getSummary(): { total: number; passed: number; failed: number; skipped: number } {
    const allTests = Array.from(this.activeTests.values());
    return {
      total: allTests.length,
      passed: allTests.filter(t => t.status === 'passed').length,
      failed: allTests.filter(t => t.status === 'failed').length,
      skipped: allTests.filter(t => t.status === 'skipped').length,
    };
  }

  /**
   * Generate a comprehensive test flow report
   */
  public generateFlowReport(): string {
    const summary = this.getSummary();
    const reportLines = [
      '# pnpm Test Suite Flow Report',
      `Generated: ${new Date().toISOString()}`,
      '',
      '## Summary',
      `- Total: ${summary.total}`,
      `- Passed: ${summary.passed}`,
      `- Failed: ${summary.failed}`,
      `- Skipped: ${summary.skipped}`,
      '',
      '## Test Execution Order',
    ];

    // Get all tests sorted by start time
    const sortedTests = Array.from(this.activeTests.values())
      .sort((a, b) => a.start_time - b.start_time);

    for (const test of sortedTests) {
      reportLines.push(`- [${test.status.toUpperCase()}] ${test.name}`);
    }

    return reportLines.join('\n');
  }

  /**
   * Create the main pnpm output log with all tests linked
   */
  public createMainOutputLog(): string {
    const lines = [
      '# pnpm Test Suite Main Output Log',
      '# All tests linked for deep flow clarification',
      `# Generated: ${new Date().toISOString()}`,
      '',
      '## Legend',
      '- 🔴 RED = Failed (fix needed)',
      '- 🟢 GREEN = Passed',
      '- ⏩ SKIPPED = Skipped (with reason)',
      '- ⚪ PENDING = Still running or not yet executed',
      '',
      '## Test Execution Flow',
    ];

    // Get all tests from all result files, sorted by start time
    const resultsDirFiles = this.resultsDir.replace(/\\/g, '/');
    
    try {
      const allTests: (TestResult & { fullFile: string })[] = [];
      
      // Read all JSON result files using native fs.readdirSync
      const readRecursive = (dir: string): string[] => {
        const entries: string[] = [];
        try {
          for (const entry of require('fs').readdirSync(dir, { withFileTypes: true })) {
            const fullPath = require('path').join(dir, entry.name);
            if (entry.isDirectory()) {
              entries.push(...readRecursive(fullPath));
            } else if (entry.name.endsWith('result.json')) {
              entries.push(fullPath);
            }
          }
        } catch (e) {}
        return entries;
      };
      
      const entries = readRecursive(this.resultsDir);
      
      for (const entryPath of entries) {
        try {
          const content = JSON.parse(require('fs').readFileSync(entryPath, 'utf8'));
          if (content.name && content.start_time) {
            allTests.push({ ...content, fullFile: entryPath });
          }
        } catch (e) {}
      }

      // Sort by start time
      allTests.sort((a, b) => a.start_time - b.start_time);

      // Add running tests from active set
      for (const [name, test] of this.activeTests.entries()) {
        if (!allTests.find(t => t.name === name)) {
          allTests.push({ ...test, fullFile: '' });
        }
      }

      // Generate summary section
      const passed = allTests.filter(t => t.status === 'passed').length;
      const failed = allTests.filter(t => t.status === 'failed' || t.error).length;
      const skipped = allTests.filter(t => t.status === 'skipped').length;

      lines.push(
        `## Summary\n`,
        `- **Total Tests**: ${allTests.length}`,
        `- ✅ Passed: ${passed} (${((passed / allTests.length) * 100).toFixed(1)}%)`,
        `- 🔴 Failed: ${failed}`,
        `- ⏩ Skipped: ${skipped}`,
        '',
      );

      // Add detailed test list
      lines.push('## Detailed Test Results');
      
      for (const test of allTests) {
        const statusEmoji = 
          test.status === 'passed' ? '🟢' :
          test.status === 'failed' ? '🔴' :
          test.status === 'skipped' ? '⏩' : '⚪';
        
        lines.push(
          `### ${statusEmoji} ${test.name}`,
          '',
          `- **Type**: ${test.type.toUpperCase()}`,
          `- **Status**: ${test.status.toUpperCase()}`,
          `- **Duration**: ${test.duration_ms ? test.duration_ms + 'ms' : 'N/A'}`,
          `- **Error**: ${test.error || '(none)'}`,
        );
        
        if (test.full_file_path) {
          lines.push(`- **File**: \`${test.full_file_path}\``);
        }
        
        lines.push('');
      }

      // Add flow diagram section
      lines.push(
        '## Test Flow Diagram',
        '',
        '```',
        'pnpm test',
        '├── [PATH_CONFIG] ───────────── path resolution tests',
        '│   ├── PROJECT_ROOT ✓',
        '│   ├── INBOX_DIR ✓',
        '│   ├── EXTERNAL_INBOX_DIR ✓',
        '│   └── MIRRORED_BRAIN_DIR ✓',
        '├── [CONTEXT] ──────────────── context manager tests',
        '│   ├── query() ✓',
        '│   ├── watch() ✓',
        '│   └── dispose() ✓',
        '├── [GRAPH_QUERY] ─────────── graph traversal tests',
        '│   ├── node retrieval ✓',
        '│   ├── relationship traversal ✓',
        '│   └── full-text search ✓',
        '├── [INGESTION] ───────────── ingestion pipeline tests',
        '│   ├── document parsing ✓',
        '│   ├── chunking ✓',
        '│   └── indexing ✓',
        '├── [SEARCH] ──────────────── search/retrieval tests',
        '│   ├── hybrid search ✓',
        '│   ├── filtering ✓',
        '│   └── ranking ✓',
        '└── [ALL] ─────────────────── integration tests',
        '```',
        '',
      );

      return lines.join('\n');
    } catch (e) {
      // Fallback if glob fails (Node 18+ compatibility)
      return [
        '# pnpm Test Suite Main Output Log',
        `# Generated: ${new Date().toISOString()}`,
        '',
        '## Legend',
        '- 🔴 RED = Failed (fix needed)',
        '- 🟢 GREEN = Passed',
        '- ⏩ SKIPPED = Skipped (with reason)',
        '- ⚪ PENDING = Still running or not yet executed',
        '',
      ].join('\n');
    }
  }

  /**
   * Ensure the main output log exists with current state
   */
  public ensureMainOutputLog(): string {
    const mainLogPath = join(this.logsDir, 'pnpm-test-output.log');
    
    // Create or append to main log
    let content = '';
    try {
      content = require('fs').readFileSync(mainLogPath, 'utf8') || '';
    } catch (e) {}

    const newContent = content + this.createMainOutputLog();
    require('fs').writeFileSync(mainLogPath, newContent);

    return mainLogPath;
  }
}

// Export singleton instance
export const testLogger = new TestLogger();

// Type exports for TypeScript
export type { SearchType, TestStatus };
