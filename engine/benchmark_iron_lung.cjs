
const { performance } = require('perf_hooks');
const path = require('path');

// 1. Load Native Module
let native;
try {
    native = require('./build/Release/ece_native.node');
} catch (e) {
    console.error("Could not load native module for benchmarking.");
    process.exit(1);
}

// 2. Legacy JS Implementation (The Control)
function atomizeJS(text, strategy) {
    if (strategy === 'code') {
        const lines = text.split('\n');
        const atoms = [];
        let currentChunk = '';
        const pushChunk = () => {
            if (currentChunk.trim().length > 0) {
                atoms.push(currentChunk.trim());
                currentChunk = '';
            }
        };
        for (const line of lines) {
            const isTopLevel = /^[^\s]/.test(line) && !/^[\}\] \t]*$/.test(line);
            if (isTopLevel && currentChunk.length > 500) pushChunk();
            if ((currentChunk + line).length > 2000) pushChunk();
            currentChunk += line + '\n';
        }
        pushChunk();
        return atoms;
    }
    // Prose
    const rawBlocks = text.split(/\n\s*\n/);
    const atoms = [];
    for (const block of rawBlocks) {
        if (block.trim().length === 0) continue;
        if (block.length > 800) {
            const sentences = block.match(/[^.!?]+[.!?]+(\s+|$)|[^.!?]+$/g) || [block];
            let currentChunk = "";
            for (const sentence of sentences) {
                if ((currentChunk + sentence).length > 800) {
                    if (currentChunk.trim().length > 0) atoms.push(currentChunk.trim());
                    currentChunk = sentence;
                } else {
                    currentChunk += sentence;
                }
            }
            if (currentChunk.trim().length > 0) atoms.push(currentChunk.trim());
        } else {
            atoms.push(block.trim());
        }
    }
    return atoms;
}

// 3. Generators
function generateProse(sizeMB) {
    const sentence = "The quick brown fox jumps over the lazy dog. ";
    const para = sentence.repeat(20) + "\n\n";
    const targetSize = sizeMB * 1024 * 1024;
    return para.repeat(Math.ceil(targetSize / para.length)).slice(0, targetSize);
}

function generateCode(sizeMB) {
    const block = `
function test() {
    console.log("Hello");
    if (true) {
        return;
    }
}
class Foo {
    bar() {
        return "baz";
    }
}
`;
    const targetSize = sizeMB * 1024 * 1024;
    return block.repeat(Math.ceil(targetSize / block.length)).slice(0, targetSize);
}

// 4. Benchmark Runner
function runBenchmark(label, fn) {
    const start = performance.now();
    const result = fn();
    const end = performance.now();
    // Force GC if possible or just use heap stats?
    // We just return time for now.
    return { time: end - start, count: result.length };
}

console.log("=== OPERATION IRON LUNG: BENCHMARK ===");

const SIZES = [1, 10]; // MB

for (const size of SIZES) {
    console.log(`\n--- Size: ${size}MB ---`);

    // CODE Test
    const codeText = generateCode(size);
    console.log(`[Code] Generated ${codeText.length} chars.`);

    const jsCode = runBenchmark('JS Code', () => atomizeJS(codeText, 'code'));
    const cppCode = runBenchmark('C++ Code', () => native.atomize(codeText, 'code'));

    console.log(`JS Code:  ${jsCode.time.toFixed(2)}ms (${jsCode.count} atoms)`);
    console.log(`C++ Code: ${cppCode.time.toFixed(2)}ms (${cppCode.count} atoms)`);
    console.log(`🚀 Speedup: ${(jsCode.time / cppCode.time).toFixed(1)}x`);

    // PROSE Test
    const proseText = generateProse(size);
    console.log(`[Prose] Generated ${proseText.length} chars.`);

    const jsProse = runBenchmark('JS Prose', () => atomizeJS(proseText, 'prose'));
    const cppProse = runBenchmark('C++ Prose', () => native.atomize(proseText, 'prose'));

    console.log(`JS Prose:  ${jsProse.time.toFixed(2)}ms (${jsProse.count} atoms)`);
    console.log(`C++ Prose: ${cppProse.time.toFixed(2)}ms (${cppProse.count} atoms)`);
    console.log(`🚀 Speedup: ${(jsProse.time / cppProse.time).toFixed(1)}x`);
}
