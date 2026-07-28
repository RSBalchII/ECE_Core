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
import { PROJECT_ROOT, PATHS } from '../../config/paths.js';
import { ingestAtoms } from './ingest.js';
import { config } from '../../config/index.js';
import { pathManager } from '../../utils/path-manager.js';
import { systemStatus } from '../system-status.js';
import { StructuredLogger } from '../../utils/structured-logger.js';

let watcher: chokidar.FSWatcher | null = null;
const IGNORE_PATTERNS = /(^|[\/\\])\../; // Ignore dotfiles
const IGNORE_PATHS = [
    'distilled',           // Ignore distillation outputs (prevent self-contamination)
    'distills',            // Ignore distills directory
    'synonym-ring',        // Ignore auto-generated synonym files
];

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
        StructuredLogger.info('WATCHDOG_POST_INGESTION_SYNONYMS_START', {});
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
            StructuredLogger.info('WATCHDOG_POST_INGESTION_SYNONYMS_COMPLETE', { path: synonymPath });
        } catch (error: any) {
            StructuredLogger.warn('WATCHDOG_POST_INGESTION_SYNONYMS_FAILED', { error: error.message });
        }
    }, INGESTION_DEBOUNCE_MS);
}

export async function startWatchdog(customPaths?: string[]): Promise<void> {
    if (watcher) return;

    // If custom paths provided, use them instead of inbox/external-inbox
    const pathsToUse = customPaths && customPaths.length > 0 ? customPaths : [];

    // Verify inbox and external-inbox exist (Standard 051: Ephemeral Index)
    if (pathsToUse.length === 0) {
        const inbox = PATHS.INBOX_DIR;
        const externalInbox = PATHS.EXTERNAL_INBOX_DIR;

        if (!fs.existsSync(inbox)) {
            fs.mkdirSync(inbox, { recursive: true });
            StructuredLogger.info('WATCHDOG_CREATED_INBOX', { path: inbox });
        }
        if (!fs.existsSync(externalInbox)) {
            fs.mkdirSync(externalInbox, { recursive: true });
            StructuredLogger.info('WATCHDOG_CREATED_EXTERNAL_INBOX', { path: externalInbox });
        }

        // P0 Critical Fix: Auto-enable watchdog when extra_paths is configured
        const extraPaths = config.WATCHER_EXTRA_PATHS || [];
        if (extraPaths.length > 0) {
            StructuredLogger.info('WATCHDOG_AUTO_ENABLED', { extraPathCount: extraPaths.length, paths: extraPaths });
        }

        StructuredLogger.info('WATCHDOG_STARTING', { inbox, externalInbox });

        // Validate extra paths (already logged above if configured)
        const validExtraPaths = extraPaths.filter((p: string) => {
            if (fs.existsSync(p)) return true;
            StructuredLogger.warn('WATCHDOG_EXTRA_PATH_NOT_FOUND', { path: p });
            return false;
        });

        pathsToUse.push(inbox, externalInbox, ...validExtraPaths);
    } else {
        // Custom paths provided - validate they exist
        for (const p of pathsToUse) {
            if (!fs.existsSync(p)) {
                StructuredLogger.warn('WATCHDOG_PATH_NOT_FOUND', { path: p });
            } else {
                StructuredLogger.info('WATCHDOG_WATCHING_CUSTOM_PATH', { path: p });
            }
        }
    }

    watcher = chokidar.watch(pathsToUse, {
        ignored: IGNORE_PATTERNS,
        persistent: true,
        ignoreInitial: false, // Force scan on start to ingest existing files
        awaitWriteFinish: {
            stabilityThreshold: config.WATCHER_STABILITY_THRESHOLD_MS,
            pollInterval: 100,
        },
    });

    watcher.on('add', path => processFile(path, 'add'));
    watcher.on('change', path => processFile(path, 'change'));
    watcher.on('addDir', path => StructuredLogger.info('WATCHDOG_NEW_DIRECTORY', { path }));

    // CRITICAL FIX: Trigger initial ingestion of all existing files immediately when polling starts.
    // This couples ingestion with polling so no file gets missed on startup.
    triggerManualIngest().then((result) => {
        if (result.status === 'success') {
            StructuredLogger.info('WATCHDOG_INITIAL_SCAN_COMPLETE', result);
        } else {
            StructuredLogger.error('WATCHDOG_INITIAL_SCAN_FAILED', new Error(result.message));
        }
    }).catch((err) => {
        StructuredLogger.error('WATCHDOG_INITIAL_INGESTION_ERROR', err);
    });

    // .on('unlink', (path) => deleteFile(path)); // Implement delete logic later
}

// Dynamic Path Management
export function getWatchedPaths(): string[] {
    return [PATHS.INBOX_DIR, PATHS.EXTERNAL_INBOX_DIR, ...(config.WATCHER_EXTRA_PATHS || [])];
}

export async function addWatchPath(newPath: string): Promise<boolean> {
    if (!fs.existsSync(newPath)) {
        throw new Error(`Path does not exist: ${newPath}`);
    }

    // Add to watcher if it's running
    if (watcher) {
        watcher.add(newPath);
        StructuredLogger.info(`[Watchdog] Added dynamic watch path: ${newPath}`);
    } else {
        StructuredLogger.info(`[Watchdog] Path saved for later (watchdog not running);: ${newPath}`);
    }

    // Update Config (In-Memory)
    if (!config.WATCHER_EXTRA_PATHS) config.WATCHER_EXTRA_PATHS = [];
    if (!config.WATCHER_EXTRA_PATHS.includes(newPath)) {
        config.WATCHER_EXTRA_PATHS.push(newPath);

        // Persist to user_settings.json (always do this, even if watchdog isn't running)
        try {
            const settingsPath = PATHS.USER_SETTINGS;
            if (fs.existsSync(settingsPath)) {
                const settingsRequest = await fs.promises.readFile(settingsPath, 'utf8');
                const settings = JSON.parse(settingsRequest);

                if (!settings.watcher) settings.watcher = {};
                if (!settings.watcher.extra_paths) settings.watcher.extra_paths = [];

                if (!settings.watcher.extra_paths.includes(newPath)) {
                    settings.watcher.extra_paths.push(newPath);
                    await fs.promises.writeFile(settingsPath, JSON.stringify(settings, null, 4));
                    StructuredLogger.info('[Watchdog] Persisted path to user_settings.json');
                }
            }
        } catch (e: any) {
            StructuredLogger.error(`[Watchdog] Failed to persist settings: ${e.message}`);
        }
    }

    return true;
}

export async function removeWatchPath(pathToRemove: string): Promise<boolean> {
    // Remove from chokidar watcher if it exists (watchdog is running)
    if (watcher) {
        // Use a timeout to prevent unwatch from hanging indefinitely (test showed 10s+ hangs)
        const unwatchPromise = watcher.unwatch(pathToRemove);
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('unwatch timed out after 5s')), 5000);
        });
        try {
            await Promise.race([unwatchPromise, timeoutPromise]);
            StructuredLogger.info(`[Watchdog] Removed watch path: ${pathToRemove}`);
        } catch (e: any) {
            StructuredLogger.warn(`[Watchdog] unwatch timed out for ${pathToRemove} — continuing anyway: ${e.message}`);
        }
    } else {
        StructuredLogger.info(`[Watchdog] Path marked for removal (watchdog not running);: ${pathToRemove}`);
    }

    // Update Config (In-Memory)
    if (config.WATCHER_EXTRA_PATHS && config.WATCHER_EXTRA_PATHS.includes(pathToRemove)) {
        config.WATCHER_EXTRA_PATHS = config.WATCHER_EXTRA_PATHS.filter((p: string) => p !== pathToRemove);

        // Persist to user_settings.json
        try {
            const settingsPath = PATHS.USER_SETTINGS;
            if (fs.existsSync(settingsPath)) {
                const settingsRequest = await fs.promises.readFile(settingsPath, 'utf8');
                const settings = JSON.parse(settingsRequest);

                if (settings.watcher && settings.watcher.extra_paths) {
                    settings.watcher.extra_paths = settings.watcher.extra_paths.filter((p: string) => p !== pathToRemove);
                    await fs.promises.writeFile(settingsPath, JSON.stringify(settings, null, 4));
                    StructuredLogger.info('[Watchdog] Persisted path removal to user_settings.json');
                }
            }
        } catch (e: any) {
            StructuredLogger.error(`[Watchdog] Failed to persist settings removal: ${e.message}`);
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
        StructuredLogger.info('[Watchdog] Stopped watching files');
    }
}

/**
 * Get watchdog status
 */
export function getWatcherStatus(): { isRunning: boolean; watchedPaths: string[] } {
    return {
        isRunning: watcher !== null,
        watchedPaths: [PATHS.INBOX_DIR, PATHS.EXTERNAL_INBOX_DIR, ...(config.WATCHER_EXTRA_PATHS || [])],
    };
}

/**
 * Trigger manual ingestion scan
 */
export async function triggerManualIngest(): Promise<{ status: string; message: string; filesProcessed?: number; filesIngested?: number }> {
    try {
        const inbox = PATHS.INBOX_DIR;
        const externalInbox = PATHS.EXTERNAL_INBOX_DIR;

        StructuredLogger.info(`[ManualIngest] Inbox directory: ${inbox}`);
        StructuredLogger.info(`[ManualIngest] External inbox directory: ${externalInbox}`);

        if (!fs.existsSync(inbox)) {
            return { status: 'error', message: 'Inbox directory not found' };
        }

        let filesProcessed = 0;
        let filesIngested = 0;

        // Scan inbox directory
        const files = fs.readdirSync(inbox, { recursive: true }) as string[];
        StructuredLogger.info(`[ManualIngest] Found ${files.length} items in inbox`);

        for (const file of files) {
            const filePath = path.join(inbox, file);

            // Skip directories and ignored patterns
            if (fs.statSync(filePath).isDirectory()) continue;
            if (IGNORE_PATTERNS.test(file)) continue;

            filesProcessed++;
            StructuredLogger.info(`[ManualIngest] Processing file ${filesProcessed}: ${filePath}`);

            // Trigger actual ingestion by calling processFile
            try {
                const result = await processFile(filePath, 'manual');
                if (result.ingested) {
                    filesIngested++;
                    StructuredLogger.info(`[ManualIngest] Successfully ingested file ${filesIngested}: ${filePath}`);
                } else {
                    StructuredLogger.info(`[ManualIngest] Skipped file ${filePath}: ${result.reason}`);
                }
            } catch (error: any) {
                StructuredLogger.error(`[ManualIngest] Failed to process ${file}:`, error.message);
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
                    const result = await processFile(filePath, 'manual');
                    if (result.ingested) {
                        filesIngested++;
                    }
                } catch (error: any) {
                    StructuredLogger.error(`[ManualIngest] Failed to process ${file}:`, error.message);
                }
            }
        }

        // Also scan extra watched paths
        const extraPaths = config.WATCHER_EXTRA_PATHS || [];
        for (const extraPath of extraPaths) {
            if (!fs.existsSync(extraPath)) {
                StructuredLogger.info(`[ManualIngest] Extra path does not exist: ${extraPath}`);
                continue;
            }

            StructuredLogger.info(`[ManualIngest] Scanning extra path: ${extraPath}`);
            const extraFiles = fs.readdirSync(extraPath, { recursive: true }) as string[];
            StructuredLogger.info(`[ManualIngest] Found ${extraFiles.length} items in extra path`);

            for (const file of extraFiles) {
                const filePath = path.join(extraPath, file);

                if (fs.statSync(filePath).isDirectory()) continue;
                if (IGNORE_PATTERNS.test(file)) continue;

                filesProcessed++;
                StructuredLogger.info(`[ManualIngest] Processing file ${filesProcessed}: ${filePath}`);

                try {
                    const result = await processFile(filePath, 'manual');
                    if (result.ingested) {
                        filesIngested++;
                        StructuredLogger.info(`[ManualIngest] Successfully ingested file ${filesIngested}: ${filePath}`);
                    } else {
                        StructuredLogger.info(`[ManualIngest] Skipped file ${filePath}: ${result.reason}`);
                    }
                } catch (error: any) {
                    StructuredLogger.error(`[ManualIngest] Failed to process ${file}:`, error.message);
                }
            }
        }

        return {
            status: 'success',
            message: `Manual ingest complete: ${filesIngested}/${filesProcessed} files processed`,
            filesProcessed,
            filesIngested,
        };
    } catch (error: any) {
      // Return user-friendly error message instead of raw error object
      let errorMessage = `Manual ingest failed: ${error.message}`;
      
      if (error.code === 'ENOENT') {
        errorMessage += '. No files found to process.';
      } else if (error.code === 'EACCES') {
        errorMessage += '. Permission denied. Please check directory permissions.';
      }

      StructuredLogger.error('[Watchdog] Manual ingest error:', errorMessage);

      return {
            status: 'error',
            message: errorMessage,
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

async function processFile(filePath: string, event: string): Promise<{ ingested: boolean; reason?: string }> {
    StructuredLogger.info(`[Watchdog] Starting processFile: ${filePath}, event: ${event}`);

    // Accept markdown, text, YAML, CSV, JSON, JSONL, and HTML files
    if (!filePath.endsWith('.md') && !filePath.endsWith('.txt') && !filePath.endsWith('.yaml') &&
        !filePath.endsWith('.csv') && !filePath.endsWith('.json') && !filePath.endsWith('.jsonl') &&
        !filePath.endsWith('.html') && !filePath.endsWith('.htm')) {
        StructuredLogger.info(`[Watchdog] Skipping: ${filePath} - unsupported extension`);
        return { ingested: false, reason: 'unsupported_extension' };
    }
    if (filePath.includes('mirrored_brain')) {
        StructuredLogger.info(`[Watchdog] Skipping: ${filePath} - mirrored_brain path`);
        return { ingested: false, reason: 'mirrored_brain' };
    }

    StructuredLogger.info(`[Watchdog] Detected ${event}: ${filePath}`);

    // Set system status to ingesting
    systemStatus.setState('ingesting', `Processing: ${path.basename(filePath)}`);

    try {
        const buffer = await fs.promises.readFile(filePath);
        if (buffer.length === 0) return { ingested: false, reason: 'empty_file' };

        // Calculate File Hash and Relative Path using correct source directory
        const fileHash = crypto.createHash('sha256').update(buffer).digest('hex');
        const sourceDir = filePath.includes('external-inbox') ? PATHS.EXTERNAL_INBOX_DIR : PATHS.INBOX_DIR;
        const relativePath = path.relative(sourceDir, filePath);
        const content = buffer.toString('utf8');

        // 2. Check Source Table (Change Detection)
        const sourceQuery = 'SELECT path, hash FROM sources WHERE path = $1';
        const sourceResult = await db.run(sourceQuery, [relativePath]);

        // Handle potential null result
        if (!sourceResult || !sourceResult.rows) {
            StructuredLogger.info(`[Watchdog] No existing record for path: ${relativePath}`);
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
                StructuredLogger.info(`[Watchdog] File unchanged (hash match);: ${relativePath}`);
                systemStatus.setState('idle');
                return { ingested: false, reason: 'hash_match' };
            }
        }

        StructuredLogger.info(`[Watchdog] Processing Pipeline: ${relativePath}`);
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
            provenance,
        );

        // Skip ingestion if transient data was detected
        if (!atomizeResult) {
            StructuredLogger.info(`[Watchdog] ⚠️ SKIP: ${relativePath} - Transient data, skipping ingestion`);
            return { ingested: false, reason: 'transient_data' };
        }

        const { compound, molecules, atoms } = atomizeResult;

        // 5. INGEST (Atomic) with progress tracking
        const filename = relativePath.split(/[/\\]/).pop() || relativePath;
        
        await atomicIngest.ingestResult(
            compound,
            molecules,
            atoms,
            [bucket],
            (step: number, total: number, description: string) => {
                systemStatus.setProgress(step, total, `${filename}: ${description}`);
            }
        );

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
                Date.now(),
            ],
        );

        StructuredLogger.info(`[Watchdog] Sync Complete: ${relativePath}`);

        // Standard 016: Invalidate search cache after successful watchdog ingestion
        try {
            const { searchCache } = await import('../search/search.js');
            searchCache.clear();
            StructuredLogger.info('[Watchdog] ✅ Search cache invalidated after ingestion');
        } catch (e) {
            StructuredLogger.warn('[Watchdog] Could not invalidate search cache:', e as any);
        }

        // Trigger Mirror: write cleaned content from original file (Standard 051 - Pointer Only)
        // Since compound_body is removed, we read from the original file and sanitize
        StructuredLogger.info('[Watchdog] Preparing mirror write from original file...');
        StructuredLogger.info(`[Watchdog] compound exists: ${!!compound}`);
        StructuredLogger.info(`[Watchdog] provenance: ${provenance}`);

        try {
            StructuredLogger.info('[Watchdog] Importing mirror and atomizer modules...');
            const { writeMirroredFile } = await import('../mirror/mirror.js');
            const fs = await import('fs');
            
            // Read original file content
            const originalContent = fs.readFileSync(filePath, 'utf-8');
            
            // Sanitize content (same logic as atomizer)
            const { AtomizerService } = await import('./atomizer-service.js');
            const atomizer = new AtomizerService();
            const cleanContent = atomizer.sanitize(originalContent, filePath);
            
            StructuredLogger.info('[Watchdog] Writing sanitized content to mirror...');
            await writeMirroredFile(relativePath, cleanContent, provenance);
            StructuredLogger.info('[Watchdog] ✓ Mirror write completed successfully');
        } catch (e: any) {
            StructuredLogger.error(`[Watchdog] ✗ Mirror write failed: ${e.message}`, undefined, { original: String(e) });
            StructuredLogger.debug('[Watchdog] Stack trace', e);
        }

        // Trigger post-ingestion synonym generation (debounced)
        triggerPostIngestionSynonyms();

        // Reset system status to idle after ingestion completes
        if (typeof (global as any).gc === 'function') (global as any).gc();
        systemStatus.setState('idle');
        systemStatus.clearProgress();
        StructuredLogger.info('[SystemStatus] Ingestion complete, system ready for search');

        return { ingested: true };

    } catch (error: any) {
      // Return user-friendly error message instead of raw error object
      let errorMessage = `Failed to process ${filePath}: ${error.message}`;
      
      // Provide specific guidance for common errors
      if (error.code === 'ENOENT') {
        errorMessage += '. File not found.';
      } else if (error.code === 'EACCES') {
        errorMessage += '. Permission denied. Please check file permissions.';
      } else if (error.message.includes('token')) {
        errorMessage += '. Token limit exceeded - content may be too large for ingestion.';
      }

      StructuredLogger.error(`[Watchdog] ${errorMessage}`);
      systemStatus.setState('idle');
      systemStatus.clearProgress();

      return { ingested: false, reason: 'processing_error' };
    }
}""
