
import { db } from '../src/core/db.js';
import config from '../src/config/index.js';

async function runTest() {
    console.log("Initializing DB...");
    await db.init();

    // Raw Failing Atom (Copied from Debug Log)
    // "atom_3449feb29c1ea488", 1768844295178, "Block 2...", "inbox\\atom_test...", "beacbd...", 1, "text", "3449fe...", ["inbox"], [], [], "external", [0.1...]

    // Construct exactly as ingestAtoms does
    // Schema: id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding

    const atomData = [
        "atom_3449feb29c1ea488",
        1768844295178,
        "Block 2: atom_test_1768659429156 continued.",
        "inbox\\atom_test_1768659429156.md",
        "beacbd2a7598600c6acb4fe2e7c36323",
        1,
        "text",
        "3449feb29c1ea488",
        ["inbox"],
        [], // epochs
        [], // tags
        "external",
        new Array(768).fill(0.1)
    ];

    const chunk = [atomData];

    console.log("Attempting Insert...");
    try {
        await db.run(`
            ?[id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding] <- $data
            :put memory {id, timestamp, content, source, source_id, sequence, type, hash, buckets, epochs, tags, provenance, embedding}
        `, { data: chunk });
        console.log("SUCCESS: Insert worked!");
    } catch (e: any) {
        console.error("FAILURE: Insert failed:", e.message);
    }
}

runTest().catch(console.error);
