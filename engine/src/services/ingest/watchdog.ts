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

/**
 * Fast path filter — reject directories that contain no knowledge content.
 * Prevents wasted I/O on session logs, build artifacts, etc.
 */
const REJECT_PATH_PATTERNS = [
    /[/\\]_run_journal[/\\]/i,       // Session run journals (JSONL logs)
    /[/\\]node_modules[/\\]/i,      // Dependencies
    /[/\\]\.git[/\\]/i,             // Git internals
    /[/\\]dist[/\\]/i,              // Build outputs
    /[/\\]__pycache__[/\\]/i,       // Python cache
    /[/\\]\.next[/\\]/i,            // Next.js build
    /[/\\]build[/\\]/i,             // Generic build output
];

function shouldRejectPath(filePath: string): boolean {
    for (const pattern of REJECT_PATH_PATTERNS) {
        if (pattern.test(filePath)) return true;
    }
    return false;
}

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

    // chokidar v3 tests `ignored` against *absolute* paths. The engine's own data
    // directory (~/.anchor) contains a dot-segment, so the plain dotfile regex above
    // would match every path under it and silently disable watching of inbox /
    // external-inbox (and any extra path living inside a dot-directory). Test only
    // the segments *below* each watch root instead.
    const ignoredWatchRoots = [...pathsToUse]
        .map(p => p.replace(/\\/g, '/') + '/')
        .sort((a, b) => b.length - a.length);
    function isIgnoredWatchPath(p: string): boolean {
        const norm = p.replace(/\\/g, '/');
        for (const root of ignoredWatchRoots) {
            if (norm.startsWith(root)) {
                return IGNORE_PATTERNS.test('/' + norm.slice(root.length));
            }
        }
        return false; // Not under a known watch root — don't ignore.
    }

    watcher = chokidar.watch(pathsToUse, {
        ignored: isIgnoredWatchPath,
        persistent: true,
        ignoreInitial: pathsToUse.length > 0 && customPaths && customPaths.length > 0, // Skip initial scan for explicit paths — batch pipeline handles it
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

/**
 * Collect valid file paths from a directory tree.
 * Applies all filters (directory check, ignore patterns, path rejection).
 */
function collectFiles(baseDir: string): string[] {
    const files: string[] = [];
    try {
        const entries = fs.readdirSync(baseDir, { recursive: true }) as string[];
        for (const entry of entries) {
            const filePath = path.join(baseDir, entry);
            if (fs.statSync(filePath).isDirectory()) continue;
            if (IGNORE_PATTERNS.test(entry)) continue;
            if (shouldRejectPath(filePath)) continue;
            files.push(filePath);
        }
    } catch { /* directory may not exist */ }
    return files;
}

/**
 * Bounded-concurrency batch processor for file ingestion.
 * Processes files in parallel batches to speed up scanning while
 * keeping RSS under the 3GB RAM ceiling.
 */
async function processFilesInBatches(
    filePaths: string[],
    event: string,
    onProgress: (processed: number, ingested: number) => void,
): Promise<{ processed: number; ingested: number }> {
    const BATCH_SIZE = 1; // Serialize DB writes — PGlite corrupts under concurrent writes (fixes "Unknown authenticationOk message type" error)
    let processed = 0;
    let ingested = 0;

    for (let i = 0; i < filePaths.length; i += BATCH_SIZE) {
        const batch = filePaths.slice(i, i + BATCH_SIZE);
        const results = await Promise.allSettled(
            batch.map(async (filePath) => {
                try {
                    const result = await processFile(filePath, event);
                    return { ingested: result.ingested };
                } catch {
                    return { ingested: false };
                }
            }),
        );

        for (const r of results) {
            if (r.status === 'fulfilled' && r.value.ingested) {
                ingested++;
            }
            processed++;
        }

        onProgress(processed, ingested);

        // Yield between batches to allow GC and event loop
        await new Promise(resolve => setImmediate(resolve));
    }

    return { processed, ingested };
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
 * Per-path validation report for a watched directory — used by the enhanced
 * status/validation endpoints so operators can see at a glance which paths are
 * healthy (exist, accessible, non-empty) vs misconfigured.
 */
export interface WatchedPathReport {
    path: string;
    exists: boolean;
    accessible: boolean;
    fileCount: number;
}

/**
 * Build a detailed report of every watched path — existence, accessibility, and
 * how many files it currently holds. Used by /v1/watchdog/status and
 * /v1/watchdog/validate so operators can spot misconfigured paths without logs.
 */
export function validateWatchedPaths(): {
    active: boolean;
    inboxDir: string;
    externalInboxDir: string;
    watchedPaths: WatchedPathReport[];
} {
    const allPaths = [PATHS.INBOX_DIR, PATHS.EXTERNAL_INBOX_DIR, ...(config.WATCHER_EXTRA_PATHS || [])];

    const reports: WatchedPathReport[] = allPaths.map((p) => {
        let exists = false;
        let accessible = false;
        try {
            exists = fs.existsSync(p);
            if (exists) {
                const stat = fs.statSync(p);
                if (stat.isDirectory()) {
                    // accessSync throws on EACCES/ENOENT — the outer catch handles it.
                    fs.accessSync(p, fs.constants.R_OK | fs.constants.X_OK);
                    accessible = true;
                }
            }
        } catch { /* path unusable — report as inaccessible */ }

        let fileCount = 0;
        if (exists) {
            try {
                fileCount = collectFiles(p).length;
            } catch { /* count non-critical */ }
        }

        return { path: p, exists, accessible, fileCount };
    });

    return {
        active: watcher !== null,
        inboxDir: PATHS.INBOX_DIR,
        externalInboxDir: PATHS.EXTERNAL_INBOX_DIR,
        watchedPaths: reports,
    };
}

/**
 * Get watchdog status — enriched with per-path validation so the /status and
 * /validate endpoints can report which paths are healthy vs misconfigured.
 */
export function getWatcherStatus(): { isRunning: boolean; active: boolean; inboxDir: string; externalInboxDir: string; watchedPaths: WatchedPathReport[] } {
    return {
        ...validateWatchedPaths(),
        isRunning: watcher !== null,
    };
}

/**
 * Trigger manual ingestion scan — uses batch-concurrent processing.
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

        let totalProcessed = 0;
        let totalIngested = 0;

        // Collect files from all sources first (fast, no I/O beyond readdir)
        const inboxFiles = collectFiles(inbox);
        StructuredLogger.info(`[ManualIngest] Inbox: ${inboxFiles.length} valid files after filtering`);

        let extraPathsFiles: string[] = [];
        const extraPaths = config.WATCHER_EXTRA_PATHS || [];
        for (const ep of extraPaths) {
            if (!fs.existsSync(ep)) continue;
            const ef = collectFiles(ep);
            StructuredLogger.info(`[ManualIngest] Extra path ${ep}: ${ef.length} valid files after filtering`);
            extraPathsFiles.push(...ef);
        }

        // Process inbox + external-inbox in batches
        const inboxAndExternal = [...inboxFiles];
        if (fs.existsSync(externalInbox)) {
            inboxAndExternal.push(...collectFiles(externalInbox));
        }

        StructuredLogger.info(`[ManualIngest] Processing ${inboxAndExternal.length} inbox files via batch-concurrent pipeline`);
        
        const inboxResult = await processFilesInBatches(inboxAndExternal, 'manual', (processed, ingested) => {
            totalProcessed += processed;
            totalIngested += ingested;
        });

        // Process extra watched paths in batches
        if (extraPathsFiles.length > 0) {
            StructuredLogger.info(`[ManualIngest] Processing ${extraPathsFiles.length} extra-path files via batch-concurrent pipeline`);
            
            const extraResult = await processFilesInBatches(extraPathsFiles, 'manual', (processed, ingested) => {
                totalProcessed += processed;
                totalIngested += ingested;
            });
        }

        return {
            status: 'success',
            message: `Manual ingest complete: ${totalIngested}/${totalProcessed} files processed`,
            filesProcessed: totalProcessed,
            filesIngested: totalIngested,
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
        let buffer: Buffer | null = await fs.promises.readFile(filePath);
        if (!buffer || buffer.length === 0) return { ingested: false, reason: 'empty_file' };

        // Calculate File Hash and Relative Path using correct source directory
        const fileHash = crypto.createHash('sha256').update(buffer).digest('hex');
        const sourceDir = filePath.includes('external-inbox') ? PATHS.EXTERNAL_INBOX_DIR : PATHS.INBOX_DIR;
        const relativePath = path.relative(sourceDir, filePath);
        const content = buffer.toString('utf8');
        // Release the raw Buffer before the long atomize+ingest phase so only one full-file copy stays alive.
        buffer = null;

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
        // ISSUE-19: derive a real basename for progress messages — the previous
        // `.split(...).pop()` could yield an empty string or the full relative path,
        // which then rendered as "null"/a bare directory in status strings.
        const filename = path.basename(relativePath) || relativePath;
        
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
            
            // Reuse the already-read `content` instead of a second full-file read (bounded memory).
            const originalContent = content;
            
            // Sanitize content (reuse singleton atomizer — no per-file instantiation)
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

        // Force GC before the mirror write so transient atomize/ingest structures are reclaimed.
        if (typeof (global as any).gc === 'function') (global as any).gc();
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
