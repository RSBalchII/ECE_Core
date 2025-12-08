# Setting up Cline to Work with ECE MCP Server

This guide explains how to configure Cline to use your ECE (Executive Cognitive Enhancement) MCP server for memory operations.

## Prerequisites

1. **ECE Core running**: Make sure your ECE Core server is running on port 8000
2. **MCP Server**: Make sure MCP is enabled in your config (should be by default)
3. **Reka Model Configuration**: If you're using the Reka configuration, set the environment variable before starting the model

## Starting the Services

### For Reka Model (21B):
```bash
# Set environment variable for Reka configuration
set REKA_MODEL=1
set MODEL_PATH=your_reka_model_path.gguf
# Then run the server
start-llama-server.bat
```

### Start ECE Core:
```bash
cd ece-core
python -m src.main
```

## Configure Cline to Use MCP

### Option 1: MCP Configuration
1. In VS Code settings, configure Cline to use your MCP server
2. Set the MCP endpoint to `http://localhost:8000/mcp` (or `http://127.0.0.1:8000/mcp`)
3. If authentication is required, set the API key in your Cline settings

### Option 2: Environment Variables
Set these environment variables before launching VS Code:
```bash
ECE_API_KEY=your_api_key (if auth is enabled)
MCP_URL=http://localhost:8000
```

## MCP Server Configuration in ECE

Your MCP server is configured in `configs/config.yaml`:
```yaml
mcp:
  url: "http://localhost:8000"  # Use 8000 for unified launcher /mcp endpoints
  timeout: 30
  max_tool_iterations: 5
  enabled: true
```

## Available MCP Tools

The MCP server exposes these memory tools:
- `add_memory` - Add memories to the Neo4j graph
- `search_memories` - Search memories with graph traversal
- `get_summaries` - Get recent session summaries
- Aliases: `write_memory`, `read_memory`, `get_memory_summaries`

## Troubleshooting

1. **Connection Issues**: Check that both ECE Core (port 8000) and LLM server (port 8080) are running
2. **Authentication**: If `ece_require_auth` is true, ensure API keys match
3. **Model Loading**: Make sure your model file exists and llama-server can access it

## Testing the Connection

You can test your MCP server with curl:
```bash
# List available tools
curl -X GET http://localhost:8000/mcp/tools

# Test a memory tool call
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search_memories", 
    "arguments": {"query": "test", "limit": 5}
  }'
```

## Environment Setup for Development

For development with Reka configuration, use this sequence:
1. Place your Reka model file in the `models/` directory
2. Update the model path in your environment or .env file
3. Set `REKA_MODEL=1` environment variable
4. Start the model with `start-llama-server.bat`
5. Start ECE Core with `python -m src.main`
6. Configure Cline to use your MCP server