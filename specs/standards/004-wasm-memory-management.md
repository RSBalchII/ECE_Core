# Standard 004: WASM Memory Management

## What Happened?
WASM applications experienced "memory access out of bounds" errors and crashes when handling large JSON payloads or complex database operations. This was particularly problematic in `sovereign-db-builder.html` and `unified-coda.html` where JSON parameters were passed to `db.run()`.

## The Cost
- Crashes during database operations in browser-based CozoDB
- "Maximum call stack size exceeded" errors with large JSON payloads
- Unreliable memory operations in browser-based systems
- Hours of debugging memory access violations in WASM

## The Rule
1. **JSON Stringification:** Always properly stringify JSON parameters before passing to WASM functions:
   ```javascript
   // Before calling db.run() or similar WASM functions
   const jsonString = JSON.stringify(data);
   db.run(query, jsonString);
   ```

2. **Payload Size Limits:** Implement size checks before processing large JSON payloads in browser workers:
   ```javascript
   if (JSON.stringify(payload).length > MAX_SAFE_SIZE) {
       // Handle large payloads differently or chunk them
   }
   ```

3. **Error Handling:** Add timeout protection and fallback mechanisms for hanging WASM calls:
   ```javascript
   try {
       const result = await Promise.race([
           db.run(query),
           new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 10000))
       ]);
   } catch (error) {
       // Handle timeout or memory errors gracefully
   }
   ```

4. **IndexedDB Fallback:** Use `CozoDb.new_from_indexed_db` instead of `new_from_path` for persistent browser storage to avoid filesystem access issues.