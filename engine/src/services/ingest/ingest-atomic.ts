import { db } from '../../core/db.js';
import { config } from '../../config/index.js';
import { Atom, Molecule, Compound } from '../../types/atomic.js';
import { filterTags } from '../../utils/tag-filter.js';
import { sanitizeTagsForWrite, sanitizeTagsFromDb } from '../../utils/tag-sanitizer.js';

export class AtomicIngestService {

    async ingestResult(
        compound: Compound,
        molecules: Molecule[],
        atoms: Atom[],
        buckets: string[] = ['core']
    ) {
        const startTime = Date.now();
        const filename = compound.path.split(/[/\\]/).pop() || compound.path;

        // Validate content lengths to prevent oversized atoms/molecules
        const MAX_CONTENT_LENGTH = 500 * 1024; // 500KB limit

        for (const mol of molecules) {
            if (mol.content.length > MAX_CONTENT_LENGTH) {
                console.warn(`[AtomicIngest] Warning: Molecule content exceeds maximum length (${mol.content.length} chars), truncating...`);
                mol.content = mol.content.substring(0, MAX_CONTENT_LENGTH) + '... [TRUNCATED]';
            }
        }

        for (const atom of atoms) {
            if (atom.label.length > MAX_CONTENT_LENGTH) {
                console.warn(`[AtomicIngest] Warning: Atom content exceeds maximum length (${atom.label.length} chars), truncating...`);
                atom.label = atom.label.substring(0, MAX_CONTENT_LENGTH) + '... [TRUNCATED]';
            }
        }

        console.log(`[AtomicIngest] ⏱️ START Persisting: ${filename} (${molecules.length} molecules, ${atoms.length} atoms)`);

        // BUGFIX 2026-03-03: For large ingests (>100K molecules), temporarily drop FTS index
        // to prevent PGlite corruption from concurrent index updates
        const isLargeIngestion = molecules.length > 100000;
        if (isLargeIngestion) {
            console.log(`[AtomicIngest] ⏱️ Large ingestion detected (${molecules.length} molecules), dropping FTS index...`);
            try {
                await db.run('DROP INDEX IF EXISTS idx_molecules_content_gin');
                await db.run('DROP INDEX IF EXISTS idx_atoms_content_gin');
            } catch (e: any) {
                console.warn(`[AtomicIngest] Could not drop FTS indexes: ${e.message}`);
            }
        }

        // Wrap entire ingestion in a transaction for atomicity and performance
        await db.transaction(async () => {
            await this._ingestResultInTransaction(compound, molecules, atoms, buckets);
        });

        // Recreate FTS indexes after bulk insert
        if (isLargeIngestion) {
            console.log(`[AtomicIngest] ⏱️ Recreating FTS indexes...`);
            try {
                await db.run(`
                    CREATE INDEX IF NOT EXISTS idx_molecules_content_gin
                    ON molecules
                    USING GIN(to_tsvector('simple', content));
                `);
                await db.run(`
                    CREATE INDEX IF NOT EXISTS idx_atoms_content_gin
                    ON atoms
                    USING GIN(to_tsvector('simple', content));
                `);
                // BUGFIX 2026-03-03: VACUUM ANALYZE after index rebuild to clear PGlite's cache
                // This prevents "nfig"]D errors from stale query plans
                await db.run('VACUUM ANALYZE atoms');
                await db.run('VACUUM ANALYZE molecules');
                console.log(`[AtomicIngest] ✅ FTS indexes recreated and optimized`);
            } catch (e: any) {
                console.warn(`[AtomicIngest] Could not recreate FTS indexes: ${e.message}`);
            }
        }

        const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.log(`[AtomicIngest] ✅ COMPLETE: ${filename} in ${totalTime}s`);
    }

    private async _ingestResultInTransaction(
        compound: Compound,
        molecules: Molecule[],
        atoms: Atom[],
        buckets: string[]
    ) {
        // 1. Persist Atoms (Tags)
        const atomsStart = Date.now();
        const uniqueAtomsMap = new Map<string, Atom>();
        for (const a of atoms) {
            if (!uniqueAtomsMap.has(a.id)) {
                uniqueAtomsMap.set(a.id, a);
            }
        }
        const uniqueAtoms = Array.from(uniqueAtomsMap.values());

        if (uniqueAtoms.length > 0) {
            await this.batchWriteAtoms(uniqueAtoms);
        }
        console.log(`[AtomicIngest] ⏱️ Atoms persisted: ${Date.now() - atomsStart}ms`);

        // 1.5. Persist Tags Table (The Nervous System)
        const tagsStart = Date.now();
        if (uniqueAtoms.length > 0) {
            await this.batchWriteTags(uniqueAtoms, buckets);
        }
        console.log(`[AtomicIngest] ⏱️ Tags persisted: ${Date.now() - tagsStart}ms`);

        // 2. Persist Molecules
        const moleculesStart = Date.now();
        if (molecules.length > 0) {
            await this.batchWriteMolecules(molecules);
        }
        console.log(`[AtomicIngest] ⏱️ Molecules persisted: ${((Date.now() - moleculesStart) / 1000).toFixed(2)}s`);

        // 3. Persist Atom Edges (Graph)
        const edgesStart = Date.now();
        if (compound.atoms && compound.atoms.length > 0) {
            await this.batchWriteEdges(compound.id, compound.atoms);
        }
        console.log(`[AtomicIngest] ⏱️ Edges persisted: ${Date.now() - edgesStart}ms`);

        // 4. Persist Compound (Atomic V4)
        const compoundStart = Date.now();
        await this.batchWriteCompounds([compound]);
        console.log(`[AtomicIngest] ⏱️ Compound persisted: ${((Date.now() - compoundStart) / 1000).toFixed(2)}s`);

        // 5. LEGACY BRIDGE: Populate 'atoms' table (was 'memory')
        const memoryStart = Date.now();
        await this.batchWriteMemory(compound, molecules, atoms, buckets);
        console.log(`[AtomicIngest] ⏱️ Memory/Atoms persisted: ${((Date.now() - memoryStart) / 1000).toFixed(2)}s`);

        // 6. Persist Atom Positions (Lazy Molecule Inflation)
        const positionsStart = Date.now();
        const atomLabelMap = new Map<string, string>();
        atoms.forEach(a => atomLabelMap.set(a.id, a.label));

        await this.batchWriteAtomPositions(molecules, atomLabelMap);
        console.log(`[AtomicIngest] ⏱️ Atom positions persisted: ${Date.now() - positionsStart}ms`);
    }

    private async batchWriteAtoms(atoms: Atom[]) {
        const chunkSize = 50;

        for (let i = 0; i < atoms.length; i += chunkSize) {
            const chunk = atoms.slice(i, i + chunkSize);
            // Yield to event loop
            if (i % 500 === 0 && i > 0) await new Promise(resolve => setImmediate(resolve));

            for (const atom of chunk) {
                // Sanitize tags at write time
                const sanitizedTags = sanitizeTagsForWrite([atom.label], {
                    context: `atom-${atom.id}`,
                    enableLogging: false
                });

                await db.run(
                    `INSERT INTO atoms (id, content, source_path, timestamp, simhash, embedding, provenance, buckets, tags)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (id) DO UPDATE SET
                       content = EXCLUDED.content,
                       source_path = EXCLUDED.source_path,
                       timestamp = EXCLUDED.timestamp,
                       simhash = EXCLUDED.simhash,
                       embedding = EXCLUDED.embedding,
                       provenance = EXCLUDED.provenance,
                       buckets = EXCLUDED.buckets,
                       tags = EXCLUDED.tags`,
                    [
                        atom.id,
                        atom.label, // label becomes content
                        'atom_source', // source_path
                        Date.now(), // timestamp
                        "0", // simhash
                        JSON.stringify(this.zeroVector()), // embedding
                        'internal', // provenance
                        ['atoms'], // buckets
                        JSON.stringify(sanitizedTags) // sanitized tags
                    ]
                );
            }
        }
    }

    private async batchWriteTags(atoms: Atom[], buckets: string[]) {
        const batchSize = 1000;
        let batchValues: any[] = [];
        let placeHolders: string[] = [];
        const flush = async () => {
            if (batchValues.length === 0) return;
            const query = `
                INSERT INTO tags (atom_id, tag, bucket) 
                VALUES ${placeHolders.join(', ')} 
                ON CONFLICT DO NOTHING
            `;
            await db.run(query, batchValues);
            batchValues = [];
            placeHolders = [];
        };

        for (const atom of atoms) {
            if (!atom.label) continue;
            // Ensure buckets are included
            const allBuckets = new Set([...buckets, ...(atom as any).buckets || []]);

            // Filter atom label through sanitization
            const sanitizedTags = sanitizeTagsForWrite([atom.label], {
                context: `atom-tags-${atom.id}`,
                enableLogging: false
            });
            const tags = sanitizedTags.length > 0 ? sanitizedTags : [atom.label]; // Keep original if filter removes everything

            for (const bucket of allBuckets) {
                for (const tag of tags) {
                    batchValues.push(atom.id, tag, bucket);
                    const offset = batchValues.length - 3;
                    placeHolders.push(`($${offset + 1}, $${offset + 2}, $${offset + 3})`);
                    if (placeHolders.length >= batchSize) await flush();
                }
            }
        }
        await flush();
    }

    // O(n/b) bulk INSERT — byte-budget batching to avoid PGlite WASM wire buffer overflow.
    // PGlite has an ~1MB wire message limit; large chat molecules can overflow with fixed row counts.
    private async batchWriteMolecules(molecules: Molecule[]) {
        const MAX_BATCH_ROWS = 50;
        const MAX_BATCH_BYTES = 512 * 1024; // 512KB per INSERT message (safe margin under PGlite's ~1MB limit)
        const total = molecules.length;
        const logInterval = Math.max(1000, Math.floor(total / 10));
        const molStart = Date.now();
        let i = 0;

        while (i < molecules.length) {
            // Build batch: add rows until we hit row limit OR byte budget
            const batch: Molecule[] = [];
            let batchBytes = 0;
            while (i < molecules.length && batch.length < MAX_BATCH_ROWS) {
                const m = molecules[i];
                const rowBytes = (m.content?.length ?? 0) + (m.id?.length ?? 0) + 200; // 200 = overhead estimate
                if (batch.length > 0 && batchBytes + rowBytes > MAX_BATCH_BYTES) break;
                batch.push(m);
                batchBytes += rowBytes;
                i++;
            }

            // Progress logging for large batches
            if (total > 1000 && i % logInterval === 0 && i > 0) {
                const elapsed = ((Date.now() - molStart) / 1000).toFixed(1);
                const rate = Math.round(i / ((Date.now() - molStart) / 1000));
                console.log(`[AtomicIngest] ⏱️ Molecules: ${((i / total) * 100).toFixed(0)}% (${i}/${total}) - ${elapsed}s elapsed, ${rate} mol/s`);
            }

            // Yield to event loop every 500 rows
            if (i % 500 === 0 && i > 0) {
                await new Promise(resolve => setImmediate(resolve));
            }

            // Build bulk INSERT with multiple VALUES
            const placeholders: string[] = [];
            const values: any[] = [];
            let paramIdx = 1;

            for (const m of batch) {
                // Sanitize molecule tags at write time
                const sanitizedTags = sanitizeTagsForWrite(m.tags || [], {
                    context: `molecule-${m.id}`,
                    enableLogging: false
                });

                placeholders.push(`($${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++})`);
                values.push(
                    m.id,
                    m.content,
                    m.compoundId,
                    m.sequence,
                    m.start_byte || 0,
                    m.end_byte || 0,
                    m.type || 'prose',
                    // numeric_value: PostgreSQL real has range ~1E±37, clamp out-of-range to null
                    (m.numeric_value !== undefined && m.numeric_value !== null && Math.abs(m.numeric_value) < 1e37) ? m.numeric_value : null,
                    m.numeric_unit || null,
                    m.molecular_signature || '0',
                    JSON.stringify(this.zeroVector()), // embedding (we don't compute embeddings here anymore)
                    m.timestamp || Date.now(),
                    JSON.stringify(sanitizedTags), // sanitized tags
                    JSON.stringify(m.entities || {})
                );
            }

            await db.run(
                `INSERT INTO molecules (id, content, compound_id, sequence, start_byte, end_byte, type, numeric_value, numeric_unit, molecular_signature, embedding, timestamp, tags, entities)
                 VALUES ${placeholders.join(', ')}
                 ON CONFLICT (id) DO UPDATE SET
                   content = EXCLUDED.content,
                   compound_id = EXCLUDED.compound_id,
                   sequence = EXCLUDED.sequence,
                   start_byte = EXCLUDED.start_byte,
                   end_byte = EXCLUDED.end_byte,
                   type = EXCLUDED.type,
                   numeric_value = EXCLUDED.numeric_value,
                   numeric_unit = EXCLUDED.numeric_unit,
                   molecular_signature = EXCLUDED.molecular_signature,
                   embedding = EXCLUDED.embedding,
                   timestamp = EXCLUDED.timestamp,
                   tags = EXCLUDED.tags,
                   entities = EXCLUDED.entities`,
                values
            );
        }

        const molElapsed = ((Date.now() - molStart) / 1000).toFixed(1);
        console.log(`[AtomicIngest] ⏱️ Molecules batch complete: ${total} molecules, ${molElapsed}s`);
    }

    private async batchWriteEdges(compoundId: string, atomIds: string[]) {
        const chunkSize = 50;

        for (let i = 0; i < atomIds.length; i += chunkSize) {
            const chunk = atomIds.slice(i, i + chunkSize);
            // Yield if processing many edges
            if (i % 500 === 0 && i > 0) await new Promise(resolve => setImmediate(resolve));

            for (const atomId of chunk) {
                await db.run(
                    `INSERT INTO edges (source_id, target_id, weight, relation)
                     VALUES ($1, $2, $3, $4)
                     ON CONFLICT (source_id, target_id, relation) DO UPDATE SET
                       weight = EXCLUDED.weight,
                       relation = EXCLUDED.relation`,
                    [compoundId, atomId, 1.0, 'has_tag']
                );
            }
        }
    }

    private async batchWriteCompounds(compounds: Compound[]) {
        const chunkSize = 50;
        // Limits to prevent WASM memory OOB - molecules are linked via compound_id anyway
        const MAX_BODY_SIZE = 500 * 1024; // 500KB max for compound body
        const MAX_MOLECULE_IDS = 10000;   // Don't store more than 10K IDs
        const MAX_ATOM_IDS = 1000;        // Don't store more than 1K atom IDs

        for (let i = 0; i < compounds.length; i += chunkSize) {
            const chunk = compounds.slice(i, i + chunkSize);

            for (const compound of chunk) {
                // Truncate compound body if too large (full content in molecules)
                let compoundBody = compound.compound_body || '';
                if (compoundBody.length > MAX_BODY_SIZE) {
                    compoundBody = compoundBody.substring(0, MAX_BODY_SIZE) + '\n... [TRUNCATED - see molecules for full content]';
                }

                // Limit array sizes (molecules have compound_id for lookups)
                let atoms = compound.atoms || [];
                let molecules = compound.molecules || [];

                if (atoms.length > MAX_ATOM_IDS) {
                    atoms = atoms.slice(0, MAX_ATOM_IDS);
                }
                if (molecules.length > MAX_MOLECULE_IDS) {
                    molecules = molecules.slice(0, MAX_MOLECULE_IDS);
                }

                await db.run(
                    `INSERT INTO compounds (id, compound_body, path, timestamp, provenance, molecular_signature, atoms, molecules, embedding)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                     ON CONFLICT (id) DO UPDATE SET
                       compound_body = EXCLUDED.compound_body,
                       path = EXCLUDED.path,
                       timestamp = EXCLUDED.timestamp,
                       provenance = EXCLUDED.provenance,
                       molecular_signature = EXCLUDED.molecular_signature,
                       atoms = EXCLUDED.atoms,
                       molecules = EXCLUDED.molecules,
                       embedding = EXCLUDED.embedding`,
                    [
                        compound.id,
                        compoundBody,
                        compound.path,
                        compound.timestamp,
                        compound.provenance,
                        compound.molecular_signature || '0',
                        JSON.stringify(atoms),
                        JSON.stringify(molecules),
                        JSON.stringify(this.zeroVector())
                    ]
                );
            }
        }
    }

    // O(n/b) bulk INSERT for atoms
    private async batchWriteMemory(
        compound: Compound,
        molecules: Molecule[],
        atoms: Atom[],
        buckets: string[]
    ) {
        // 1. Write Compound Row
        const MAX_ATOM_CONTENT_SIZE = 500 * 1024;
        let atomContent = compound.compound_body;
        if (atomContent.length > MAX_ATOM_CONTENT_SIZE) {
            atomContent = atomContent.substring(0, MAX_ATOM_CONTENT_SIZE) + '... [TRUNCATED]';
        }

        await db.run(
            `INSERT INTO atoms (id, content, source_path, timestamp, simhash, embedding, provenance, buckets, tags, compound_id, start_byte, end_byte)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
             ON CONFLICT (id) DO UPDATE SET
               content = EXCLUDED.content,
               source_path = EXCLUDED.source_path,
               timestamp = EXCLUDED.timestamp,
               simhash = EXCLUDED.simhash,
               embedding = EXCLUDED.embedding,
               provenance = EXCLUDED.provenance,
               buckets = EXCLUDED.buckets,
               tags = EXCLUDED.tags,
               compound_id = EXCLUDED.compound_id,
               start_byte = EXCLUDED.start_byte,
               end_byte = EXCLUDED.end_byte`,
            [
                compound.id,
                atomContent,
                compound.path,
                compound.timestamp,
                compound.molecular_signature || "0",
                JSON.stringify(this.zeroVector()),
                compound.provenance,
                buckets,
                atoms.map(a => a.label),
                compound.id,
                0,
                compound.compound_body.length
            ]
        );

        // 2. Write Molecule Rows in Batches
        const atomLabelMap = new Map<string, string>();
        atoms.forEach(a => atomLabelMap.set(a.id, a.label));

        const batchSize = 50;
        const total = molecules.length;
        const logInterval = Math.max(1000, Math.floor(total / 10));

        for (let i = 0; i < molecules.length; i += batchSize) {
            const batch = molecules.slice(i, Math.min(i + batchSize, molecules.length));

            // Progress logging
            if (total > 1000 && i % logInterval === 0 && i > 0) {
                console.log(`[AtomicIngest] ⏱️ Memory/Atoms: ${((i / total) * 100).toFixed(0)}% (${i}/${total})`);
            }
            if (i % 500 === 0 && i > 0) await new Promise(resolve => setImmediate(resolve));

            const placeholders: string[] = [];
            const values: any[] = [];
            let paramIdx = 1;

            for (const m of batch) {
                // Extract tags from atoms and filter through blacklist
                const rawTags = (m.atoms || []).map(id => atomLabelMap.get(id)).filter(l => l !== undefined) as string[];
                const specificTags = filterTags(rawTags);

                placeholders.push(`($${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++})`);

                values.push(
                    m.id,
                    m.content,
                    compound.path,
                    m.timestamp || compound.timestamp,
                    m.molecular_signature || this.generateHash(m.content),
                    JSON.stringify(this.zeroVector()),
                    compound.provenance,
                    buckets,
                    specificTags,
                    m.compoundId,
                    m.start_byte || 0,
                    m.end_byte || 0
                );
            }

            await db.run(
                `INSERT INTO atoms (id, content, source_path, timestamp, simhash, embedding, provenance, buckets, tags, compound_id, start_byte, end_byte)
                 VALUES ${placeholders.join(', ')}
                 ON CONFLICT (id) DO UPDATE SET
                   content = EXCLUDED.content,
                   source_path = EXCLUDED.source_path,
                   timestamp = EXCLUDED.timestamp,
                   simhash = EXCLUDED.simhash,
                   embedding = EXCLUDED.embedding,
                   provenance = EXCLUDED.provenance,
                   buckets = EXCLUDED.buckets,
                   tags = EXCLUDED.tags,
                   compound_id = EXCLUDED.compound_id,
                   start_byte = EXCLUDED.start_byte,
                   end_byte = EXCLUDED.end_byte`,
                values
            );
        }
    }

    // Bulk INSERT for atom positions (Lazy Molecule Inflation)
    private async batchWriteAtomPositions(molecules: Molecule[], atomLabelMap: Map<string, string>) {
        const batchSize = 100;
        let batch: any[] = [];

        // Iterate molecules and generate position rows on the fly
        // This avoids creating a massive array of all position rows in memory
        for (const m of molecules) {
            if (!m.atoms || m.atoms.length === 0) continue;
            const midByte = m.start_byte !== undefined ? Math.floor((m.start_byte + (m.end_byte || m.start_byte)) / 2) : 0;

            for (const atomId of m.atoms) {
                const label = atomLabelMap.get(atomId);
                if (label) {
                    batch.push(m.compoundId, label, midByte);

                    // If batch is full, flush it
                    if (batch.length >= batchSize * 3) { // 3 params per row * batchSize
                        await this.flushAtomPositionsBatch(batch);
                        batch = [];
                    }
                }
            }
        }

        // Flush remaining
        if (batch.length > 0) {
            await this.flushAtomPositionsBatch(batch);
        }
    }

    private async flushAtomPositionsBatch(flatValues: any[]) {
        const rowsCount = flatValues.length / 3;
        const placeholders: string[] = [];
        let paramIdx = 1;

        for (let i = 0; i < rowsCount; i++) {
            placeholders.push(`($${paramIdx++}, $${paramIdx++}, $${paramIdx++})`);
        }

        await db.run(
            `INSERT INTO atom_positions (compound_id, atom_label, byte_offset)
             VALUES ${placeholders.join(', ')}
             ON CONFLICT (compound_id, atom_label, byte_offset) DO NOTHING`,
            flatValues
        );
    }


    private zeroVector() {
        return new Array(config.MODELS.EMBEDDING_DIM).fill(0.1);
    }

    private generateHash(str: string): string {
        // Simple hash for legacy field
        let hash = 0;
        if (str.length === 0) return "0";
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash |= 0;
        }
        return hash.toString(16);
    }
}