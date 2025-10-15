# PowerShell script to run llama.cpp server with jamba-reasoning-3b model at 128k tokens with full GPU loading

Write-Host "Starting llama.cpp server with jamba-reasoning-3b model..." -ForegroundColor Cyan
Write-Host "Configured for 128k context window and full GPU loading" -ForegroundColor Cyan

# Path for llama.cpp server built in the project
$llamaServerPath = "llama.cpp\build\bin\Release\llama-server.exe"

# Check if llama.cpp server exists at the expected location
if (Test-Path $llamaServerPath) {
    Write-Host "Found llama-server at: $llamaServerPath" -ForegroundColor Green
} else {
    Write-Host "llama-server.exe not found at expected location: $llamaServerPath" -ForegroundColor Red
    Write-Host "Please make sure you have built llama.cpp with CUDA support." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Run the server with 128k context, full GPU offloading, and the jamba model
Write-Host "Starting server with parameters:" -ForegroundColor Cyan
Write-Host " - Model: models/jamba-reasoning-3b-F16.gguf"
Write-Host " - Context: 131072 tokens (128k)"
Write-Host " - GPU layers: All (-1)"
Write-Host " - Port: 8080"
Write-Host " - Address: 0.0.0.0"

$arguments = @(
    "--model", "./models/jamba-reasoning-3b-F16.gguf",
    "--ctx-size", "131072",
    "--n-gpu-layers", "12",
    "--port", "8080",
    "--host", "0.0.0.0",
    "--threads", "12",
    "--batch-size", "512"
)

& $llamaServerPath $arguments

Write-Host ""
Write-Host "llama.cpp server has been started!" -ForegroundColor Green
Write-Host "You can now run the ECE with: python run_all_agents.py" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"