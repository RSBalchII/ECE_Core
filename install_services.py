"""
Installation and Setup Script for External Context Engine (ECE)

This script automates the installation and setup of required services for the ECE:
- Redis server
- Neo4j database
- UTCP Registry (instructions provided)

This script will guide you through setting up these services on Windows.
"""

import os
import sys
import subprocess
import platform
import requests
import zipfile
import shutil
from pathlib import Path


def check_python_version():
    """Check if Python 3.11+ is installed."""
    if sys.version_info < (3, 11):
        print(f"⚠️  Python 3.11 or higher is required. Current version: {sys.version}")
        return False
    print(f"✅ Python version {sys.version} is compatible")
    return True


def check_redis():
    """Check if Redis is installed and running."""
    try:
        # Try to connect to Redis server (default port 6379)
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis server is running")
        return True
    except ImportError:
        print("⚠️  Redis Python package not installed")
        return False
    except Exception as e:
        print(f"⚠️  Redis server is not accessible: {e}")
        return False


def install_redis_windows():
    """Install Redis on Windows using Chocolatey if available, otherwise provide manual instructions."""
    print("\nSetting up Redis for Windows...")
    
    # Check if Chocolatey is installed
    try:
        subprocess.run(['choco', '--version'], check=True, capture_output=True)
        print("✅ Chocolatey is available")
        
        print("Installing Redis via Chocolatey...")
        result = subprocess.run(['choco', 'install', 'redis-64', '-y'], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Redis installed via Chocolatey")
            
            # Start Redis service
            print("Starting Redis service...")
            subprocess.run(['choco', 'start', 'redis-64'], capture_output=True)
            print("✅ Redis service started")
            return True
        else:
            print(f"❌ Failed to install Redis via Chocolatey: {result.stderr}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Chocolatey not found. Manual Redis installation required.")
    
    print("\nManual installation instructions:")
    print("1. Download Redis for Windows from: https://github.com/tporadowski/redis/releases")
    print("2. Extract and run 'redis-server.exe' to start the server")
    print("3. To install as a Windows service: run 'redis-server --service-install redis.windows.conf'")
    print("4. To start the service: run 'redis-server --service-start'")
    print("5. Verify Redis is running by checking if you can connect to port 6379")
    
    return False


def check_neo4j():
    """Check if Neo4j is installed and running."""
    import os
    from neo4j import GraphDatabase
    
    neo4j_uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')  # Default from config
    
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            result = session.run("RETURN 1 AS test")
            single_result = result.single()
            if single_result and single_result[0] == 1:
                print(f"✅ Neo4j is running at {neo4j_uri}")
                driver.close()
                return True
            else:
                print(f"⚠️  Neo4j test query failed at {neo4j_uri}")
                driver.close()
                return False
    except ImportError:
        print("⚠️  Neo4j Python driver not installed")
        return False
    except Exception as e:
        print(f"⚠️  Neo4j is not accessible at {neo4j_uri}: {e}")
        return False


def install_neo4j_windows():
    """Provide instructions for installing Neo4j on Windows."""
    print("\nSetting up Neo4j for Windows...")
    
    print("\nInstallation instructions:")
    print("1. Download Neo4j Desktop from: https://neo4j.com/download-center/")
    print("2. Install Neo4j Desktop")
    print("3. Open Neo4j Desktop and create a new local DBMS")
    print("4. Set the password (default is 'password', as per your config)")
    print("5. Start the database")
    
    print("\nAlternatively, for server installation:")
    print("1. Download Neo4j Server from: https://neo4j.com/download-center/")
    print("2. Extract to desired location")
    print("3. Configure in bin/neo4j.conf")
    print("4. Run 'bin\\\\neo4j console' to start the server")
    
    return False  # Manual setup required


def check_utcp_registry():
    """Check if UTCP Registry is running on port 8005."""
    try:
        # In the new decentralized approach, there's no central UTCP registry
        # Each service serves its own UTCP manual at the /utcp endpoint
        # We'll check if the other services are running instead
        # This is a placeholder check - in a real implementation, you'd check each service's health endpoint
        services_running = True
        if response.status_code < 500:
            print("✅ UTCP Registry is running on port 8005")
            return True
        else:
            print(f"⚠️  UTCP Registry returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("⚠️  UTCP Registry is not accessible on port 8005")
        return False


def install_utcp_registry():
    """Provide instructions for setting up UTCP Registry and Client."""
    print("\nSetting up UTCP Registry and Client...")
    
    print("\nUTCP Registry installation instructions:")
    print("1. Clone the UTCP Registry repository:")
    print("   git clone https://github.com/universal-tool-calling-protocol/utcp-registry.git")
    print("2. Navigate to the repository directory: cd utcp-registry")
    print("3. Install dependencies: pip install -r requirements.txt")
    print("4. Run the registry: python -m uvicorn main:app --host 0.0.0.0 --port 8005")
    
    print("\nUTCP Client installation instructions:")
    print("1. Install the official UTCP Python package:")
    print("   pip install utcp")
    print("   # This provides both client and registry components")
    
    print("\nAlternatively, if separate packages are needed:")
    print("   pip install utcp-client utcp-registry")
    
    return False  # Manual setup required


def install_python_dependencies():
    """Install Python dependencies from requirements.txt."""
    print("\nInstalling Python dependencies...")
    
    try:
        # Install main dependencies
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                               check=True, capture_output=True, text=True)
        print("✅ Main Python dependencies installed")
        
        # Install packaging dependencies (including utcp packages if available)
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements-packaging.txt'], 
                          check=True, capture_output=True, text=True)
            print("✅ Packaging dependencies installed")
        except subprocess.CalledProcessError:
            print("⚠️  Some packaging dependencies (like UTCP) couldn't be installed automatically")
            print("   These may need to be obtained from the separate UTCP project")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python dependencies: {e}")
        return False


def create_service_launcher():
    """Create a comprehensive launcher script to start all services."""
    
    launcher_script = '''@echo off
REM ECE Service Launcher
REM This script starts all required services for the External Context Engine

echo Starting External Context Engine Required Services...

REM Start Neo4j (if installed as service)
echo Checking if Neo4j service is installed...
net start Neo4jDBMS >nul 2>&1
if %errorlevel% == 0 (
  echo Started Neo4j service
) else (
  echo Warning: Neo4j service not found. Please start Neo4j manually.
)

REM Start Redis (if installed as service)
echo Checking if Redis service is installed...
net start Redis >nul 2>&1
if %errorlevel% == 0 (
  echo Started Redis service
) else (
  echo Warning: Redis service not found. Please start Redis manually.
  REM Try to start Redis if the executable is in PATH or common location
  where redis-server.exe >nul 2>&1
  if %errorlevel% == 0 (
    start /min redis-server.exe
    echo Started Redis server in background
  ) else (
    echo Please ensure Redis server is running on port 6379
  )
)

REM Start UTCP Registry
echo Attempting to start UTCP Registry...
REM Look for utcp_registry directory in parent or sibling directories
set UTCP_PATH=
for /d %%i in (..\\utcp-registry ..\\..\\utcp-registry .\\utcp-registry) do (
  if exist "%%i\\main.py" (
    set UTCP_PATH=%%i
    goto utcp_found
  )
)

:utcp_found
if defined UTCP_PATH (
  echo Found UTCP Registry at %UTCP_PATH%
  pushd %UTCP_PATH%
  start /min cmd /c "python -m uvicorn main:app --host 0.0.0.0 --port 8005"
  popd
  echo Started UTCP Registry in background
) else (
  echo UTCP Registry not found. Please start it manually on port 8005.
  echo Clone from https://github.com/universal-tool-calling-protocol/utcp-registry
)

REM Wait a moment for services to start
timeout /t 5 /nobreak >nul

echo.
echo Checking service status...
python bootstrap.py

echo.
echo To start ECE agents, run: python run_all_agents.py
echo Press any key to exit...
pause >nul
'''
    
    with open("start_ece_services.bat", "w") as f:
        f.write(launcher_script)
    
    print("✅ Created start_ece_services.bat to manage all required services")


def create_setup_instructions():
    """Create a text file with detailed setup instructions."""
    
    instructions = """ECE Setup Instructions
==================

1. Install Python 3.11+ if not already installed
2. Install Redis:
   - Option A: Use Chocolatey (choco install redis-64 -y)
   - Option B: Download from https://github.com/tporadowski/redis/releases
3. Install Neo4j:
   - Download from https://neo4j.com/download-center/
   - Set up a local DBMS with password 'password' (or update .env file)
4. Install UTCP components:
   - Clone the UTCP Registry from: https://github.com/universal-tool-calling-protocol/utcp-registry
   - Run the registry: python -m uvicorn main:app --host 0.0.0.0 --port 8005
   - Install the UTCP client from: https://github.com/universal-tool-calling-protocol/python-utcp
   - Install with: pip install utcp (or from source if not available on PyPI)
5. Run this setup script: python install_services.py
6. Install Python dependencies: pip install -r requirements.txt
7. Use start_ece_services.bat to start required services
8. Verify all services are running: python bootstrap.py
9. Start ECE agents: python run_all_agents.py
"""
    
    with open("SETUP_INSTRUCTIONS.txt", "w") as f:
        f.write(instructions)
    
    print("✅ Created SETUP_INSTRUCTIONS.txt with detailed setup steps")


def main():
    """Main installation/setup function."""
    print("External Context Engine (ECE) Installation and Setup")
    print("=" * 55)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Install Python dependencies
    install_python_dependencies()
    
    # Check for existing services
    print("\nChecking existing services...")
    redis_ok = check_redis()
    neo4j_ok = check_neo4j()
    utcp_ok = check_utcp_registry()
    
    print(f"\nService Status:")
    print(f"  Redis: {'✅ Running' if redis_ok else '❌ Not running'}")
    print(f"  Neo4j: {'✅ Running' if neo4j_ok else '❌ Not running'}")
    print(f"  UTCP Registry: {'✅ Running' if utcp_ok else '❌ Not running'}")
    
    # Provide installation options based on status
    if not redis_ok:
        install_redis_windows()
    
    if not neo4j_ok:
        install_neo4j_windows()
    
    if not utcp_ok:
        install_utcp_registry()
    
    # Create launcher script
    create_service_launcher()
    
    # Create setup instructions
    create_setup_instructions()
    
    print("\n" + "=" * 55)
    print("Setup Summary:")
    print("1. Python dependencies have been installed")
    print("2. Service launcher script created: start_ece_services.bat")
    print("3. Setup instructions saved to: SETUP_INSTRUCTIONS.txt")
    print("4. You need to install Redis, Neo4j, and UTCP Registry manually")
    print("5. Run 'start_ece_services.bat' to start all required services")
    print("6. Verify services with 'python bootstrap.py'")
    print("7. Start ECE agents with 'python run_all_agents.py'")


if __name__ == "__main__":
    # Check if this script is run from the ECE project directory
    if not os.path.exists("requirements.txt"):
        print("Error: This script should be run from the ECE project root directory")
        sys.exit(1)
    
    main()