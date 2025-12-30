@echo off
echo ⚓ STARTING ANCHOR SYSTEM...

REM 1. Start the Unified Server (Background)
start "Anchor Core" /min cmd /k "cd tools && python webgpu_bridge.py"

REM 2. Wait for Server
timeout /t 2 /nobreak >nul

REM 3. Launch the Ghost Engine (Minimized Browser)
REM Points to the new chat.html on the single port
start "Ghost Engine" /min msedge --app=http://localhost:8000/chat.html?headless=true --start-minimized --remote-debugging-port=9222
REM OR use chrome if edge is missing:
REM start "Ghost Engine" /min chrome --app=http://localhost:8000/chat.html?headless=true --start-minimized

echo.
echo ✅ System Online at http://localhost:8000
echo    - UI: http://localhost:8000/chat.html
echo    - Terminal: http://localhost:8000/terminal.html
echo.
pause