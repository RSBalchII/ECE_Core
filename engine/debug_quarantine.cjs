
const path = require('path');
const fs = require('fs');

async function check() {
    console.log("Loading Cozo...");
    let native;
    try {
        native = require('cozo-node');
        console.log("Loaded cozo-node from node_modules");
    } catch (e) {
        console.log("Failed to load cozo-node, trying local binary...", e.message);
        try {
            native = require('./cozo_node_win32.node');
            console.log("Loaded local binary");
        } catch (e2) {
            console.error("Failed to load local binary:", e2.message);
            return;
        }
    }

    const { CozoDb } = native;

    console.log("Check DB...");
    const dbPath = './context.db';
    const db = new CozoDb('rocksdb', dbPath);

    // Check 1: Provenance = 'quarantine'
    const q1 = `?[count] := *memory{provenance}, provenance = 'quarantine' :count`;
    try {
        const r1 = await db.run(q1);
        console.log("Atoms with provenance='quarantine':", r1.rows[0][0]);
    } catch (e) {
        console.log("Query 1 failed:", e.message);
    }

    // Check 2: Tag = '#manually_quarantined'
    const q2 = `
        ?[id, tags, provenance] := *memory{id, tags, provenance},
        tag in tags,
        tag = '#manually_quarantined'
    `;
    try {
        const r2 = await db.run(q2);
        console.log("Atoms with tag '#manually_quarantined':", r2.rows ? r2.rows.length : 0);
        if (r2.rows && r2.rows.length > 0) {
            console.log("Sample:", r2.rows[0]);
        }
    } catch (e) {
        console.log("Query 2 failed:", e.message);
    }

    // Check 3: Tag = '#auto_quarantined'
    const q3 = `
        ?[id, tags, provenance] := *memory{id, tags, provenance},
        tag in tags,
        tag = '#auto_quarantined'
    `;
    try {
        const r3 = await db.run(q3);
        console.log("Atoms with tag '#auto_quarantined':", r3.rows ? r3.rows.length : 0);
    } catch (e) {
        console.log("Query 3 failed:", e.message);
    }

}
check().catch(console.error);
