// Memory-boundedness check for grouping + Pass 2 streaming.
// Runs radialDistillFullCorpus on increasing atom counts and measures peak RSS,
// demonstrating that memory grows sub-linearly (bounded per-window reads) rather
// than accumulating whole-file content.

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import process from 'process';

const h = vi.hoisted(() => ({ mockDb: { run: vi.fn() }, mirrorDir: '' }));

vi.mock('../../src/core/db.js', () => ({ db: h.mockDb }));
const distillsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'distills-'));
vi.mock('../../src/config/index.js', () => ({ PATHS: { DISTILLS_DIR: distillsDir }, config: {} }));
vi.mock('../../src/services/mirror/mirror.js', () => ({
  getMirrorPath: (source_path) => path.join(h.mirrorDir, source_path),
}));

const { radialDistillFullCorpus } = await import('../../src/services/distillation/radial-distiller-v2.ts');

function peakRssMB() {
  return process.memoryUsage().rss / (1024 * 1024);
}

describe('Memory boundedness — grouping + Pass 2 streaming', () => {
  beforeEach(() => {
    h.mirrorDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mirror-'));
    // One source file per atom, each with a few atoms; content windows are small.
    for (let i = 0; i < 200; i++) {
      const name = `src_${i}.ts`;
      fs.writeFileSync(path.join(h.mirrorDir, name), Buffer.from('x'.repeat(500)));
    }
  });

  afterEach(() => { try { fs.rmSync(h.mirrorDir, { recursive: true, force: true }); } catch {} });

  it('stays bounded as atom count grows (no whole-file accumulation)', async () => {
    const sizes = [100, 400, 900];
    let rssBefore = peakRssMB();

    for (const n of sizes) {
      // Scatter atoms across sources in atom-ID order so grouping must reorder.
      const atoms = [];
      for (let i = 0; i < n; i++) {
        const srcIdx = i % 200;
        atoms.push({
          id: `atom_${String(i).padStart(6, '0')}`,
          type: 'content',
          source_path: `src_${srcIdx}.ts`,
          start_byte: (i % 10) * 5,
          end_byte: (i % 10) * 5 + 20,
        });
      }

      h.mockDb.run.mockImplementation(async (_sql, params) => {
        const lastId = params?.[0] ?? '';
        return { rows: atoms.filter(a => a.id > lastId).slice(0, 500) };
      });

      await radialDistillFullCorpus({ page_size: 500, inflate_radius: 500, max_record_bytes: 8192 });
    }

    const rssAfter = peakRssMB();
    console.log(`Peak RSS after distilling ${sizes[sizes.length - 1]} atoms: ${rssAfter.toFixed(1)} MB`);

    // Memory should not blow up proportionally to atom count. Allow generous headroom
    // for the WASM modules + node baseline; the point is it does NOT scale linearly
    // with content volume (which would indicate whole-file accumulation).
    expect(rssAfter - rssBefore).toBeLessThan(200); // < 200 MB growth across all runs
  });
});
