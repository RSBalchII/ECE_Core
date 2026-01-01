# Standard 017: File Ingestion Debounce and Hash Checking

## What Happened?
The Watchdog service was triggering excessive memory ingestion when modern editors (VS Code, Obsidian) would autosave files frequently. This caused "Memory Churn" in CozoDB with duplicate content being ingested repeatedly, fragmenting the database and spiking CPU usage.

## The Cost
- High CPU usage from repeated ingestion of unchanged content
- Database fragmentation from duplicate entries
- Poor performance during active editing sessions
- 2+ hours spent implementing debounce and hash checking to prevent "Autosave Flood"

## The Rule
1. **Debounce File Events**: Implement a debounce mechanism that waits for a period of silence before processing file changes:
   ```python
   # Wait for debounce period before processing
   debounce_time = 2.0  # seconds
   ```

2. **Content Hash Verification**: Calculate MD5 hash of file content before ingestion and compare with previously ingested version:
   ```python
   import hashlib
   current_hash = hashlib.md5(content).hexdigest()
   if file_path in self.file_hashes and self.file_hashes[file_path] == current_hash:
       # Skip ingestion - content hasn't changed
       return
   ```

3. **Cancel Pending Operations**: Cancel any existing debounce timer when a new file event occurs for the same file:
   ```python
   if file_path in self.debounce_timers:
       self.debounce_timers[file_path].cancel()
   ```

4. **Proper Cleanup**: Clean up debounce timer references after processing:
   ```python
   if file_path in self.debounce_timers:
       del self.debounce_timers[file_path]
   ```

This standard prevents excessive database writes from autosave features while ensuring all actual changes are captured.