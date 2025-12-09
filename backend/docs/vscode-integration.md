# ARCHIVED: VSCode integration guide moved to an archive location

This document has been archived and moved to `archive/docs_removed/docs/vscode-integration.md`.
For active documentation, see `specs/TROUBLESHOOTING.md` and `specs/spec.md`.

## Quick test with curl

### Normal (non-streaming)
```powershell
$body = @{
    model = 'ece-core'
    messages = @(
        @{ role = 'system'; content = 'You are a helpful assistant for VSCode.' },
        @{ role = 'user'; content = 'List the top-level files in the repository' }
    )
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/v1/chat/completions' -Body $body -ContentType 'application/json' -Headers @{ Authorization = 'Bearer <API_KEY_HERE>' }
```

### Streaming (SSE)
```powershell
$body = @{
    model = 'ece-core'
    messages = @(
        @{ role = 'system'; content = 'You are a helpful assistant for VSCode.' },
        @{ role = 'user'; content = 'Summarize the repository' }
    )
    stream = $true
} | ConvertTo-Json -Depth 4

# Using curl you can receive SSE chunks as they arrive:
curl -N -H "Authorization: Bearer <API_KEY_HERE>" -H "Content-Type: application/json" -X POST "http://localhost:8000/v1/chat/completions" -d $body
```

## Configure VSCode (example for 'Custom OpenAI endpoint')
- Open `Settings` → `Extensions` → `Chat` or the settings for the Chat provider you use
- Add a custom endpoint with URL: `http://localhost:8000/v1/chat/completions`
- Model: `ece-core`
- If API key is required, set a secret with key `Authorization` value `Bearer <API_KEY>` for the provider
- Set `stream` to `true` where the provider supports it

## Notes & Limitations
- The adapter maps the last `user` message to the ECE chat `message` and concatenates `system` messages into `system_prompt`.
- We do not currently map the entire conversation history (assistant and user messages) into ECE's internal context, though ECE itself has a memory manager for session context. We can extend mapping if needed.
- Tools: ECE integrates with an MCP tool provider. When the model wants to use tools, it produces `TOOL_CALL` blocks in the response which ECE will validate and execute. VSCode itself won't be able to operate the anchored tools directly, but ECE will perform tool calls internally.
- Security: Only enable this adapter on trusted networks. The adapter runs local services that may access the filesystem and tools.

If you want, I can also:
- Add a more complete message mapping that includes the entire conversation history (assistant + user roles) to the ECE context (for better grounding).  
- Add extra headers handling or CORS settings for remote use.  
- Add a small test in `tests/` to ensure the endpoint remains compatible.
