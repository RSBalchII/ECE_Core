/**
 * Test Setup File for Vitest v4+
 *
 * Provides global setup, mocks, and configuration for the Anchor Engine test suite.
 */

import { join } from 'path';
import { homedir } from 'os';

// Global test environment variables
process.env.NODE_ENV = process.env.NODE_ENV || 'test';
// FIX (2026-08-21): ANCHOR_ROOT must resolve to ~/.anchor (Standard 110). The previous default
// ('/.anchor', relative) resolved against vitest's cwd and made test loggers create directories
// inside the repo (<workspace>/.anchor, <engine>/.anchor/...). Now it defaults to an absolute
// homedir-based path; callers that need a sandbox location should export ANCHOR_ROOT explicitly.
if (!process.env.ANCHOR_ROOT) process.env.ANCHOR_ROOT = join(homedir(), '.anchor');
process.env.TS_NODE_TRANSPILE_ONLY = 'true';

// Set up global mocks for ESM module resolution using vitest's mock API
// Note: In vitest v4, mocks need to be set up differently
const mockPathManager = {
  pathManager: {
    getNativePath: (binaryName: string) => `/path/to/${binaryName}`,
  },
};

const mockModule = {
  createRequire: () => (modulePath: string) => {
    if (modulePath.includes('fail')) {
      throw new Error(`Module not found: ${modulePath}`);
    }
    return {
      testFunction: () => 'success',
      cleanse: (str: string) => str,
      atomize: (content: string) => content.split(/\n\n+/),
      fingerprint: (str: string) => BigInt(Date.now()),
      distance: (a: bigint, b: bigint) => Number(a ^ b),
    };
  },
};

// Export mocks for use in tests
export { mockPathManager, mockModule };

// Log test environment setup
console.log('[Test Setup] Environment configured:', {
  NODE_ENV: process.env.NODE_ENV,
  ANCHOR_ROOT: process.env.ANCHOR_ROOT,
});