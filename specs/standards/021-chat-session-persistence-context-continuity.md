# Standard 021: Chat Session Persistence for Context Continuity

## What Happened?
The anchor.py CLI client maintained conversation history only in memory. If the terminal was closed or the CLI crashed, the entire conversation history was lost. This created a "Lost Context" risk where valuable conversation history was not preserved.

## The Cost
- Loss of conversation history on CLI crashes or termination
- Broken loop between active chatting and long-term memory
- 45 minutes spent implementing chat session persistence to context folder

## The Rule
1. **Auto-Save Sessions**: Automatically save each chat message to a session file:
   ```python
   def save_message_to_session(role, content):
       # Create timestamped session file in context/sessions/
       # Append each message as it occurs
   ```

2. **Session Directory**: Create a dedicated `context/sessions/` directory for chat logs:
   ```python
   SESSIONS_DIR = os.path.join(CONTEXT_DIR, "sessions")
   os.makedirs(SESSIONS_DIR, exist_ok=True)
   ```

3. **Markdown Format**: Save conversations in markdown format for easy reading and processing:
   ```python
   # Format: ## Role\nContent\n\n for each message
   ```

4. **Loop Closure**: Ensure that chat sessions become text files that the Watchdog service can monitor and ingest into long-term memory automatically.

This standard ensures conversation history survives CLI crashes and becomes part of the persistent context.