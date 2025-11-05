#!/usr/bin/env python3
"""
Script to run all ECE agents simultaneously using uvicorn for FastAPI apps.
This script starts all ECE agents on their respective ports.
"""

import subprocess
import sys
import os
from pathlib import Path
import time
import threading
import signal
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def start_agent(agent_name, command, working_dir):
    """Start an agent in a subprocess."""
    logger.info(
        f"Starting {agent_name} with command: {' '.join(command)} in {working_dir}"
    )

    try:
        # Change to the working directory for this agent
        original_cwd = os.getcwd()
        os.chdir(working_dir)

        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Restore the original working directory
        os.chdir(original_cwd)

        # Log output from the process
        def log_output(pipe, prefix):
            for line in iter(pipe.readline, ""):
                logger.info(f"[{prefix}] {line.strip()}")
            pipe.close()

        stdout_thread = threading.Thread(
            target=log_output, args=(process.stdout, f"{agent_name}-OUT")
        )
        stderr_thread = threading.Thread(
            target=log_output, args=(process.stderr, f"{agent_name}-ERR")
        )

        stdout_thread.start()
        stderr_thread.start()

        return process, stdout_thread, stderr_thread
    except Exception as e:
        logger.error(f"Failed to start {agent_name}: {e}")
        return None, None, None


def main():
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    ece_dir = project_root / "ece"

    if not ece_dir.exists():
        logger.error(f"ECE directory does not exist: {ece_dir}")
        sys.exit(1)

    # Python executable to use
    python_exe = sys.executable
    uvicorn_exe = [python_exe, "-m", "uvicorn"]

    # Define agents to start with their module paths and ports
    agents = [
        {
            "name": "Orchestrator",
            "module": "ece.agents.tier1.orchestrator.main:app",
            "port": os.getenv("ORCHESTRATOR_PORT", "8000"),
            "working_dir": project_root,
        },
        {
            "name": "Distiller",
            "module": "ece.agents.tier3.distiller.distiller_agent:app",
            "port": os.getenv("DISTILLER_PORT", "8001"),
            "working_dir": project_root,
        },
        {
            "name": "QLearning",
            "module": "ece.agents.tier3.qlearning.qlearning_app:app",  # Using qlearning_app.py
            "port": os.getenv("QLEARNING_PORT", "8002"),
            "working_dir": project_root,
        },
        {
            "name": "Archivist",
            "module": "ece.agents.tier3.archivist.archivist_agent:app",
            "port": os.getenv("ARCHIVIST_PORT", "8003"),
            "working_dir": project_root,
        },
        {
            "name": "Injector",
            "module": "ece.agents.tier3.injector.main:app",  # Using main.py in injector
            "port": os.getenv("INJECTOR_PORT", "8004"),
            "working_dir": project_root,
        },
        {
            "name": "FileSystem",
            "module": "ece.agents.tier2.filesystem_agent:app",
            "port": os.getenv("FILESYSTEM_PORT", "8006"),
            "working_dir": project_root,
        },
        {
            "name": "WebSearch",
            "module": "ece.agents.tier2.web_search_app:app",  # Using web_search_app.py
            "port": os.getenv("WEBSEARCH_PORT", "8007"),
            "working_dir": project_root,
        },
        {
            "name": "Git",
            "module": "ece.agents.tier2.git_agent:app",  # Using git_agent.py
            "port": os.getenv("GIT_PORT", "8009"),
            "working_dir": project_root,
        },
    ]

    # Start all agents
    processes = []
    threads = []

    for agent in agents:
        logger.info(f"Starting {agent['name']} agent on port {agent['port']}...")

        # Construct the uvicorn command
        command = uvicorn_exe + [
            agent["module"],
            "--host",
            "127.0.0.1",
            "--port",
            agent["port"],
            "--reload",  # Enable auto-reload for development
        ]

        process, stdout_thread, stderr_thread = start_agent(
            agent["name"], command, agent["working_dir"]
        )

        if process:
            processes.append((agent["name"], process))
            threads.extend([stdout_thread, stderr_thread])
            time.sleep(3)  # Longer delay to allow agent to fully start
        else:
            logger.error(f"Failed to start {agent['name']}, stopping other agents...")
            # Stop all previously started agents
            for _, proc in processes:
                proc.terminate()
            sys.exit(1)

    logger.info(f"Started {len(processes)} agents successfully")

    # Give all agents some time to fully initialize
    logger.info("Waiting for agents to fully initialize...")
    time.sleep(10)

    # Verify agents are running by checking if the ports are open
    import socket

    for agent in agents:
        port = int(agent["port"])
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                logger.info(f"{agent['name']} is accessible on port {port}")
            else:
                logger.warning(
                    f"{agent['name']} might not be accessible on port {port}"
                )

    # Wait for any process to exit
    try:
        while True:
            time.sleep(1)
            # Check if any process has terminated
            for name, proc in processes:
                if proc.poll() is not None:
                    logger.error(
                        f"{name} process terminated with code {proc.returncode}"
                    )
                    logger.info("Shutting down other agents...")
                    # Terminate all other processes
                    for _, other_proc in processes:
                        if other_proc != proc and other_proc.poll() is None:
                            other_proc.terminate()
                    sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down agents...")
        # Terminate all processes
        for name, proc in processes:
            logger.info(f"Terminating {name}...")
            proc.terminate()

        # Wait for processes to terminate
        for name, proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"{name} did not terminate gracefully, killing...")
                proc.kill()

        logger.info("All agents terminated")
        sys.exit(0)


if __name__ == "__main__":
    main()
