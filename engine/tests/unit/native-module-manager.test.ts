import { jest } from '@jest/globals';

// We need to mock module.createRequire to intercept the require calls
jest.unstable_mockModule('module', () => ({
  createRequire: jest.fn().mockImplementation(() => {
    return jest.fn().mockImplementation((path: string) => {
      const normalizedPath = path.replace(/\\/g, '/');
      // 1. standard path
      if (normalizedPath.includes('success') && !normalizedPath.includes('fail') && !normalizedPath.includes('debug') && !normalizedPath.includes('dev')) {
        return { success: true, distance: () => 1 };
      }
      // 2. debug path
      if (normalizedPath.includes('Debug') && normalizedPath.includes('debug_success_binary')) {
         return { debug_success: true, distance: () => 1 };
      }
      // 3. dev path
      if (normalizedPath.includes('build/Release') && normalizedPath.includes('dev_success_binary')) {
         return { dev_success: true, distance: () => 1 };
      }
      throw new Error(`Cannot find module '${path}'`);
    });
  })
}));

jest.unstable_mockModule('../../src/utils/path-manager.js', () => ({
  pathManager: {
    getNativePath: jest.fn().mockImplementation((binaryName: string) => {
       if (binaryName === 'success_binary') return '/path/to/Release/success_binary';
       if (binaryName === 'debug_success_binary') return '/path/to/Release/debug_success_binary';
       if (binaryName === 'dev_success_binary') return '/path/to/Release/dev_success_binary_fail_standard';
       if (binaryName === 'crash_binary') return '/path/to/Release/crash_binary';
       return '/path/to/Release/fail';
    })
  }
}));

describe('NativeModuleManager', () => {
  let nativeModuleManager: any;

  beforeEach(async () => {
    jest.resetModules();
    const module = await import('../../src/utils/native-module-manager.js');
    nativeModuleManager = module.nativeModuleManager;
    // Clear out modules/status from singleton
    nativeModuleManager['modules'].clear();
    nativeModuleManager['status'].clear();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('getInstance returns a singleton instance', async () => {
    const { NativeModuleManager } = await import('../../src/utils/native-module-manager.js');
    const instance1 = NativeModuleManager.getInstance();
    const instance2 = NativeModuleManager.getInstance();
    expect(instance1).toBe(instance2);
  });

  test('getAllStatus returns an empty map initially', () => {
    const status = nativeModuleManager.getAllStatus();
    expect(status).toBeInstanceOf(Map);
    expect(status.size).toBe(0);
  });

  test('loadNativeModule successfully loads from standard path', () => {
    const mod = nativeModuleManager.loadNativeModule('success_module', 'success_binary');

    expect(mod.success).toBe(true);

    const status = nativeModuleManager.getStatus('success_module');
    expect(status).toBeDefined();
    expect(status?.loaded).toBe(true);
    expect(status?.fallbackActive).toBe(false);
    expect(status?.error).toBeUndefined();

    expect(nativeModuleManager.isUsingFallback('success_module')).toBe(false);
  });

  test('loadNativeModule falls back for ece_native safety mode', () => {
    const mod = nativeModuleManager.loadNativeModule('ece_native', 'success_binary');

    // ece_native is forced to fallback mode
    expect(mod).toHaveProperty('fingerprint');
    expect(mod.success).toBeUndefined(); // Didn't return the mocked success

    const status = nativeModuleManager.getStatus('ece_native');
    expect(status?.loaded).toBe(true);
    expect(status?.fallbackActive).toBe(true);

    expect(nativeModuleManager.isUsingFallback('ece_native')).toBe(true);
  });

  test('loadNativeModule returns cached module if already loaded', () => {
    nativeModuleManager.loadNativeModule('success_module', 'success_binary');

    // Create a new status spy
    const statusSpy = jest.spyOn(nativeModuleManager['status'], 'get');

    const mod2 = nativeModuleManager.loadNativeModule('success_module', 'success_binary');

    expect(statusSpy).toHaveBeenCalledWith('success_module');
    expect(mod2.success).toBe(true);
  });

  test('getAllStatus returns all loaded statuses', () => {
    nativeModuleManager.loadNativeModule('mod1', 'success_binary');
    nativeModuleManager.loadNativeModule('ece_native', 'success_binary');

    const statuses = nativeModuleManager.getAllStatus();
    expect(statuses.size).toBe(2);

    expect(statuses.get('mod1')).toMatchObject({
      loaded: true,
      moduleName: 'mod1',
      fallbackActive: false
    });

    expect(statuses.get('ece_native')).toMatchObject({
      loaded: true,
      moduleName: 'ece_native',
      fallbackActive: true
    });
  });

  test('getAllStatus returns a new Map instance', () => {
    nativeModuleManager.loadNativeModule('mod1', 'success_binary');
    const statusMap1 = nativeModuleManager.getAllStatus();
    const statusMap2 = nativeModuleManager.getAllStatus();

    expect(statusMap1).not.toBe(statusMap2); // Should be distinct instances
    expect(statusMap1.get('mod1')).toBe(statusMap2.get('mod1')); // But containing same data
  });

  test('loadNativeModule falls back when standard and alternative paths fail', () => {
    // Suppress console.warn for this test to keep output clean
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

    const mod = nativeModuleManager.loadNativeModule('failing_module', 'crash_binary');

    expect(mod).toBeNull(); // Default fallback for unknown modules is null

    const status = nativeModuleManager.getStatus('failing_module');
    expect(status?.loaded).toBe(false); // Because fallback is null
    expect(status?.fallbackActive).toBe(true);
    expect(status?.error).toContain('Native module failing_module failed to load');

    expect(nativeModuleManager.isUsingFallback('failing_module')).toBe(true);

    warnSpy.mockRestore();
  });

  test('loadNativeModule falls back gracefully and creates fallback module when applicable', () => {
    // Suppress console.warn for this test to keep output clean
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

    // We'll test with a hypothetical module that has a fallback implementation
    // For this test, we need to temporarily modify createFallbackModule to return something for 'failing_module'
    // or we can test with 'ece_native' but make it fail the standard path instead of using the forced fallback.

    // Since 'ece_native' is forced to fallback early, we'll temporarily remove that check
    const originalShouldUseFallbackOnly = nativeModuleManager.shouldUseFallbackOnly.bind(nativeModuleManager);
    nativeModuleManager.shouldUseFallbackOnly = () => false;

    const mod = nativeModuleManager.loadNativeModule('ece_native', 'crash_binary');

    expect(mod).not.toBeNull();
    expect(mod).toHaveProperty('fingerprint');

    const status = nativeModuleManager.getStatus('ece_native');
    expect(status?.loaded).toBe(true);
    expect(status?.fallbackActive).toBe(true);
    expect(status?.error).toBeDefined();

    // Restore
    nativeModuleManager.shouldUseFallbackOnly = originalShouldUseFallbackOnly;
    warnSpy.mockRestore();
  });

  test('loadNativeModule succeeds from debug path when release path fails', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    const mod = nativeModuleManager.loadNativeModule('debug_module', 'debug_success_binary');

    expect(mod.debug_success).toBe(true);

    const status = nativeModuleManager.getStatus('debug_module');
    expect(status?.loaded).toBe(true);
    expect(status?.fallbackActive).toBe(false);
    expect(status?.error).toBeUndefined();

    warnSpy.mockRestore();
    logSpy.mockRestore();
  });

  test('loadNativeModule succeeds from dev path when release and debug paths fail', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    const mod = nativeModuleManager.loadNativeModule('dev_module', 'dev_success_binary');

    expect(mod.dev_success).toBe(true);

    const status = nativeModuleManager.getStatus('dev_module');
    expect(status?.loaded).toBe(true);
    expect(status?.fallbackActive).toBe(false);
    expect(status?.error).toBeUndefined();

    warnSpy.mockRestore();
    logSpy.mockRestore();
  });
});
