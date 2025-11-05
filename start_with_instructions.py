#!/usr/bin/env python3
"""
Helper script to start ECE and provide connection instructions for qwen-code-ece and forge-cli.
"""

import subprocess
import sys
import time
import os
import signal
from pathlib import Path


def print_connection_instructions():
    """Print instructions for connecting qwen-code-ece and forge-cli to ECE."""
    print("\n" + "=" * 80)
    print("🔧 CONNECTION INSTRUCTIONS FOR qwen-code-ece AND forge-cli")
    print("=" * 80)
    print(
        "\nTo connect qwen-code-ece or forge-cli to this ECE system, use these settings:"
    )
    print("\n📋 ENVIRONMENT VARIABLES:")
    print(
        "   UTCP_ENDPOINTS=http://localhost:8007,http://localhost:8006,http://localhost:8009"
    )
    print("   or")
    print(
        "   UTCP_SERVICE_ENDPOINTS=http://localhost:8007,http://localhost:8006,http://localhost:8009"
    )
    print("\n📁 .ENV FILE CONFIGURATION:")
    print("   Create a .env file in your qwen-code-ece or forge-cli directory with:")
    print(
        "   UTCP_ENDPOINTS=http://localhost:8007,http://localhost:8006,http://localhost:8009"
    )
    print("\n⚡ SERVICE ENDPOINTS:")
    print("   - WebSearch Agent:  http://localhost:8007")
    print("   - FileSystem Agent: http://localhost:8006")
    print("   - Git Agent:        http://localhost:8009")
    print("\n💡 TESTING THE CONNECTION:")
    print("   Run this command to verify all services are accessible:")
    print("   python test_ece_services.py")
    print("\n📖 DETAILED DOCUMENTATION:")
    print("   See docs/ece_service_configuration.md for complete configuration guide")
    print("=" * 80)


def main():
    """Main function to start ECE and provide connection instructions."""
    print("🚀 Starting External Context Engine (ECE)...")
    print("This script will start the complete ECE system and provide connection")
    print("instructions for qwen-code-ece and forge-cli applications.")

    try:
        # Start the ECE system
        ece_process = subprocess.Popen(
            [sys.executable, "start_simplified_ecosystem.py"]
        )

        print(f"\n📦 ECE system started with PID {ece_process.pid}")
        print("⏳ Waiting for services to initialize...")

        # Wait for a bit to let services start
        time.sleep(10)

        # Print connection instructions
        print_connection_instructions()

        print("\n🛑 Press Ctrl+C to stop the ECE system")

        # Wait for the process to complete or for user interruption
        try:
            ece_process.wait()
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down ECE system...")
            ece_process.terminate()
            try:
                ece_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                ece_process.kill()
            print("✅ ECE system stopped successfully")

    except FileNotFoundError:
        print("❌ Error: start_simplified_ecosystem.py not found!")
        print(
            "   Make sure you're running this script from the ECE project root directory."
        )
        return 1
    except Exception as e:
        print(f"❌ Error starting ECE system: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
