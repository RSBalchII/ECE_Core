import { nativeModuleManager, NativeModuleManager } from '../../src/utils/native-module-manager.js';

function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(`❌ FAIL: ${message}`);
  }
}

function assertEquals(actual: any, expected: any, message: string) {
  if (actual !== expected) {
    throw new Error(`❌ FAIL: ${message} (Expected ${expected}, got ${actual})`);
  }
}

async function testNativeModuleManager() {
  console.log('--- Testing Native Module Manager ---');

  // Test 1: Singleton Instance
  {
    console.log('Test 1: Singleton Instance');
    const instance1 = NativeModuleManager.getInstance();
    const instance2 = NativeModuleManager.getInstance();
    assert(instance1 === instance2, 'Should return the same instance');
    assert(nativeModuleManager === instance1, 'Exported instance should be the singleton');
    console.log('✅ PASS: Singleton Instance');
  }

  // Test 2: Fallback for ece_native
  {
    console.log('Test 2: Fallback for ece_native');

    // ece_native should be forced into fallback mode by shouldUseFallbackOnly
    const module = nativeModuleManager.loadNativeModule('ece_native', 'anchor_core.node');

    assert(module !== null, 'Module should not be null');
    assert(typeof module.cleanse === 'function', 'Should have cleanse function');
    assert(typeof module.atomize === 'function', 'Should have atomize function');
    assert(typeof module.fingerprint === 'function', 'Should have fingerprint function');
    assert(typeof module.distance === 'function', 'Should have distance function');

    assert(nativeModuleManager.isUsingFallback('ece_native') === true, 'ece_native should be using fallback');

    const status = nativeModuleManager.getStatus('ece_native');
    assert(status !== undefined, 'Status should be defined');
    assertEquals(status!.loaded, true, 'Status should be loaded');
    assertEquals(status!.fallbackActive, true, 'Status fallbackActive should be true');

    console.log('✅ PASS: Fallback for ece_native');
  }

  // Test 3: Fallback Functionality (ece_native)
  {
    console.log('Test 3: Fallback Functionality (ece_native)');
    const module = nativeModuleManager.loadNativeModule('ece_native', 'anchor_core.node');

    // cleanse
    const cleansed = module.cleanse('hello \\"world\\" \\n test');
    assert(!cleansed.includes('\\"'), 'Should unescape quotes');
    assert(!cleansed.includes('\\n'), 'Should unescape newlines');

    // atomize
    const atomizedCode = module.atomize('function a() {}\\nfunction b() {}', 'code');
    assert(atomizedCode.length >= 1, 'Should split code into chunks');

    const atomizedProse = module.atomize('Paragraph 1\n\nParagraph 2', 'prose');
    assertEquals(atomizedProse.length, 2, 'Should split prose into paragraphs');

    // fingerprint
    const fp1 = module.fingerprint('hello world');
    const fp2 = module.fingerprint('hello world');
    assertEquals(fp1, fp2, 'Fingerprint should be deterministic');

    // distance
    const dist1 = module.distance(1n, 1n); // 0 differences
    assertEquals(dist1, 0, 'Distance of identical fingerprints should be 0');

    const dist2 = module.distance(1n, 3n); // 1 and 3 in binary are 01 and 11, 1 bit diff
    assertEquals(dist2, 1, 'Distance between 1 and 3 should be 1');

    console.log('✅ PASS: Fallback Functionality (ece_native)');
  }

  // Test 4: Default Fallback for Unknown Modules
  {
    console.log('Test 4: Default Fallback for Unknown Modules');

    // This will try to require non_existent.node, which will fail, triggering the default fallback
    const module = nativeModuleManager.loadNativeModule('unknown_module', 'non_existent.node');

    // The default fallback returns null
    assertEquals(module, null, 'Unknown module fallback should be null');

    assert(nativeModuleManager.isUsingFallback('unknown_module') === true, 'unknown_module should be marked as fallback');

    const status = nativeModuleManager.getStatus('unknown_module');
    assert(status !== undefined, 'Status should be defined');
    assertEquals(status!.loaded, false, 'Status should NOT be loaded');
    assertEquals(status!.fallbackActive, true, 'Status fallbackActive should be true');
    assert(status!.error !== undefined, 'Status should have an error message');

    console.log('✅ PASS: Default Fallback for Unknown Modules');
  }

  // Test 5: getAllStatus
  {
    console.log('Test 5: getAllStatus');

    const allStatus = nativeModuleManager.getAllStatus();
    assert(allStatus instanceof Map, 'Should return a Map');
    assert(allStatus.has('ece_native'), 'Should include ece_native');
    assert(allStatus.has('unknown_module'), 'Should include unknown_module');

    console.log('✅ PASS: getAllStatus');
  }
}

testNativeModuleManager().catch(e => {
  console.error(e);
  process.exit(1);
});
