import subprocess
import sys


def install_utcp_packages():
    """Install UTCP packages using subprocess."""
    packages = ["utcp", "utcp-http", "utcp-mcp"]

    for package in packages:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                print(f"✓ Successfully installed {package}")
                print(result.stdout)
            else:
                print(f"✗ Failed to install {package}")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
        except subprocess.TimeoutExpired:
            print(f"✗ Installation of {package} timed out")
        except Exception as e:
            print(f"✗ Error installing {package}: {e}")


if __name__ == "__main__":
    install_utcp_packages()

    # Test imports after installation
    print("\nTesting imports...")
    try:
        import utcp

        print("✓ UTCP package imported successfully")
        print(
            "UTCP available attributes:",
            [attr for attr in dir(utcp) if not attr.startswith("_")],
        )
    except ImportError as e:
        print(f"✗ Failed to import UTCP: {e}")

    try:
        from utcp.utcp_client import UtcpClient

        print("✓ UTCPClient imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import UtcpClient: {e}")
