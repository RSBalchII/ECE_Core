/**
 * Mirror Protocol Service - "Tangible Knowledge Graph"
 *
 * Mirrors source files to mirrored_brain/ for fast access.
 * The database stores only metadata/pointers; content lives in files.
 */

import * as fs from 'fs';
import * as path from 'path';
import yaml from 'js-yaml';
import { db } from '../../core/db.js';
import PATHS from '../../config/paths.js';

export const MIRRORED_BRAIN_PATH = PATHS.MIRRORED_BRAIN_DIR;

/**
 * Mirror Protocol: Rebuild mirrored_brain/ from source files.
 * Copies from inbox/notebook to mirrored_brain (metadata only in DB).
 */
export async function createMirror() {
    console.log('🪞 Mirror Protocol: Rebuilding from source files...');

    // Create mirror root
    if (!fs.existsSync(MIRRORED_BRAIN_PATH)) {
        fs.mkdirSync(MIRRORED_BRAIN_PATH, { recursive: true });
    }

    // Get all sources from DB (just paths, no content)
    const result = await db.run('SELECT path FROM sources ORDER BY path');
    const rows = result.rows || [];
    
    if (rows.length === 0) {
        console.log('🪞 Mirror Protocol: No sources to mirror.');
        return;
    }

    let fileCount = 0;
    let skippedCount = 0;

    for (const row of rows) {
        const dbPath: string = Array.isArray(row) ? row[0] : row.path;

        if (!dbPath) continue;

        // Determine mirror subdirectory
        let provenanceDir = '@inbox';
        if (dbPath.includes('external-inbox')) {
            provenanceDir = '@external-inbox';
        } else if (dbPath.includes('quarantine')) {
            provenanceDir = '@quarantine';
        }

        // Resolve source path — files live in inbox or external-inbox based on prefix
        let sourcePath = dbPath;
        if (!path.isAbsolute(sourcePath)) {
            const sourceDir = dbPath.startsWith('external-inbox') ? PATHS.EXTERNAL_INBOX_DIR : PATHS.INBOX_DIR;
            sourcePath = path.join(sourceDir, sourcePath);
        }

        if (!fs.existsSync(sourcePath)) {
            skippedCount++;
            continue;
        }

        // Copy to mirror
        const relativePath = getRelativePath(dbPath);
        const mirrorPath = path.join(MIRRORED_BRAIN_PATH, provenanceDir, relativePath);
        await copyFile(sourcePath, mirrorPath);
        fileCount++;
    }

    console.log(`🪞 Mirror Protocol: Complete. ${fileCount} files mirrored, ${skippedCount} skipped.`);
}

/**
 * Write a single file's content directly to mirrored_brain/.
 * Called by watchdog after atomization.
 */
export async function writeMirroredFile(
    relativePath: string,
    content: string,
    provenance: 'internal' | 'external' | 'quarantine' = 'internal',
): Promise<void> {
    console.log(`[MirrorWrite] Starting write for: ${relativePath}`);
    console.log(`[MirrorWrite] Content length: ${content?.length || 0} chars`);
    console.log(`[MirrorWrite] Provenance: ${provenance}`);
    console.log(`[MirrorWrite] MIRRORED_BRAIN_PATH: ${MIRRORED_BRAIN_PATH}`);

    if (!fs.existsSync(MIRRORED_BRAIN_PATH)) {
        console.log('[MirrorWrite] Creating mirrored_brain directory...');
        fs.mkdirSync(MIRRORED_BRAIN_PATH, { recursive: true });
        console.log('[MirrorWrite] ✓ Directory created');
    }
    const mirrorPath = getMirrorPath(relativePath, provenance);
    console.log(`[MirrorWrite] Target path: ${mirrorPath}`);

    try {
        await writeFile(mirrorPath, content);
        console.log(`[MirrorWrite] ✓ SUCCESS: Written ${content?.length || 0} chars to ${mirrorPath}`);
    } catch (error: any) {
        console.error(`[MirrorWrite] ✗ FAILED: ${error.message}`);
        throw error;
    }
}

/**
 * Get relative path from inbox roots
 */
function getRelativePath(absolutePath: string): string {
    if (!absolutePath) return 'unknown_file';

    const inboxDir = PATHS.INBOX_DIR;
    const externalDir = PATHS.EXTERNAL_INBOX_DIR;

    if (absolutePath.startsWith(inboxDir)) {
        return path.relative(inboxDir, absolutePath);
    }
    if (absolutePath.startsWith(externalDir)) {
        return path.relative(externalDir, absolutePath);
    }

    // Handle pre-relative paths (e.g. from DB)
    if (absolutePath.startsWith('inbox/') || absolutePath.startsWith('inbox\\')) {
        return absolutePath.substring(6); // remove 'inbox/'
    }
    if (absolutePath.startsWith('external-inbox/') || absolutePath.startsWith('external-inbox\\')) {
        return absolutePath.substring(15); // remove 'external-inbox/'
    }

    // Fallback: use filename only
    return path.basename(absolutePath);
}

/**
 * Copy a file to mirror location
 */
async function copyFile(source: string, dest: string): Promise<void> {
    try {
        const destDir = path.dirname(dest);
        if (!fs.existsSync(destDir)) {
            fs.mkdirSync(destDir, { recursive: true });
        }
        fs.copyFileSync(source, dest);
    } catch (e: any) {
        console.warn(`🪞 Mirror: Failed to copy ${source}: ${e.message}`);
    }
}

/**
 * Write content to a file
 */
async function writeFile(filePath: string, content: string): Promise<void> {
    try {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(filePath, content, 'utf-8');
    } catch (e: any) {
        console.warn(`🪞 Mirror: Failed to write ${filePath}: ${e.message}`);
    }
}

/**
 * Get the mirrored path for a source file
 * Used by context inflator to read from mirror instead of DB
 */
export function getMirrorPath(sourcePath: string, provenance: string = 'internal'): string {
    const provenanceDir = provenance === 'external' ? '@external-inbox' :
        provenance === 'quarantine' ? '@quarantine' : '@inbox';
    const relativePath = getRelativePath(sourcePath);
    return path.join(MIRRORED_BRAIN_PATH, provenanceDir, relativePath);
}
