@echo off
setlocal

:: Define the User Data Directory (Project Relative)
set "USER_DATA=%~dp0browser_data"
if not exist "%USER_DATA%" mkdir "%USER_DATA%"

:: Define Flags for D3D12 (Default for Windows)
:: We REMOVE --use-angle=vulkan
:: We ADD --ignore-gpu-blocklist to force it to try even if "known bad"
set "FLAGS=--user-data-dir="%USER_DATA%" --ignore-gpu-blocklist --enable-webgpu-developer-features --enable-unsafe-webgpu --enable-dawn-features=allow_unsafe_apis --disable-gpu-watchdog"
set "URL=http://localhost:8000/model-server-chat.html"

echo 🔍 Checking for installed browsers...

:: 1. Try Microsoft Edge
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    echo ✅ Found Microsoft Edge.
    set "BROWSER=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    goto launch
)

:: 2. Try Google Chrome
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo ✅ Found Google Chrome.
    set "BROWSER=C:\Program Files\Google\Chrome\Application\chrome.exe"
    goto launch
)
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo ✅ Found Google Chrome (x86).
    set "BROWSER=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    goto launch
)

:: 3. Try Brave
if exist "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" (
    echo ✅ Found Brave Browser.
    set "BROWSER=C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    goto launch
)

echo ❌ No compatible Chromium browser found.
pause
exit /b

:launch
echo 🚀 Launching with D3D12 (Default) backend...
echo Path: "%BROWSER%"
echo Data: "%USER_DATA%"
echo.
"%BROWSER%" %FLAGS% %URL%
pause
