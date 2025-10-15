@echo off
REM Script to run llama.cpp server with jamba-reasoning-3b model at optimized VRAM usage

echo Starting llama.cpp server with jamba-reasoning-3b model...
echo Configured for optimized VRAM usage (8-12GB) with partial GPU loading

REM Path for llama.cpp server built in the project
set LLAMA_SERVER_PATH=llama.cpp\\build\\bin\\Release\\llama-server.exe

REM Check if llama.cpp server exists at the expected location
if exist "%LLAMA_SERVER_PATH%" (
    echo Found llama-server at: %LLAMA_SERVER_PATH%
) else (
    echo llama-server.exe not found at expected location: %LLAMA_SERVER_PATH%
    echo Please make sure you have built llama.cpp with CUDA support.
    pause
    exit /b 1
)

REM Run the server with optimized settings for 3B model (using ~8-12GB VRAM)
echo Starting server with parameters:
echo  - Model: models\jamba-reasoning-3b-F16.gguf
echo  - Context: 4096 tokens (reduced from 128k to save VRAM)
echo  - GPU layers: 15 (reduced from all to save VRAM)
echo  - Port: 8080
echo  - Address: 0.0.0.0

"%LLAMA_SERVER_PATH%" ^
    --model "./models/jamba-reasoning-3b-F16.gguf" ^
    --ctx-size 4096 ^
    --n-gpu-layers 15 ^
    --port 8080 ^
    --host 0.0.0.0 ^
    --threads 16 ^
    --batch-size 512 ^
    --tensor-split 0

echo.
echo llama.cpp server has been started!
echo You can now run the ECE with: python run_all_agents.py
echo.
pause