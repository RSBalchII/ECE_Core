#!/usr/bin/env node
/**
 * Graph Distillation CLI - Standard 133 Radial Distillation
 *
 * Usage:
 *   node --loader ts-node/esm src/commands/distill.ts [options] [seed_query]
 *
 * Options:
 *   --seed-ids, -s    Comma-separated compound IDs to start from
 *   --radius, -r      Inflation radius (default: 2000)
 *   --output, -o      Output file path (default: ./reports/distill-report-<timestamp>.md)
 *   --yaml            Output as YAML
  --format=decision-records  Output as Decision Records (semantic blocks)
 *   --json            Output as JSON
  --format=decision-records  Output as Decision Records (semantic blocks)
 *   --export, -e      Export to inbox/distilled/ folder
 *   --strict          Strict normalization (default)
 *   --lenient         Lenient normalization
 *   --mode=full-corpus   Seedless full-corpus mode (dedup every atom, stream JSONL)
 *   --page-size=N              full-corpus: atoms per DB page (default 500)
 *   --inflate-radius=N         full-corpus: bytes each side of pointer (default 300, max 1000)
 *   --max-record-bytes=N       full-corpus: cap on inflated bytes per record (default 8192)
 *   --simhash-threshold=N      full-corpus: Hamming bits to treat as duplicate (default 3)
 */

import { db } from '../core/db.js';
import type { RadialDistillRequest } from '../services/distillation/radial-distiller-v2.js';
import { radialDistill as radialDistillV2 } from '../services/distillation/radial-distiller-v2.js';
import { radialDistill as radialDistillLegacy } from '../services/distillation/radial-distiller.js';
import { config } from '../config/index.js';
import path from 'path';
import fs from 'fs';

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Graph Distillation CLI - Standard 133 Radial Distillation

Usage:
  node --loader ts-node/esm src/commands/distill.ts [options] [seed_query]

Options:
  --seed-ids, -s    Comma-separated compound IDs to start from
  --radius, -r      Inflation radius (default: 2000)
  --strict          Strict normalization (default)
  --lenient         Lenient normalization
  --output, -o      Output file path
  --yaml            Output as YAML
  --json            Output as JSON
  --export, -e      Export to inbox/distilled/ folder

Examples:
  node src/commands/distill.ts
  node src/commands/distill.ts --radius 5000
  node src/commands/distill.ts --strict --export
  node src/commands/distill.ts --lenient --yaml
    `);
    process.exit(0);
  }

  // Parse arguments
  const seedIdsIndex = args.indexOf('--seed-ids') !== -1 ? args.indexOf('--seed-ids') : args.indexOf('-s');
  const seedIds = seedIdsIndex >= 0 ? args[seedIdsIndex + 1].split(',') : undefined;

  const radiusIndex = args.indexOf('--radius') !== -1 ? args.indexOf('--radius') : args.indexOf('-r');
  const radius = radiusIndex >= 0 ? parseInt(args[radiusIndex + 1]) : 2000;

  const asJson = args.includes('--json');
  const asYaml = args.includes('--yaml') || args.includes('-y');
  const exportToInbox = args.includes('--export') || args.includes('-e');
  const strictNormalization = args.includes('--strict');
  const lenientNormalization = args.includes('--lenient');

  // Check if decision-records format is requested (via --format flag or direct argument)
  const hasDecisionRecordsFlag = args.includes('--format') && args[args.indexOf('--format') + 1] === 'decision-records';
  const explicitFormat = args.find(a => a.startsWith('--format'))?.split('=')[1];

  const outputIndex = args.indexOf('--output') !== -1 ? args.indexOf('--output') : args.indexOf('-o');
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

  // Full-corpus / tuning flags (Standard 133 seedless mode)
  const mode = args.find(a => a.startsWith('--mode'))?.split('=')[1];
  const pageSize = args.find(a => a.startsWith('--page-size'))?.split('=')[1];
  const inflateRadius = args.find(a => a.startsWith('--inflate-radius'))?.split('=')[1];
  const maxRecordBytes = args.find(a => a.startsWith('--max-record-bytes'))?.split('=')[1];
  const simhashThreshold = args.find(a => a.startsWith('--simhash-threshold'))?.split('=')[1];
  const consumedFlagValues = new Set<string>();
  for (const f of ['--mode', '--page-size', '--inflate-radius', '--max-record-bytes', '--simhash-threshold']) {
    const idx = args.indexOf(f);
    if (idx >= 0 && idx + 1 < args.length) consumedFlagValues.add(args[idx + 1]);
  }

  let outputFormat: RadialDistillRequest['output_format'] = 'decision-records'; // Default to decision-records in v2
  if (explicitFormat && explicitFormat.includes('yaml')) {
    outputFormat = 'yaml';
  } else if (explicitFormat && explicitFormat.includes('json-full')) {
    outputFormat = 'json-full';
  }

  const ext = outputFormat === 'yaml' ? 'yaml' : (outputFormat === 'decision-records' ? 'json' : outputFormat === 'json-full' ? 'json' : 'md');
  const defaultOutput = `./reports/distill-report-${timestamp}.${ext}`;
  const outputPath = outputIndex >= 0 ? args[outputIndex + 1] : defaultOutput;

  // Remaining arg is the seed query (excluding consumed flag values)
  const seedQuery = args.filter(a => !a.startsWith('-') && args.indexOf(a) !== seedIdsIndex + 1 && args.indexOf(a) !== outputIndex + 1 && args.indexOf(a) !== radiusIndex + 1 && !consumedFlagValues.has(a))[0];

  console.log('='.repeat(60));
  console.log('  Anchor Engine - Graph Distiller');
  console.log('='.repeat(60));
  console.log();

  try {
    // IMPORTANT: Do not wipe database on command run
    config.DATABASE.WIPE_ON_STARTUP = false;

    console.log('Initializing database...');
    await db.init();

    // Standard 133: Radial Distillation (v2)
    const radialRequest: RadialDistillRequest = {
      seed: {
        query: seedQuery,
        compound_ids: seedIds,
      },
      radius: radius,
      max_radius: radius * 2, // Use double radius for deduplication buffer zone
      output_format: asYaml ? 'yaml' : (asJson ? 'json' : 'decision-records'),
      output_path: outputPath,
      export_to_inbox: exportToInbox,
      // Full-corpus / seedless tuning (Standard 133)
      mode: (mode as RadialDistillRequest['mode']) || undefined,
      page_size: pageSize ? parseInt(pageSize, 10) : undefined,
      inflate_radius: inflateRadius ? parseInt(inflateRadius, 10) : undefined,
      max_record_bytes: maxRecordBytes ? parseInt(maxRecordBytes, 10) : undefined,
      simhash_hamming_threshold: simhashThreshold ? parseInt(simhashThreshold, 10) : undefined,
    };

    console.log('Radial Distilling (Standard 133)...');
    console.log(`  Target: ${seedQuery || (seedIds ? seedIds.join(',') : 'All Compounds')}`);
    console.log(`  Radius: ${radius} chars`);
    console.log('  Mode: Line-level deduplication');
    if (exportToInbox) console.log('  Export: Enabled (→ inbox/distilled/)');
    console.log();

    const result = await radialDistillV2(radialRequest);

    console.log();
    console.log('Radial Distillation Complete:');
    console.log(`  Compounds Processed: ${result.stats.compounds_processed}`);
    console.log(`  Blocks Total: ${result.stats.blocks_total}`);
    console.log(`  Unique Blocks: ${result.stats.blocks_unique}`);
    console.log(`  Compression: ${result.stats.compression_ratio}`);
    console.log(`  Duration: ${(result.stats.duration_ms / 1000).toFixed(2)}s`);
    console.log(`  Memory Peak: ${result.stats.memory_peak_mb}MB`);
    console.log(`  Output: ${result.output.path}`);
    console.log();

    await db.close();
  } catch (error: any) {
    console.error('Error during distillation:', error.message);
    process.exit(1);
  }
}

main();
