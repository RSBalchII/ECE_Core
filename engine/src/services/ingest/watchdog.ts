/**
 * Watchdog Service
 *
 * Scans the Notebook directory for changes and ingests new content.
 * Uses 'chokidar' for efficient file watching.
 */

import * as chokidar from 'chokidar';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { db } from '../../core/db.js';
import { NOTEBOOK_DIR } from '../../config/paths.js';
import { ingestAtoms } from './ingest.js';
import { refineContent } from './refiner.js';

let watcher: chokidar.FSWatcher | null = null;
const IGNORE_PATTERNS = /(^|[\/\\])\../; // Ignore dotfiles

export async function startWatchdog() {
    if (watcher) return;

    if (!fs.existsSync(NOTEBOOK_DIR)) {
        console.warn(`[Watchdog] Notebook directory not found: ${NOTEBOOK_DIR}. Skipping watch.`);
        return;
    }

    const inbox = path.join(NOTEBOOK_DIR, 'inbox');
    console.log(`[Watchdog] Starting watch on: ${inbox}`);

    if (!fs.existsSync(inbox)) {
        console.warn(`[Watchdog] Inbox directory not found: ${inbox}. Skipping watch.`);
        return;
    }

    watcher = chokidar.watch(inbox, {
        ignored: IGNORE_PATTERNS,
        persistent: true,
        ignoreInitial: false, // Force scan on start to ingest existing files
        awaitWriteFinish: {
            stabilityThreshold: 2000,
            pollInterval: 100
        }
    });

    watcher
        .on('add', (path) => processFile(path, 'add'))
        .on('change', (path) => processFile(path, 'change'));
    // .on('unlink', (path) => deleteFile(path)); // Implement delete logic later
}

async function processFile(filePath: string, event: string) {
    if (!filePath.endsWith('.md') && !filePath.endsWith('.txt') && !filePath.endsWith('.yaml')) return;
    if (filePath.includes('mirrored_brain')) return;

    console.log(`[Watchdog] Detected ${event}: ${filePath}`);

    try {
        const buffer = await fs.promises.readFile(filePath);
        if (buffer.length === 0) return;

        // 1. Calculate File Hash (Raw for Change Detection)
        const fileHash = crypto.createHash('sha256').update(buffer).digest('hex');
        const relativePath = path.relative(NOTEBOOK_DIR, filePath);

        // 2. Check Source Table
        const sourceQuery = `?[path, hash] := *source{path, hash}, path = $path`;
        const sourceResult = await db.run(sourceQuery, { path: relativePath });

        let shouldIngest = true;
        if (sourceResult.rows && sourceResult.rows.length > 0) {
            const [_path, existingHash] = sourceResult.rows[0];
            if (existingHash === fileHash) {
                console.log(`[Watchdog] File unchanged (hash match): ${relativePath}`);
                shouldIngest = false;
            }
        }

        if (!shouldIngest) return;

        console.log(`[Watchdog] Refinement Pipeline: ${relativePath}`);

        // 3. Smart Refinement (Dry Run)
        // Parse atoms WITHOUT generating embeddings first
        const { enrichAtoms } = await import('./refiner.js');
        const dryRunAtoms = await refineContent(buffer, relativePath, { skipEmbeddings: true });

        const sourceId = crypto.createHash('md5').update(relativePath).digest('hex');

        // 4. Fetch Existing Atoms from DB for this source
        // We need ID and Hash to compare
        const existingQuery = `?[id, hash] := *memory{id, source_id, hash}, source_id = $sid`;
        const existingResult = await db.run(existingQuery, { sid: sourceId });

        const existingMap = new Map<string, string>(); // ID -> Hash
        if (existingResult.rows) {
            existingResult.rows.forEach((r: any) => existingMap.set(r[0], r[1]));
        }

        // 5. Calculate Diff
        // New Atoms: Present in dryRun but NOT in DB (by ID) OR Hash mismatch
        // Deleted Atoms: Present in DB but NOT in dryRun (by ID)

        const atomsToIngest: any[] = [];
        const atomIdsToKeep = new Set<string>();

        for (const atom of dryRunAtoms) {
            atomIdsToKeep.add(atom.id);
            const existingHash = existingMap.get(atom.id);

            // If it's new (not in DB) or changed (hash mismatch), we need to ingest it
            // Note: Atom ID includes hash in standard refiner, so usually ID change = content change.
            // But if we change ID generation later, comparing hashes is safer.
            if (!existingHash) {
                atomsToIngest.push(atom);
            } else if (existingHash !== atom.id.replace('atom_', '')) {
                // Fallback check if hash isn't explicit
                atomsToIngest.push(atom);
            }
        }

        const idsToDelete: string[] = [];
        for (const [id] of existingMap) {
            if (!atomIdsToKeep.has(id)) {
                idsToDelete.push(id);
            }
        }

        console.log(`[Watchdog] Smart Diff for ${relativePath}: +${atomsToIngest.length} / -${idsToDelete.length} / =${atomIdsToKeep.size - atomsToIngest.length}`);

        // 6. Execute Updates

        // A. DELETE orphans
        if (idsToDelete.length > 0) {
            await db.run(`?[id] <- $ids :delete memory {id}`, { ids: idsToDelete.map(id => [id]) });
        }

        // B. ENRICH & INSERT new/changed
        if (atomsToIngest.length > 0) {
            // Now we pay the cost of embedding ONLY for the new stuff
            const enrichedAtoms = await enrichAtoms(atomsToIngest);

            // Improved Bucket Logic for Subfolders
            const parts = relativePath.split(path.sep);
            let bucket = 'notebook';

            if (parts.length >= 2) {
                // Check if it's inside 'inbox'
                if (parts[0] === 'inbox') {
                    // inbox/subfolder/file.md -> use 'subfolder'
                    // inbox/file.md -> use 'inbox'
                    bucket = parts.length > 2 ? parts[1] : 'inbox';
                } else {
                    // other_folder/file.md -> use 'other_folder'
                    bucket = parts[0];
                }
            }

            const bucketList = [bucket];

            await ingestAtoms(enrichedAtoms, relativePath, bucketList, []);
        }

        // 7. Update Source Table - ONLY if we reached here without error
        await db.run(
            `?[path, hash, total_atoms, last_ingest] <- [[$path, $hash, $total, $last]] 
             :put source {path, hash, total_atoms, last_ingest}`,
            {
                path: relativePath,
                hash: fileHash,
                total: dryRunAtoms.length, // Total is now current valid count
                last: Date.now()
            }
        );

        if (atomsToIngest.length > 0 || idsToDelete.length > 0) {
            console.log(`[Watchdog] Sync Complete: ${relativePath}`);

            // Trigger Mirror Protocol for Near-Real-Time visibility
            try {
                const { createMirror } = await import('../mirror/mirror.js');
                await createMirror();
            } catch (mirrorError: any) {
                console.error(`[Watchdog] Mirror Protocol trigger failed:`, mirrorError.message);
            }
        } else {
            console.log(`[Watchdog] No atom changes detected (Metadata update only).`);
        }

    } catch (e: any) {
        console.error(`[Watchdog] Error processing ${filePath}:`, e.message);
    }
}
