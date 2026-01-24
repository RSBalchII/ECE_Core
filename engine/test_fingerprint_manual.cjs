
const path = require('path');

console.log('--- Native Fingerprint Verification ---');

try {
    const nativePath = path.join(__dirname, 'build/Release/ece_native.node');
    console.log(`Loading native binary from: ${nativePath}`);
    const native = require(nativePath);

    console.log('Native module loaded.');

    if (!native.fingerprint || !native.distance) {
        throw new Error('Native SimHash functions not found!');
    }

    // TEST CASES
    const textA = "The sovereign context engine is a powerful tool for memory management.";
    const textB = "The sovereign context engine is a powerful tool for memory management!"; // 1 char diff
    const textC = "The sovereign context engine is a powerful tool for MEMORY management."; // Case diff 
    const textD = "Completely different text about pizza and pineapples.";

    console.log(`\nInput A: "${textA}"`);
    console.log(`Input B: "${textB}" (Minor Punctuation Change)`);
    console.log(`Input D: "${textD}" (Different Topic)`);

    const hashA = native.fingerprint(textA);
    const hashB = native.fingerprint(textB);
    const hashD = native.fingerprint(textD);

    console.log(`\nHash A: ${hashA} (BigInt)`);
    console.log(`Hash B: ${hashB}`);
    console.log(`Hash D: ${hashD}`);

    const distAB = native.distance(hashA, hashB);
    const distAD = native.distance(hashA, hashD);

    console.log(`\nDistance A <-> B: ${distAB} (Expected: Low)`);
    console.log(`Distance A <-> D: ${distAD} (Expected: High ~32)`);

    // Verification Logic
    if (distAB < 5 && distAD > 10) {
        console.log('\nPASS: SimHash Locality Sensitivity confirmed.');
    } else {
        console.error('\nFAIL: Distance metrics unexpected.');
    }

} catch (e) {
    console.error('FAIL:', e);
}
