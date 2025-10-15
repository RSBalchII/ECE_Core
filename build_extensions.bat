@echo off
REM Build script for ECE optimized modules using Cython
REM This script compiles the C++ extensions for the QLearning and Distiller agents

echo Building ECE optimized modules with Cython...

REM Make sure we're in the right directory
cd /d "C:\Users\rsbiiw\Projects\External-Context-Engine-ECE"

REM Build the Cython extensions
python setup.py build_ext --inplace

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build completed successfully!
    echo Optimized modules are now available for use in the ECE.
) else (
    echo.
    echo Build failed. Please check the error messages above.
    echo Make sure you have Cython, setuptools, and a C++ compiler installed.
)

pause