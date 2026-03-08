/**
 * Backup Restore Service - "Phoenix Protocol"
 * 
 * Restores database AND rebuilds inbox/external-inbox folder structure from backup.
 * This ensures the source of truth (filesystem) matches the backup state.
 */

import * as fs from 'fs';
import * as path from 'path';
import { db } from '../../core/db.js';
import PATHS from '../../config/paths.js';

const BACKUP_DIR = PATHS.BACKUPS_DIR;

export interface RestoreStats {
    memory_count: number;
    source_count: number;
    engram_count: number;
    files_restored: number;
    inbox_restored: number;
    external_inbox_restored: number;
    timestamp: string;
}

interface BackupSource {
    path: string;
    hash: string;
    total_atoms: number;
    last_ingest: string;
}

interface BackupAtom {
    id: string;
    timestamp: number;
    content: string;
    source_path: string;
    source_id: string | null;
    sequence: number | null;
    type: string | null;
    hash: string | null;
    buckets: string[];
    tags: string[];
    epochs: string | null;
    provenance: 'internal' | 'external' | 'system';
    simhash: string;
    embedding: number[];
}

/**
 * Phoenix Protocol: Full system restore from backup
 * - Restores database tables (atoms, sources, engrams)
 * - Rebuilds inbox/external-inbox folder structure from source_path
 * - Preserves original file content from atom content aggregation
 */
export async function restoreFromBackup(filename: string): Promise<RestoreStats> {
    const filePath = path.join(BACKUP_DIR, filename);
    if (!fs.existsSync(filePath)) {
        throw new Error(`Backup file not found: ${filename}`);
    }

    console.log(`[Phoenix] 🔄 Starting full system restore from ${filename}...`);

    const stats: RestoreStats = {
        memory_count: 0,
        source_count: 0,
        engram_count: 0,
        files_restored: 0,
        inbox_restored: 0,
        external_inbox_restored: 0,
        timestamp: new Date().toISOString()
    };

    // Parse backup file
    const backupData = await parseBackupFile(filePath);

    // Restore sources first (for reference integrity)
    console.log(`[Phoenix] 📦 Restoring ${backupData.sources.length} sources...`);
    for (const source of backupData.sources) {
        await db.run(
            `INSERT INTO sources (path, hash, total_atoms, last_ingest)
             VALUES ($1, $2, $3, $4)
             ON CONFLICT (path) DO UPDATE SET
               hash = EXCLUDED.hash,
               total_atoms = EXCLUDED.total_atoms,
               last_ingest = EXCLUDED.last_ingest`,
            [source.path, source.hash, source.total_atoms, source.last_ingest]
        );
        stats.source_count++;
    }

    // Restore atoms
    console.log(`[Phoenix] 🧠 Restoring ${backupData.atoms.length} atoms...`);
    const BATCH_SIZE = 100;
    for (let i = 0; i < backupData.atoms.length; i += BATCH_SIZE) {
        const batch = backupData.atoms.slice(i, i + BATCH_SIZE);

        if (batch.length === 0) continue;

        const placeholders: string[] = [];
        const values: any[] = [];
        let paramIndex = 1;

        for (const atom of batch) {
            placeholders.push(`($${paramIndex}, $${paramIndex + 1}, $${paramIndex + 2}, $${paramIndex + 3}, $${paramIndex + 4}, $${paramIndex + 5}, $${paramIndex + 6}, $${paramIndex + 7}, $${paramIndex + 8}, $${paramIndex + 9}, $${paramIndex + 10}, $${paramIndex + 11}, $${paramIndex + 12}, $${paramIndex + 13})`);
            values.push(
                atom.id, atom.timestamp, atom.content, atom.source_path,
                atom.source_id, atom.sequence, atom.type, atom.hash,
                atom.buckets, atom.tags, atom.epochs, atom.provenance,
                atom.simhash, atom.embedding
            );
            paramIndex += 14;
        }

        await db.run(
            `INSERT INTO atoms (id, timestamp, content, source_path, source_id, sequence, type, hash, buckets, tags, epochs, provenance, simhash, embedding)
             VALUES ${placeholders.join(', ')}
             ON CONFLICT (id) DO UPDATE SET
               content = EXCLUDED.content,
               timestamp = EXCLUDED.timestamp,
               source_path = EXCLUDED.source_path,
               source_id = EXCLUDED.source_id,
               sequence = EXCLUDED.sequence,
               type = EXCLUDED.type,
               hash = EXCLUDED.hash,
               buckets = EXCLUDED.buckets,
               tags = EXCLUDED.tags,
               epochs = EXCLUDED.epochs,
               provenance = EXCLUDED.provenance,
               simhash = EXCLUDED.simhash,
               embedding = EXCLUDED.embedding`,
            values
        );
        stats.memory_count += batch.length;
    }

    // Restore engrams
    console.log(`[Phoenix] 🧬 Restoring ${backupData.engrams.length} engrams...`);
    for (const engram of backupData.engrams) {
        await db.run(
            `INSERT INTO engrams (key, value)
             VALUES ($1, $2)
             ON CONFLICT (key) DO UPDATE SET
               value = EXCLUDED.value`,
            [engram.key, engram.value]
        );
        stats.engram_count++;
    }

    // Rebuild inbox/external-inbox from sources
    console.log(`[Phoenix] 📁 Rebuilding inbox/external-inbox folder structure...`);
    await rebuildInboxFromSources(backupData.sources, backupData.atoms, stats);

    console.log(`[Phoenix] ✅ Restore complete!`, stats);
    return stats;
}

/**
 * Rebuild inbox and external-inbox folders from source data
 * Groups atoms by source_path and writes aggregated content to files
 */
async function rebuildInboxFromSources(
    sources: BackupSource[],
    atoms: BackupAtom[],
    stats: RestoreStats
): Promise<void> {
    const INBOX_DIR = PATHS.INBOX_DIR;
    const EXTERNAL_INBOX_DIR = PATHS.EXTERNAL_INBOX_DIR;

    // Ensure directories exist
    if (!fs.existsSync(INBOX_DIR)) {
        fs.mkdirSync(INBOX_DIR, { recursive: true });
    }
    if (!fs.existsSync(EXTERNAL_INBOX_DIR)) {
        fs.mkdirSync(EXTERNAL_INBOX_DIR, { recursive: true });
    }

    // Group atoms by source_path
    const atomsBySource = new Map<string, BackupAtom[]>();
    for (const atom of atoms) {
        if (!atom.source_path) continue;
        
        const existing = atomsBySource.get(atom.source_path) || [];
        existing.push(atom);
        atomsBySource.set(atom.source_path, existing);
    }

    // Rebuild each source file
    for (const source of sources) {
        const sourceAtoms = atomsBySource.get(source.path) || [];
        if (sourceAtoms.length === 0) continue;

        // Determine target directory based on provenance
        let targetDir = INBOX_DIR;
        const firstAtom = sourceAtoms[0];
        
        if (firstAtom.provenance === 'external' || 
            source.path.includes('external-inbox') ||
            source.path.includes('web_scrape') ||
            source.path.includes('news_agent')) {
            targetDir = EXTERNAL_INBOX_DIR;
            stats.external_inbox_restored++;
        } else {
            stats.inbox_restored++;
        }

        // Reconstruct file path
        let relativePath = source.path;
        
        // Strip inbox/external-inbox prefix if present
        if (relativePath.startsWith('inbox/') || relativePath.startsWith('inbox\\')) {
            relativePath = relativePath.substring(6);
        }
        if (relativePath.startsWith('external-inbox/') || relativePath.startsWith('external-inbox\\')) {
            relativePath = relativePath.substring(15);
        }

        const targetPath = path.join(targetDir, relativePath);
        const targetDirPath = path.dirname(targetPath);

        // Create directory structure
        if (!fs.existsSync(targetDirPath)) {
            fs.mkdirSync(targetDirPath, { recursive: true });
        }

        // Aggregate atom content into file
        // Sort atoms by sequence or timestamp for proper ordering
        sourceAtoms.sort((a, b) => {
            if (a.sequence !== null && b.sequence !== null) {
                return a.sequence - b.sequence;
            }
            return a.timestamp - b.timestamp;
        });

        // Combine content from all atoms
        const content = sourceAtoms.map(atom => atom.content).join('\n');

        try {
            fs.writeFileSync(targetPath, content, 'utf-8');
            stats.files_restored++;
            console.log(`[Phoenix] 📄 Restored: ${targetPath}`);
        } catch (error: any) {
            console.warn(`[Phoenix] ⚠️ Failed to write ${targetPath}: ${error.message}`);
        }
    }
}

/**
 * Parse backup JSON file into structured data (streaming for large files)
 * Handles multi-line JSON objects (e.g., embedding arrays)
 */
async function parseBackupFile(filePath: string): Promise<{
    atoms: BackupAtom[];
    sources: BackupSource[];
    engrams: { key: string; value: any }[];
}> {
    const atoms: BackupAtom[] = [];
    const sources: BackupSource[] = [];
    const engrams: { key: string; value: any }[] = [];

    // Read file in chunks
    const CHUNK_SIZE = 64 * 1024 * 1024; // 64MB chunks
    const fileSize = fs.statSync(filePath).size;
    const fd = fs.openSync(filePath, 'r');
    
    try {
        let position = 0;
        let buffer = '';
        let braceCount = 0;
        let inString = false;
        let escapeNext = false;
        let currentObject = '';
        let objectsParsed = 0;

        while (position < fileSize) {
            // Read next chunk
            const readSize = Math.min(CHUNK_SIZE, fileSize - position);
            const chunkBuffer = Buffer.alloc(readSize);
            fs.readSync(fd, chunkBuffer, 0, readSize, position);
            position += readSize;

            // Append to buffer
            buffer += chunkBuffer.toString('utf8');

            // Process character by character to find complete JSON objects
            let i = 0;
            while (i < buffer.length) {
                const char = buffer[i];

                // Handle escape sequences
                if (escapeNext) {
                    currentObject += char;
                    escapeNext = false;
                    i++;
                    continue;
                }

                if (char === '\\') {
                    escapeNext = true;
                    currentObject += char;
                    i++;
                    continue;
                }

                // Track string state
                if (char === '"') {
                    inString = !inString;
                    currentObject += char;
                    i++;
                    continue;
                }

                // Only track braces when not in string
                if (!inString) {
                    if (char === '{') {
                        if (braceCount === 0) {
                            currentObject = ''; // Start new object
                        }
                        braceCount++;
                        currentObject += char;
                    } else if (char === '}') {
                        currentObject += char;
                        braceCount--;

                        // Complete object found
                        if (braceCount === 0 && currentObject.trim()) {
                            try {
                                const item = JSON.parse(currentObject.trim());
                                
                                // Determine type by properties
                                if (item.id && item.content !== undefined) {
                                    atoms.push(item as BackupAtom);
                                } else if (item.path && item.hash !== undefined) {
                                    sources.push(item as BackupSource);
                                } else if (item.key && item.value !== undefined) {
                                    engrams.push(item);
                                }

                                objectsParsed++;
                                if (objectsParsed % 10000 === 0) {
                                    console.log(`[Phoenix] 📊 Parsed ${objectsParsed} items...`);
                                }
                            } catch (e) {
                                // Skip malformed objects
                                console.warn('[Phoenix] ⚠️ Failed to parse object:', e);
                            }
                            currentObject = '';
                        }
                    } else {
                        if (braceCount > 0) {
                            currentObject += char;
                        }
                    }
                } else {
                    if (braceCount > 0) {
                        currentObject += char;
                    }
                }

                i++;
            }

            // Keep only unprocessed data in buffer (when we're inside an object)
            if (braceCount > 0) {
                buffer = currentObject;
            } else {
                buffer = '';
                currentObject = '';
            }

            // Log memory usage periodically
            if (position % (512 * 1024 * 1024) === 0) {
                const memUsage = process.memoryUsage();
                console.log(`[Phoenix] 📊 Progress: ${(position / fileSize * 100).toFixed(1)}% | Heap: ${(memUsage.heapUsed / 1024 / 1024).toFixed(0)}MB`);
            }
        }

        console.log(`[Phoenix] 📊 Parse complete: ${atoms.length} atoms, ${sources.length} sources, ${engrams.length} engrams`);

    } finally {
        fs.closeSync(fd);
    }

    return { atoms, sources, engrams };
}

/**
 * Get the latest backup file
 */
export async function getLatestBackup(): Promise<string | null> {
    if (!fs.existsSync(BACKUP_DIR)) {
        return null;
    }
    
    const files = await fs.promises.readdir(BACKUP_DIR);
    const backups = files.filter(f => f.endsWith('.json')).sort().reverse();
    
    return backups.length > 0 ? backups[0] : null;
}

/**
 * Check if a backup exists and is valid (optimized for massive files up to 100GB+)
 */
export async function validateBackup(filename: string): Promise<{ 
    valid: boolean; 
    error?: string; 
    size?: number; 
    sizeFormatted?: string;
    note?: string;
}> {
    const filePath = path.join(BACKUP_DIR, filename);
    
    if (!fs.existsSync(filePath)) {
        return { valid: false, error: 'Backup file not found' };
    }

    try {
        // Get file stats without reading content
        const stats = fs.statSync(filePath);
        const fileSize = stats.size;
        
        // For massive files (>1GB), just verify file exists and has reasonable size
        if (fileSize > 1024 * 1024 * 1024) {
            return { 
                valid: true,
                size: fileSize,
                sizeFormatted: formatFileSize(fileSize),
                note: 'Large file - full validation skipped for performance'
            };
        }
        
        // For smaller files (<1GB), read first 10KB to validate structure
        const fd = fs.openSync(filePath, 'r');
        const buffer = Buffer.alloc(10240); // 10KB
        fs.readSync(fd, buffer, 0, 10240, 0);
        fs.closeSync(fd);
        
        const startContent = buffer.toString('utf8').trim();
        
        // Check if it starts with valid JSON object
        if (!startContent.startsWith('{')) {
            return { valid: false, error: 'Invalid JSON structure' };
        }
        
        // Check for required fields — accept both v1 ("memory") and v2 ("files") formats
        const hasTimestamp = startContent.includes('"timestamp"');
        const hasContent = startContent.includes('"files"') || startContent.includes('"memory"');
        
        if (!hasTimestamp || !hasContent) {
            return { valid: false, error: 'Missing required backup fields (timestamp + files/memory)' };
        }
        
        return { 
            valid: true,
            size: fileSize,
            sizeFormatted: formatFileSize(fileSize)
        };
    } catch (error: any) {
        return { valid: false, error: `Validation error: ${error.message}` };
    }
}

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}
