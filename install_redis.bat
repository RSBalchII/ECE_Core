@echo off
REM Redis Installation Script for ECE
REM This script installs and starts Redis on Windows

echo Installing Redis for ECE...

REM Check if Chocolatey is installed
choco --version >nul 2>&1
if %errorlevel% == 0 (
  echo Installing Redis using Chocolatey...
  choco install redis-64 -y
  if %errorlevel% == 0 (
    echo Starting Redis service...
    redis-server --service-install redis.windows.conf --loglevel verbose
    redis-server --service-start
    
    echo Redis installed and started successfully
    echo You can stop the service with: redis-server --service-stop
  ) else (
    echo Failed to install Redis via Chocolatey
  )
) else (
  echo Chocolatey not found, checking for manual Redis installation...

  REM Check if redis-server is in PATH
  where redis-server >nul 2>&1
  if %errorlevel% == 0 (
    echo Redis server is already available in PATH
  ) else (
    echo Please install Redis manually:
    echo 1. Download from https://github.com/tporadowski/redis/releases
    echo 2. Extract the files to a directory
    echo 3. Add that directory to your system PATH environment variable
    echo 4. Start Redis with: redis-server.exe
  )
)

echo.
echo To verify Redis is running, use: redis-cli ping
echo This should return 'PONG' if Redis is running correctly.

pause