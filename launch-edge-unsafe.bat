@echo off
echo 🔪 CTX-OS: Ensuring clean environment...
taskkill /F /IM msedge.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo Starting Microsoft Edge with UNLOCKED WebGPU Flags...
echo This configuration is optimized for Snapdragon X Elite.
echo.
echo Flags applied:
echo - enable-unsafe-webgpu (Force GPU access)
echo - enable-dawn-features=allow_unsafe_apis (Unlock larger buffers)
echo - disable-gpu-watchdog (Prevent TDR timeouts)
echo.

start msedge --enable-unsafe-webgpu --enable-dawn-features=allow_unsafe_apis --disable-gpu-watchdog http://localhost:8000/model-server-chat.html

echo Browser launched.
echo.
echo NOTE: Please select the "Qwen2.5-1.5B" model first to test connection.
echo 7B models may still struggle with buffer limits on this driver.
echo.
pause
