
@echo ON

REM Set the name of the application
SET APP_NAME=ece_app

REM Set the entry point script
SET ENTRY_POINT=run_all_agents.py

REM Set the output directory
SET DIST_PATH=./dist

REM Set the build directory
SET BUILD_PATH=./build

REM Clean up previous builds
rmdir /s /q %DIST_PATH%
rmdir /s /q %BUILD_PATH%
del /q %APP_NAME%.spec

REM Run PyInstaller
pyinstaller --name %APP_NAME% ^
    --onefile ^
    --windowed ^
    --distpath %DIST_PATH% ^
    --workpath %BUILD_PATH% ^
    --add-data "config.yaml;." ^
    --add-data "config_executable.yaml;." ^
    --add-data "poml;poml" ^
    --add-data "ece;ece" ^
    %ENTRY_POINT%



