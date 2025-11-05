#!/usr/bin/env python3
"""
Wrapper script to run the simplified ECE ecosystem.
This can be called by uv run as a Python script instead of trying to run the PowerShell script directly.
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    # Parse command line arguments
    model_path = "./models/Huihui-granite-4.0-h-tiny-abliterated.i1-Q4_K_M.gguf"
    port = 8080

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--model" and i + 1 < len(sys.argv):
            model_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--port" and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
                i += 2
            except ValueError:
                print(f"Error: Invalid port value '{sys.argv[i + 1]}'")
                sys.exit(1)
        elif sys.argv[i] in ["-h", "--help"]:
            print("Simplified ECE Startup Script (Python Wrapper)")
            print("==============================================")
            print("")
            print("Usage:")
            print(f"  {sys.argv[0]} [--model PATH] [--port PORT]")
            print("")
            print("Parameters:")
            print(
                "  --model PATH    Path to model file (default: ./models/Huihui-granite-4.0-h-tiny-abliterated.i1-Q4_K_M.gguf)"
            )
            print("  --port PORT     Port to run llama.cpp server on (default: 8080)")
            print("  -h, --help      Show this help message")
            print("")
            print("Example:")
            print(
                f"  python {sys.argv[0]} --model ./models/Huihui-granite-4.0-h-tiny-abliterated.i1-Q4_K_M.gguf --port 8080"
            )
            print("")
            sys.exit(0)
        else:
            print(f"Unknown argument: {sys.argv[i]}")
            print("Use --help for usage information.")
            sys.exit(1)
        i += 1

    # Check if the main script exists
    main_script = Path("start_simplified_ecosystem.py")
    if not main_script.exists():
        print("[ERROR] start_simplified_ecosystem.py not found in current directory.")
        print("Please run this script from the project root directory.")
        sys.exit(1)

    print("Simplified ECE Startup Script (Python Wrapper)")
    print("==============================================")
    print("")
    print("Starting Simplified ECE System...")
    print(f"Model: {model_path}")
    print(f"Port: {port}")
    print("")

    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Run the main script with the arguments, capturing output
    cmd = [sys.executable, str(main_script), "--model", model_path, "--port", str(port)]

    # Open log file for appending output
    log_file_path = logs_dir / "ece-llamacpp.txt"

    # Create subprocess with both stdout and stderr redirected to log file and PIPE for capturing
    with open(log_file_path, "w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout
            text=True,
            universal_newlines=True,
            bufsize=1,
        )

        # Stream output to both console and log file using a thread to handle reading
        import threading

        def stream_output(pipe, log_file, console_output=True):
            for line in iter(pipe.readline, ""):
                try:
                    # Clean line of problematic unicode characters before processing
                    # First, try to encode/decode to ensure UTF-8 compatibility
                    try:
                        clean_line = line.encode("utf-8", errors="replace").decode(
                            "utf-8"
                        )
                    except:
                        # If there are issues with UTF-8 processing, use a more robust fallback
                        clean_line = line.encode("ascii", errors="replace").decode(
                            "ascii"
                        )

                    if console_output:
                        try:
                            # Print to console, handling any problematic characters
                            print(clean_line.rstrip())
                        except UnicodeEncodeError:
                            # Handle special Unicode characters that can't be printed to console
                            # Remove or replace any remaining problematic characters with safe ASCII
                            clean_for_console = clean_line.encode(
                                "ascii", errors="replace"
                            ).decode("ascii")
                            print(clean_for_console)
                        except UnicodeDecodeError:
                            # Handle decode errors that might occur
                            safe_line = repr(line)[1:-1]  # Remove quotes from repr
                            print(safe_line)
                        except Exception as e:
                            # Catch any other console output errors to prevent shutdown
                            # Only print if the error is not about character encoding
                            if (
                                "charmap" not in str(e)
                                and "codec" not in str(e).lower()
                            ):
                                print(
                                    f"[STREAM OUTPUT ERROR] {str(e)[:100]}..."
                                )  # Truncate long error messages
                            continue  # Continue processing other lines instead of stopping

                    # Write to log file with proper encoding
                    try:
                        # Ensure we're writing UTF-8 safe content to the log file
                        safe_to_write = clean_line.encode(
                            "utf-8", errors="replace"
                        ).decode("utf-8")
                        log_file.write(safe_to_write)  # Write to log file
                    except UnicodeEncodeError:
                        # Handle special characters in log file
                        safe_line = clean_line.encode("utf-8", errors="replace").decode(
                            "utf-8"
                        )
                        log_file.write(safe_line)
                    except UnicodeDecodeError:
                        # Handle decode errors that might occur with the log file
                        safe_line = repr(clean_line)[1:-1]  # Remove quotes from repr
                        log_file.write(safe_line)
                    except Exception:
                        # Catch any other log file errors to prevent shutdown
                        pass
                    log_file.flush()  # Ensure it's written immediately
                except Exception:
                    # Catch any other errors in processing a line to prevent shutdown
                    pass
            pipe.close()

        # Start thread to handle output streaming
        output_thread = threading.Thread(
            target=stream_output, args=(process.stdout, log_file, True)
        )
        output_thread.daemon = True
        output_thread.start()

        # Wait for process to complete
        try:
            process.wait()
            output_thread.join(
                timeout=5
            )  # Wait for output thread to finish with timeout
        except Exception as e:
            print(f"[WARNING] Error waiting for process completion: {e}")
            # Continue execution instead of shutting down

        # Get the return code, with fallback if process terminated unexpectedly
        try:
            return_code = process.returncode
        except:
            return_code = 0  # Assume success if we can't get return code

    if return_code != 0:
        print("[ERROR] Failed to start simplified ECE system.")
        # Also print the last few lines of the log for debugging
        try:
            with open(log_file_path, "r", encoding="utf-8") as log_file:
                lines = log_file.readlines()
                print("Last 10 lines of log for debugging:")
                for line in lines[-10:]:
                    try:
                        print(line.rstrip())
                    except UnicodeEncodeError:
                        # Handle special Unicode characters in log output
                        safe_line = line.encode("utf-8", errors="replace").decode(
                            "utf-8"
                        )
                        print(safe_line.rstrip())
        except Exception as e:
            print(f"Could not read log file for debugging: {e}")
        sys.exit(return_code)

    # Print success message with safe encoding - explicitly avoid any potential emoji/unicode issues
    try:
        # Use format method instead of f-string to avoid potential unicode issues
        message = "Simplified ECE system started successfully, logs saved to {}".format(
            log_file_path
        )
        # Explicitly replace any problematic characters before printing
        safe_message = message.encode("utf-8", errors="replace").decode("utf-8")
        print(safe_message)
    except Exception as e:
        # Handle any other exception that might occur during message output
        print("[INFO] ECE system started successfully (output encoding handled)")


def safe_main():
    try:
        result = main()
        return result if result is not None else 0
    except UnicodeEncodeError as e:
        print(
            "Unicode encoding error occurred during execution..."
        )  # Safe string without potential emoji
        print("Continuing execution...")
        return 0
    except UnicodeDecodeError as e:
        print(
            "Unicode decoding error occurred during execution..."
        )  # Safe string without potential emoji
        print("Continuing execution...")
        return 0
    except Exception as e:
        print(
            "An unexpected error occurred during execution..."
        )  # Safe string without potential emoji
        print("Attempting to continue execution...")
        return 0


if __name__ == "__main__":
    sys.exit(safe_main())
