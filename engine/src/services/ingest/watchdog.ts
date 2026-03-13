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
import { NOTEBOOK_DIR, PROJECT_ROOT } from '../../config/paths.js';
import { ingestAtoms } from './ingest.js';
import { config } from '../../config/index.js';
import { pathManager } from '../../utils/path-manager.js';
import { systemStatus } from '../system-status.js';

let watcher: chokidar.FSWatcher | null = null;
const IGNORE_PATTERNS = /(^|[\/\\])\../; // Ignore dotfiles

// Post-ingestion synonym generation
let ingestionTimeout: NodeJS.Timeout | null = null;
const INGESTION_DEBOUNCE_MS = 30000; // Wait 30 seconds after last ingestion

async function triggerPostIngestionSynonyms() {
    // Clear any pending timeout
    if (ingestionTimeout) {
        clearTimeout(ingestionTimeout);
    }

    // Set new timeout to generate synonyms after ingestion stops
    ingestionTimeout = setTimeout(async () => {
        console.log('[Watchdog] Post-ingestion synonym generation starting...');
        try {
            const { AutoSynonymGenerator } = await import('../synonyms/auto-synonym-generator.js');
            const generator = new AutoSynonymGenerator();
            const synonyms = await generator.generateSynonymRings();
            const synonymDir = path.join(pathManager.getDatabasePath(), 'synonyms');
            if (!fs.existsSync(synonymDir)) {
                fs.mkdirSync(synonymDir, { recursive: true });
            }
            const synonymPath = path.join(synonymDir, 'synonym-ring-auto.json');
            await generator.saveSynonymRings(synonyms, synonymPath);
            console.log(`[Watchdog] ✅ Post-ingestion synonym rings saved to ${synonymPath}`);
        } catch (error: any) {
            console.warn('[Watchdog] Post-ingestion synonym generation failed:', error.message);
        }
    }, INGESTION_DEBOUNCE_MS);
}

export async function startWatchdog() {
    if (watcher) return;

    if (!fs.existsSync(NOTEBOOK_DIR)) {
        console.warn(`[Watchdog] Notebook directory not found: ${NOTEBOOK_DIR}. Skipping watch.`);
        return;
    }

    const inbox = path.join(PROJECT_ROOT, 'inbox');
    const externalInbox = path.join(PROJECT_ROOT, 'external-inbox');

    // Auto-create inbox directories if missing (Standard 051: Ephemeral Index)
    // These are gitignored and should be created on-demand
    if (!fs.existsSync(inbox)) {
        fs.mkdirSync(inbox, { recursive: true });
        console.log(`[Watchdog] Created inbox directory: ${inbox}`);
    }
    if (!fs.existsSync(externalInbox)) {
        fs.mkdirSync(externalInbox, { recursive: true });
        console.log(`[Watchdog] Created external-inbox directory: ${externalInbox}`);
    }

    console.log(`[Watchdog] Starting watch on: ${inbox} and ${externalInbox}`);

    // Load extra paths from config
    const extraPaths = config.WATCHER_EXTRA_PATHS || [];
    const validExtraPaths = extraPaths.filter((p: string) => {
        if (fs.existsSync(p)) return true;
        console.warn(`[Watchdog] Extra path not found: ${p}`);
        return false;
    });

    const pathsToWatch = [inbox, externalInbox, ...validExtraPaths];

    watcher = chokidar.watch(pathsToWatch, {
        ignored: IGNORE_PATTERNS,
        persistent: true,
        ignoreInitial: false, // Force scan on start to ingest existing files
        awaitWriteFinish: {
            stabilityThreshold: config.WATCHER_STABILITY_THRESHOLD_MS,
            pollInterval: 100
        }
    });

    watcher
        .on('add', (path) => processFile(path, 'add'))
        .on('change', (path) => processFile(path, 'change'))
        .on('addDir', (path) => console.log(`[Watchdog] Detected new directory: ${path}`));

    // .on('unlink', (path) => deleteFile(path)); // Implement delete logic later
}

// Dynamic Path Management
export function getWatchedPaths(): string[] {
    if (!watcher) return [];
    // chokidar.getWatched() returns an object where keys are paths
    // But it returns all subdirectories too. We mainly want the roots we added.
    // For simplicity, we can return the configured roots + static roots.

    // Better approach: Return the paths explicitly tracked
    const inbox = path.join(PROJECT_ROOT, 'inbox');
    const externalInbox = path.join(PROJECT_ROOT, 'external-inbox');
    const extraPaths = config.WATCHER_EXTRA_PATHS || [];

    return [inbox, externalInbox, ...extraPaths];
}

export async function addWatchPath(newPath: string): Promise<boolean> {
    if (!fs.existsSync(newPath)) {
        throw new Error(`Path does not exist: ${newPath}`);
    }

    // Add to watcher if it's running
    if (watcher) {
        watcher.add(newPath);
        console.log(`[Watchdog] Added dynamic watch path: ${newPath}`);
    } else {
        console.log(`[Watchdog] Path saved for later (watchdog not running): ${newPath}`);
    }

    // Update Config (In-Memory)
    if (!config.WATCHER_EXTRA_PATHS) config.WATCHER_EXTRA_PATHS = [];
    if (!config.WATCHER_EXTRA_PATHS.includes(newPath)) {
        config.WATCHER_EXTRA_PATHS.push(newPath);

        // Persist to user_settings.json (always do this, even if watchdog isn't running)
        try {
            const settingsPath = path.join(process.cwd(), 'user_settings.json');
            if (fs.existsSync(settingsPath)) {
                const settingsRequest = await fs.promises.readFile(settingsPath, 'utf8');
                const settings = JSON.parse(settingsRequest);

                if (!settings.watcher) settings.watcher = {};
                if (!settings.watcher.extra_paths) settings.watcher.extra_paths = [];

                if (!settings.watcher.extra_paths.includes(newPath)) {
                    settings.watcher.extra_paths.push(newPath);
                    await fs.promises.writeFile(settingsPath, JSON.stringify(settings, null, 4));
                    console.log(`[Watchdog] Persisted path to user_settings.json`);
                }
            }
        } catch (e: any) {
            console.error(`[Watchdog] Failed to persist settings: ${e.message}`);
        }
    }

    return true;
}

export async function removeWatchPath(pathToRemove: string): Promise<boolean> {
    // Remove from chokidar watcher if it exists (watchdog is running)
    if (watcher) {
        watcher.unwatch(pathToRemove);
        console.log(`[Watchdog] Removed watch path: ${pathToRemove}`);
    } else {
        console.log(`[Watchdog] Path marked for removal (watchdog not running): ${pathToRemove}`);
    }

    // Update Config (In-Memory)
    if (config.WATCHER_EXTRA_PATHS && config.WATCHER_EXTRA_PATHS.includes(pathToRemove)) {
        config.WATCHER_EXTRA_PATHS = config.WATCHER_EXTRA_PATHS.filter((p: string) => p !== pathToRemove);

        // Persist to user_settings.json
        try {
            const settingsPath = path.join(process.cwd(), 'user_settings.json');
            if (fs.existsSync(settingsPath)) {
                const settingsRequest = await fs.promises.readFile(settingsPath, 'utf8');
                const settings = JSON.parse(settingsRequest);

                if (settings.watcher && settings.watcher.extra_paths) {
                    settings.watcher.extra_paths = settings.watcher.extra_paths.filter((p: string) => p !== pathToRemove);
                    await fs.promises.writeFile(settingsPath, JSON.stringify(settings, null, 4));
                    console.log(`[Watchdog] Persisted path removal to user_settings.json`);
                }
            }
        } catch (e: any) {
            console.error(`[Watchdog] Failed to persist settings removal: ${e.message}`);
        }
    }

    return true;
}

/**
 * Stop the watchdog service
 */
export async function stopWatchdog(): Promise<void> {
    if (watcher) {
        await watcher.close();
        watcher = null;
        console.log('[Watchdog] Stopped watching files');
    }
}

/**
 * Get watchdog status
 */
export function getWatcherStatus(): { isRunning: boolean; watchedPaths: string[] } {
    const inbox = path.join(PROJECT_ROOT, 'inbox');
    const externalInbox = path.join(PROJECT_ROOT, 'external-inbox');
    const extraPaths = config.WATCHER_EXTRA_PATHS || [];
    
    return {
        isRunning: watcher !== null,
        watchedPaths: [inbox, externalInbox, ...extraPaths]
    };
}

/**
 * Trigger manual ingestion scan
 */
export async function triggerManualIngest(): Promise<{ status: string; message: string; filesProcessed?: number; filesIngested?: number }> {
    try {
        const inbox = path.join(PROJECT_ROOT, 'inbox');
        const externalInbox = path.join(PROJECT_ROOT, 'external-inbox');

        if (!fs.existsSync(inbox)) {
            return { status: 'error', message: 'Inbox directory not found' };
        }

        let filesProcessed = 0;
        let filesIngested = 0;

        // Scan inbox directory
        const files = fs.readdirSync(inbox, { recursive: true }) as string[];
        
        for (const file of files) {
            const filePath = path.join(inbox, file);
            
            // Skip directories and ignored patterns
            if (fs.statSync(filePath).isDirectory()) continue;
            if (IGNORE_PATTERNS.test(file)) continue;
            
            filesProcessed++;
            
            // Trigger actual ingestion by calling processFile
            try {
                await processFile(filePath, 'manual');
                filesIngested++;
            } catch (error: any) {
                console.error(`[ManualIngest] Failed to process ${file}:`, error.message);
            }
        }

        // Also scan external-inbox if it exists
        if (fs.existsSync(externalInbox)) {
            const externalFiles = fs.readdirSync(externalInbox, { recursive: true }) as string[];
            
            for (const file of externalFiles) {
                const filePath = path.join(externalInbox, file);
                
                if (fs.statSync(filePath).isDirectory()) continue;
                if (IGNORE_PATTERNS.test(file)) continue;
                
                filesProcessed++;
                
                try {
                    await processFile(filePath, 'manual');
                    filesIngested++;
                } catch (error: any) {
                    console.error(`[ManualIngest] Failed to process ${file}:`, error.message);
                }
            }
        }

        return {
            status: 'success',
            message: `Manual ingest complete: ${filesIngested}/${filesProcessed} files processed`,
            filesProcessed,
            filesIngested
        };
    } catch (error: any) {
        return {
            status: 'error',
            message: `Manual ingest failed: ${error.message}`
        };
    }
}

// Revert to AtomizerService for performance
// import { SemanticIngestionService } from '../semantic/semantic-ingestion-service.js';
import { AtomizerService } from './atomizer-service.js';
import { AtomicIngestService } from './ingest-atomic.js';
// import { ingestAtoms } from './ingest.js'; // Already imported at top of file

// Singleton Services
// const semanticIngest = new SemanticIngestionService();
const atomizer = new AtomizerService();
const atomicIngest = new AtomicIngestService();

async function processFile(filePath: string, event: string) {
    // Accept markdown, text, YAML, CSV, JSON, JSONL, and HTML files
    if (!filePath.endsWith('.md') && !filePath.endsWith('.txt') && !filePath.endsWith('.yaml') &&
        !filePath.endsWith('.csv') && !filePath.endsWith('.json') && !filePath.endsWith('.jsonl') &&
        !filePath.endsWith('.html') && !filePath.endsWith('.htm')) return;
    if (filePath.includes('mirrored_brain')) return;

    console.log(`[Watchdog] Detected ${event}: ${filePath}`);

    // Set system status to ingesting
    systemStatus.setState('ingesting', `Processing: ${path.basename(filePath)}`);

    try {
        const buffer = await fs.promises.readFile(filePath);
        if (buffer.length === 0) return;

        // 1. Calculate File Hash (Raw)
        const fileHash = crypto.createHash('sha256').update(buffer).digest('hex');
        const relativePath = path.relative(NOTEBOOK_DIR, filePath);
        const content = buffer.toString('utf8');

        // 2. Check Source Table (Change Detection)
        const sourceQuery = `SELECT path, hash FROM sources WHERE path = $1`;
        const sourceResult = await db.run(sourceQuery, [relativePath]);

        // Handle potential null result
        if (!sourceResult || !sourceResult.rows) {
            console.log(`[Watchdog] No existing record for path: ${relativePath}`);
        }

        if (sourceResult && sourceResult.rows && sourceResult.rows.length > 0) {
            const row = sourceResult.rows[0];
            // Handle both array and object formats that PGlite might return
            let existingHash;
            if (Array.isArray(row)) {
                // Row is in array format [path, hash]
                existingHash = row[1];
            } else {
                // Row is in object format {path, hash}
                existingHash = row.hash;
            }
            if (existingHash === fileHash) {
                console.log(`[Watchdog] File unchanged (hash match): ${relativePath}`);
                systemStatus.setState('idle');
                return;
            }
        }

        console.log(`[Watchdog] Processing Pipeline: ${relativePath}`);
        systemStatus.setProgress(0, 100, 'Starting ingestion...');

        // 3. DETERMINE METADATA
        // Determine buckets
        const parts = relativePath.split(path.sep);
        let bucket = 'notebook';

        // logic: if inside a root folder (inbox/external-inbox) and has a subfolder, use subfolder as bucket
        // otherwise use the root folder
        if (parts.length >= 2) {
            const root = parts[0];
            if ((root === 'inbox' || root === 'external-inbox') && parts.length > 2) {
                bucket = parts[1];
            } else {
                bucket = root;
            }
        }

        // Determine type (auto-detect HTML for cleaning)
        const ext = path.extname(filePath).replace('.', '');
        let type = ext || 'text';

        // Auto-detect HTML content for cleaning pipeline
        if (ext === 'html' || ext === 'htm') {
            type = 'web_page';  // Triggers full HTML cleaning
        }

        // Determine Provenance
        let provenance: 'internal' | 'external' = 'internal';
        if (relativePath.includes('external-inbox') || relativePath.includes('web_scrape')) {
            provenance = 'external';
        }

        // 4. ATOMIZE (Legacy Pipeline)
        // This is the fast, regex-based splitter that respects token limits and semantics without heavy NLP
        const atomizeResult = await atomizer.atomize(
            content,
            relativePath,
            provenance
        );

        // Skip ingestion if transient data was detected
        if (!atomizeResult) {
            console.log(`[Watchdog] ⚠️ SKIP: ${relativePath} - Transient data, skipping ingestion`);
            return; // Exit early, no ingestion
        }

        const { compound, molecules, atoms } = atomizeResult;

        // 5. INGEST (Atomic)
        // Use the specialized AtomicIngestService for efficiency
        await atomicIngest.ingestResult(compound, molecules, atoms, [bucket]);

        // 6. Update Source Table
        await db.run(
            `INSERT INTO sources (path, hash, total_atoms, last_ingest)
             VALUES ($1, $2, $3, $4)
             ON CONFLICT (path) DO UPDATE SET
               hash = EXCLUDED.hash,
               total_atoms = EXCLUDED.total_atoms,
               last_ingest = EXCLUDED.last_ingest`,
            [
                relativePath,
                fileHash,
                atoms.length,
                Date.now()
            ]
        );

        console.log(`[Watchdog] Sync Complete: ${relativePath}`);

        // Trigger Mirror: write cleaned content directly (O(1) vs full rebuild)
        console.log(`[Watchdog] Preparing mirror write...`);
        console.log(`[Watchdog] compound exists: ${!!compound}`);
        console.log(`[Watchdog] compound.compound_body exists: ${!!compound?.compound_body}`);
        console.log(`[Watchdog] compound.compound_body length: ${compound?.compound_body?.length || 0}`);
        console.log(`[Watchdog] provenance: ${provenance}`);

        try {
            console.log(`[Watchdog] Importing mirror module...`);
            const { writeMirroredFile } = await import('../mirror/mirror.js');
            console.log(`[Watchdog] Mirror module imported, calling writeMirroredFile...`);
            await writeMirroredFile(relativePath, compound.compound_body, provenance);
            console.log(`[Watchdog] ✓ Mirror write completed successfully`);
        } catch (e: any) {
            console.error(`[Watchdog] ✗ Mirror write failed:`, e.message);
            console.error(`[Watchdog] Stack trace:`, e.stack);
        }

        // Trigger post-ingestion synonym generation (debounced)
        triggerPostIngestionSynonyms();

        // Reset system status to idle after ingestion completes
        if (typeof (global as any).gc === 'function') (global as any).gc();
        systemStatus.setState('idle');
        systemStatus.clearProgress();
        console.log(`[SystemStatus] Ingestion complete, system ready for search`);

    } catch (error: any) {
        console.error(`[Watchdog] Error processing ${filePath}:`, error.message);
        systemStatus.setState('idle');
        systemStatus.clearProgress();
        throw error;
    }
}
