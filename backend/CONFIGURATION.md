# Configuration Guide for ECE_Core

## Setting up Environment Variables

The system can be configured through environment variables or by creating a `.env` file based on the `.env.example` template.

### Creating your .env file

1. Copy the `.env.example` file to create a new `.env` file:
   ```bash
   cd ece-core
   copy .env.example .env
   ```

2. Edit the `.env` file to customize settings for your environment.

## Key Configuration Options

### Model and Context Configuration
- `LLM_CONTEXT_SIZE`: Set the context window size (e.g., 4096, 8192, 16384, 32768)
- `LLM_MODEL_NAME`: Specify the model name to use
- `LLM_GPU_LAYERS`: Number of GPU layers to offload (-1 for all, 0 for CPU only)
- `LLM_THREADS`: Number of CPU threads to use

### Server Configuration
- `LLM_API_BASE`: Base URL for the LLM API (default: http://localhost:8080/v1)
- `LLAMA_SERVER_DEFAULT_PORT`: Port for the main llama server (default: 8080)
- `LLAMA_EMBED_SERVER_DEFAULT_PORT`: Port for the embedding server (default: 8081)

### Memory Management
- `MAX_CONTEXT_TOKENS`: Maximum tokens in total context
- `SUMMARIZE_THRESHOLD`: Token count that triggers summarization

## Starting the Servers

### Starting the main LLM server:
```bash
# From the Context-Engine root directory
start-llama-server.bat
```

### Starting the embedding server:
```bash
# From the Context-Engine root directory  
start-embed-server.bat
```

The batch scripts will attempt to find the appropriate model and use settings from your configuration files or .env file. If no model is configured, the system will attempt to use interactive model selection.

## Troubleshooting

If you encounter issues with the server startup scripts, check that:

1. The `llama-server.exe` binary is built and located at `tools\llama.cpp\build\bin\Release\llama-server.exe`
2. Your configuration files are properly set up
3. The required ports are available
4. Models are properly located in the models directory