import { estimateTokenCount, truncateTokens, estimateTokenCountAdvanced } from '../../src/utils/token-utils.js';

async function testTokenUtils() {
    console.log('--- Testing Token Utilities ---');
    let passed = 0;
    let failed = 0;

    function assert(condition: boolean, message: string) {
        if (condition) {
            console.log(`✅ PASS: ${message}`);
            passed++;
        } else {
            console.error(`❌ FAIL: ${message}`);
            failed++;
        }
    }

    function assertEqual(actual: any, expected: any, message: string) {
        if (actual === expected) {
            console.log(`✅ PASS: ${message}`);
            passed++;
        } else {
            console.error(`❌ FAIL: ${message} (Expected ${expected}, got ${actual})`);
            failed++;
        }
    }

    // --- estimateTokenCount ---
    console.log('\nTesting estimateTokenCount()');
    assertEqual(estimateTokenCount(''), 0, 'Empty string returns 0 tokens');
    assertEqual(estimateTokenCount('   '), 0, 'Whitespace only string returns 0 tokens');
    assertEqual(estimateTokenCount('hello world'), 2, 'Basic string counts correctly');
    assertEqual(estimateTokenCount('  hello   world  '), 2, 'Extra whitespace ignored');
    assertEqual(estimateTokenCount('hello, world!'), 2, 'Punctuation attached to words');

    // --- truncateTokens ---
    console.log('\nTesting truncateTokens()');
    assertEqual(truncateTokens('', 10), '', 'Empty string returns empty string');
    assertEqual(truncateTokens('hello world', 0), '', '0 maxTokens returns empty string');
    assertEqual(truncateTokens('hello world', -1), '', 'Negative maxTokens returns empty string');
    assertEqual(truncateTokens('hello world', 1), 'hello', 'Truncates to 1 token correctly');
    assertEqual(truncateTokens('hello world', 2), 'hello world', 'Truncates to exactly 2 tokens correctly');
    assertEqual(truncateTokens('hello world', 5), 'hello world', 'Truncates with maxTokens > actual tokens');
    assertEqual(truncateTokens('this is a test sentence', 3), 'this is a', 'Truncates multiple words correctly');

    // --- estimateTokenCountAdvanced ---
    console.log('\nTesting estimateTokenCountAdvanced()');
    assertEqual(estimateTokenCountAdvanced(''), 0, 'Empty string returns 0 tokens');
    assertEqual(estimateTokenCountAdvanced('   '), 0, 'Whitespace only string returns 0 tokens');
    assertEqual(estimateTokenCountAdvanced('hello world'), 2, 'Basic string counts correctly');
    assertEqual(estimateTokenCountAdvanced('  hello   world  '), 2, 'Extra whitespace ignored');

    // Punctuation tests for Advanced Token Estimation
    assertEqual(estimateTokenCountAdvanced('hello, world!'), 4, 'Punctuation counted as separate tokens (hello , world !)');
    assertEqual(estimateTokenCountAdvanced('Wait... what?'), 6, 'Multiple punctuation characters (Wait . . . what ?)');
    assertEqual(estimateTokenCountAdvanced('user:password'), 3, 'Colon separated words (user : password)');
    assertEqual(estimateTokenCountAdvanced('a b c'), 3, 'Single character tokens');

    console.log('\n-----------------------------------');
    console.log(`Tests Completed: ${passed} Passed, ${failed} Failed`);

    if (failed > 0) {
        process.exit(1);
    }
}

testTokenUtils().catch(e => {
    console.error(e);
    process.exit(1);
});
