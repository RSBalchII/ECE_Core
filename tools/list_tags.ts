
import { db } from '../engine/src/core/db.js';
// import { config } from '../engine/src/config/index.js';
// TODO: is this being used?
async function listTags() {
    try {
        console.log('Initializing DB...');
        await db.init();

        console.log('Querying tags...');
        // Query to get all tags from all atoms
        // traversing the list in 'tags' column
        const query = `
            ?[tag] := *memory{tags}, tag_item in tags, tag = tag_item
            :distinct tag
        `;

        const result = await db.run(query);

        if (!result.rows || result.rows.length === 0) {
            console.log('No tags found in the database.');
        } else {
            console.log(`Found ${result.rows.length} unique tags:`);
            console.log('----------------------------------------');
            result.rows.forEach(row => {
                console.log(`- ${row[0]}`);
            });
            console.log('----------------------------------------');
        }

        // Also count atoms per tag
        const countQuery = `
            ?[tag, count(id)] := *memory{id, tags}, tag in tags
        `;
        const countResult = await db.run(countQuery);
        if (countResult.rows && countResult.rows.length > 0) {
            console.log('\nTag Counts:');
            console.log('----------------------------------------');
            countResult.rows.forEach(row => {
                console.log(`${row[0]}: ${row[1]}`);
            });
        }


    } catch (e) {
        console.error('Error listing tags:', e);
    }
}

listTags();
