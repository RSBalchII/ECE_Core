#!/bin/bash

# Script to run llama.cpp server with jamba-reasoning-3b model at 128k tokens with full GPU loading

echo "Starting llama.cpp server with jamba-reasoning-3b model..."
echo "Configured for 128k context window and full GPU loading"

# Path for llama.cpp server built in the project
LLAMA_SERVER_PATH="./llama.cpp/build/bin/Release/llama-server.exe"

# Check if llama.cpp server exists at the expected location
if [ -f "$LLAMA_SERVER_PATH" ]; then
    echo "Found llama-server at: $LLAMA_SERVER_PATH"
else
    echo "llama-server.exe not found at expected location: $LLAMA_SERVER_PATH"
    echo "Please make sure you have built llama.cpp with CUDA support."
    read -p "Press any key to exit..."
    exit 1
fi

# Run the server with 128k context, full GPU offloading, and the jamba model
echo "Starting server with parameters:"
echo " - Model: ./models/jamba-reasoning-3b-F16.gguf"
echo " - Context: 131072 tokens (128k)"
echo " - GPU layers: All (-1)"
echo " - Port: 8080"
echo " - Address: 0.0.0.0"

$LLAMA_SERVER_PATH \
    --model "./models/jamba-reasoning-3b-F16.gguf" \
    --ctx-size 131072 \
    --n-gpu-layers -1 \
    --port 8080 \
    --host 0.0.0.0 \
    --threads 16 \
    --batch-size 1024

echo
echo "llama.cpp server has been started!"
echo "You can now run the ECE with: python run_all_agents.py"
echo
read -p "Press any key to exit..."