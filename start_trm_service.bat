@echo off
REM Script to start the TRM (Tokenized Reasoning Model) Mock Service
REM This service provides the Markovian Thinker functionality

echo Starting TRM Mock Service on port 8081...
echo This service provides Markovian thinking capabilities for the ECE.

REM Set the path to the TRM service
set TRM_SERVICE_PATH=ece\agents\common\trm_service_mock.py

REM Check if the file exists
if not exist "%TRM_SERVICE_PATH%" (
    echo Error: TRM service file not found at %TRM_SERVICE_PATH%
    echo Please make sure you are running this from the ECE root directory.
    pause
    exit /b 1
)

REM Start the TRM service
echo Starting TRM service with uvicorn...
python -m uvicorn "ece.agents.common.trm_service_mock:app" --host 0.0.0.0 --port 8081

echo TRM service has stopped.
pause