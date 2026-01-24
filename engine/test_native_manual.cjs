
const path = require('path');

console.log('--- Native Module Verification ---');

try {
    const nativePath = path.join(__dirname, 'build/Release/ece_native.node');
    console.log(`Loading native binary from: ${nativePath}`);
    const native = require(nativePath);

    console.log('Native module loaded successfully.');

    // Test Data
    const input = 'Hello\\nWorld! \\"Iron Lung\\"';
    console.log(`Input: ${input}`);

    const start = process.hrtime.bigint();
    const output = native.cleanse(input);
    const end = process.hrtime.bigint();

    console.log(`Output: ${JSON.stringify(output)}`);
    console.log(`Duration: ${Number(end - start)}ns`);

    if (output === 'Hello\nWorld! "Iron Lung"') {
        console.log('PASS: Logic verified.');
    } else {
        console.error('FAIL: Output mismatch.');
    }

} catch (e) {
    console.error('FAIL: Could not load native module.');
    console.error(e);
}
