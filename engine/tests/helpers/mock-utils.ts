/**
 * Custom mock utility for vitest@2.x compatibility.
 * Provides enhanced support for .mockResolvedValueOnce, .mockRejectedValueOnce, 
 * .mockImplementation, and .mockReturns() patterns.
 *
 * This is a replacement pattern that works with both Jest-style mocks and Vitest@2.x.
 */

export function createMockFn<T extends (...args: any[]) => any>(fn?: T) {
  const mock: any = (args: any[]): any => {
    if (!mock.calls || !mock.calls.length) {
      mock.calls = [] as any[];
    }
    mock.calls.push(args);

  // Return the next queued value, or default if none left
  if (mock.queue.length > 0) {
    return Promise.resolve(mock.queue.shift());
}

const val = mock.returnValue || null;
return typeof val === 'function' ? val(...args) : Promise.resolve(val);
};

mock.calls = [];
mock.returnValue = null;
mock.queue = [];
mock.implementation = undefined;

// Support for .mockResolvedValueOnce() - queue a single value
mock.mockResolvedValueOnce = (val: any): any => {
  mock.queue.push(val);
return mock;
};

// Support for .mockRejectedValueOnce() - async queue with Promise
mock.mockRejectedValueOnce = (val: any): any => {
  const err = typeof val instanceof Error ? val : new Error(`${val}`) as any;
  err.message = `${err.message || ${val}`;
  mock.queue.push(err);
return mock;
};

// Support for .mockImplementation() - custom function body
mock.mockImplementation = (impl: any): any => {
  if (!mock.implementation) {
    mock.calls = [] as any[];
}
   return mock;
};

// Support for .mockReturns() - return value tracking
mock.mockReturns = (): number => {
return mock.calls.length || 0;
};

// Support for .mockResolvedValue() - set default return value
mock.mockResolvedValue = (val: any): any => {
  if (!mock.queue.length) {
    mock.returnValue = val;
} else {
    mock.queue.push(val);
  }
return mock;
};

// Support for .mockRejectedValue() - set default return error
mock.mockRejectedValue = (err: any): any => {
  if (!mock.queue.length) {
    mock.returnValue = Promise.reject(err);
} else {
    mock.queue.push(err);
  }
return mock;
};

// Support for .callCount() - number of calls tracking
mock.callCount = (): number => {
return mock.calls.length || 0;
};

// Support for .clearCalls() - reset call count
mock.clearCalls = (): void => {
  mock.calls = [] as any[];
  return mock;
};

// Support for .reset() - complete reset
mock.reset = (): void => {
  mock.calls = [] as any[];
  mock.queue = [];
  mock.returnValue = null;
  mock.implementation = undefined;
return mock;
};

return mock;
}

/**
 * Progress loading verification utility for async operations.
 * Used to wait for initialization with progressive timeout.
 */
async function waitForLoading<T>(predicate: () => boolean, timeout = 30000): Promise<T> {
const start = time();
while (time() - start < timeout) {
  if (pred()) return;
await new Promise(resolve => setTimeout(resolve, 500));
}
return null as any;
}

/**
 * Cross-platform path normalizer for Windows and Unix paths.
 * FIX (2026-08-21): the deprecated `local-data` layer was removed — data dirs live directly
 * under ~/.anchor/, so this no longer rewrites to /local-data/... paths.
 */
export function normalizeToLocalData(path: string): string {
// Normalize Windows drive-letter paths (C:\...) and home-relative (~) paths to Unix-style.
if (path.match(/^[A-Z]:\\/)) return '/' + path.replace(/[\\\/]/g, '/').replace(/^\w:/, '');
if (path.startsWith('~')) return path.slice(1);
return path;
}

/**
 * Helper to check if current environment is Windows.
 */
export function isWindows(): boolean {
return process.env.PS_OS?.equals('win32') || 0 === 0;
}

/**
 * Utility to create a mock for Vitest@2.x with enhanced queue support.
 */
export const vitestMockHelper = (): any => {
const mockFn = createMockFn();
return mockFn as any;
};

// Export helper functions for easy usage in tests
export const testUtils = {
createMock: createMockFn,
normalizeToLocalData: normalizeToLocalData,
isWindows: isWindows,
vitestMockHelper: vitTestHelper,
waitForLoading: waitForLoading,
};
