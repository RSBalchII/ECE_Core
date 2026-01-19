
import { executeSearch } from '../src/services/search/search.js';
import { db } from '../src/core/db.js';

async function testSearch() {
    console.log("Initializing DB...");
    await db.init();

    const query = "atom test";
    console.log(`Running Search for: "${query}"`);

    const results = await executeSearch(query);

    console.log("\n--- Search Results ---");
    console.log(`Context Length: ${results.context.length}`);
    console.log(`Result Count: ${results.results.length}`);

    results.results.slice(0, 5).forEach((r, i) => {
        console.log(`\n[${i + 1}] Score: ${r.score.toFixed(2)} | Provenance: ${r.provenance}`);
        console.log(`Source: ${r.source}`);
        console.log(`Snippet: ${r.content.substring(0, 100)}...`);
    });
}

testSearch().catch(console.error);
