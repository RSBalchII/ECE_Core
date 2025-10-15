# ECE Packaging and Distribution Guide

This document describes the process for packaging the External Context Engine into a distributable executable.

## Overview

The ECE can be packaged into a single executable using PyInstaller. This makes distribution and deployment easier, as users don't need to install Python or manage dependencies manually.

## Prerequisites

- Python 3.10+ installed on the build machine
- PyInstaller: `pip install pyinstaller`
- All ECE dependencies installed: `pip install -r requirements.txt`

## Packaging Process

### 1. Prepare the Application for Packaging

Before packaging, ensure:
- All configuration files (config.yaml, .env) are properly set up
- The application runs correctly in its development environment
- All required services (Redis, Neo4j) are accessible

### 2. Build the Executable

Use the appropriate build script for your platform:

**Windows:**
```
build_package.bat
```

**Linux/macOS:**
```
chmod +x build_package.sh
./build_package.sh
```

This will create the executable in the `dist/` directory.

### 3. The PyInstaller Spec File

The packaging process uses `ece_app.spec`, which defines:
- All necessary data files to include (config.yaml, POML files, etc.)
- Hidden imports needed by the application
- Binary files to include (C++ extensions)
- Exclusion of unnecessary modules to reduce size

### 4. Bootstrapping Mechanism

The packaged application includes a bootstrapping process that:
- Checks for required services (Redis, Neo4j, LLM service, UTCP Registry)
- Reports which services are unavailable
- Only starts the agents when all required services are available

## Running the Packaged Application

After successful packaging, you can run the application directly:
- Windows: `dist\ece_app.exe`
- Linux/macOS: `dist/ece_app`

Or use the convenience scripts:
- Windows: `run_packaged_ece.bat`
- Linux/macOS: `run_packaged_ece.sh`

## Deployment Requirements

The packaged application requires these external services to be running:

1. **Redis Server**: For caching functionality
2. **Neo4j Database**: For knowledge graph storage
3. **LLM Service**: Either Ollama, llama.cpp, or Docker Desktop service
4. **UTCP Registry**: For tool discovery (if UTCP features are used)

## Testing the Packaged Application

Before distributing, test the packaged application on a clean system without Python installed to ensure all dependencies are properly included.

Run the packaging verification tests:
```bash
python -m pytest Tests/test_packaging_verification.py
```

## Troubleshooting

### Common Issues

1. **Missing Modules**: If a module is not found at runtime, add it to the `hiddenimports` list in `ece_app.spec`

2. **Missing Data Files**: Ensure all required data files are listed in the `datas` list in `ece_app.spec`

3. **C++ Extensions**: If C++ extensions are not working, ensure the appropriate platform-specific binaries are included in the spec file

4. **Large File Size**: If the executable is too large, consider using UPX compression or excluding unnecessary modules

### Verifying Service Dependencies

Use the `bootstrap.py` script to test service connectivity before running the full application:

```bash
python bootstrap.py
```

This will perform all the same service checks as the packaged application but in a more verbose manner.

## Updating the Packaged Application

To update the packaged application:
1. Make code changes
2. Run all tests to ensure functionality
3. Rebuild the package using the build scripts
4. Test the new executable
5. Distribute the updated executable

## Versioning and Updates

The packaged application should include version information in its filename, e.g., `ece_app_v1.2.3.exe`.

Future enhancements may include:
- Auto-update functionality
- Version-specific configuration handling
- Rollback capabilities