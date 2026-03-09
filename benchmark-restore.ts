import { restoreBackup } from './engine/src/services/backup/backup.js';
import { restoreFromBackup } from './engine/src/services/backup/backup-restore.js';
import { db } from './engine/src/core/db.js';
import fs from 'fs';
import path from 'path';

const BACKUP_DIR = './engine/backups';

if (!fs.existsSync(BACKUP_DIR)) {
    fs.mkdirSync(BACKUP_DIR, { recursive: true });
}

async function createMockBackup(filename: string, numAtoms: number, numSources: number, numEngrams: number) {
    const filePath = path.join(BACKUP_DIR, filename);

    console.log(`Creating mock backup: ${filePath} with ${numAtoms} atoms...`);

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

    await write('{\n  "timestamp": "' + new Date().toISOString() + '",\n');
    await write('  "version": "2",\n');
    await write('  "files": [],\n');

    await write('  "source": [\n');
    for (let i = 0; i < numSources; i++) {
        const source = {
            path: `inbox/mock_source_${i}.txt`,
            hash: `hash_${i}`,
            total_atoms: 10,
            last_ingest: Date.now()
        };
        if (i > 0) await write(',\n');
        await write('    ' + JSON.stringify(source));
    }
    await write('\n  ],\n');

    await write('  "engrams": [\n');
    for (let i = 0; i < numEngrams; i++) {
        const engram = {
            key: `mock_engram_${i}`,
            value: `mock_value_${i}`
        };
        if (i > 0) await write(',\n');
        await write('    ' + JSON.stringify(engram));
    }
    await write('\n  ],\n');

    await write('  "memory": [\n');
    for (let i = 0; i < numAtoms; i++) {
        const atom = {
            id: `mock_atom_${i}`,
            timestamp: Date.now(),
            content: `This is mock atom number ${i} content`,
            source_path: `inbox/mock_source_${i % numSources}.txt`,
            source_id: `mock_source_id_${i % numSources}`,
            sequence: i,
            type: 'text',
            hash: `atom_hash_${i}`,
            buckets: ['mock_bucket'],
            tags: ['mock_tag1', 'mock_tag2'],
            epochs: 'mock_epoch',
            provenance: 'internal',
            simhash: '1234567890abcdef',
            embedding: [0.1, 0.2, 0.3, 0.4]
        };
        if (i > 0) await write(',\n');
        await write('    ' + JSON.stringify(atom));
    }
    await write('\n  ]\n}');

    return new Promise((resolve) => {
        stream.end(resolve);
    });
}

async function runBenchmark() {
    try {
        await db.init();

        // Create first test file
        const file1 = 'benchmark_backup_1.json';
        await createMockBackup(file1, 5000, 500, 500);

        console.log(`\n--- Running restoreBackup (backup.ts) ---`);
        let start = Date.now();
        await restoreBackup(file1);
        let end = Date.now();
        console.log(`restoreBackup took ${end - start} ms`);

        // Create second test file
        const file2 = 'benchmark_backup_2.json';
        await createMockBackup(file2, 5000, 500, 500);

        console.log(`\n--- Running restoreFromBackup (backup-restore.ts) ---`);
        start = Date.now();
        await restoreFromBackup(file2);
        end = Date.now();
        console.log(`restoreFromBackup took ${end - start} ms`);

        await db.close();
    } catch (error) {
        console.error("BENCHMARK ERROR:", error);
    }
}

runBenchmark();
