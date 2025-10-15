@echo off
REM Neo4j Installation Script for ECE
REM This script provides instructions for installing Neo4j on Windows

echo Installing Neo4j for ECE...

echo Neo4j Installation Options:
echo.
echo Option 1: Neo4j Desktop (Recommended for development)
echo   1. Download from: https://neo4j.com/download-center/
echo   2. Install Neo4j Desktop
echo   3. Create a new local DBMS
echo   4. Set password to 'password' (or update your .env file)
echo   5. Start the database
echo.
echo Option 2: Neo4j Server
echo   1. Download from: https://neo4j.com/download-center/
echo   2. Extract to desired location (e.g., C:\neo4j)
echo   3. Navigate to the installation directory
echo   4. Modify data/conf/neo4j.conf to set password and other settings
echo   5. Start with: bin\neo4j console
echo.
echo Required Configuration for ECE:
echo   - Username: neo4j (default)
echo   - Password: password (or as configured in your .env file)
echo   - Port: 7687 (default Bolt port)
echo.
echo After installation, verify the connection with your .env settings:
echo   NEO4J_URI=neo4j://localhost:7687
echo   NEO4J_USER=neo4j
echo   NEO4J_PASSWORD=password

echo.
echo Press any key to continue...
pause