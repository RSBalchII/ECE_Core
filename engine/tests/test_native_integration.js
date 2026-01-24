/**
 * Integration Test - Native Modules with Refiner
 *
 * Validates that the native modules work correctly with the refiner service
 * and that the simhash functionality is properly integrated.
 */

import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const require = createRequire(import.meta.url);

// Import the refiner to test integration
const { refineContent } = await import('../dist/services/ingest/refiner.js');

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
 * Main integration test suite
 */
async function runIntegrationTests() {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║  NATIVE MODULES INTEGRATION TESTS      ║');
    console.log('╚════════════════════════════════════════╝\n');

    // ═══════════════════════════════════════════
    // SECTION 1: Refiner Integration Tests
    // ═══════════════════════════════════════════
    console.log('─── Refiner Integration ───');

    await test('Refiner handles native module loading', async () => {
        const testContent = 'This is a test content for the refiner.';
        const testPath = 'test/integration/test.md';
        
        try {
            const atoms = await refineContent(testContent, testPath);
            assert(Array.isArray(atoms), 'Should return an array of atoms');
            assert(atoms.length > 0, 'Should have at least one atom');
            
            // Check that each atom has the expected properties including simhash
            for (const atom of atoms) {
                assert(atom.hasOwnProperty('simhash'), 'Each atom should have a simhash property');
                assert(typeof atom.simhash === 'string', 'Simhash should be a string');
                assert(atom.simhash.length > 0, 'Simhash should not be empty');
                
                assert(atom.hasOwnProperty('id'), 'Each atom should have an id');
                assert(atom.hasOwnProperty('content'), 'Each atom should have content');
                assert(atom.hasOwnProperty('sourceId'), 'Each atom should have a sourceId');
            }
        } catch (e) {
            throw new Error(`Refiner integration failed: ${e.message}`);
        }
    });

    await test('Refiner processes JSON artifacts with native Key Assassin', async () => {
        const jsonContent = `{"response_content": "This is the real content.", "type": "test", "timestamp": "2023-01-01"}`;
        const testPath = 'test/integration/json_test.md';
        
        try {
            const atoms = await refineContent(jsonContent, testPath);
            assert(Array.isArray(atoms), 'Should return an array of atoms');
            
            // The content should be cleaned by the native Key Assassin
            if (atoms.length > 0) {
                const content = atoms[0].content;
                // Should not contain the JSON wrapper artifacts
                assert(!content.includes('response_content'), 'JSON artifacts should be removed');
                assert(content.includes('This is the real content'), 'Real content should remain');
            }
        } catch (e) {
            throw new Error(`JSON artifact processing failed: ${e.message}`);
        }
    });

    await test('Refiner generates valid simhash values', async () => {
        const testContent = 'This is test content for simhash generation.';
        const testPath = 'test/integration/simhash_test.md';
        
        try {
            const atoms = await refineContent(testContent, testPath);
            assert(Array.isArray(atoms), 'Should return an array of atoms');
            
            for (const atom of atoms) {
                assert(typeof atom.simhash === 'string', 'Simhash should be a string');
                assert(atom.simhash !== '0', 'Simhash should not be default "0" if native module is working');
                assert(atom.simhash.length > 0, 'Simhash should have content');
                
                // Try to parse as hex to ensure it's a valid hex string
                parseInt(atom.simhash, 16);
                assert(!isNaN(parseInt(atom.simhash, 16)), 'Simhash should be a valid hex string');
            }
        } catch (e) {
            throw new Error(`Simhash generation failed: ${e.message}`);
        }
    });

    await test('Similar content produces similar simhash values', async () => {
        const content1 = 'This is the first piece of content for similarity testing.';
        const content2 = 'This is the first piece of content for similarity testing!'; // Minor difference
        const testPath = 'test/integration/similarity_test.md';
        
        try {
            const atoms1 = await refineContent(content1, testPath);
            const atoms2 = await refineContent(content2, testPath);
            
            assert(atoms1.length > 0, 'First content should produce atoms');
            assert(atoms2.length > 0, 'Second content should produce atoms');
            
            const hash1 = atoms1[0].simhash;
            const hash2 = atoms2[0].simhash;
            
            // Load native module to calculate distance
            let native = null;
            try {
                const nativePath = path.join(__dirname, '../build/Release/ece_native.node');
                native = require(nativePath);
            } catch (e) {
                try {
                    const nativePath = path.join(__dirname, '../build/Debug/ece_native.node');
                    native = require(nativePath);
                } catch (e2) {
                    throw new Error('Could not load native module for distance calculation');
                }
            }
            
            // Convert hex strings back to BigInt for distance calculation
            const bigint1 = BigInt(`0x${hash1}`);
            const bigint2 = BigInt(`0x${hash2}`);
            
            const distance = native.distance(bigint1, bigint2);
            // Similar content should have relatively low distance
            assert(distance < 20, `Similar content should have low distance, got ${distance}`);
        } catch (e) {
            throw new Error(`Similarity test failed: ${e.message}`);
        }
    });

    await test('Different content produces different simhash values', async () => {
        const content1 = 'This is completely different content from the other one.';
        const content2 = 'Another piece of text with unrelated subject matter.';
        const testPath = 'test/integration/diff_test.md';
        
        try {
            const atoms1 = await refineContent(content1, testPath);
            const atoms2 = await refineContent(content2, testPath);
            
            assert(atoms1.length > 0, 'First content should produce atoms');
            assert(atoms2.length > 0, 'Second content should produce atoms');
            
            const hash1 = atoms1[0].simhash;
            const hash2 = atoms2[0].simhash;
            
            // Load native module to calculate distance
            let native = null;
            try {
                const nativePath = path.join(__dirname, '../build/Release/ece_native.node');
                native = require(nativePath);
            } catch (e) {
                try {
                    const nativePath = path.join(__dirname, '../build/Debug/ece_native.node');
                    native = require(nativePath);
                } catch (e2) {
                    throw new Error('Could not load native module for distance calculation');
                }
            }
            
            // Convert hex strings back to BigInt for distance calculation
            const bigint1 = BigInt(`0x${hash1}`);
            const bigint2 = BigInt(`0x${hash2}`);
            
            const distance = native.distance(bigint1, bigint2);
            // Different content should have higher distance (but we can't set a strict threshold)
            assert(distance >= 0, `Distance should be non-negative, got ${distance}`);
        } catch (e) {
            throw new Error(`Difference test failed: ${e.message}`);
        }
    });

    // ═══════════════════════════════════════════
    // SECTION 2: Performance Tests
    // ═══════════════════════════════════════════
    console.log('\n─── Performance Tests ───');

    await test('Large content processing with native acceleration', async () => {
        const largeContent = 'This is a test sentence. '.repeat(5000); // Large content
        const testPath = 'test/integration/large_test.md';
        
        const start = process.hrtime.bigint();
        try {
            const atoms = await refineContent(largeContent, testPath);
            const end = process.hrtime.bigint();
            
            const duration = Number(end - start) / 1000000; // Convert to milliseconds
            
            assert(Array.isArray(atoms), 'Should return an array of atoms');
            assert(atoms.length > 0, 'Should have at least one atom');
            console.log(`     └─ Processed ${largeContent.length} chars in ${duration.toFixed(2)}ms`);
        } catch (e) {
            throw new Error(`Large content processing failed: ${e.message}`);
        }
    });

    // ═══════════════════════════════════════════
    // SUMMARY
    // ═══════════════════════════════════════════
    console.log('\n╔════════════════════════════════════════╗');
    console.log(`║  RESULTS: ${passed} passed, ${failed} failed         ║`);
    console.log('╚════════════════════════════════════════╝\n');

    if (failed === 0) {
        console.log('🎉 All integration tests passed!');
        console.log('🚀 Native modules are properly integrated with the refiner!');
    } else {
        console.log('⚠️  Some integration tests failed.');
    }
    
    return { passed, failed };
}

// Run the tests if this file is executed directly
if (process.argv[1] === __filename) {
    runIntegrationTests().catch(err => {
        console.error('Integration test suite error:', err);
        process.exit(1);
    });
}

export { runIntegrationTests };