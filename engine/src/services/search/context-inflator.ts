import * as fs from 'fs';
import * as path from 'path';
import { db } from '../../core/db.js';
import type { SearchResult } from './search.js';
import { getMirrorPath, MIRRORED_BRAIN_PATH } from '../mirror/mirror.js';
import { PATHS } from '../../config/paths.js';
import { processWithAdaptiveConcurrency, getOptimalBatchSize } from '../../utils/adaptive-concurrency.js';
import { batchFetchCompounds } from '../../utils/db-batch.js';
import { pooledOpenFile } from '../../utils/file-handle-pool.js';

interface ContextWindow {
    compoundId: string;
    source: string;
    start: number;
    end: number;
    originalResults: SearchResult[];
}

export class ContextInflator {

    /**
     * Inflate search results into expanded Context Windows.
     *
     * Architecture: Atoms are POINTERS — the DB stores entity labels + byte coordinates.
     * Content lives ONLY in the original files on disk (mirrored). This method:
     *   1. Skips results already inflated by inflateFromAtomPositions (read from disk)
     *   2. For results with compound coordinates: resolves file path → reads from disk with radial expansion
     *   3. Returns null if file doesn't exist (NO database fallback)
     *
     * Progressive Inflation: Top results get larger radius for better budget allocation.
     *
     * The DB is a lightweight routing layer. Actual content comes from the filesystem ONLY.
     */
    static async inflate(results: SearchResult[], totalBudget?: number, radius: number = 0): Promise<SearchResult[]> {
        if (results.length === 0) return [];

        // 0. Pre-sort results by score to ensure top items get priority
        results.sort((a, b) => (b.score || 0) - (a.score || 0));

        // OPTIMIZATION: Pre-fetch all compounds in a single batch query
        // Instead of N individual queries, use 1 batch query (O(N) → O(1))
        const compoundIds = Array.from(new Set(results.map(r => r.compound_id).filter(Boolean) as string[]));
        const compoundCache = new Map<string, { path: string; provenance: string }>();

        if (compoundIds.length > 0) {
            try {
                const fetched = await batchFetchCompounds(compoundIds);
                // Merge into cache
                for (const [id, data] of fetched.entries()) {
                    compoundCache.set(id, data);
                }
            } catch (e) {
                console.warn('[ContextInflator] Batch compound fetch failed, falling back to individual queries:', e);
            }
        }

        // Dynamic radius: if caller didn't specify, scale based on budget and result count
        // Target: fill the budget evenly across results
        let baseRadius = radius;
        if (baseRadius <= 0 && totalBudget && results.length > 0) {
            const targetWindowSize = Math.floor(totalBudget / Math.min(results.length, 10));
            baseRadius = Math.max(200, Math.floor(targetWindowSize / 2));
            // Cap to prevent massive reads
            baseRadius = Math.min(baseRadius, 5000);
        }
        // Absolute minimum radius so we don't get zero-width slices
        baseRadius = Math.max(baseRadius, 200);

        // Cache: compound_id → Promise<{ filePath, provenance } | null>
        // Use promises to deduplicate concurrent requests for the same compound
        const compoundPathCache = new Map<string, Promise<{ filePath: string, provenance: string } | null>>();

        const processedResults: SearchResult[] = [];
        let inflatedFromDisk = 0;
        let skippedAlready = 0;
        let skippedNoCoords = 0;

        // Progressive inflation: allocate more budget to top results
        // Top 10% get 2x radius, next 40% get 1.5x, rest get 1x
        const topTenPercent = Math.max(1, Math.floor(results.length * 0.1));
        const nextFortyPercent = Math.floor(results.length * 0.4);

        // Process in batches to limit concurrency (file handles/DB connections)
        // Use adaptive batch size based on available memory (Standard 132)
        const BATCH_SIZE = await getOptimalBatchSize();

        for (let i = 0; i < results.length; i += BATCH_SIZE) {
            const batch = results.slice(i, i + BATCH_SIZE);
            const batchResults = await processWithAdaptiveConcurrency(batch, async (res, indexInBatch) => {
                const globalIndex = i + indexInBatch;
                // Progressive radius allocation based on rank
                let radiusMultiplier = 1.0;
                if (globalIndex < topTenPercent) {
                    radiusMultiplier = 2.0;  // Top 10% get 2x radius
                } else if (globalIndex < topTenPercent + nextFortyPercent) {
                    radiusMultiplier = 1.5;  // Next 40% get 1.5x
                }
                // Rest get 1.0x (base)

                const effectiveRadius = Math.floor(baseRadius * radiusMultiplier);

                // 1. Skip results already inflated from disk (e.g., by inflateFromAtomPositions)
                if (res.is_inflated) {
                    skippedAlready++;
                    return res;
                }

                // 2. Skip if no compound coordinates — use as-is (entity label)
                if (!res.compound_id || res.start_byte === undefined || res.end_byte === undefined) {
                    skippedNoCoords++;
                    return res;
                }

                try {
                    // 3. Inflate from DISK (mirrored file) - NO DB fallback
                    const diskContent = await this.inflateFromDisk(res, effectiveRadius, compoundCache);

                    if (diskContent !== null) {
                        inflatedFromDisk++;
                        return {
                            ...res,
                            content: `...${diskContent}...`,
                            is_inflated: true,
                        };
                    }

                    // 4. File not found — use raw result as-is (file may not exist yet)
                    console.warn(`[ContextInflator] File not found for compound ${res.compound_id}, returning uninflated result`);
                    return res;
                } catch (e) {
                    console.error(`[ContextInflator] Failed to inflate result for ${res.source}`, e);
                    return res;
                }
            });

            processedResults.push(...batchResults);
        }

        // Rate-limit this log to once per minute to reduce noise
        const now = Date.now();
        const lastLog = (global as any).__contextInflatorLastLog || 0;
        if (now - lastLog > 60000) {
            console.log(`[ContextInflator] inflate(): ${inflatedFromDisk} from disk, ${skippedAlready} already inflated, ${skippedNoCoords} no coordinates. Base Radius: ${baseRadius}`);
            (global as any).__contextInflatorLastLog = now;
        }
        
        // Debug: Log why content might be missing
        const noContentCount = processedResults.filter(r => !r.content || r.content.length === 0).length;
        if (noContentCount > 0) {
            console.log(`[ContextInflator] WARN: ${noContentCount}/${processedResults.length} results have NO content after inflation`);
            // Log first few examples
            processedResults.filter(r => !r.content || r.content.length === 0).slice(0, 3).forEach(r => {
                console.log(`[ContextInflator] Empty content example: id=${r.id}, source=${r.source}, compound_id=${r.compound_id}`);
            });
        }

        // The processedResults array might not be in original sort order because promises resolve out of order within batch
        // But since we sort results at start, we should re-sort or just assume score is king.
        processedResults.sort((a, b) => (b.score || 0) - (a.score || 0));

        return processedResults;
    }

    /**
     * Helper: Expand logical window to nearest sentence boundary
     */
    private static snapToSentenceBoundary(content: string, targetStart: number, targetEnd: number): { start: number, end: number, text: string } {
        // We look for sentence terminators: . ! ? followed by space or newline
        // effectively we are operating on a "Chunk" of text that is likely larger than the target window
        // targetStart/End are indices relative to the "content" string provided.

        // 1. Snap Start (Move backwards to find previous sentence end)
        let snappedStart = 0;
        // Search backwards from targetStart for a sentence terminator
        // We want the Start of the *current* sentence, so we look for the *end* of the *previous* sentence
        // validation: ensure we don't go back too far? Content is already a window.

        // Simple heuristic: valid sentence starts after (.!?)\s
        const preceeding = content.substring(0, targetStart);
        const matchStart = preceeding.match(/([.!?]\s|\n\s*\n)(?=[^.!?\n]*$)/);

        if (matchStart && matchStart.index !== undefined) {
            snappedStart = matchStart.index + matchStart[0].length;
        } else {
            // If no sentence end found, maybe just snap to first spaces
            const spaceMatch = preceeding.match(/\s(?=[^\s]*$)/);
            if (spaceMatch && spaceMatch.index !== undefined) {
                snappedStart = spaceMatch.index + 1;
            } else {
                snappedStart = 0; // consistent with start of string
            }
        }

        // 2. Snap End (Move forwards to find next sentence end)
        let snappedEnd = content.length;
        const succeeding = content.substring(targetEnd);
        // Look for the *first* sentence terminator
        const matchEnd = succeeding.match(/([.!?]\s|\n\s*\n)/);

        if (matchEnd && matchEnd.index !== undefined) {
            snappedEnd = targetEnd + matchEnd.index + 1; // Include the punctuation
        } else {
            // Fallback to next space
            const spaceMatch = succeeding.match(/\s/);
            if (spaceMatch && spaceMatch.index !== undefined) {
                snappedEnd = targetEnd + spaceMatch.index;
            }
        }

        return {
            start: snappedStart,
            end: snappedEnd,
            text: content.substring(snappedStart, snappedEnd).trim(),
        };
    }

    /**
     * Inflate a single result from the mirrored file on disk.
     * Returns the extracted content string, or null if the file doesn't exist.
     */
    private static async inflateFromDisk(
        res: SearchResult,
        radius: number,
        compoundCache?: Map<string, { path: string; provenance: string }>,
    ): Promise<string | null> {
        if (!res.compound_id) return null;

        // OPTIMIZATION: Use pre-fetched compound cache if available
        if (compoundCache && compoundCache.has(res.compound_id)) {
            const compound = compoundCache.get(res.compound_id)!;
            return this.inflateFromPath(res, radius, { filePath: compound.path, provenance: compound.provenance });
        }

        // If not in cache at all, do a batch fetch of the single ID
        try {
            const batchResult = await batchFetchCompounds([res.compound_id]);
            const cached = batchResult.get(res.compound_id);
            if (!cached) return null;
            return this.inflateFromPath(res, radius, { filePath: cached.path, provenance: cached.provenance });
        } catch (e) {
            console.warn(`[ContextInflator] Batch fetch failed for compound ${res.compound_id}`, e);
            return null;
        }
    }

    /**
     * Common inflation logic from a resolved path
     */
    private static async inflateFromPath(
        res: SearchResult,
        radius: number,
        pathInfo: { filePath: string; provenance: string },
    ): Promise<string | null> {
        // Resolve to absolute path: try mirrored file first, then original
        const mirrorPath = getMirrorPath(pathInfo.filePath, pathInfo.provenance);
        let absolutePath = mirrorPath;

        // Using fs.promises to avoid blocking the event loop
        let fileExists = false;
        try {
            await fs.promises.access(mirrorPath, fs.constants.F_OK);
            fileExists = true;
        } catch {
            fileExists = false;
        }

        if (!fileExists) {
             absolutePath = path.isAbsolute(pathInfo.filePath)
                ? pathInfo.filePath
                : path.join(MIRRORED_BRAIN_PATH, pathInfo.filePath);

             try {
                await fs.promises.access(absolutePath, fs.constants.F_OK);
                fileExists = true;
            } catch {
                fileExists = false;
            }
        }

        if (!fileExists) return null;

        let fd: fs.promises.FileHandle | null = null;
        try {
            const stats = await fs.promises.stat(absolutePath);
            const fileSize = stats.size;

            // Over-read by 1000 bytes on each side to find boundaries
            const lookahead = 1000;
            const rawStart = Math.max(0, (res.start_byte ?? 0) - radius - lookahead);
            const rawEnd = Math.min(fileSize, (res.end_byte ?? fileSize) + radius + lookahead);
            const chunkLength = rawEnd - rawStart;

            if (chunkLength <= 0) return null;

            const buffer = Buffer.alloc(chunkLength);
            fd = await pooledOpenFile(absolutePath, 'r');

            // fs.promises.read returns { bytesRead, buffer }
            await fd.read(buffer, 0, chunkLength, rawStart);

            const rawContent = buffer.toString('utf-8');

            // Calculate where our "Ideal" window sits within this raw buffer
            // ideal window start (relative to buffer) = (res.start - radius) - rawStart
            // But actually we just want to snap around the center roughly?
            // Let's rely on snapToSentenceBoundary relative to the *whole buffer*.
            // We want the text that *contains* the hit (res.start...res.end).

            // Relative offsets of the HIT within the buffer
            const hitStartRel = Math.max(0, (res.start_byte ?? 0) - rawStart);
            const hitEndRel = Math.min(chunkLength, (res.end_byte ?? fileSize) - rawStart);

            // Our "Target" window is the hit +/- radius
            const targetStartRel = Math.max(0, hitStartRel - radius);
            const targetEndRel = Math.min(chunkLength, hitEndRel + radius);

            // Snap!
            const snapped = this.snapToSentenceBoundary(rawContent, targetStartRel, targetEndRel);

            return snapped.text.length > 0 ? snapped.text : null;

        } catch {
            return null;
        } finally {
            if (fd) await fd.close();
        }
    }

    /**
     * Get atom locations for Elastic Context sizing
     * Returns the raw positions so we can calculate density/hits BEFORE inflating
     *
     * Phase 2C: Queries molecules directly (no compounds table JOIN).
     * Molecule fields (source_path, provenance) replace compound fields.
     */
    static async getAtomLocations(term: string, limit: number = 100, options: { buckets?: string[], provenance?: string } = {}): Promise<{ compoundId: string, byteOffset: number, filePath: string, timestamp: number, provenance: string }[]> {
        const termWithHash = term.startsWith('#') ? term : `#${term}`;
        const termWithoutHash = term.startsWith('#') ? term.slice(1) : term;

        // Step 1: Fetch unique compound metadata in a single batch query.
        // Phase 2C: Query molecules directly instead of JOINing compounds table.
        // Molecules have source_path, provenance — use those as path/provenance.
        let metaQuery = `
            SELECT DISTINCT ON (ap.compound_id) ap.compound_id, m.source_path AS path, MAX(m.timestamp) AS timestamp, m.provenance
            FROM atom_positions ap
            JOIN molecules m ON ap.compound_id = m.compound_id
            WHERE
               (LOWER(ap.atom_label) = LOWER($1)
               OR LOWER(ap.atom_label) = LOWER($2)
               OR ap.atom_label ILIKE $3)
        `;

        const metaParams: any[] = [termWithHash, termWithoutHash, `${termWithoutHash}%`];

        if (options.provenance && options.provenance !== 'all') {
            metaParams.push(options.provenance);
            metaQuery += ` AND m.provenance = $${metaParams.length}`;
        }

        if (options.buckets && options.buckets.length > 0) {
            metaParams.push(options.buckets);
            metaQuery += ` AND EXISTS (
                SELECT 1 FROM atoms a
                WHERE a.compound_id = m.compound_id
                AND EXISTS (
                    SELECT 1 FROM unnest(a.buckets) as b WHERE b = ANY($${metaParams.length})
                )
            )`;
        }

        metaQuery += ` ORDER BY ap.compound_id, m.timestamp DESC`;

        let compoundCache: Map<string, { path: string; timestamp: number; provenance: string }> = new Map();

        try {
            const metaResult = await db.run(metaQuery, metaParams);
            if (metaResult.rows && metaResult.rows.length > 0) {
                for (const row of metaResult.rows) {
                    compoundCache.set(row.compound_id as string, {
                        path: row.path as string,
                        timestamp: row.timestamp as number,
                        provenance: row.provenance as string,
                    });
                }
            }
        } catch (e) {
            console.error('[ContextInflator] Compound metadata fetch failed for getAtomLocations', e);
        }

        // Step 2: Fetch atom positions with compound_id only.
        let posQuery = `
            SELECT ap.compound_id, ap.byte_offset
            FROM atom_positions ap
            WHERE
               (LOWER(ap.atom_label) = LOWER($1)
               OR LOWER(ap.atom_label) = LOWER($2)
               OR ap.atom_label ILIKE $3)
        `;

        const posParams: any[] = [termWithHash, termWithoutHash, `${termWithoutHash}%`];

        if (options.provenance && options.provenance !== 'all') {
            // Filter atom_positions by provenance via the compound cache
            const cachedIds = Array.from(compoundCache.keys());
            if (cachedIds.length > 0) {
                posQuery += ` AND ap.compound_id = ANY($${posParams.length})`;
                posParams.push(cachedIds);
            } else {
                // No compounds matched — nothing to return
                return [];
            }
        }

        if (options.buckets && options.buckets.length > 0) {
            const cachedIds = Array.from(compoundCache.keys());
            if (cachedIds.length > 0) {
                posQuery += ` AND ap.compound_id = ANY($${posParams.length})`;
                posParams.push(cachedIds);
            } else {
                return [];
            }
        }

        posQuery += ` ORDER BY ap.byte_offset LIMIT $${posParams.length + 1}`;
        posParams.push(limit);

        try {
            const result = await db.run(posQuery, posParams);
            if (!result.rows) return [];

            // Step 3: Look up compound metadata from the pre-fetched cache.
            return result.rows.map((row: any) => {
                const cid = row.compound_id as string;
                const meta = compoundCache.get(cid);
                if (!meta) {
                    console.warn(`[ContextInflator] Compound ${cid} not found in metadata cache`);
                    return null;
                }
                return {
                    compoundId: cid,
                    byteOffset: row.byte_offset as number,
                    filePath: meta.path,
                    timestamp: meta.timestamp,
                    provenance: meta.provenance,
                };
            }).filter(Boolean) as any;
        } catch (e) {
            console.error(`[ContextInflator] Check locations failed for ${term}`, e);
            return [];
        }
    }

    /**
     * Radial Inflation from Atom Positions (Lazy Molecule Architecture)
     * Searches atom_positions for keyword occurrences and expands radially
     * 
     * @param searchTerm - The atom/keyword to search for
     * @param radius - How many bytes to expand in each direction (default 500)
     * @param maxResults - Maximum results to return
     */
    static async inflateFromAtomPositions(
        searchTerm: string,
        radius: number = 500,
        maxResults: number = 20,
        maxWindowSize: number = radius * 3, // Default cap if not provided
        options: { buckets?: string[], provenance?: string } = {},
    ): Promise<SearchResult[]> {
        const results: SearchResult[] = [];

        try {
            // Find all positions where this atom appears
            // Atoms are stored with # prefix (e.g. "#Rob") but search terms come without
            // So we search for both formats: "#Rob" and "Rob"
            const termWithHash = searchTerm.startsWith('#') ? searchTerm : `#${searchTerm}`;
            const termWithoutHash = searchTerm.startsWith('#') ? searchTerm.slice(1) : searchTerm;

            // Step 1: Query atom_positions + molecules for (compound_id, byte_offset) — no compounds table.
            let query = `
                SELECT ap.compound_id, ap.byte_offset
                FROM atom_positions ap
                WHERE (LOWER(ap.atom_label) = LOWER($1) OR LOWER(ap.atom_label) = LOWER($2))
            `;

            const params: any[] = [termWithHash, termWithoutHash];

            // Apply provenance filter via molecules table (Phase 2C: no compounds JOIN)
            if (options.provenance && options.provenance !== 'all') {
                query += ` AND ap.compound_id IN (SELECT DISTINCT compound_id FROM molecules WHERE provenance = $${params.length})`;
                params.push(options.provenance);
            }

            // Apply bucket filter via atoms table
            if (options.buckets && options.buckets.length > 0) {
                query += ` AND ap.compound_id IN (
                    SELECT a.compound_id FROM atoms a
                    WHERE a.compound_id = ap.compound_id
                    AND EXISTS (SELECT 1 FROM unnest(a.buckets) as b WHERE b = ANY($${params.length}))
                )`;
                params.push(options.buckets);
            }

            query += ` ORDER BY ap.byte_offset LIMIT $${params.length + 1}`;
            params.push(maxResults * 2);

            const positionsResult = await db.run(query, params);
            if (!positionsResult.rows || positionsResult.rows.length === 0) {
                return [];
            }

            // Step 2: Collect unique compound_ids for batch molecule fetch.
            const compoundIds = Array.from(new Set(
                positionsResult.rows.map((row: any) => row.compound_id as string),
            ));

            if (compoundIds.length === 0) {
                return [];
            }

            // Step 3: Batch-fetch molecules by compound_id (Phase 2C: include source_path/provenance from molecule).
            const moleculeQuery = `
                SELECT id, content, compound_id, start_byte, end_byte, source_path, provenance
                FROM molecules
                WHERE compound_id = ANY($1)
                ORDER BY timestamp DESC
            `;

            let moleculesByCompound = new Map<string, Array<{ id: string; content: string; start_byte: number; end_byte: number; source_path: string; molecule_provenance: string }>>();

            try {
                const molResult = await db.run(moleculeQuery, [compoundIds]);
                if (molResult.rows && molResult.rows.length > 0) {
                    for (const row of molResult.rows) {
                        const cid = row.compound_id as string;
                        if (!moleculesByCompound.has(cid)) {
                            moleculesByCompound.set(cid, []);
                        }
                        moleculesByCompound.get(cid)!.push({
                            id: row.id as string,
                            content: row.content as string,
                            start_byte: row.start_byte as number,
                            end_byte: row.end_byte as number,
                            source_path: row.source_path as string,
                            molecule_provenance: row.provenance as string,
                        });
                    }
                }
            } catch (e) {
                console.warn('[ContextInflator] Molecule batch fetch failed, falling back to file reads:', e);
            }

            // Step 4: Group atom positions by compound_id.
            const compoundPositions = new Map<string, number[]>();

            for (const row of positionsResult.rows) {
                const cid = row.compound_id as string;
                if (!compoundPositions.has(cid)) {
                    compoundPositions.set(cid, []);
                }
                compoundPositions.get(cid)!.push(row.byte_offset as number);
            }

            // Step 5: For each compound, inflate using molecule content instead of raw file reads.
            const resultsArrays = await processWithAdaptiveConcurrency(
                Array.from(compoundPositions.entries()),
                async ([compoundId, positions]) => {
                    const molecules = moleculesByCompound.get(compoundId) || [];

                    if (molecules.length === 0) {
                        // Fallback: read from disk like before
                        return this.inflateFromAtomPositionsFallback(
                            compoundId, positions, radius, maxWindowSize
                        );
                    }

                    const compoundResults: SearchResult[] = [];

                    for (const molecule of molecules) {
                        const molStart = Math.max(0, molecule.start_byte - radius);
                        const molEnd = molecule.end_byte + radius;

                        // Clean up partial words at boundaries
                        let content = molecule.content;
                        if (molStart > 0 && content.length > 0) {
                            const firstSpace = content.indexOf(' ');
                            if (firstSpace !== -1 && firstSpace < 50) {
                                content = content.substring(firstSpace + 1);
                            }
                        }
                        if (content.length > 0) {
                            const lastSpace = content.lastIndexOf(' ');
                            if (lastSpace > content.length - 50) {
                                content = content.substring(0, lastSpace);
                            }
                        }

                        if (!content || content.trim().length === 0) continue;

                        compoundResults.push({
                            id: `virtual_${compoundId}_${molecule.start_byte}_${molecule.end_byte}`,
                            content: `...${content}...`,
                            source: molecule.source_path, // use molecule's source_path (Phase 2C)
                            timestamp: Date.now() / 1000,
                            buckets: ['core'],
                            tags: [searchTerm],
                            epochs: '',
                            provenance: molecule.molecule_provenance,
                            score: 500,
                            compound_id: compoundId,
                            start_byte: molecule.start_byte,
                            end_byte: molecule.end_byte,
                            is_inflated: true,
                        });
                    }

                    return compoundResults;
                },
            );
            // Flatten results
            resultsArrays.forEach(arr => results.push(...arr));

            // Sort by score/relevance (simple approximation for now)
            results.sort((a, b) => (b.score || 0) - (a.score || 0));

            // Slice to maxResults
            if (results.length > maxResults) {
                results.length = maxResults;
            }

            console.log(`[ContextInflator] Radially inflated ${results.length} merged virtual molecules for "${searchTerm}"`);
            return results;

        } catch (e) {
            console.error('[ContextInflator] Failed to inflate from atom positions: ', e);
            return [];
        }
    }

    /**
     * Fallback: when no molecules are found, read directly from disk files.
     * Uses batch-fetched compound metadata for file path resolution.
     */
    private static async inflateFromAtomPositionsFallback(
        compoundId: string,
        positions: number[],
        radius: number,
        maxWindowSize: number,
    ): Promise<SearchResult[]> {
        // Batch-fetch compound metadata to resolve file paths
        const compoundCache = await batchFetchCompounds([compoundId]);
        const meta = compoundCache.get(compoundId);
        if (!meta) return [];

        const mirrorPath = getMirrorPath(meta.path, meta.provenance);
        let absolutePath = mirrorPath;

        if (!fs.existsSync(mirrorPath)) {
            absolutePath = path.isAbsolute(meta.path)
                ? meta.path
                : path.join(MIRRORED_BRAIN_PATH, meta.path);
        }

        if (!fs.existsSync(absolutePath)) return [];

        let fileSize = 0;
        try {
            const stats = await fs.promises.stat(absolutePath);
            fileSize = stats.size;
        } catch (e) {
            console.warn(`[ContextInflator] Failed to stat file: ${absolutePath}`);
            return [];
        }

        // Calculate raw windows for all positions using file size
        const rawWindows = positions.map(byteOffset => ({
            start: Math.max(0, byteOffset - radius),
            end: Math.min(fileSize, byteOffset + radius),
            offset: byteOffset,
        }));

        // Sort by start position for merge algorithm
        rawWindows.sort((a, b) => a.start - b.start);

        // Merge overlapping OR ADJACENT windows
        const MERGE_GAP_THRESHOLD = 500;
        const mergedWindows: { start: number; end: number; offsets: number[] }[] = [];
        for (const window of rawWindows) {
            const last = mergedWindows[mergedWindows.length - 1];
            if (last && (window.start <= last.end || (window.start - last.end) < MERGE_GAP_THRESHOLD)) {
                const newEnd = Math.max(last.end, window.end);
                if ((newEnd - last.start) <= maxWindowSize) {
                    last.end = newEnd;
                    last.offsets.push(window.offset);
                } else {
                    mergedWindows.push({ start: window.start, end: window.end, offsets: [window.offset] });
                }
            } else {
                mergedWindows.push({ start: window.start, end: window.end, offsets: [window.offset] });
            }
        }

        const compoundResults: SearchResult[] = [];
        let fd: fs.promises.FileHandle | null = null;

        try {
            fd = await pooledOpenFile(absolutePath, 'r');

            for (const window of mergedWindows) {
                const chunkLength = window.end - window.start;
                if (chunkLength <= 0) continue;

                const buffer = Buffer.alloc(chunkLength);
                await fd.read(buffer, 0, chunkLength, window.start);

                let inflatedContent = buffer.toString('utf-8');

                // Clean up partial words at boundaries
                if (window.start > 0) {
                    const firstSpace = inflatedContent.indexOf(' ');
                    if (firstSpace !== -1 && firstSpace < 50) {
                        inflatedContent = inflatedContent.substring(firstSpace + 1);
                    }
                }
                if (window.end < fileSize) {
                    const lastSpace = inflatedContent.lastIndexOf(' ');
                    if (lastSpace > inflatedContent.length - 50) {
                        inflatedContent = inflatedContent.substring(0, lastSpace);
                    }
                }

                if (inflatedContent.trim().length === 0) continue;

                compoundResults.push({
                    id: `virtual_${compoundId}_${window.start}_${window.end}`,
                    content: `...${inflatedContent}...`,
                    source: meta.path,
                    timestamp: Date.now() / 1000,
                    buckets: ['core'],
                    tags: [],
                    epochs: '',
                    provenance: meta.provenance,
                    score: 500,
                    compound_id: compoundId,
                    start_byte: window.start,
                    end_byte: window.end,
                    is_inflated: true,
                });
            }
        } catch (err) {
            console.warn(`[ContextInflator] Error reading file ${absolutePath}:`, err);
        } finally {
            if (fd) await fd.close();
        }

        return compoundResults;
    }

    /**
     * Fetch additional context to fill the token budget with less directly connected but still relevant data
     */
    private static async fetchAdditionalContext(baseResults: SearchResult[], remainingBudget: number): Promise<SearchResult[]> {
        // Only run if we have significant budget left (> 50% of typical large window)
        // or if we have very primitive results.
        if (remainingBudget < 1000) return [];

        // Extract tags and buckets from base results to find related content
        const allTags = new Set<string>();
        const allBuckets = new Set<string>();

        // We only consider tags/buckets from TOP results to avoid drift
        const topResults = baseResults.slice(0, 5);
        for (const result of topResults) {
            if (result.tags) {
                result.tags.forEach(tag => allTags.add(tag));
            }
            if (result.buckets) {
                result.buckets.forEach(bucket => allBuckets.add(bucket));
            }
        }

        // Convert sets to arrays for use in queries
        const tagsArray = Array.from(allTags);
        const bucketsArray = Array.from(allBuckets);

        // Query for related content that shares tags or buckets but wasn't in the original results
        const query = `
            SELECT id, content, source_path as source, timestamp,
    buckets, tags, epochs, provenance, simhash as molecular_signature,
    100 as score  --Lower score for less directly connected content
            FROM atoms
WHERE `;

        const params: any[] = [];
        const conditions: string[] = [];

        // Add conditions for tags if we have any
        if (tagsArray.length > 0) {
            conditions.push(`EXISTS(
    SELECT 1 FROM unnest(tags) as tag WHERE tag = ANY($${params.length + 1})
)`);
            params.push(tagsArray);
        }

        // Add conditions for buckets if we have any
        if (bucketsArray.length > 0) {
            const bucketParamIndex = params.length + 1;
            conditions.push(`EXISTS(
    SELECT 1 FROM unnest(buckets) as bucket WHERE bucket = ANY($${bucketParamIndex})
)`);
            params.push(bucketsArray);
        }

        // Combine conditions with OR (so we get content that matches either tags OR buckets)
        let queryConditions = '';
        if (conditions.length > 0) {
            queryConditions = `(${conditions.join(' OR ')})`;
        } else {
            // If no tags or buckets to match, just get some random content
            queryConditions = 'TRUE';
        }

        // Exclude original results
        const originalIds = baseResults.map(r => r.id);
        let fullQuery = query + queryConditions;
        if (originalIds.length > 0) {
            const excludeParamIndex = params.length + 1;
            fullQuery += ` AND id != ALL($${excludeParamIndex})`;
            params.push(originalIds);
        }

        // Limit to avoid fetching too much
        fullQuery += ' ORDER BY timestamp DESC LIMIT 10';

        try {
            const result = await db.run(fullQuery, params);
            if (!result.rows) return [];

            // Convert rows to SearchResult objects
            const additionalResults: SearchResult[] = result.rows.map((row: any) => ({
                id: row.id,
                content: row.content,
                source: row.source,
                timestamp: row.timestamp,
                buckets: row.buckets,
                tags: row.tags,
                epochs: row.epochs,
                provenance: row.provenance,
                molecular_signature: row.simhash,
                score: row.score || 100, // Default score if not provided
                is_inflated: true,
            }));

            // Further filter and truncate content to fit the remaining budget
            let totalChars = 0;
            const filteredResults: SearchResult[] = [];

            for (const result of additionalResults) {
                if (!result.content) continue;

                const availableSpace = remainingBudget - totalChars;
                if (availableSpace <= 0) break;

                if (result.content.length <= availableSpace) {
                    // If the content fits entirely, add it
                    filteredResults.push(result);
                    totalChars += result.content.length;
                } else {
                    // If the content is too large, truncate it to fit
                    const truncatedContent = result.content.substring(0, availableSpace);
                    filteredResults.push({
                        ...result,
                        content: truncatedContent,
                    });
                    totalChars += truncatedContent.length;
                    break; // Budget is filled
                }
            }

            console.log(`[ContextInflator] Fetched ${filteredResults.length} additional results to fill budget`);
            return filteredResults;
        } catch (e) {
            console.error('[ContextInflator] Failed to fetch additional context: ', e);
            return [];
        }
    }
}