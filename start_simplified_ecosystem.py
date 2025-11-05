#!/usr/bin/env python3
"""
Simplified ECE Startup Script

This script starts both the ECE ecosystem and the llama.cpp model server
with output routed through the run_simplified_ecosystem.py script to logs/ece-llamacpp.txt.
"""

import subprocess
import sys
import time
import os
import argparse
from pathlib import Path
import signal
import psutil
import requests
from dotenv import dotenv_values

# Load environment variables from .env file
config = dotenv_values(".env")  # Load environment variables


# Simple print wrapper functions for consistency
def print_info(message):
    print(f"{message}")


def print_error(message):
    print(f"[ERROR] {message}")


def print_success(message):
    print(f"[SUCCESS] {message}")


def print_warning(message):
    print(f"[WARNING] {message}")


def print_debug(message):
    print(f"[DEBUG] {message}")


class SimplifiedECEStartup:
    def __init__(self):
        self.processes = []
        self.running = True

    def find_llama_cpp_server(self):
        """Find the llama.cpp server executable."""
        # Check if server executable path is specified in environment variable
        server_exe_path = os.getenv("LLAMA_CPP_SERVER_PATH")
        if server_exe_path:
            server_exe = Path(server_exe_path)
            if server_exe.exists():
                print_info(
                    f"Found llama.cpp server executable from environment: {server_exe}"
                )
                return server_exe

        # Common locations for the server executable
        possible_paths = [
            Path("llama.cpp/server.exe"),  # Windows
            Path("llama.cpp/server"),  # Linux/Mac
            Path("llama.cpp/llama-server.exe"),  # Windows alternative
            Path("llama.cpp/llama-server"),  # Linux/Mac alternative
            Path("llama.cpp/bin/Release/server.exe"),  # Windows build
            Path("llama.cpp/build/bin/Release/server.exe"),  # Windows build
            Path("llama.cpp/build/bin/server.exe"),  # Alternative Windows build
            Path("llama.cpp/build/server.exe"),  # Another alternative Windows build
            Path(
                "llama.cpp/build/bin/Release/llama-server.exe"
            ),  # Windows build alternative name
            Path(
                "llama.cpp/build/bin/llama-server.exe"
            ),  # Alternative Windows build alternative name
            Path(
                "llama.cpp/build/llama-server.exe"
            ),  # Another alternative Windows build alternative name
            Path("llama.cpp/bin/server.exe"),  # Alternative Windows build location
            Path(
                "llama.cpp/bin/llama-server.exe"
            ),  # Alternative Windows build location alternative name
        ]

        # Also check in the build directory after cmake build
        build_dirs = [
            Path("llama.cpp/build"),
            Path("llama.cpp/build/bin"),
            Path("llama.cpp/build/bin/Release"),
            Path("llama.cpp/bin"),
            Path("llama.cpp/bin/Release"),
        ]

        # Check for executable files in build directories
        for build_dir in build_dirs:
            if build_dir.exists():
                # Look for server executables in the build directory
                for exe_name in [
                    "server.exe",
                    "server",
                    "llama-server.exe",
                    "llama-server",
                ]:
                    exe_path = build_dir / exe_name
                    if exe_path.exists():
                        print_info(f"Found llama.cpp server executable: {exe_path}")
                        return exe_path

        # Check the predefined paths
        for path in possible_paths:
            if path.exists():
                print_info(f"Found llama.cpp server executable: {path}")
                return path

        print_warning("llama.cpp server executable not found in common locations")
        print_info("")
        print_info("Troubleshooting llama.cpp server:")
        print_info(
            "- Make sure llama.cpp is properly cloned in the llama.cpp directory"
        )
        print_info("- Build llama.cpp using CMake and a C++ compiler")
        print_info(
            "- Install build tools (CMake and C++ compiler) if not already installed"
        )
        print_info(
            "- Download a pre-built llama.cpp server binary from https://github.com/ggerganov/llama.cpp/releases"
        )
        print_info("- Install llama-cpp-python: pip install llama-cpp-python")
        print_info("- Use a different model serving approach")
        print_info("")
        print_info("Alternative solutions:")
        print_info(
            "1. Install Visual Studio Community with C++ development tools and try again"
        )
        print_info("2. Install CMake from https://cmake.org/download/")
        print_info("3. Install MinGW-w64 for Windows or GCC for Linux/Mac")
        print_info(
            "4. Download a pre-built llama.cpp server binary from the releases page"
        )
        print_info("5. Install llama-cpp-python package: pip install llama-cpp-python")
        return None

    def build_llama_cpp(self):
        """Build llama.cpp if not already built."""
        print_info("Attempting to build llama.cpp...")

        # Check if llama.cpp directory exists
        if not Path("llama.cpp").exists():
            print_error("llama.cpp directory not found")
            print_info("")
            print_info("Troubleshooting llama.cpp build:")
            print_info(
                "- Make sure llama.cpp is properly cloned in the llama.cpp directory"
            )
            print_info(
                "- Clone llama.cpp: git clone https://github.com/ggerganov/llama.cpp"
            )
            print_info(
                "- Check that the llama.cpp directory exists in the current directory"
            )
            return False

        # Check if build tools are available
        if not self.check_build_tools():
            print_error(
                "Build tools not found. Please install CMake and a C++ compiler (Visual Studio, GCC, or Clang)"
            )
            print_info("")
            print_info("Alternative solutions:")
            print_info("1. Install Visual Studio Community with C++ development tools")
            print_info("2. Install CMake from https://cmake.org/download/")
            print_info("3. Install MinGW-w64 for Windows or GCC for Linux/Mac")
            print_info("4. Use a pre-built llama.cpp server binary")
            print_info(
                "5. Install llama-cpp-python package: pip install llama-cpp-python"
            )
            print_info("")
            print_info("For more information, see the documentation in README.md")
            return False

        try:
            # Try to build using cmake
            print_info("Building llama.cpp with cmake...")

            # Create build directory
            build_dir = Path("llama.cpp/build")
            build_dir.mkdir(exist_ok=True)

            # Configure CMake
            cmake_cmd = [
                "cmake",
                "..",
                "-G",
                "Visual Studio 17 2022",  # Windows default
            ]

            # Check if we're on a non-Windows system
            import platform

            if platform.system().lower() != "windows":
                cmake_cmd = ["cmake", ".."]  # Linux/Mac default

            result = subprocess.run(
                cmake_cmd, cwd=build_dir, capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                print_error(f"CMake configuration failed: {result.stderr}")
                print_info("")
                print_info("Troubleshooting CMake configuration:")
                print_info(
                    "- Try installing Visual Studio Community with C++ development tools"
                )
                print_info("- Install CMake from https://cmake.org/download/")
                print_info(
                    "- Check that the CMake version is compatible with llama.cpp"
                )
                print_info("- Verify that all required dependencies are installed")
                print_info(
                    "- Try running cmake manually: cd llama.cpp/build && cmake .."
                )
                print_info("")
                print_info("For more information, see the documentation in README.md")
                return False

            # Build
            build_cmd = ["cmake", "--build", ".", "--config", "Release"]
            result = subprocess.run(
                build_cmd, cwd=build_dir, capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                print_error(f"Build failed: {result.stderr}")
                print_info("")
                print_info("Troubleshooting build process:")
                print_info(
                    "- Try installing Visual Studio Community with C++ development tools"
                )
                print_info("- Check that the CMake configuration was successful")
                print_info("- Verify that all required dependencies are installed")
                print_info(
                    "- Try running the build manually: cd llama.cpp/build && cmake --build . --config Release"
                )
                print_info("- Check the build logs for detailed error information")
                print_info("")
                print_info("For more information, see the documentation in README.md")
                return False

            print_success("[SUCCESS] llama.cpp built successfully")
            return True
        except subprocess.TimeoutExpired:
            print_error("Build timed out")
            print_info("")
            print_info("Troubleshooting build timeout:")
            print_info("- The build process may take a long time on slower systems")
            print_info("- Increase the timeout value in the script if needed")
            print_info("- Check system resources (CPU, memory, disk space)")
            print_info(
                "- Try building manually: cd llama.cpp/build && cmake --build . --config Release"
            )
            print_info("")
            print_info("For more information, see the documentation in README.md")
            return False
        except Exception as e:
            print_error(f"Error building llama.cpp: {e}")
            print_info("")
            print_info("Troubleshooting build errors:")
            print_info("- Make sure all build tools are properly installed")
            print_info("- Check that the llama.cpp directory structure is correct")
            print_info("- Verify that all required dependencies are installed")
            print_info(
                "- Try building manually: cd llama.cpp/build && cmake --build . --config Release"
            )
            print_info("- Check the build logs for detailed error information")
            print_info("")
            print_info("For more information, see the documentation in README.md")
            return False

    def check_build_tools(self):
        """Check if required build tools are available."""
        try:
            # Check for cmake
            cmake_result = subprocess.run(
                ["cmake", "--version"], capture_output=True, text=True, timeout=10
            )
            if cmake_result.returncode != 0:
                print_warning("CMake not found")
                print_info("")
                print_info("Troubleshooting build tools:")
                print_info("- Install CMake from https://cmake.org/download/")
                print_info(
                    "- Make sure CMake is added to your PATH environment variable"
                )
                print_info(
                    "- Restart your terminal/command prompt after installing CMake"
                )
                print_info(
                    "- Check that the CMake version is compatible with llama.cpp"
                )
                return False

            # Check for compiler (try different options)
            compilers_to_check = [
                ["cl", "/?"],  # MSVC
                ["gcc", "--version"],  # GCC
                ["clang", "--version"],  # Clang
            ]

            compiler_found = False
            for compiler_cmd in compilers_to_check:
                try:
                    result = subprocess.run(
                        compiler_cmd, capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        compiler_found = True
                        print_info(f"Found compiler: {' '.join(compiler_cmd[:-1])}")
                        break
                except:
                    continue

            if not compiler_found:
                print_warning("No C++ compiler found")
                print_info("")
                print_info("Troubleshooting build tools:")
                print_info("- Install a C++ compiler (Visual Studio, GCC, or Clang)")
                print_info(
                    "- For Windows: Install Visual Studio Community with C++ development tools"
                )
                print_info(
                    "- For Linux: Install GCC with 'sudo apt-get install build-essential'"
                )
                print_info(
                    "- For Mac: Install Xcode command line tools with 'xcode-select --install'"
                )
                print_info(
                    "- Make sure the compiler is added to your PATH environment variable"
                )
                print_info(
                    "- Restart your terminal/command prompt after installing the compiler"
                )
                print_info(
                    "- Check that the compiler version is compatible with llama.cpp"
                )
                return False

            print_success("[SUCCESS] Build tools found: CMake and C++ compiler")
            return True
        except Exception as e:
            print_warning(f"Error checking build tools: {e}")
            print_info("")
            print_info("Troubleshooting build tools:")
            print_info("- Install CMake from https://cmake.org/download/")
            print_info("- Install a C++ compiler (Visual Studio, GCC, or Clang)")
            print_info(
                "- For Windows: Install Visual Studio Community with C++ development tools"
            )
            print_info(
                "- For Linux: Install GCC with 'sudo apt-get install build-essential'"
            )
            print_info(
                "- For Mac: Install Xcode command line tools with 'xcode-select --install'"
            )
            print_info(
                "- Make sure all build tools are added to your PATH environment variable"
            )
            print_info(
                "- Restart your terminal/command prompt after installing build tools"
            )
            print_info(
                "- Check that the build tool versions are compatible with llama.cpp"
            )
            return False

    def start_llama_server(self, model_path, port):
        """Start the llama.cpp server with the specified model."""
        print_info(f"Starting llama.cpp server on port {port}...")
        print_info(f"Using model: {model_path}")

        # Check if model file exists
        model_file = Path(model_path)
        if not model_file.exists():
            print_error(f"Model file not found: {model_path}")
            print_info("")
            print_info("Troubleshooting model file:")
            print_info(
                "- Please download or place the model file in the models directory"
            )
            print_info("- Check that the model file path is correct")
            print_info("- Verify that the file exists in the specified location")
            print_info("- Make sure the model file is a valid GGUF file")
            print_info(
                "- Check that you have sufficient permissions to access the model file"
            )
            return False

        # Find server executable
        server_exe = self.find_llama_cpp_server()
        if not server_exe:
            print("Attempting to build llama.cpp...")
            if self.build_llama_cpp():
                server_exe = self.find_llama_cpp_server()

            if not server_exe:
                print(
                    "Cannot start llama.cpp server - executable not found and build failed"
                )
                print("")
                print("Troubleshooting steps:")
                print("1. Install build tools (CMake and C++ compiler) and try again")
                print("2. Download a pre-built llama.cpp server binary")
                print("3. Install llama-cpp-python: pip install llama-cpp-python")
                print("4. Use a different model serving approach")
                print("")
                print("Alternative solutions:")
                print("- Install Visual Studio Community with C++ development tools")
                print("- Install CMake from https://cmake.org/download/")
                print("- Install MinGW-w64 for Windows or GCC for Linux/Mac")
                print(
                    "- Download a pre-built llama.cpp server binary from https://github.com/ggerganov/llama.cpp/releases"
                )
                print(
                    "- Install llama-cpp-python package: pip install llama-cpp-python"
                )
                print("")
                print("For more information, see the documentation in README.md")
                return False

        # Get configuration from environment variables
        context_size = os.getenv("LLAMA_CPP_CONTEXT_SIZE", "4096")
        n_gpu_layers = os.getenv("LLAMA_CPP_N_GPU_LAYERS", "-1")
        timeout = os.getenv("LLAMA_CPP_TIMEOUT", "1800")

        # Build the command
        cmd = [
            str(server_exe),
            "-m",
            str(model_file),
            "-c",
            str(context_size),
            "--n-gpu-layers",
            str(n_gpu_layers),
            "--timeout",
            str(timeout),
            "--port",
            str(port),
            "--host",
            "0.0.0.0",
        ]

        print(f"Running command: {' '.join(cmd)}")

        try:
            # Start the server process with real-time output streaming
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
            )
            self.processes.append(("llama.cpp server", process))
            print(f"[SUCCESS] llama.cpp server started with PID {process.pid}")

            # Stream output in real-time
            import threading

            def stream_output(pipe, prefix=""):
                for line in iter(pipe.readline, ""):
                    if line.strip():  # Only print non-empty lines
                        print(f"[llama.cpp] {line.rstrip()}")
                pipe.close()

            # Start threads to handle stdout and stderr
            stdout_thread = threading.Thread(
                target=stream_output, args=(process.stdout,)
            )
            stderr_thread = threading.Thread(
                target=stream_output, args=(process.stderr,)
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait briefly to see if it starts successfully
            time.sleep(3)

            if process.poll() is not None:
                # Process has already exited
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)

                print(
                    f"✗ llama.cpp server failed to start. Exit code: {process.returncode}"
                )
                print("")
                print("Troubleshooting llama.cpp server startup:")
                print(
                    "- Check that the model file is valid and compatible with llama.cpp"
                )
                print("- Verify that the model file path is correct")
                print("- Ensure sufficient system resources (memory, GPU VRAM)")
                print("- Check that the port is not already in use")
                print(
                    "- Verify that the llama.cpp server executable is compatible with your system"
                )
                print(
                    "- Try running the command manually to see detailed error messages"
                )
                print("- Check the logs in the logs/ directory for more information")
                return False

            print("[SUCCESS] llama.cpp server started successfully")
            return True

        except Exception as e:
            print(f"Error starting llama.cpp server: {e}")
            print("")
            print("Troubleshooting llama.cpp server startup:")
            print("- Check that the model file is valid and compatible with llama.cpp")
            print("- Verify that the model file path is correct")
            print("- Ensure sufficient system resources (memory, GPU VRAM)")
            print("- Check that the port is not already in use")
            print(
                "- Verify that the llama.cpp server executable is compatible with your system"
            )
            print("- Try running the command manually to see detailed error messages")
            print("- Check the logs in the logs/ directory for more information")
            return False

    def start_docker_services(self):
        """Start Redis and Neo4j services using docker-compose."""
        print("Starting Redis and Neo4j services...")

        try:
            # Get docker compose file path from environment
            compose_file_path = os.getenv("DOCKER_COMPOSE_FILE", "docker-compose.yml")
            compose_file = Path(compose_file_path)
            if not compose_file.exists():
                print(f"Error: Docker compose file not found: {compose_file_path}")
                print("")
                print("Troubleshooting Docker services:")
                print(
                    "- Make sure you're running this script from the project root directory"
                )
                print(
                    f"- Check that {compose_file_path} exists in the current directory"
                )
                print("- Verify Docker Desktop is installed and running")
                print("- Ensure you have sufficient permissions to run Docker commands")
                print("- Restart your terminal/command prompt after installing Docker")
                print("- Check that the Docker daemon is running properly")
                return False

            # Check if Docker is available
            try:
                docker_result = subprocess.run(
                    ["docker", "--version"], capture_output=True, text=True, timeout=10
                )
                if docker_result.returncode != 0:
                    print("Error: Docker not found")
                    print("")
                    print("Troubleshooting Docker services:")
                    print(
                        "- Install Docker Desktop from https://www.docker.com/products/docker-desktop"
                    )
                    print("- Make sure Docker Desktop is running")
                    print("- Add Docker to your PATH environment variable")
                    print(
                        "- Restart your terminal/command prompt after installing Docker"
                    )
                    print("- Check that the Docker daemon is running properly")
                    print(
                        "- Verify that Docker has sufficient system resources allocated"
                    )
                    return False
            except Exception as e:
                print(f"Error checking Docker availability: {e}")
                print("")
                print("Troubleshooting Docker services:")
                print(
                    "- Install Docker Desktop from https://www.docker.com/products/docker-desktop"
                )
                print("- Make sure Docker Desktop is running")
                print("- Add Docker to your PATH environment variable")
                print("- Restart your terminal/command prompt after installing Docker")
                print("- Check that the Docker daemon is running properly")
                print("- Verify that Docker has sufficient system resources allocated")
                return False

            # Start services with real-time output
            process = subprocess.Popen(
                [
                    "docker-compose",
                    "-f",
                    compose_file_path,
                    "up",
                    "--remove-orphans",
                    "-d",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
            )

            # Stream docker-compose output in real-time
            import threading

            def stream_output(pipe, prefix=""):
                for line in iter(pipe.readline, ""):
                    if line.strip():  # Only print non-empty lines
                        print(f"[docker] {line.rstrip()}")
                pipe.close()

            # Start threads to handle stdout and stderr
            stdout_thread = threading.Thread(
                target=stream_output, args=(process.stdout,)
            )
            stderr_thread = threading.Thread(
                target=stream_output, args=(process.stderr,)
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for the process to complete
            process.wait()

            # Wait for threads to finish
            stdout_thread.join()
            stderr_thread.join()

            if process.returncode == 0:
                print("[SUCCESS] Redis and Neo4j services started successfully")
                return True
            else:
                print(
                    f"✗ Failed to start Docker services with return code: {process.returncode}"
                )
                print("")
                print("Troubleshooting Docker services:")
                print("- Make sure Docker Desktop is installed and running")
                print(
                    "- Check that Neo4j and Redis containers are configured in docker-compose.yml"
                )
                print("- Verify Docker has sufficient resources allocated")
                print(
                    "- Try running 'docker-compose -f {} up --remove-orphans -d' manually to see detailed error messages".format(
                        compose_file_path
                    )
                )
                print("- Check Docker logs for more information: 'docker-compose logs'")
                print("- Restart Docker Desktop and try again")
                print("- Check that the Docker daemon is running properly")
                print("- Verify that Docker has sufficient system resources allocated")
                print(
                    "- Ensure no conflicting containers are running on the same ports"
                )
                return False
        except subprocess.CalledProcessError as e:
            print(f"Failed to start Docker services: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            print("")
            print("Troubleshooting Docker services:")
            print("- Make sure Docker Desktop is installed and running")
            print(
                "- Check that Neo4j and Redis containers are configured in docker-compose.yml"
            )
            print("- Verify Docker has sufficient resources allocated")
            print(
                "- Try running 'docker-compose -f {} up --remove-orphans -d' manually to see detailed error messages".format(
                    compose_file_path
                )
            )
            print("- Check Docker logs for more information: 'docker-compose logs'")
            print("- Restart Docker Desktop and try again")
            print("- Check that the Docker daemon is running properly")
            print("- Verify that Docker has sufficient system resources allocated")
            print("- Ensure no conflicting containers are running on the same ports")
            return False
        except Exception as e:
            print(f"Unexpected error starting Docker services: {e}")
            print("")
            print("Troubleshooting Docker services:")
            print("- Make sure Docker Desktop is installed and running")
            print(
                "- Check that Neo4j and Redis containers are configured in docker-compose.yml"
            )
            print("- Verify Docker has sufficient resources allocated")
            print(
                "- Try running 'docker-compose -f {} up --remove-orphans -d' manually to see detailed error messages".format(
                    compose_file_path
                )
            )
            print("- Check Docker logs for more information: 'docker-compose logs'")
            print("- Restart Docker Desktop and try again")
            print("- Check that the Docker daemon is running properly")
            print("- Verify that Docker has sufficient system resources allocated")
            print("- Ensure no conflicting containers are running on the same ports")
            return False

    def start_ece_agents(self):
        """Start all ECE agents."""
        print("Starting ECE agents...")

        try:
            # Change to ece directory
            ece_dir = Path("ece")
            if not ece_dir.exists():
                print("Error: ece directory not found")
                print("")
                print("Troubleshooting ECE agents:")
                print(
                    "- Make sure you're running this script from the project root directory"
                )
                print("- Check that the ece directory exists in the current directory")
                print("- Verify that all ECE components are properly installed")
                print(
                    "- Ensure Python dependencies are installed: pip install -r requirements.txt"
                )
                print("- Check that the ECE directory structure is correct")
                print(
                    "- Restart your terminal/command prompt after installing dependencies"
                )
                return False

            # Start the orchestrator agent first
            orchestrator_path = (
                ece_dir / "agents" / "tier1" / "orchestrator" / "main.py"
            )
            if not orchestrator_path.exists():
                print(f"Error: Orchestrator agent not found: {orchestrator_path}")
                print("")
                print("Troubleshooting ECE agents:")
                print("- Make sure the ECE directory structure is correct")
                print("- Check that all ECE components are properly installed")
                print(
                    "- Verify that orchestrator agent exists at ece/agents/tier1/orchestrator/main.py"
                )
                print(
                    "- Ensure Python dependencies are installed: pip install -r requirements.txt"
                )
                print(
                    "- Restart your terminal/command prompt after installing dependencies"
                )
                print(
                    "- Check that the ECE directory structure matches the expected layout"
                )
                return False

            # Use uvicorn to run the orchestrator as a proper ASGI server
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "ece.agents.tier1.orchestrator.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ]
            print(f"Running ECE orchestrator: {' '.join(cmd)}")

            # Start the orchestrator process with real-time output streaming
            import threading

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
            )
            self.processes.append(("ECE orchestrator", process))
            print(f"[SUCCESS] ECE orchestrator started with PID {process.pid}")

            # Stream orchestrator output in real-time
            def stream_output(pipe, prefix=""):
                for line in iter(pipe.readline, ""):
                    if line.strip():  # Only print non-empty lines
                        print(f"[orchestrator] {line.rstrip()}")
                pipe.close()

            # Start threads to handle stdout and stderr
            stdout_thread = threading.Thread(
                target=stream_output, args=(process.stdout,)
            )
            stderr_thread = threading.Thread(
                target=stream_output, args=(process.stderr,)
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for orchestrator to be ready with reduced timeout
            orchestrator_port = os.getenv("ORCHESTRATOR_PORT", "8000")
            if not self.wait_for_service(
                f"http://localhost:{orchestrator_port}/health",
                "ECE Orchestrator",
                timeout=30,
            ):  # Reduced from 60
                print(
                    "ECE Orchestrator failed to become ready within the timeout period"
                )
                return False

            # Start other agents (Distiller, QLearning, Archivist, etc.)
            # For simplicity, we'll start them using the run_all_agents.py script if it exists
            run_all_script = Path("utility_scripts/run_all_agents.py")
            if run_all_script.exists():
                cmd = [sys.executable, str(run_all_script)]
                print(f"Running ECE agents: {' '.join(cmd)}")

                # Start agents with real-time output streaming
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1,
                )
                self.processes.append(("ECE agents", process))
                print(f"[SUCCESS] ECE agents started with PID {process.pid}")

                # Stream agents output in real-time
                def stream_agents_output(pipe, prefix=""):
                    for line in iter(pipe.readline, ""):
                        if line.strip():  # Only print non-empty lines
                            print(f"[agents] {line.rstrip()}")
                    pipe.close()

                # Start threads to handle stdout and stderr
                agents_stdout_thread = threading.Thread(
                    target=stream_agents_output, args=(process.stdout,)
                )
                agents_stderr_thread = threading.Thread(
                    target=stream_agents_output, args=(process.stderr,)
                )

                agents_stdout_thread.start()
                agents_stderr_thread.start()

                # Wait for the agents to start up (reduced wait time)
                time.sleep(2)  # Reduced from 5

                # Check if the agents are ready by testing their endpoints
                agents_ready = True
                port_checks = [
                    (os.getenv("DISTILLER_PORT", "8001"), "Distiller"),
                    (os.getenv("QLEARNING_PORT", "8002"), "QLearning"),
                    (os.getenv("ARCHIVIST_PORT", "8003"), "Archivist"),
                    (os.getenv("INJECTOR_PORT", "8004"), "Injector"),
                    (os.getenv("FILESYSTEM_PORT", "8006"), "FileSystem"),
                    (os.getenv("WEBSEARCH_PORT", "8007"), "WebSearch"),
                ]

                for port, name in port_checks:
                    if not self.wait_for_port(
                        f"ECE {name}", int(port), timeout=15
                    ):  # Reduced from 45
                        print(f"ECE {name} on port {port} is not responding")
                        agents_ready = False
                    else:
                        print(f"ECE {name} on port {port} is responding")

                if agents_ready:
                    print("All ECE agents started and responding successfully")
                else:
                    print("Some ECE agents might not be responding yet, continuing...")

            else:
                print("run_all_agents.py not found, starting orchestrator only...")
                print(
                    "Consider creating utility_scripts/run_all_agents.py for a complete agent setup"
                )

            print("[SUCCESS] ECE agents started successfully")
            return True

        except Exception as e:
            print(f"Error starting ECE agents: {e}")
            print("")
            print("Troubleshooting ECE agents:")
            print(
                "- Make sure all Python dependencies are installed: pip install -r requirements.txt"
            )
            print("- Check that the ECE directory structure is correct")
            print("- Verify that Redis and Neo4j services are running")
            print("- Check logs in the logs/ directory for detailed error information")
            print("- Ensure Docker services are properly configured and running")
            print(
                "- Restart your terminal/command prompt after installing dependencies"
            )
            print("- Check that all required Python packages are properly installed")
            print(
                "- Verify that the ECE components are compatible with your Python version"
            )
            return False

    def stop_all_processes(self):
        """Stop all started processes."""
        print("Stopping all processes...")

        for name, process in self.processes:
            try:
                if process.poll() is None:  # Process is still running
                    print(f"Terminating {name} (PID {process.pid})...")
                    process.terminate()

                    # Wait for graceful termination
                    try:
                        process.wait(timeout=10)
                        print(f"[SUCCESS] {name} terminated gracefully")
                    except subprocess.TimeoutExpired:
                        print(f"Force killing {name}...")
                        process.kill()
                        process.wait()
                        print(f"[SUCCESS] {name} force killed")
            except Exception as e:
                print(f"Error stopping {name}: {e}")

        print("[INFO] All processes stopped")

    def wait_for_service(self, url, service_name, timeout=30):  # Reduced from 60
        """Wait for a service to be ready by checking its health endpoint."""
        import time
        import requests
        from requests.exceptions import RequestException

        print(
            f"Waiting for {service_name} to become ready at {url}... (timeout: {timeout}s)"
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=2)  # Reduced from 5
                if response.status_code == 200:
                    print(f"[SUCCESS] {service_name} is ready at {url}")
                    return True
            except RequestException:
                pass  # Service not ready yet, continue waiting
            except Exception as e:
                print(f"Debug: Error checking {service_name} health: {e}")

            time.sleep(0.5)  # Reduced from 2 seconds to speed up communication

        print(
            f"Health check failed for {service_name} at {url}, trying port availability..."
        )
        # If health check fails, try to connect to the port directly
        return self.wait_for_port(
            service_name, int(url.split(":")[-1].split("/")[0]), timeout
        )

    def wait_for_port(self, service_name, port, timeout=30):  # Reduced from 60
        """Wait for a port to become available."""
        import time
        import socket

        print(
            f"Waiting for {service_name} port {port} to become available... (timeout: {timeout}s)"
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)  # Reduced from 2 seconds
                    result = sock.connect_ex(("localhost", port))
                    if result == 0:
                        print(f"[SUCCESS] {service_name} port {port} is available")
                        return True
            except Exception as e:
                pass  # Continue waiting

            time.sleep(0.5)  # Reduced from 2 seconds to speed up communication

        print(f"Timeout waiting for {service_name} port {port}")
        return False

    def signal_handler(self, signum, frame):
        """Handle termination signals."""
        print_info(f"Received signal {signum}, shutting down...")
        self.running = False
        self.stop_all_processes()
        print_info("[INFO] All processes stopped successfully")
        sys.exit(0)

    def run(self, model_path, port):
        """Run the complete ECE startup process."""
        print("Simplified ECE Startup")
        print("=====================")

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            # 1. Start Docker services (Redis, Neo4j)
            if not self.start_docker_services():
                print("Failed to start Docker services")
                print("")
                print("Troubleshooting Docker services:")
                print("- Make sure Docker Desktop is installed and running")
                print(
                    "- Check that Neo4j and Redis containers are configured in docker-compose.yml"
                )
                print("- Verify Docker has sufficient resources allocated")
                return 1

            # Wait a bit for services to start (reduced time)
            time.sleep(2)  # Reduced from 5

            # 2. Start llama.cpp server
            if not self.start_llama_server(model_path, port):
                print("Failed to start llama.cpp server")
                print("")
                print("Troubleshooting llama.cpp server:")
                print("- Install build tools (CMake and C++ compiler) and try again")
                print("- Download a pre-built llama.cpp server binary")
                print("- Install llama-cpp-python: pip install llama-cpp-python")
                print("- Use a different model serving approach")
                print("")
                print("For more information, see the documentation in README.md")
                return 1

            # 3. Start ECE agents
            if not self.start_ece_agents():
                print("Failed to start ECE agents")
                print("")
                print("Troubleshooting ECE agents:")
                print("- Make sure all Python dependencies are installed")
                print("- Check that the ECE directory structure is correct")
                print("- Verify that Redis and Neo4j services are running")
                print(
                    "- Check logs in the logs/ directory for detailed error information"
                )
                return 1

            print("")
            print(
                "Simplified ECE System is running!"
            )  # Removed emoji to prevent encoding issues
            print("===================================")
            print("Services:")

            # Get Redis and Neo4j ports from .env or use defaults
            redis_port = os.getenv("REDIS_PORT", "6379")
            neo4j_port = os.getenv("NEO4J_PORT", "7687")

            print(f"  - Redis: localhost:{redis_port}")
            print(f"  - Neo4j: localhost:{neo4j_port}")
            print(f"  - llama.cpp server: localhost:{port}")

            # Get ECE agent ports from environment variables
            orchestrator_port = os.getenv("ORCHESTRATOR_PORT", "8000")
            distiller_port = os.getenv("DISTILLER_PORT", "8001")
            qlearning_port = os.getenv("QLEARNING_PORT", "8002")
            archivist_port = os.getenv("ARCHIVIST_PORT", "8003")
            injector_port = os.getenv("INJECTOR_PORT", "8004")
            filesystem_port = os.getenv("FILESYSTEM_PORT", "8006")
            websearch_port = os.getenv("WEBSEARCH_PORT", "8007")

            print(f"  - ECE Orchestrator: localhost:{orchestrator_port}")
            print(f"  - ECE Distiller: localhost:{distiller_port}")
            print(f"  - ECE QLearning: localhost:{qlearning_port}")
            print(f"  - ECE Archivist: localhost:{archivist_port}")
            print(f"  - ECE Injector: localhost:{injector_port}")
            print(f"  - ECE FileSystem: localhost:{filesystem_port}")
            print(f"  - ECE WebSearch: localhost:{websearch_port}")
            print("")
            print(
                "Configuration for qwen-code-ece/forge-cli:"
            )  # Removed emoji to prevent encoding issues
            print(
                "   To connect qwen-code-ece/forge-cli to this ECE system, use these UTCP endpoints:"
            )
            print(
                f"   - UTCP_ENDPOINTS=http://localhost:{websearch_port},http://localhost:{filesystem_port}"
            )
            print("   Note: GitAgent is not available in this ECE setup")
            print("")
            print("Press Ctrl+C to stop all services")
            print("")

            # Keep the script running
            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nReceived interrupt signal, shutting down...")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            self.stop_all_processes()

        return 0


def signal_handler(signum, frame):
    """Handle termination signals at module level."""
    print_info(f"Received signal {signum}, shutting down...")
    # We can't access the system instance from here, so we'll just exit
    sys.exit(0)


def main():
    # Load environment variables first
    from dotenv import load_dotenv

    load_dotenv()  # Load .env file if it exists

    parser = argparse.ArgumentParser(description="Simplified ECE Startup Script")
    parser.add_argument(
        "--model",
        default=os.getenv(
            "LLM_LLAMA_CPP_MODEL_PATH",
            "./models/Huihui-granite-4.0-h-tiny-abliterated.i1-Q4_K_M.gguf",
        ),
        help="Path to model file (defaults to LLM_LLAMA_CPP_MODEL_PATH env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("LLAMA_CPP_PORT", "8080")),
        help="Port to run llama.cpp server on (defaults to LLAMA_CPP_PORT env var)",
    )

    args = parser.parse_args()

    print_info("Simplified ECE Startup")
    print_info("=====================")

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run the simplified startup system
    system = SimplifiedECEStartup()
    return system.run(args.model, args.port)


if __name__ == "__main__":
    sys.exit(main())
