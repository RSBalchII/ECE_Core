"""
Bootstrapping script for the External Context Engine.
This script checks for required services (Redis, Neo4j) before starting the agents.
"""

import os
import sys
import time
import subprocess
import requests
import socket
from urllib.parse import urlparse
import yaml


def check_port(host, port, service_name):
    """Check if a service is available on a specific host and port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)  # 5 second timeout
            result = sock.connect_ex((host, port))
            if result == 0:
                print(f"✓ {service_name} is available at {host}:{port}")
                return True
            else:
                print(f"✗ {service_name} is NOT available at {host}:{port}")
                return False
    except Exception as e:
        print(f"✗ Error checking {service_name} at {host}:{port}: {e}")
        return False


def check_url(url, service_name, timeout=10):
    """Check if a service is available at a specific URL."""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code < 500:  # Consider it available if not a server error
            print(f"✓ {service_name} is available at {url}")
            return True
        else:
            print(
                f"✗ {service_name} returned status code {response.status_code} at {url}"
            )
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ {service_name} is NOT available at {url}: {e}")
        return False


def check_redis_connection(redis_url):
    """Check if Redis is available and responsive."""
    try:
        import redis

        parsed_url = urlparse(redis_url)
        r = redis.Redis(
            host=parsed_url.hostname,
            port=parsed_url.port,
            db=0,
            username=parsed_url.username,
            password=parsed_url.password,
            ssl=parsed_url.scheme == "rediss",
        )

        # Test the connection with a simple ping
        r.ping()
        print(f"✓ Redis is available and responsive at {redis_url}")
        return True
    except ImportError:
        # If redis module isn't available in the packaged app, fall back to port check
        parsed_url = urlparse(redis_url)
        return check_port(parsed_url.hostname, parsed_url.port or 6379, "Redis")
    except Exception as e:
        print(f"✗ Redis is NOT available at {redis_url}: {e}")
        return False


def check_neo4j_connection(neo4j_url, username, password):
    """Check if Neo4j is available and responsive."""
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(neo4j_url, auth=(username, password))

        # Test the connection with a simple query
        with driver.session() as session:
            result = session.run("RETURN 1 AS test")
            single_result = result.single()
            if single_result and single_result[0] == 1:
                print(f"✓ Neo4j is available and responsive at {neo4j_url}")
                driver.close()
                return True
            else:
                print(f"✗ Neo4j test query failed at {neo4j_url}")
                driver.close()
                return False
    except ImportError:
        # If neo4j module isn't available in the packaged app, fall back to port check
        parsed_url = urlparse(neo4j_url)
        return check_port(parsed_url.hostname, parsed_url.port or 7687, "Neo4j")
    except Exception as e:
        print(f"✗ Neo4j is NOT available at {neo4j_url}: {e}")
        return False


def load_config(config_path="config.yaml"):
    """Load the ECE configuration."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"✗ Error loading configuration from {config_path}: {e}")
        return None


def check_required_services():
    """Check if all required services are available."""
    print("Checking required services for ECE...")

    # Load configuration
    config = load_config()
    if not config:
        return False

    # Check Redis
    redis_url = config.get("cache", {}).get("redis_url", "redis://localhost:6379")
    redis_ok = check_redis_connection(redis_url)

    # Check Neo4j
    neo4j_uri = os.getenv(
        "NEO4J_URI", config.get("neo4j", {}).get("uri", "neo4j://localhost:7687")
    )
    neo4j_user = os.getenv("NEO4J_USER", config.get("neo4j", {}).get("user", "neo4j"))
    neo4j_password = os.getenv(
        "NEO4J_PASSWORD", config.get("neo4j", {}).get("password", "password")
    )
    neo4j_ok = check_neo4j_connection(neo4j_uri, neo4j_user, neo4j_password)

    # Check if LLM service is available (based on config)
    llm_config = config.get("llm", {})
    active_provider = llm_config.get("active_provider", "ollama")
    provider_config = llm_config.get("providers", {}).get(active_provider, {})

    llm_ok = True  # Default to True, only check if api_base is configured
    if "api_base" in provider_config:
        api_base = provider_config["api_base"]
        llm_ok = check_url(f"{api_base}/models", f"{active_provider} LLM Service")

    # UTCP Registry is no longer used in the decentralized approach
    # Each service handles its own UTCP manual endpoint
    utcp_ok = True

    all_ok = redis_ok and neo4j_ok and llm_ok and utcp_ok

    if all_ok:
        print("\n✓ All required services are available!")
    else:
        print(
            "\n✗ Some required services are not available. Please ensure all services are running before starting ECE."
        )
        if not redis_ok:
            print("  - Redis: Ensure Redis server is running")
        if not neo4j_ok:
            print("  - Neo4j: Ensure Neo4j database is running and accessible")
        if not llm_ok:
            print(
                f"  - LLM Service ({active_provider}): Ensure the {active_provider} server is running"
            )
        if not utcp_ok:
            print("  - UTCP Registry: Not required in the decentralized approach")

    return all_ok


def start_ece_agents():
    """Start all ECE agents after confirming services are available."""
    print("\nStarting ECE agents...")

    try:
        # Run the main run_all_agents.py script
        result = subprocess.run(
            [sys.executable, "run_all_agents.py"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        print("ECE agents started successfully!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error starting ECE agents: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
    except Exception as e:
        print(f"Unexpected error starting ECE agents: {e}")


def main():
    """Main function to run the bootstrap process."""
    print("External Context Engine - Bootstrapping Process")
    print("=" * 50)

    # Check if required services are available
    if check_required_services():
        print("\nAll checks passed. Starting ECE...")
        start_ece_agents()
    else:
        print("\nBootstrapping failed due to unavailable services.")
        sys.exit(1)


if __name__ == "__main__":
    main()
