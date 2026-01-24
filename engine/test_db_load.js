
console.log('Testing import of dist/core/db.js...');
try {
    const { db } = await import('./dist/core/db.js');
    console.log('SUCCESS: DB loaded', db);
} catch (e) {
    console.error('FAIL: Could not load DB');
    console.error(e);
}
