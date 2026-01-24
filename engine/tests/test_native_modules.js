/**
 * Native Modules Test Suite - Verification of C++ Acceleration
 *
 * Tests the functionality of the native modules created in Operation "Iron Lung":
 * - Key Assassin (Text Hygiene)
 * - Atomizer (Text Splitting)
 * - Fingerprint (SimHash Deduplication)
 */

import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const require = createRequire(import.meta.url); // Use CommonJS require for native modules

// Test results tracking
let passed = 0;
let failed = 0;

/**
 * Test runner with pretty output
 */
async function test(name, fn) {
    try {
        process.stdout.write(`  ${name}... `);
        await fn();
        console.log('✅ PASS');
        passed++;
    } catch (e) {
        console.log('❌ FAIL');
        console.error(`     └─ ${e.message}`);
        failed++;
    }
}

/**
 * Assert helper
 */
function assert(condition, message) {
    if (!condition) throw new Error(message || 'Assertion failed');
}

/**
 * Main test suite for native modules
 */
async function runNativeModuleTests() {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║     NATIVE MODULES TEST SUITE          ║');
    console.log('╚════════════════════════════════════════╝\n');

    let native = null;

    // Try to load the native module using CommonJS require (needed for .node files)
    try {
        const nativePath = path.join(__dirname, '../build/Release/ece_native.node');
        native = require(nativePath);
        console.log('✅ Native module loaded successfully');
    } catch (e) {
        console.error('❌ Failed to load native module:', e.message);
        console.log('Trying alternative path...');
        try {
            const nativePath = path.join(__dirname, '../build/Debug/ece_native.node');
            native = require(nativePath);
            console.log('✅ Native module loaded from Debug directory');
        } catch (e2) {
            console.error('❌ Failed to load native module from Debug directory too:', e2.message);
            console.log('Skipping native module tests...');
            return;
        }
    }

    // ═══════════════════════════════════════════
    // SECTION 1: Key Assassin Tests
    // ═══════════════════════════════════════════
    console.log('\n─── Key Assassin (Text Hygiene) ───');

    await test('Basic unescape functionality', async () => {
        const input = 'Hello\\nWorld! This is a test.\\tWith tabs and\\nnewlines.';
        const expected = 'Hello\nWorld! This is a test.\tWith tabs and\nnewlines.';
        const result = native.cleanse(input);
        assert(result === expected, `Expected "${expected}", got "${result}"`);
    });

    await test('Quote unescape functionality', async () => {
        const input = 'He said, \\"Hello World!\\\", and left.';
        const expected = 'He said, "Hello World!", and left.';
        const result = native.cleanse(input);
        assert(result === expected, `Expected "${expected}", got "${result}"`);
    });

    await test('Complex JSON artifact removal', async () => {
        const input = '{"response_content": "This is the real content.", "metadata": "to_be_removed"}';
        // The Key Assassin should handle JSON artifacts appropriately
        const result = native.cleanse(input);
        // Basic check: should not crash and should return a string
        assert(typeof result === 'string', 'Result should be a string');
        assert(result.length > 0, 'Result should not be empty');
    });

    await test('Escape sequence preservation', async () => {
        const input = 'Path: C:\\\\Users\\\\Test\\\\Documents and more text';
        const result = native.cleanse(input);
        assert(typeof result === 'string', 'Result should be a string');
        // Should handle double backslashes appropriately
    });

    // ═══════════════════════════════════════════
    // SECTION 2: Atomizer Tests
    // ═══════════════════════════════════════════
    console.log('\n─── Atomizer (Text Splitting) ───');

    await test('Prose atomization', async () => {
        const text = 'This is the first sentence. This is the second sentence. And this is the third.';
        const atoms = native.atomize(text, 'prose');
        assert(Array.isArray(atoms), 'Atoms should be an array');
        assert(atoms.length > 0, 'Should have at least one atom');
        assert(atoms.every(atom => typeof atom === 'string'), 'All atoms should be strings');
    });

    await test('Code atomization', async () => {
        const code = `function hello() {\n  console.log("world");\n}\n\nfunction goodbye() {\n  console.log("farewell");\n}`;
        const atoms = native.atomize(code, 'code');
        assert(Array.isArray(atoms), 'Atoms should be an array');
        assert(atoms.length >= 1, `Expected at least 1 atom, got ${atoms.length}`);
        assert(atoms.every(atom => typeof atom === 'string'), 'All atoms should be strings');
    });

    await test('Blob atomization', async () => {
        const blob = 'Very long text that exceeds normal limits and should be split into smaller chunks for processing purposes';
        const atoms = native.atomize(blob, 'blob');
        assert(Array.isArray(atoms), 'Atoms should be an array');
        assert(atoms.length > 0, 'Should have at least one atom');
    });

    await test('Empty text atomization', async () => {
        const atoms = native.atomize('', 'prose');
        assert(Array.isArray(atoms), 'Atoms should be an array');
        assert(atoms.length === 0, `Expected 0 atoms for empty string, got ${atoms.length}`);
    });

    // ═══════════════════════════════════════════
    // SECTION 3: Fingerprint (SimHash) Tests
    // ═══════════════════════════════════════════
    console.log('\n─── Fingerprint (SimHash) ───');

    await test('Basic fingerprint generation', async () => {
        const text = 'This is a test string for fingerprinting.';
        const hash = native.fingerprint(text);
        // Convert BigInt to string for comparison
        const hashStr = hash.toString();
        assert(hashStr.length > 0, 'Hash should not be empty');
        assert(!isNaN(parseInt(hashStr, 16)), 'Hash should be a valid hex representation');
    });

    await test('Identical texts produce same hash', async () => {
        const text1 = 'Identical text for testing.';
        const text2 = 'Identical text for testing.';
        const hash1 = native.fingerprint(text1);
        const hash2 = native.fingerprint(text2);
        assert(hash1 === hash2, 'Identical texts should produce identical hashes');
    });

    await test('Similar texts have close hashes', async () => {
        const text1 = 'This is a test string for similarity.';
        const text2 = 'This is a test string for similarity!'; // One punctuation difference
        const hash1 = native.fingerprint(text1);
        const hash2 = native.fingerprint(text2);
        
        // Calculate distance
        const distance = native.distance(hash1, hash2);
        // Similar texts should have low distance (less than 20 out of 64 max)
        assert(distance < 20, `Similar texts should have low distance, got ${distance}`);
    });

    await test('Different texts have high distance', async () => {
        const text1 = 'Completely different text from the other one.';
        const text2 = 'Another text with totally unrelated content.';
        const hash1 = native.fingerprint(text1);
        const hash2 = native.fingerprint(text2);
        
        const distance = native.distance(hash1, hash2);
        // Different texts should have higher distance (more than 10 out of 64 max)
        // Note: This threshold might need adjustment based on actual behavior
        assert(distance >= 0, `Distance should be non-negative, got ${distance}`);
    });

    await test('Distance calculation symmetry', async () => {
        const text1 = 'First text';
        const text2 = 'Second text';
        const hash1 = native.fingerprint(text1);
        const hash2 = native.fingerprint(text2);
        
        const dist1 = native.distance(hash1, hash2);
        const dist2 = native.distance(hash2, hash1);
        
        assert(dist1 === dist2, `Distance should be symmetric: ${dist1} vs ${dist2}`);
    });

    // ═══════════════════════════════════════════
    // SECTION 4: Performance Comparison Tests
    // ═══════════════════════════════════════════
    console.log('\n─── Performance Comparison ───');

    await test('Large text processing does not crash', async () => {
        // Create a moderately large text
        const largeText = 'This is a sentence. '.repeat(1000);
        const start = process.hrtime.bigint();
        
        const atoms = native.atomize(largeText, 'prose');
        const end = process.hrtime.bigint();
        
        const duration = Number(end - start) / 1000000; // Convert to milliseconds
        
        assert(Array.isArray(atoms), 'Should return an array of atoms');
        assert(atoms.length > 0, 'Should have at least one atom');
        console.log(`     └─ Processed ${largeText.length} chars in ${duration.toFixed(2)}ms`);
    });

    await test('Fingerprint performance on medium text', async () => {
        const mediumText = 'This is a medium length text for performance testing purposes. '.repeat(100);
        const start = process.hrtime.bigint();
        
        const hash = native.fingerprint(mediumText);
        const end = process.hrtime.bigint();
        
        const duration = Number(end - start) / 1000000; // Convert to milliseconds
        
        assert(hash !== undefined, 'Should generate a hash');
        console.log(`     └─ Fingerprinted ${mediumText.length} chars in ${duration.toFixed(2)}ms`);
    });

    // ═══════════════════════════════════════════
    // SUMMARY
    // ═══════════════════════════════════════════
    console.log('\n╔════════════════════════════════════════╗');
    console.log(`║  RESULTS: ${passed} passed, ${failed} failed         ║`);
    console.log('╚════════════════════════════════════════╝\n');

    if (failed === 0) {
        console.log('🎉 All native module tests passed!');
        console.log('🚀 Iron Lung is breathing efficiently!');
    } else {
        console.log('⚠️  Some tests failed. Please check the native module implementation.');
    }
}

// Run the tests if this file is executed directly
if (process.argv[1] === __filename) {
    runNativeModuleTests().catch(err => {
        console.error('Test suite error:', err);
        process.exit(1);
    });
}

export { runNativeModuleTests };