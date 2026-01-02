@echo off
echo ⚓ STARTING ANCHOR SYSTEM IN BACKGROUND...

REM Check for low-resource mode
if "%LOW_RESOURCE_MODE%"=="true" (
    echo 📱 Low-Resource Mode Enabled
) else (
    if "%CPU_ONLY_MODE%"=="true" (
        echo 💻 CPU-Only Mode Enabled
    )
)

REM 1. Start the Unified Server (Truly Background - no window)
if "%LOW_RESOURCE_MODE%"=="true" (
    start "Anchor Core" /min cmd /c "cd tools && set LOW_RESOURCE_MODE=true && python webgpu_bridge.py"
) else (
    if "%CPU_ONLY_MODE%"=="true" (
        start "Anchor Core" /min cmd /c "cd tools && set CPU_ONLY_MODE=true && python webgpu_bridge.py"
    ) else (
        start "Anchor Core" /min cmd /c "cd tools && python webgpu_bridge.py"
    )
)

REM 1.5 Start Watchdog (File Monitor)
start "Anchor Watchdog" /min cmd /c "cd tools && python anchor_watchdog.py"

REM 2. Wait for Server to initialize
echo Waiting for server to initialize...
timeout /t 5 /nobreak >nul

REM 3. Launch the Ghost Engine
REM Handled automatically by the Bridge (Resurrection Manager)
echo 👻 Ghost Engine managed by Bridge...

echo.
echo ✅ Anchor System Started in Background
echo    Open http://localhost:8000 in your browser when ready
echo    Services will start automatically when you access the UI
echo.
echo 💡 For low-resource devices: set LOW_RESOURCE_MODE=true before running
echo 💡 For CPU-only: set CPU_ONLY_MODE=true before running
echo.
echo 🔄 Ghost Engine should connect automatically to enable chat and memory search