#!/usr/bin/env node
/**
 * Coherence check for distill output.
 * Measures the "terminator rate": fraction of records whose content ends with a
 * proper terminator (sentence boundary). A record that does NOT end with a
 * terminator is likely mid-sentence — i.e. incoherent / truncated by an arbitrary
 * byte cut. Higher terminator rate = more coherent chunks.
 *
 * Usage: node coherence-check.mjs <baseline.jsonl> [rechunked.jsonl]
 */

import { readFileSync } from 'fs';

const TERMINATORS = /[.!?。！？…\n\r\t]\s*$/;

function analyze(path) {
  let total = 0;
  let terminated = 0;
  const lines = readFileSync(path, 'utf-8').split('\n').filter(Boolean);
  for (const line of lines) {
    try {
      const rec = JSON.parse(line);
      if (!rec || typeof rec.content !== 'string') continue;
      total++;
      if (TERMINATORS.test(rec.content)) terminated++;
    } catch {}
  }
  return { total, terminated, rate: total ? terminated / total : 0 };
}

const [base, rechunk] = process.argv.slice(2);
if (!base) {
  console.error('Usage: node coherence-check.mjs <baseline.jsonl> [rechunked.jsonl]');
  process.exit(1);
}

const b = analyze(base);
console.log(`Baseline   : ${b.terminated}/${b.total} terminated (${(b.rate * 100).toFixed(1)}%)`);

if (rechunk) {
  const r = analyze(rechunk);
  console.log(`Rechunked  : ${r.terminated}/${r.total} terminated (${(r.rate * 100).toFixed(1)}%)`);
  const delta = (r.rate - b.rate) * 100;
  console.log(`Delta      : ${delta > 0 ? '+' : ''}${delta.toFixed(1)}pp`);
}
