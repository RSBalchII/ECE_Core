
import * as crypto from 'crypto';
import { atomizeContent as rawAtomize } from './atomizer.js';

/**
 * Atom Interface
 * Represents a single unit of thought/memory.
 */
export interface Atom {
    id: string;
    content: string;
    sourceId: string;
    sourcePath: string;
    sequence: number;
    timestamp: number;
    provenance: 'sovereign' | 'external';
    embedding?: number[]; // Placeholder for vector
}

/**
 * Refine Content
 * 
 * The Orchestrator for ingestion:
 * 1. Sanitizes Input (BOM, Encoding)
 * 2. Selects Strategy (Code vs Prose)
 * 3. Atomizes (via Atomizer)
 * 4. Enriches (Metadata injection)
 */
import { getEmbeddings } from '../llm/provider.js';
import config from '../../config/index.js';

// ...

export async function refineContent(rawBuffer: Buffer | string, filePath: string, options: { skipEmbeddings?: boolean } = {}): Promise<Atom[]> {
    // ... (Sanitization unchanged)
    let cleanText = '';

    if (Buffer.isBuffer(rawBuffer)) {
        // DEBUG: Check raw buffer for nulls
        let bufferNulls = 0;
        for (let k = 0; k < Math.min(rawBuffer.length, 2000); k++) {
            if (rawBuffer[k] === 0) bufferNulls++;
        }
        console.log(`[Refiner] Raw Buffer Analysis: Size=${rawBuffer.length}, First 2000 Nulls=${bufferNulls}`);

        // 1. Check for BOM (Byte Order Mark)
        if (rawBuffer.length >= 2) {
            if (rawBuffer[0] === 0xFF && rawBuffer[1] === 0xFE) {
                console.log(`[Refiner] Detected UTF-16 LE BOM. Decoding as UTF-16LE...`);
                cleanText = rawBuffer.toString('utf16le');
            } else if (rawBuffer[0] === 0xFE && rawBuffer[1] === 0xFF) {
                console.log(`[Refiner] Detected UTF-16 BE BOM. Decoding as UTF-16BE...`);
                // Node.js doesn't natively support utf16be in toString, swap bytes
                const swapped = Buffer.alloc(rawBuffer.length);
                for (let i = 0; i < rawBuffer.length; i += 2) {
                    swapped[i] = rawBuffer[i + 1];
                    swapped[i + 1] = rawBuffer[i];
                }
                cleanText = swapped.toString('utf16le');
            } else {
                // 2. Heuristic: Check for High Null Density (UTF-16 without BOM)
                let nullCount = 0;
                // Check start, middle, and end segments to be sure
                const checkLen = Math.min(rawBuffer.length, 1000);
                const midStart = Math.floor(rawBuffer.length / 2);
                const midLen = Math.min(rawBuffer.length - midStart, 1000);

                // Scan start
                for (let i = 0; i < checkLen; i++) {
                    if (rawBuffer[i] === 0x00) nullCount++;
                }
                // Scan middle
                if (midLen > 0) {
                    for (let i = midStart; i < midStart + midLen; i++) {
                        if (rawBuffer[i] === 0x00) nullCount++;
                    }
                }

                const totalChecked = checkLen + midLen;
                const ratio = nullCount / totalChecked;

                // If > 20% nulls, assume UTF-16LE
                if (totalChecked > 10 && ratio > 0.2) {
                    console.log(`[Refiner] Auto-detected UTF-16LE (Null Density: ${ratio.toFixed(2)}). Decoding as UTF-16LE...`);
                    cleanText = rawBuffer.toString('utf16le');
                } else {
                    cleanText = rawBuffer.toString('utf8');
                }
            }
        } else {
            cleanText = rawBuffer.toString('utf8');
        }
    } else {
        cleanText = rawBuffer;
    }

    if (cleanText.charCodeAt(0) === 0xFEFF) {
        cleanText = cleanText.slice(1);
    }

    // Encoding Correction: Aggressive Cleanup
    // Remove null bytes (\u0000) and replacement characters (\uFFFD)
    // Also remove other control characters that might confuse the tokenizer
    cleanText = cleanText.replace(/[\u0000\uFFFD]/g, '');

    // DEBUG: Verify clean text
    const cleanNulls = (cleanText.match(/\0/g) || []).length;
    if (cleanNulls > 0) {
        console.error(`[Refiner] CRITICAL: cleanText still has ${cleanNulls} nulls after cleaning!`);
    } else {
        // console.log(`[Refiner] Text cleaned successfully. Length: ${cleanText.length}`);
    }

    // Normalize line endings
    cleanText = cleanText.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

    // ... (Strategy Selection unchanged)
    // 3. Heuristic Strategy Selection
    // If we have very few lines relative to length, it's likely a minified blob or dense log
    // Ratio: Chars per line. Normal code ~30-80. Minified > 200.
    const lineCount = cleanText.split('\n').length;
    const avgLineLength = cleanText.length / (lineCount || 1);

    let strategy: 'code' | 'prose' | 'blob' = 'prose';

    if (avgLineLength > 300 || cleanText.length > 50000 && lineCount < 50) {
        console.log(`[Refiner] Detected BLOB content (Avg Line Len: ${avgLineLength.toFixed(0)}). Using 'blob' strategy.`);
        strategy = 'blob';
    } else if (filePath.endsWith('.ts') || filePath.endsWith('.js') || filePath.endsWith('.py') || filePath.endsWith('.rs') || filePath.endsWith('.cpp')) {
        strategy = 'code';
    }

    // 4. Atomize
    // strategy can be 'blob' - atomizer signature is updated
    const rawAtoms = rawAtomize(cleanText, strategy);

    // FILTER: Remove atoms that look like garbage/binary (Last Line of Defense)
    const validAtoms = rawAtoms.filter(atom => {
        // 1. Strict Null Check (If sanitization missed any)
        if (atom.indexOf('\u0000') !== -1) return false;

        // 2. Replacement Character Density (Bad decoding artifacts)
        const badCharCount = (atom.match(/[\uFFFD]/g) || []).length;
        if (badCharCount > 0 && (badCharCount / atom.length) > 0.05) return false;

        // 3. Control Character Density (Binary blob read as ASCII)
        // Count chars < 32 (excluding \n, \r, \t)
        // This regex matches control chars except newline, return, tab
        const controlCharCount = (atom.match(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g) || []).length;
        if (controlCharCount > 0 && (controlCharCount / atom.length) > 0.1) return false;

        return true;
    });

    if (rawAtoms.length !== validAtoms.length) {
        console.warn(`[Refiner] GARBAGE COLLECTION: Dropped ${rawAtoms.length - validAtoms.length} atoms from ${filePath} (contained nulls or binary data).`);
    }

    const sourceId = crypto.createHash('md5').update(filePath).digest('hex');
    const timestamp = Date.now();
    const normalizedPath = filePath.replace(/\\/g, '/');
    let provenance: 'sovereign' | 'external' = 'external';

    if (normalizedPath.includes('/inbox') ||
        normalizedPath.includes('/chat_logs') ||
        normalizedPath.includes('/diary') ||
        normalizedPath.includes('sovereign')) {
        provenance = 'sovereign';
    }

    // Process Atoms (Sequential Embedding Generation to prevent worker flood)
    // 3. Batch Embedding Generation
    // 3. Batch Embedding Generation (Optional)
    if (options.skipEmbeddings) {
        // Return atoms without embeddings
        return rawAtoms.map((content, index) => {
            const idHash = crypto.createHash('sha256')
                .update(sourceId + index.toString() + content)
                .digest('hex')
                .substring(0, 16);
            return {
                id: `atom_${idHash}`,
                content: content,
                sourceId: sourceId,
                sourcePath: normalizedPath,
                sequence: index,
                timestamp: timestamp,
                provenance: provenance,
                embedding: [] // Empty
            };
        });
    }

    const { processInBatches } = await import('../../core/batch.js');
    const BATCH_SIZE = 50;
    console.log(`[Refiner] Generating embeddings for ${rawAtoms.length} atoms (Batch size: ${BATCH_SIZE})...`);

    const chunkResults = await processInBatches(rawAtoms, async (chunkTexts, batchIndex) => {
        console.log(`[Refiner] Processing batch ${batchIndex + 1}/${Math.ceil(rawAtoms.length / BATCH_SIZE)} (${chunkTexts.length} atoms)...`);

        let batchEmbeddings: number[][] | null = null;
        try {
            batchEmbeddings = await getEmbeddings(chunkTexts);
        } catch (e) {
            console.error(`[Refiner] Batch embedding failed, skipping vectors for this batch:`, e);
        }

        const batchAtoms: Atom[] = [];
        for (let j = 0; j < chunkTexts.length; j++) {
            const atomIndex = (batchIndex * BATCH_SIZE) + j;
            const content = chunkTexts[j];

            if (content.includes('\0')) {
                console.error(`[Refiner] CRITICAL: Atom ${atomIndex} contains NULL bytes! Content snippet: ${JSON.stringify(content.substring(0, 50))}`);
            }

            const idHash = crypto.createHash('sha256')
                .update(sourceId + atomIndex.toString() + content)
                .digest('hex')
                .substring(0, 16);

            let embedding = new Array(config.MODELS.EMBEDDING_DIM).fill(0.1);
            if (batchEmbeddings && batchEmbeddings[j] && batchEmbeddings[j].length > 0) {
                embedding = batchEmbeddings[j];
            }

            batchAtoms.push({
                id: `atom_${idHash}`,
                content: content,
                sourceId: sourceId,
                sourcePath: normalizedPath,
                sequence: atomIndex,
                timestamp: timestamp,
                provenance: provenance,
                embedding: embedding
            });
        }
        return batchAtoms;
    }, { batchSize: BATCH_SIZE });

    // Flatten results
    const atoms = chunkResults.flat();

    return atoms;
}

/**
 * Enriches a list of atoms with embeddings.
 * Used for differential ingestion (only embedding new/changed atoms).
 */
export async function enrichAtoms(atoms: Atom[]): Promise<Atom[]> {
    if (atoms.length === 0) return atoms;

    const { processInBatches } = await import('../../core/batch.js');
    const BATCH_SIZE = 50;
    console.log(`[Refiner] Enriching ${atoms.length} atoms with embeddings...`);

    const totalBatches = Math.ceil(atoms.length / BATCH_SIZE);

    const chunkResults = await processInBatches(atoms, async (chunkAtoms, batchIndex) => {
        if ((batchIndex + 1) % 5 === 0 || batchIndex === 0) {
            console.log(`[Refiner] Enriching batch ${batchIndex + 1}/${totalBatches} (${chunkAtoms.length} atoms)...`);
        }

        // Extract content for embedding
        const texts = chunkAtoms.map(a => a.content);

        let batchEmbeddings: number[][] | null = null;
        try {
            batchEmbeddings = await getEmbeddings(texts);
        } catch (e) {
            console.error(`[Refiner] Enrichment failed for batch ${batchIndex}:`, e);
        }

        // Apply embeddings back to atoms
        return chunkAtoms.map((atom, i) => {
            if (batchEmbeddings && batchEmbeddings[i]) {
                return { ...atom, embedding: batchEmbeddings[i] };
            }
            return atom; // Return without embedding if failed (will be zero-filled by ingest)
        });
    }, { batchSize: BATCH_SIZE });

    return chunkResults.flat();
}
