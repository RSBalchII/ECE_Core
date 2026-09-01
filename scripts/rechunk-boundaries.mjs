// Boundary re-chunker prototype for Anchor Engine full-corpus distills.
//
// Problem (verified): the radial distiller streams one ~300-byte window per atom
// in atom-ID order, so records are scattered across sources and 95%+ end mid-sentence.
//
// This post-processor reads an existing distill JSONL, groups content-bearing atoms
// by source file, reconstructs contiguous text from their byte-pointer coverage
// (deduping overlaps), then splits at semantic boundaries -> coherent records with
// full sentences/sections. Provenance is kept via the original atom IDs + byte
// ranges that contributed to each chunk.
//
// Memory: holds all parsed records in RAM (~file size). Fine for a batch prototype;
// for true phone streaming this would run grouped-by-source during Pass 2 of the
// distiller instead of post-hoc.

import fs from 'node:fs';
import path from 'node:path';

const dir = '/home/rsbiiw/.anchor/distills';
const candidates = fs.readdirSync(dir).filter(f => f.startsWith('distilled_fullcorpus_') && f.endsWith('.jsonl') && !f.includes('_rechunked'));
if (!candidates.length) { console.error('no distill files found'); process.exit(1); }
candidates.sort().reverse(); // newest first (timestamp-ish suffix sorts lexically)
const INPUT = path.join(dir, candidates[0]);
const OUT = INPUT.replace(/\.jsonl$/, '_rechunked.jsonl');

function isCleanTerminator(s) {
  const t = s.trimEnd();
  return /[.!?\"]$/.test(t) || /\n$/.test(t);
}

// Split reconstructed text into coherent chunks at semantic boundaries,
// returning {text, startByte, endByte} with accurate UTF-8 byte offsets.
function splitSemantic(content, baseByte) {
  const chunks = [];
  let buf = '';
  let bufStart = baseByte;
  const n = content.length;
  let i = 0;

  const flush = () => {
    if (buf.length) chunks.push({ text: buf, start: bufStart, end: bufStart + Buffer.byteLength(buf, 'utf8') });
    buf = '';
  };

  while (i < n) {
    const ch = content[i];
    const next = content[i + 1];

    // Markdown header on its own line -> close current sentence, start fresh chunk.
    if (ch === '\n' && /^#{1,6}\s/.test(content.slice(i + 1))) {
      flush();
      buf += ch; i++; continue;
    }
    // Blank line -> boundary.
    if (ch === '\n' && next === '\n') {
      buf += ch; flush(); i += 2; continue;
    }

    buf += ch;
    if (ch === '.' || ch === '!' || ch === '?') {
      if (next === undefined || /\s/.test(next)) { flush(); i++; continue; }
    }
    i++;
  }
  flush();
  return chunks;
}

// Reconstruct contiguous regions from atom byte ranges, deduping overlaps.
function reconstructRegions(atoms) {
  const arr = atoms.filter(a => a.content && a.end > a.start).sort((a, b) => (a.start - b.start) || (a.end - b.end));
  const regions = [];
  for (const a of arr) {
    let merged = false;
    for (let r = regions.length - 1; r >= 0; r--) {
      const reg = regions[r];
      if (a.start <= reg.end + 1) { // overlap or adjacent
        const overlap = reg.end - a.start;
        const extra = overlap > 0 ? a.content.slice(overlap) : a.content;
        reg.content += extra;
        if (a.end > reg.end) reg.end = a.end;
        reg.ids.push(...a.ids);
        merged = true; break;
      } else break;
    }
    if (!merged) regions.push({ start: a.start, end: a.end, content: a.content, ids: [...a.ids] });
  }
  return regions;
}

// ---- synchronous read of the distill file ----------------------------------
const recordsBySource = new Map(); // source_path -> [{start,end,content,ids}]
let totalLines = 0, contentLines = 0, emptyLines = 0;

for (const line of fs.readFileSync(INPUT, 'utf-8').split('\n')) {
  if (!line.trim()) continue;
  totalLines++;
  let rec;
  try { rec = JSON.parse(line); } catch { continue; }
  const content = typeof rec.content === 'string' ? rec.content : '';
  if (!content.trim()) { emptyLines++; continue; }
  contentLines++;
  const src = rec.source_path || 'unknown';
  // widest real occurrence for byte range + contributing atom ids
  let best = null, bestSpan = -1;
  for (const o of rec.occurrences || []) {
    if (o.source_path !== src) continue;
    const span = Math.max(0, o.end_byte - o.start_byte);
    if (span > bestSpan) { bestSpan = span; best = o; }
  }
  const occ = best || (rec.occurrences && rec.occurrences[0]) || {};
  const list = recordsBySource.get(src) || [];
  list.push({ start: occ.start_byte || 0, end: occ.end_byte || 0, content, ids: [rec.id] });
  recordsBySource.set(src, list);
}

// ---- re-chunk per source ---------------------------------------------------
const outLines = [];
let outRecords = 0, gapRegions = 0;
const sizeBySource = {};

for (const [src, atoms] of recordsBySource) {
  const regions = reconstructRegions(atoms);
  for (const reg of regions) {
    if (reg.content.trim().length < 8) continue; // skip near-empty
    let prevEnd = reg.start;
    for (const chunk of splitSemantic(reg.content, reg.start)) {
      if (chunk.text.trim().length < 3) continue;
      const gap = chunk.start - prevEnd;
      prevEnd = chunk.end;
      if (gap > 16) gapRegions++; // note: small gaps are normal between atoms
      outRecords++;
      sizeBySource[src] = (sizeBySource[src] || 0) + Buffer.byteLength(chunk.text, 'utf8');
      outLines.push(JSON.stringify({
        id: `chunk_${outRecords}`,
        type: 'content',
        content: chunk.text,
        source_path: src,
        start_byte: chunk.start,
        end_byte: chunk.end,
        provenance: 'rechunked-from-distill',
        contributing_atom_ids: [...new Set(reg.ids)],
      }));
    }
  }
}
fs.writeFileSync(OUT, outLines.join('\n') + '\n');

// ---- metrics ----------------------------------------------------------------
const clean = (s) => isCleanTerminator(s);
console.log('=== RECHUNK PROTOTYPE RESULTS ===');
console.log(`Input distill : ${path.basename(INPUT)}`);
console.log(`Output        : ${path.basename(OUT)}`);
console.log(`Distill records read   : ${totalLines} (content=${contentLines}, empty=${emptyLines})`);
console.log(`Distinct source files  : ${recordsBySource.size}`);
console.log(`Rechunked records      : ${outRecords}`);
console.log(`Regions with gaps      : ${gapRegions} (inter-atom whitespace, expected)`);

// baseline mid-sentence rate on original content lines
let baseNoTerm = 0;
for (const line of fs.readFileSync(INPUT, 'utf-8').split('\n')) {
  if (!line.trim()) continue;
  let rec; try { rec = JSON.parse(line); } catch { continue; }
  const c = typeof rec.content === 'string' ? rec.content : '';
  if (!c.trim()) continue;
  if (!clean(c)) baseNoTerm++;
}
console.log(`\n--- BASELINE (original distill) ---`);
console.log(`Records ending mid-sentence / no terminator: ${baseNoTerm}/${contentLines} = ${(100*baseNoTerm/contentLines).toFixed(1)}%`);

// rechunked clean-terminator rate by reading output
let rcClean = 0, rcTotal = 0;
for (const line of fs.readFileSync(OUT, 'utf-8').split('\n')) {
  if (!line.trim()) continue;
  try { const r = JSON.parse(line); if (r.content?.trim()) { rcTotal++; if (clean(r.content)) rcClean++; } } catch {}
}
console.log(`\n--- RECHUNKED output ---`);
console.log(`Records ending on clean terminator: ${rcClean}/${rcTotal} = ${(100*rcClean/rcTotal).toFixed(1)}%`);

// top sources by reconstructed chars (density)
const top = Object.entries(sizeBySource).sort((a,b)=>b[1]-a[1]).slice(0,5);
console.log(`\nTop sources by reconstructed chars: ${top.map(([s,n])=>`${Math.round(n/1024)}KB`).join(', ')}`);
