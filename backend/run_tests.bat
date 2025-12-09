@echo off
REM run_tests.bat - Run test suite for ECE_Core

echo =========================================
echo   ECE_Core Test Suite
echo =========================================
echo.

REM Check if pytest is installed
python -c "import pytest" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

echo Running tests...
echo.

REM Run tests with coverage
pytest tests/ ^
    --verbose ^
    --cov=. ^
    --cov-report=term-missing ^
    --cov-report=html:coverage_html ^
    --tb=short

REM Check exit code
if %errorlevel% equ 0 (
    echo.
    echo All tests passed!
    echo.
    echo Coverage report: coverage_html\index.html
) else (
    echo.
    echo Some tests failed
    exit /b 1
)
