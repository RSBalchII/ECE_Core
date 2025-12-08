@echo off
REM Utility script to stop all ECE-related processes
REM This can help when services get stuck

echo Stopping ECE-related processes...
echo.

REM Find and kill processes by name
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "start_ece.py">NUL
if "%ERRORLEVEL%"=="0" taskkill /F /IM "start_ece.py" 2>NUL

tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "start_llm_server.py">NUL  
if "%ERRORLEVEL%"=="0" taskkill /F /IM "start_llm_server.py" 2>NUL

tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "start_embedding_server.py">NUL
if "%ERRORLEVEL%"=="0" taskkill /F /IM "start_embedding_server.py" 2>NUL

tasklist /FI "IMAGENAME eq llama-server.exe" 2>NUL | find /I /N "llama-server.exe">NUL
if "%ERRORLEVEL%"=="0" taskkill /F /IM "llama-server.exe" 2>NUL

echo Services stopped (if running).
echo.
echo You can also check Task Manager for any remaining Python or llama-server processes.
pause