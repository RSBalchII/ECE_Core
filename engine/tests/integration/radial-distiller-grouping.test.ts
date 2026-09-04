import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

// Hoist shared mock state so vi.mock factories (hoisted above imports) can reference it
const h = vi.hoisted(() => {
  return {
    mockDb: { run: vi.fn() },
    mirrorDir: '',
    mirrorData: new Map<string, Buffer>(),
  };
});

// Mock the db module (Pass 1): db.run(sqlString, paramsArray) -> { rows }
vi.mock('../../src/core/db.js', () => ({ db: h.mockDb }));

// Mock config so PATHS.DISTILLS_DIR resolves to a real temp dir
const distillsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'distills-'));
vi.mock('../../src/config/index.js', () => ({
  PATHS: { DISTILLS_DIR: distillsDir },
  config: {},
}));

// Mock getMirrorPath to return a real file path on disk
vi.mock('../../src/services/mirror/mirror.js', () => ({
  getMirrorPath: (source_path: string) => path.join(h.mirrorDir, source_path),
}));

// Import after mocks are set up
const { radialDistillFullCorpus } = await import('../../src/services/distillation/radial-distiller-v2.ts');

// Deterministic pseudo-random ASCII content. Files are large enough that the
// test's inflate_radius (500) does NOT swallow each file into one identical
// window: atoms differ by end_byte, so each reads a uniquely-sized, varied
// window and therefore a unique SimHash — letting this test measure contiguous
// per-file grouping INDEPENDENT of content-based dedup.
const content = (len: number, seed: number): string => {
  let s = seed >>> 0;
  let out = '';
  for (let i = 0; i < len; i++) {
    s = (Math.imul(s, 1103515245) + 12345) >>> 0;
    out += String.fromCharCode(33 + (s % 94));
  }
  return out;
};

describe('Radial Distiller v2 — Full-Corpus Grouping', () => {
  beforeEach(() => {
    h.mirrorDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mirror-'));
    h.mirrorData.clear();

    // Write real mirror files so readRangeFromMirror's fs calls succeed
    const writeMirror = (name: string, content: Buffer) => {
      const p = path.join(h.mirrorDir, name);
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, content);
      h.mirrorData.set(name, content);
    };

    writeMirror('fileA.ts', Buffer.from(content(1000, 1)));
    writeMirror('fileB.ts', Buffer.from(content(600, 2)));
    writeMirror('fileC.ts', Buffer.from(content(1000, 3)));
  });

  afterEach(() => {
    vi.clearAllMocks();
    try { fs.rmSync(h.mirrorDir, { recursive: true, force: true }); } catch {}
  });

  it('streams records grouped by source_path (contiguous per file)', async () => {
    // Synthetic atoms from 3 sources, in atom-ID order (scattered). Each carries
    // an explicit compound_id so records key cleanly to their own compound (6
    // compounds -> 6 survivors); distinct per-file content keeps them out of the
    // content-dedup path. Byte ranges chosen so span increases with start_byte
    // within each file, making intra-file ordering deterministic under the sort key.
    const atoms = [
      { id: 'atom1', compound_id: 'c1', type: 'content', source_path: 'fileA.ts', start_byte: 100, end_byte: 130 }, // span 30
      { id: 'atom2', compound_id: 'c2', type: 'content', source_path: 'fileB.ts', start_byte: 50,  end_byte: 60  }, // span 10
      { id: 'atom3', compound_id: 'c3', type: 'content', source_path: 'fileC.ts', start_byte: 200, end_byte: 280 }, // span 80
      { id: 'atom4', compound_id: 'c4', type: 'content', source_path: 'fileA.ts', start_byte: 50,  end_byte: 60  }, // span 10
      { id: 'atom5', compound_id: 'c5', type: 'content', source_path: 'fileB.ts', start_byte: 10,  end_byte: 20  }, // span 10
      { id: 'atom6', compound_id: 'c6', type: 'content', source_path: 'fileA.ts', start_byte: 200, end_byte: 280 }, // span 80
    ];

    // Pass 1: keyset-paginate atoms (pointers only) — respect WHERE id > $1
    h.mockDb.run.mockImplementation(async (_sql: string, params: any[]) => {
      const lastId = params?.[0] ?? '';
      const pageSize = params?.[1] ?? 500;
      // Filter by keyset and limit to simulate real pagination
      const filtered = atoms.filter(a => a.id > lastId).slice(0, pageSize);
      return { rows: filtered };
    });

    const request = {
      page_size: 500,
      inflate_radius: 500,
      max_record_bytes: 8192,
    };

    await radialDistillFullCorpus(request);

    // Read the actual output file Pass 2 wrote to PATHS.DISTILLS_DIR
    const files = fs.readdirSync(distillsDir).filter(f => f.endsWith('.jsonl'));
    expect(files.length).toBeGreaterThan(0);
    const outFile = path.join(distillsDir, files[files.length - 1]);
    const writtenContent = fs.readFileSync(outFile, 'utf-8');

    // Parse output JSONL and extract source_path order
    const lines = writtenContent.trim().split('\n').filter(Boolean);
    const records = lines.map(l => JSON.parse(l));
    const sources = records.map(r => r.source_path);

    console.log('Output order:', sources.join(', '));

    // Assert: all fileA records are contiguous, then fileB, then fileC
    const expectedOrder = ['fileA.ts', 'fileA.ts', 'fileA.ts', 'fileB.ts', 'fileB.ts', 'fileC.ts'];
    expect(sources).toEqual(expectedOrder);

    // Assert: all 6 records present
    expect(records.length).toBe(6);

    // Intra-file ordering follows the sort key: span (end-start) ascending,
    // ties broken by insertion order. With our data that yields a deterministic
    // compound-id sequence across the whole stream (records are keyed by
    // compound_id in Pass 1).
    const expectedIds = ['c4', 'c1', 'c6', 'c2', 'c5', 'c3'];
    expect(records.map(r => r.id)).toEqual(expectedIds);
  });
});
