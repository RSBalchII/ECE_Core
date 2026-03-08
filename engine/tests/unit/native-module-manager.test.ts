import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NativeModuleManager } from '../../src/utils/native-module-manager.js';
import { pathManager } from '../../src/utils/path-manager.js';

// Mock pathManager
vi.mock('../../src/utils/path-manager.js', () => ({
  pathManager: {
    getNativePath: vi.fn(),
  },
}));

// We need to mock 'module' since NativeModuleManager uses createRequire
vi.mock('module', () => {
  return {
    createRequire: vi.fn(() => {
      const mockRequire = (path: string) => {
        if (path.includes('fail')) {
          throw new Error('Module not found');
        }
        if (path.includes('success')) {
          return { testFunction: () => 'success' };
        }
        if (path.includes('distance-fail')) {
          return { distance: () => 'not a number' }; // Fails safety test
        }
        return {};
      };
      return mockRequire;
    }),
  };
});

describe('NativeModuleManager', () => {
  let manager: any;

  beforeEach(() => {
    // Reset singleton instance for testing isolation
    // @ts-ignore - Accessing private property for testing
    NativeModuleManager.instance = undefined;
    manager = NativeModuleManager.getInstance();

    // Clear mock histories
    vi.clearAllMocks();
  });

  describe('Singleton Pattern', () => {
    it('should return the same instance', () => {
      const instance1 = NativeModuleManager.getInstance();
      const instance2 = NativeModuleManager.getInstance();
      expect(instance1).toBe(instance2);
    });
  });

  describe('Module Loading - ece_native (Forced Fallback)', () => {
    it('should force fallback for ece_native without attempting to load native module', () => {
      const module = manager.loadNativeModule('ece_native', 'ece_native.node');

      expect(module).toBeDefined();
      expect(module.cleanse).toBeInstanceOf(Function);
      expect(module.atomize).toBeInstanceOf(Function);
      expect(module.fingerprint).toBeInstanceOf(Function);
      expect(module.distance).toBeInstanceOf(Function);

      expect(manager.isUsingFallback('ece_native')).toBe(true);

      const status = manager.getStatus('ece_native');
      expect(status).toBeDefined();
      expect(status?.loaded).toBe(true); // Fallback is considered loaded
      expect(status?.fallbackActive).toBe(true);
    });
  });

  describe('Module Loading - Standard', () => {
    it('should successfully load a native module', () => {
      // Mock pathManager to return a path that triggers success in our mockRequire
      vi.mocked(pathManager.getNativePath).mockReturnValue('/path/to/success.node');

      const module = manager.loadNativeModule('test_module', 'test_module.node');

      expect(module).toBeDefined();
      expect(module.testFunction()).toBe('success');

      expect(manager.isUsingFallback('test_module')).toBe(false);

      const status = manager.getStatus('test_module');
      expect(status?.loaded).toBe(true);
      expect(status?.fallbackActive).toBe(false);
      expect(status?.error).toBeUndefined();
    });

    it('should fallback when module loading fails', () => {
      // Mock pathManager to return a path that triggers failure in our mockRequire
      vi.mocked(pathManager.getNativePath).mockReturnValue('/path/to/fail.node');

      const module = manager.loadNativeModule('failing_module', 'fail.node');

      expect(module).toBeNull(); // createFallbackModule returns null for unknown modules
      expect(manager.isUsingFallback('failing_module')).toBe(true);

      const status = manager.getStatus('failing_module');
      expect(status?.loaded).toBe(false); // Since fallback is null
      expect(status?.fallbackActive).toBe(true);
      expect(status?.error).toContain('failed to load');
    });

    it('should return cached module on subsequent calls', () => {
      vi.mocked(pathManager.getNativePath).mockReturnValue('/path/to/success.node');

      const module1 = manager.loadNativeModule('cached_module', 'success.node');
      const module2 = manager.loadNativeModule('cached_module', 'success.node');

      expect(module1).toBe(module2);
      // getNativePath should only be called once if it's cached
      // Note: First call is for standard path. Next calls in the original code are for alternative paths if standard fails.
      // Since standard succeeds, it's called once.
      expect(pathManager.getNativePath).toHaveBeenCalledTimes(1);
    });
  });

  describe('ece_native Fallback Implementations', () => {
    let eceModule: any;

    beforeEach(() => {
      eceModule = manager.loadNativeModule('ece_native', 'ece_native.node');
    });

    describe('cleanse', () => {
      it('should un-escape strings', () => {
        const input = 'This is a \\"test\\" with \\n newlines and \\t tabs';
        const result = eceModule.cleanse(input);
        expect(result).toBe('This is a "test" with \n newlines and \t tabs');
      });

      it('should remove metadata keys', () => {
        const input = '{"type":"message", "timestamp":"123", "source":"user", "content":"Hello"}';
        const result = eceModule.cleanse(input);
        expect(result).not.toContain('"type":"message"');
        expect(result).not.toContain('"timestamp":"123"');
        expect(result).not.toContain('"source":"user"');
        // The regex replaces '"source":"user",' with '' but leaves spaces and braces around it
        expect(result.replace(/\s+/g, '')).toContain('{"content":"Hello"}');
      });

      it('should compress slashes', () => {
        // We use String.raw to ensure that backslashes are passed exactly as written.
        // The cleanse function replaces \t with a tab character during the un-escaping phase.
        // Therefore, we should use a path that does not contain 't' or 'n' to avoid this.
        const input = String.raw`path\\dir\\file`;
        const result = eceModule.cleanse(input);
        expect(result).toBe('path/dir/file');
      });

      it('should correctly compress multiple backslashes', () => {
        const input = String.raw`path\\\\file`;
        const result = eceModule.cleanse(input);
        expect(result).toBe('path/file');
      });
    });

    describe('atomize', () => {
      it('should atomize code strategy', () => {
        const input = `
function test1() {
  return 1;
}

function test2() {
  return 2;
}
`;
        const result = eceModule.atomize(input, 'code');
        expect(result.length).toBeGreaterThan(0);
        expect(result[0]).toContain('function test1()');
      });

      it('should atomize prose strategy', () => {
        const input = 'Paragraph 1\n\nParagraph 2\n\nParagraph 3';
        const result = eceModule.atomize(input, 'prose');
        expect(result.length).toBe(3);
        expect(result[0]).toBe('Paragraph 1');
        expect(result[1]).toBe('Paragraph 2');
        expect(result[2]).toBe('Paragraph 3');
      });
    });

    describe('fingerprint', () => {
      it('should return a bigint', () => {
        const input = 'this is a test string for fingerprinting';
        const result = eceModule.fingerprint(input);
        expect(typeof result).toBe('bigint');
      });

      it('should return identical fingerprints for identical inputs', () => {
        const input = 'this is a test string for fingerprinting';
        const result1 = eceModule.fingerprint(input);
        const result2 = eceModule.fingerprint(input);
        expect(result1).toBe(result2);
      });

      it('should handle small inputs', () => {
        const result = eceModule.fingerprint('tiny');
        expect(typeof result).toBe('bigint');
      });
    });

    describe('distance', () => {
      it('should calculate hamming distance between identical bigints', () => {
        const a = BigInt('0b101010');
        const b = BigInt('0b101010');
        const result = eceModule.distance(a, b);
        expect(result).toBe(0);
      });

      it('should calculate hamming distance between different bigints', () => {
        const a = BigInt('0b101010'); // 42
        const b = BigInt('0b111000'); // 56
        // XOR: 0b010010 (18) -> 2 bits set
        const result = eceModule.distance(a, b);
        expect(result).toBe(2);
      });

      it('should respect maximum bit count (64)', () => {
        // Create a bigint with 64 bits set to 1
        const a = (1n << 64n) - 1n;
        const b = 0n;
        const result = eceModule.distance(a, b);
        expect(result).toBe(64);
      });
    });
  });

  describe('getAllStatus', () => {
    it('should return status of all loaded modules', () => {
      vi.mocked(pathManager.getNativePath).mockReturnValue('/path/to/success.node');

      manager.loadNativeModule('module1', 'success.node');
      manager.loadNativeModule('ece_native', 'ece_native.node'); // Forced fallback

      const allStatus = manager.getAllStatus();

      expect(allStatus.size).toBe(2);
      expect(allStatus.get('module1')?.loaded).toBe(true);
      expect(allStatus.get('ece_native')?.fallbackActive).toBe(true);
    });
  });
});
