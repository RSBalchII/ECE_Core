
import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';
import { db } from '../../core/db.js';
import PATHS from '../../config/paths.js';

const BACKUP_DIR = PATHS.BACKUPS_DIR;
const MIRRORED_BRAIN_DIR = PATHS.MIRRORED_BRAIN_DIR;

if (!fs.existsSync(BACKUP_DIR)) {
    fs.mkdirSync(BACKUP_DIR, { recursive: true });
}

/**
 * Convert JS array to PostgreSQL array format
 * ['a','b'] => '{a,b}'
 */
function toPgArray(arr: any[]): string {
    if (!arr || !Array.isArray(arr)) return '{}';
    return '{' + arr.map(v => {
        if (v === null || v === undefined) return 'NULL';
        const str = String(v);
        if (str.includes(',') || str.includes('{') || str.includes('}') || str.includes('"')) {
            return '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    }).join(',') + '}';
}

export interface BackupStats {
    memory_count: number;   // legacy: atom count (0 for new-format backups)
    file_count: number;     // new: files archived from mirrored_brain/
    source_count: number;
    engram_count: number;
    timestamp: string;
}

/**
 * Async generator: walks a directory recursively, yielding absolute file paths.
 */
async function* walkDir(dir: string): AsyncGenerator<string> {
    const entries = await fs.promises.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            yield* walkDir(fullPath);
        } else {
            yield fullPath;
        }
    }
}

export async function createBackup(): Promise<{ filename: string; stats: BackupStats }> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `backup_${timestamp}.json`;
    const filePath = path.join(BACKUP_DIR, filename);

    console.log(`[Backup] Starting backup to ${filename}...`);

    const stream = fs.createWriteStream(filePath, { encoding: 'utf8' });

    const write = (data: string): Promise<void> => {
        return new Promise((resolve) => {
            if (!stream.write(data)) {
                stream.once('drain', resolve);
            } else {
                resolve();
            }
        });
    };

    let fileCount = 0;
    let sourceCount = 0;
    let engramCount = 0;

    try {
        await write('{\n  "timestamp": "' + new Date().toISOString() + '",\n');
        await write('  "version": "2",\n');

        // 1. Stream mirrored_brain/ files (cleaned content)
        await write('  "files": [\n');
        let firstFile = true;

        if (fs.existsSync(MIRRORED_BRAIN_DIR)) {
            for await (const absPath of walkDir(MIRRORED_BRAIN_DIR)) {
                try {
                    const content = await fs.promises.readFile(absPath, 'utf-8');
                    const relativePath = path.relative(MIRRORED_BRAIN_DIR, absPath)
                        .replace(/\\/g, '/'); // normalize to forward slashes
                    if (!firstFile) await write(',\n');
                    await write('    ' + JSON.stringify({ path: relativePath, content }));
                    firstFile = false;
                    fileCount++;
                } catch (e: any) {
                    console.warn(`[Backup] Skipping unreadable file: ${absPath}: ${e.message}`);
                }
            }
        } else {
            console.warn('[Backup] mirrored_brain/ does not exist — files section will be empty.');
        }
        await write('\n  ],\n');

        // 2. Stream sources metadata
        await write('  "source": [\n');
        const sourceResult = await db.run('SELECT path, hash, total_atoms, last_ingest FROM sources');
        if (sourceResult.rows) {
            for (let i = 0; i < sourceResult.rows.length; i++) {
                if (i > 0) await write(',\n');
                await write('    ' + JSON.stringify(sourceResult.rows[i]));
                sourceCount++;
            }
        }
        await write('\n  ],\n');

        // 3. Stream engrams
        await write('  "engrams": [\n');
        const engramResult = await db.run('SELECT key, value FROM engrams');
        if (engramResult.rows) {
            for (let i = 0; i < engramResult.rows.length; i++) {
                if (i > 0) await write(',\n');
                await write('    ' + JSON.stringify(engramResult.rows[i]));
                engramCount++;
            }
        }
        await write('\n  ]\n}');

    } catch (e: any) {
        console.error('[Backup] Streaming failed:', e);
        stream.end();
        throw e;
    }

    return new Promise((resolve, reject) => {
        stream.end(() => {
            const stats: BackupStats = {
                memory_count: 0,
                file_count: fileCount,
                source_count: sourceCount,
                engram_count: engramCount,
                timestamp
            };
            console.log(`[Backup] Completed. Stats:`, stats);
            resolve({ filename, stats });
        });
        stream.on('error', reject);
    });
}

export async function listBackups(): Promise<string[]> {
    if (!fs.existsSync(BACKUP_DIR)) return [];
    const files = await fs.promises.readdir(BACKUP_DIR);
    return files.filter(f => f.endsWith('.json')).sort().reverse(); // Newest first
}

export async function restoreBackup(filename: string): Promise<BackupStats> {
    const filePath = path.join(BACKUP_DIR, filename);
    if (!fs.existsSync(filePath)) {
        throw new Error(`Backup file not found: ${filename}`);
    }

    const fileSize = fs.statSync(filePath).size;
    const fileSizeMB = (fileSize / 1024 / 1024).toFixed(2);
    const startTime = Date.now();

    console.log(`[Backup] 🔄 Starting restore: ${filename} (${fileSizeMB} MB)`);

    const fileStream = fs.createReadStream(filePath);
    const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });

    type Section = 'none' | 'files' | 'memory' | 'source' | 'engrams';
    let currentSection: Section = 'none';
    let batch: any[] = [];
    const BATCH_SIZE = 1000;
    let lineCount = 0;
    let lastLogTime = Date.now();

    const stats: BackupStats = {
        memory_count: 0,
        file_count: 0,
        source_count: 0,
        engram_count: 0,
        timestamp: new Date().toISOString()
    };

    // Ensure mirrored_brain/ exists for new-format restores
    if (!fs.existsSync(MIRRORED_BRAIN_DIR)) {
        fs.mkdirSync(MIRRORED_BRAIN_DIR, { recursive: true });
    }

    const flushBatch = async () => {
        if (batch.length === 0) return;

        if (currentSection === 'files') {
            // New format: write cleaned files to mirrored_brain/
            for (const row of batch) {
                if (!row.path || row.content === undefined) continue;
                const dest = path.join(MIRRORED_BRAIN_DIR, row.path);
                const destDir = path.dirname(dest);
                if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });
                try {
                    fs.writeFileSync(dest, row.content, 'utf-8');
                    stats.file_count++;
                } catch (e: any) {
                    console.warn(`[Backup] ⚠️ Failed to write ${dest}: ${e.message}`);
                }
            }
        } else if (currentSection === 'memory') {
            // Legacy format: restore atoms to DB
            const placeholders = [];
            const params: any[] = [];
            let pIdx = 1;

            for (const row of batch) {
                let embedding = row.embedding;
                if (typeof embedding === 'string') {
                    try { embedding = JSON.parse(embedding); } catch { embedding = []; }
                } else if (!Array.isArray(embedding)) { embedding = []; }

                let buckets = row.buckets;
                if (typeof buckets === 'string') {
                    try { buckets = JSON.parse(buckets); } catch { buckets = []; }
                } else if (!Array.isArray(buckets)) { buckets = []; }

                let tags = row.tags;
                if (typeof tags === 'string') {
                    try { tags = JSON.parse(tags); } catch { tags = []; }
                } else if (!Array.isArray(tags)) { tags = []; }

                placeholders.push(`($${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++})`);
                params.push(
                    row.id || '', row.timestamp || 0, row.content || '', row.source_path || '',
                    row.source_id || null, row.sequence ?? null, row.type || null, row.hash || null,
                    toPgArray(buckets), toPgArray(tags), row.epochs || null,
                    row.provenance || 'external', row.simhash || '0', toPgArray(embedding)
                );
                stats.memory_count++;
            }

            if (placeholders.length > 0) {
                await db.run(
                    `INSERT INTO atoms (id, timestamp, content, source_path, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding)
                     VALUES ${placeholders.join(', ')}
                     ON CONFLICT (id) DO UPDATE SET
                       content = EXCLUDED.content, timestamp = EXCLUDED.timestamp,
                       source_path = EXCLUDED.source_path, source_id = EXCLUDED.source_id,
                       sequence = EXCLUDED.sequence, type = EXCLUDED.type,
                       hash = EXCLUDED.hash, buckets = EXCLUDED.buckets,
                       tags = EXCLUDED.tags, epochs = EXCLUDED.epochs,
                       provenance = EXCLUDED.provenance, simhash = EXCLUDED.simhash,
                       embedding = EXCLUDED.embedding`,
                    params
                );
            }
        } else if (currentSection === 'source') {
            const placeholders = [];
            const params: any[] = [];
            let pIdx = 1;

            for (const row of batch) {
                placeholders.push(`($${pIdx++}, $${pIdx++}, $${pIdx++}, $${pIdx++})`);
                params.push(row.path || '', row.hash || '', row.total_atoms || 0, row.last_ingest || null);
                stats.source_count++;
            }

            if (placeholders.length > 0) {
                await db.run(
                    `INSERT INTO sources (path, hash, total_atoms, last_ingest)
                     VALUES ${placeholders.join(', ')}
                     ON CONFLICT (path) DO UPDATE SET
                       hash = EXCLUDED.hash, total_atoms = EXCLUDED.total_atoms,
                       last_ingest = EXCLUDED.last_ingest`,
                    params
                );
            }
        } else if (currentSection === 'engrams') {
            const placeholders = [];
            const params: any[] = [];
            let pIdx = 1;

            for (const row of batch) {
                placeholders.push(`($${pIdx++}, $${pIdx++})`);
                params.push(row.key, row.value);
                stats.engram_count++;
            }

            if (placeholders.length > 0) {
                await db.run(
                    `INSERT INTO engrams (key, value) VALUES ${placeholders.join(', ')}
                     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`,
                    params
                );
            }
        }

        batch = [];
    };

    for await (const line of rl) {
        const trimmed = line.trim();

        // Section detection
        if (trimmed.startsWith('"files": ['))   { currentSection = 'files';   continue; }
        if (trimmed.startsWith('"memory": ['))  { currentSection = 'memory';  continue; }
        if (trimmed.startsWith('"source": ['))  { currentSection = 'source';  continue; }
        if (trimmed.startsWith('"engrams": [')) { currentSection = 'engrams'; continue; }

        if (trimmed.startsWith('],')) {
            await flushBatch();
            currentSection = 'none';
            continue;
        }

        if (currentSection !== 'none') {
            lineCount++;

            const now = Date.now();
            if (lineCount % 10000 === 0 || (now - lastLogTime) > 10000) {
                console.log(`[Backup] 📊 Progress: ${lineCount} lines, ${stats.file_count} files, ${stats.memory_count} atoms`);
                lastLogTime = now;
            }

            const jsonStr = trimmed.endsWith(',') ? trimmed.slice(0, -1) : trimmed;
            try {
                if (jsonStr.startsWith('{') || jsonStr.startsWith('[')) {
                    batch.push(JSON.parse(jsonStr));
                    if (batch.length >= BATCH_SIZE) await flushBatch();
                }
            } catch { /* skip malformed lines */ }
        }
    }

    await flushBatch();

    // For new-format backups: copy mirrored_brain/ back to inbox/ so DB can rebuild
    if (stats.file_count > 0) {
        console.log(`[Backup] 📁 Rebuilding inbox/external-inbox from mirrored_brain/...`);
        await rebuildInboxFromMirror();
    } else {
        // Legacy fallback: rebuild from atom content
        console.log(`[Backup] 📁 Legacy restore: rebuilding filesystem from sources...`);
        await rebuildFilesystemFromSources();
    }

    const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);
    const itemsPerSec = Math.round((stats.file_count || stats.memory_count) / parseFloat(totalTime));

    console.log(`[Backup] ✅ Restore Completed in ${totalTime}s (${itemsPerSec} items/sec)`);
    console.log(`[Backup] 📊 Stats:`, stats);
    return stats;
}

/**
 * Rebuild inbox/ and external-inbox/ by copying from mirrored_brain/.
 * @inbox/ → inbox/  |  @external-inbox/ → external-inbox/
 * Allows watchdog + ingest pipeline to rebuild the DB on next startup.
 */
async function rebuildInboxFromMirror(): Promise<void> {
    const { INBOX_DIR, EXTERNAL_INBOX_DIR } = PATHS;

    if (!fs.existsSync(MIRRORED_BRAIN_DIR)) {
        console.warn('[Backup] mirrored_brain/ not found — skipping inbox rebuild.');
        return;
    }

    const provDirs: Array<{ from: string; to: string }> = [
        { from: path.join(MIRRORED_BRAIN_DIR, '@inbox'), to: INBOX_DIR },
        { from: path.join(MIRRORED_BRAIN_DIR, '@external-inbox'), to: EXTERNAL_INBOX_DIR },
    ];

    for (const { from, to } of provDirs) {
        if (!fs.existsSync(from)) continue;
        if (!fs.existsSync(to)) fs.mkdirSync(to, { recursive: true });

        // Recursively copy from mirror provenance dir to inbox dir
        for await (const absPath of walkDir(from)) {
            const rel = path.relative(from, absPath);
            const dest = path.join(to, rel);
            const destDir = path.dirname(dest);
            if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });
            try { fs.copyFileSync(absPath, dest); } catch (e: any) {
                console.warn(`[Backup] ⚠️ Failed to copy ${absPath}: ${e.message}`);
            }
        }
    }

    console.log('[Backup] ✅ inbox/ and external-inbox/ rebuilt from mirrored_brain/');
}

/**
 * Rebuild inbox and external-inbox from database sources
 * Mirror Protocol will populate mirrored_brain/ on next startup
 */
async function rebuildFilesystemFromSources(): Promise<void> {
    const { INBOX_DIR, EXTERNAL_INBOX_DIR } = PATHS;
    
    // Ensure directories exist
    if (!fs.existsSync(INBOX_DIR)) fs.mkdirSync(INBOX_DIR, { recursive: true });
    if (!fs.existsSync(EXTERNAL_INBOX_DIR)) fs.mkdirSync(EXTERNAL_INBOX_DIR, { recursive: true });

    // Get all sources from database
    const sourcesResult = await db.run('SELECT path, hash, total_atoms FROM sources');
    const sources = sourcesResult.rows || [];

    console.log(`[Backup] 📦 Rebuilding ${sources.length} source files in inbox/external-inbox...`);

    let inboxCount = 0;
    let externalCount = 0;
    let fileCount = 0;
    let emptyCount = 0;

    for (const source of sources) {
        const sourcePath = source.path;
        if (!sourcePath) continue;

        // Determine target directory
        let targetDir = INBOX_DIR;
        let isExternal = false;
        
        if (sourcePath.includes('external-inbox') || sourcePath.includes('web_scrape') || sourcePath.includes('news_agent')) {
            targetDir = EXTERNAL_INBOX_DIR;
            isExternal = true;
            externalCount++;
        } else {
            inboxCount++;
        }

        // Get relative path
        let relativePath = sourcePath
            .replace(/^inbox[\\/]/, '')
            .replace(/^external-inbox[\\/]/, '');

        const targetPath = path.join(targetDir, relativePath);
        const targetDirPath = path.dirname(targetPath);

        // Create directory structure
        if (!fs.existsSync(targetDirPath)) {
            fs.mkdirSync(targetDirPath, { recursive: true });
        }

        // Get atoms for this source and aggregate content
        const atomsResult = await db.run(
            `SELECT content, sequence, timestamp FROM atoms WHERE source_path = $1 ORDER BY sequence NULLS LAST, timestamp`,
            [sourcePath]
        );

        console.log(`[Backup] 🔍 Source: ${sourcePath} | Atoms found: ${atomsResult.rows?.length || 0}`);

        if (atomsResult.rows && atomsResult.rows.length > 0) {
            const content = atomsResult.rows.map((r: any) => r.content).join('\n');
            
            try {
                fs.writeFileSync(targetPath, content, 'utf-8');
                fileCount++;
                console.log(`[Backup] 📄 Restored: ${targetPath} (${content.length} chars)`);
            } catch (e: any) {
                console.warn(`[Backup] ⚠️ Failed to write ${targetPath}: ${e.message}`);
            }
        } else {
            emptyCount++;
            console.warn(`[Backup] ⚠️ No atoms found for source: ${sourcePath}`);
        }
    }

    console.log(`[Backup] ✅ Filesystem rebuild complete: ${inboxCount} inbox, ${externalCount} external, ${fileCount} files written, ${emptyCount} empty sources`);
    console.log(`[Backup] ℹ️ mirrored_brain/ will be populated on next startup by Mirror Protocol (Standard 110)`);
}
