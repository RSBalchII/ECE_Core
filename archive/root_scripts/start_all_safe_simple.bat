@echo off
REM Simplified Safe Start Script using Python launchers
REM This replaces the complex start-all-safe.bat with our new modular approach

echo Starting ECE with safe defaults using Python launchers...

REM Set safe environment variables for RTX 4090 with conservative settings
set LLAMA_SERVER_UBATCH_SIZE=256
set LLAMA_BATCH=1024
set LLAMA_PARALLEL=1
set THREADS=12

REM Start the LLM server in safe mode (using the new Python script which will provide interactive model selection)
echo Starting LLM server with safe settings...
start "LLM Server" cmd /c "python start_llm_server.py"

REM Wait a bit for the LLM server to start
timeout /t 10 /nobreak >nul

REM Start the ECE Core server with MCP integration
echo Starting ECE Core server with MCP integration...
start "ECE Core" cmd /c "python start_ece.py"

REM Start the embedding server (auto-selects gemma-300m)
echo Starting embedding server...
start "Embedding Server" cmd /c "python start_embedding_server.py"

echo.
echo All services started with safe defaults:
echo - LLM Server: localhost:8080
echo - ECE Core: localhost:8000 (with MCP tools available)
echo - Embedding Server: localhost:8081
echo.
echo To use with Cline, ensure your MCP URL is configured to http://localhost:8000
echo.
echo Note: The Python scripts will prompt for model selection if not specified.
pause