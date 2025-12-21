@echo off
setlocal EnableDelayedExpansion

:: Define the User Data Directory (Project Relative)
set "USER_DATA=%~dp0browser_data"
if not exist "%USER_DATA%" mkdir "%USER_DATA%"

:: Define Flags (Critical for Snapdragon)
set "FLAGS=--user-data-dir="%USER_DATA%" --ignore-gpu-blocklist --enable-webgpu-developer-features --enable-unsafe-webgpu --enable-dawn-features=allow_unsafe_apis --enable-features=Vulkan --use-angle=vulkan --disable-gpu-watchdog"
set "URL=http://localhost:8000/tools/model-server-chat.html"

echo ---------------------------------------------------
echo 🔍 Detecting Browsers (Vulkan Mode)...
echo ---------------------------------------------------

set "count=0"

:: 1. Check Microsoft Edge
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    set /a count+=1
    set "name[!count!]=Microsoft Edge"
    set "path[!count!]=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)

:: 2. Check Google Chrome
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set /a count+=1
    set "name[!count!]=Google Chrome"
    set "path[!count!]=C:\Program Files\Google\Chrome\Application\chrome.exe"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set /a count+=1
    set "name[!count!]=Google Chrome (x86)"
    set "path[!count!]=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set /a count+=1
    set "name[!count!]=Google Chrome (User)"
    set "path[!count!]=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
)

:: 3. Check Brave
if exist "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" (
    set /a count+=1
    set "name[!count!]=Brave Browser"
    set "path[!count!]=C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
)

:: Check if any found
if %count%==0 (
    echo ❌ No compatible Chromium browser found.
    pause
    exit /b
)

:: Display Menu
echo Select a browser to launch:
for /L %%i in (1,1,%count%) do (
    echo [%%i] !name[%%i]!
)
echo.

:prompt
set /p "choice=Enter number (1-%count%): "

:: Validate Input
if "%choice%"=="" goto prompt
if %choice% LSS 1 goto prompt
if %choice% GTR %count% goto prompt

set "BROWSER=!path[%choice%]!"
set "BROWSER_NAME=!name[%choice%]!"

echo.
echo 🚀 Launching %BROWSER_NAME% with VULKAN backend...
echo Path: "%BROWSER%"
echo Data: "%USER_DATA%"
echo.

"%BROWSER%" %FLAGS% %URL%
pause
