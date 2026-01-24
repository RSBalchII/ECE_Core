
const path = require('path');

console.log('--- Native Atomizer Verification ---');

try {
    const nativePath = path.join(__dirname, 'build/Release/ece_native.node');
    console.log(`Loading native binary from: ${nativePath}`);
    const native = require(nativePath);

    console.log('Native module loaded.');

    if (!native.atomize) {
        throw new Error('native.atomize function not found!');
    }

    // TEST 1: Prose Strategy
    console.log('\n[Test 1] Prose Strategy');
    const prose = "This is sentence one. This is sentence two! And three?\n\nNew paragraph.";
    const proseAtoms = native.atomize(prose, 'prose');
    console.log(`Input Length: ${prose.length}`);
    console.log(`Atoms Found: ${proseAtoms.length}`);
    proseAtoms.forEach((a, i) => console.log(`  Atom ${i} (${a.length} chars): "${a.replace(/\n/g, '\\n')}"`));

    // TEST 2: Code Strategy
    console.log('\n[Test 2] Code Strategy');
    const code = `
    function foo() {
        console.log("Nested");
        if (true) {
            // deep
        }
    }

    class Bar {
        method() {}
    }
    `;
    const codeAtoms = native.atomize(code, 'code');
    console.log(`Input Length: ${code.length}`);
    console.log(`Atoms Found: ${codeAtoms.length}`);
    codeAtoms.forEach((a, i) => console.log(`  Atom ${i} (${a.length} chars): [Code Block]`));

    if (proseAtoms.length > 0 && codeAtoms.length > 0) {
        console.log('\nPASS: Atomizer functional.');
    } else {
        console.error('\nFAIL: Atomizer produced no output.');
    }

} catch (e) {
    console.error('FAIL:', e);
}
