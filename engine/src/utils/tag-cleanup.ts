/**
 * Tag Cleanup Script - Run on startup to prune blacklisted tags
 * 
 * Removes all blacklisted tags from existing atoms in the database.
 * This ensures the tag space stays clean even for previously ingested content.
 */

import { db } from '../core/db.js';
import { filterTags } from '../utils/tag-filter.js';

const BATCH_SIZE = 1000;

/**
 * Get all distinct tags from the database
 */
async function getAllTags(): Promise<string[]> {
  const result = await db.run('SELECT DISTINCT tag FROM tags');
  return result.rows?.map((row: any) => row.tag) || [];
}

/**
 * Find blacklisted tags
 */
async function findBlacklistedTags(): Promise<string[]> {
  const allTags = await getAllTags();
  const blacklisted: string[] = [];
  
  for (const tag of allTags) {
    const filtered = filterTags([tag]);
    if (filtered.length === 0) {
      blacklisted.push(tag);
    }
  }
  
  return blacklisted;
}

/**
 * Remove a tag from all atoms
 */
async function removeTag(tag: string): Promise<number> {
  const result = await db.run('DELETE FROM tags WHERE tag = $1', [tag]);
  return result.changes || 0;
}

/**
 * Cleanup atoms with blacklisted tags
 * Updates the tags TEXT[] array in the atoms table.
 *
 * FIX (2026-08-25): previously this loaded EVERY atom row into JS memory and
 * ran one UPDATE per affected atom, which exhausted PGlite WASM linear memory
 * ("memory access out of bounds") on populated stores (~195k atoms). Now the
 * removal happens entirely in SQL (array_remove) — no full-table scan.
 */
async function cleanupAtomTags(blacklistedTags: string[]): Promise<number> {
  let totalCleaned = 0;

  try {
    for (const tag of blacklistedTags) {
      const result = await db.run(
        'UPDATE atoms SET tags = array_remove(tags, $1) WHERE $1 = ANY(tags)',
        [tag],
      );
      totalCleaned += result.changes || 0;
    }

    return totalCleaned;
  } catch (error) {
    console.error('[TagCleanup] Error cleaning atom tags:', error);
    return 0;
  }
}

/**
 * Main cleanup function - run on startup
 */
export async function cleanupBlacklistedTags(): Promise<void> {
  const startTime = Date.now();
  
  console.log('[TagCleanup] Starting tag cleanup on startup...');
  
  try {
    // Step 1: Remove blacklisted tags from tags table
    const blacklistedTags = await findBlacklistedTags();
    
    if (blacklistedTags.length > 0) {
      console.log(`[TagCleanup] Found ${blacklistedTags.length} blacklisted tags to remove:`);
      console.log(`[TagCleanup]   ${blacklistedTags.slice(0, 20).join(', ')}${blacklistedTags.length > 20 ? ` ... and ${blacklistedTags.length - 20} more` : ''}`);
      
      let totalDeleted = 0;
      for (const tag of blacklistedTags) {
        const deleted = await removeTag(tag);
        totalDeleted += deleted;
      }
      
      console.log(`[TagCleanup] Removed ${totalDeleted} tag entries from ${blacklistedTags.length} blacklisted tags`);
    } else {
      console.log('[TagCleanup] No blacklisted tags found in tags table');
    }
    
    // Step 2: Cleanup tags in atoms table — only when blacklisted tags exist,
    // so a populated store doesn't pay for a full atom scan on every startup.
    if (blacklistedTags.length > 0) {
      const atomsCleaned = await cleanupAtomTags(blacklistedTags);
      if (atomsCleaned > 0) {
        console.log(`[TagCleanup] Updated ${atomsCleaned} atoms with filtered tags`);
      }
    }
    
    const duration = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`[TagCleanup] ✅ Cleanup complete in ${duration}s`);
    
  } catch (error) {
    console.error('[TagCleanup] ❌ Cleanup failed:', error);
  }
}
