import { db } from '../../src/core/db.js';
import { hydrateEngramResults } from '../../src/services/search/search.js';
import { SearchResult } from '../../src/services/search/search-utils.js';

async function testEngramHydration() {
  console.log('--- Testing Engram Hydration ---');

  // Initialize DB
  await db.init();

  const testId = 'test-atom-id';
  const testContent = 'This is a test atom for engram hydration.';
  const testSource = 'test-source.md';

  // Insert a test atom
  // Note: epochs is TEXT[] in DB schema
  const insertQuery = `
    INSERT INTO atoms (id, content, source_path, timestamp, provenance, buckets, tags, epochs)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
  `;

  await db.run(insertQuery, [
    testId,
    testContent,
    testSource,
    Date.now(),
    'internal',
    ['test-bucket'],
    ['test-tag'],
    ['epoch1']
  ]);

  console.log('Inserted test atom.');

  // Hydrate the atom
  const results = await hydrateEngramResults([testId]);

  console.log(`Hydrated ${results.length} results.`);

  if (results.length !== 1) {
    console.error(`❌ FAIL: Expected 1 result, got ${results.length}`);
    process.exit(1);
  }

  const atom = results[0];
  if (atom.id !== testId) {
    console.error(`❌ FAIL: ID mismatch. Expected ${testId}, got ${atom.id}`);
    process.exit(1);
  }
  if (atom.content !== testContent) {
    console.error(`❌ FAIL: Content mismatch. Expected "${testContent}", got "${atom.content}"`);
    process.exit(1);
  }
  if (!atom.buckets.includes('test-bucket')) {
    console.error(`❌ FAIL: Bucket mismatch.`);
    process.exit(1);
  }
  if (!atom.tags.includes('test-tag')) {
      console.error(`❌ FAIL: Tag mismatch.`);
      process.exit(1);
  }
  if (!atom.epochs.includes('epoch1')) {
      console.error(`❌ FAIL: Epoch mismatch.`);
      process.exit(1);
  }

  console.log('✅ PASS: Engram hydration verified successfully.');
}

testEngramHydration().catch(e => {
  console.error(e);
  process.exit(1);
});
