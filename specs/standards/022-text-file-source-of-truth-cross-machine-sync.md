# Standard 022: Text-File Source of Truth for Cross-Machine Sync

## What Happened?
The CozoDB database lives in IndexedDB inside the headless browser profile, making it impossible to sync between machines. Chat history and learned connections were trapped in the browser instance and lost when switching laptops. The system needed a "Text-File Source of Truth" approach where the database is treated as a cache and all important data is stored in text files.

## The Cost
- Lost conversation history when switching between machines
- Inability to sync learned connections and context across devices
- 1 hour spent implementing daily session files and text-file persistence

## The Rule
1. **Database is Cache**: Treat CozoDB as a cache, not the source of truth:
   ```python
   # All important data must exist in text files first
   # Database is rebuilt from text files on each machine
   ```

2. **Daily Session Files**: Create daily markdown files for chat persistence:
   ```python
   def ensure_session_file():
       date_str = datetime.now().strftime("%Y-%m-%d")
       filename = f"chat_{date_str}.md"
       # Creates daily consolidated session files
   ```

3. **Text-File First**: All important information must be written to text files:
   ```python
   # Every chat message gets saved to markdown file
   # Files are automatically ingested by watchdog service
   # Creates infinite loop: Chat -> File -> Ingestion -> Memory -> Next Chat
   ```

4. **Cross-Machine Sync**: Use Dropbox/Git for file synchronization:
   ```python
   # Text files sync automatically via Dropbox/Git
   # Database rebuilds from text files on each machine
   # Ensures consistent context across all devices
   ```

5. **Timestamped Entries**: Format messages with timestamps for tracking:
   ```python
   # Format: ### ROLE [HH:MM:SS]\n{content}\n\n
   ```

This standard ensures that all important context is persisted in text files that can be synced across machines, making the database truly portable.