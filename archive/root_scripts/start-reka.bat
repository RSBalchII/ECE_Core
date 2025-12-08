@echo off
REM Script to start the system with Reka configuration
REM This sets up the environment and starts both the model and ECE core

echo Starting ECE with Reka-Flash-3-21B configuration...

REM Set Reka-specific environment variables
set REKA_MODEL=1
set LLAMA_SERVER_UBATCH_SIZE=2048
set LLAMA_BATCH=2048
set LLAMA_PARALLEL=1
set THREADS=12

REM Start the LLM server with Reka configuration
echo Starting LLM server with Reka configuration...
start "LLM Server" cmd /c "python start_llm_server.py"

REM Wait a bit for the LLM server to start
timeout /t 10 /nobreak >nul

REM Start the ECE Core server with MCP integration
echo Starting ECE Core server with MCP integration...
start "ECE Core" cmd /c "python start_ece.py"

echo.
echo Services started:
echo - LLM Server: localhost:8080
echo - ECE Core: localhost:8000 (with MCP tools available)
echo.
echo To use with Cline, ensure your MCP URL is configured to http://localhost:8000
echo.
pause