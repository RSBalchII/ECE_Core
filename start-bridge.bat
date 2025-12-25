@echo off
REM Start the WebGPU Bridge with proper configuration
echo Starting WebGPU Bridge...
set BRIDGE_PORT=8080
set BRIDGE_TOKEN=sovereign-secret
cd /d "%~dp0"
python tools/webgpu_bridge.py