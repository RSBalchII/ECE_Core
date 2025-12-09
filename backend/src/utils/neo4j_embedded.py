"""
Embedded Neo4j server manager for ECE_Core.
Launches Neo4j as subprocess, just like Redis.
"""
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


class EmbeddedNeo4j:
    """Manages embedded Neo4j server instance."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        
        # Determine paths
        if getattr(sys, 'frozen', False):
            # Running as bundled exe - look for Neo4j relative to exe
            self.app_dir = Path(sys._MEIPASS)
            self.data_dir = Path.cwd()
            # Check for Neo4j in db/ directory relative to exe
            local_neo4j = self.data_dir / "db" / "neo4j-community-2025.10.1"
            if local_neo4j.exists():
                self.neo4j_home = local_neo4j
            else:
                self.neo4j_home = None
        else:
            # Running as script - look for Neo4j in db/ or External-Context-Engine-ECE
            self.app_dir = Path(__file__).parent.parent
            local_neo4j = self.app_dir / "db" / "neo4j-community-2025.10.1"
            external_neo4j = self.app_dir.parent / "External-Context-Engine-ECE" / "db" / "neo4j-community-2025.10.1"
            
            if local_neo4j.exists():
                self.neo4j_home = local_neo4j
            elif external_neo4j.exists():
                self.neo4j_home = external_neo4j
            else:
                self.neo4j_home = None
        
        # Neo4j configuration
        self.bolt_port = 7687
        self.http_port = 7474
        self.username = "neo4j"
        self.password = "password"  # Default, should be configurable
    
    def start(self) -> bool:
        """Start Neo4j server."""
        if not self.neo4j_home:
            print("Neo4j not found - graph features disabled")
            return False
        
        if not self.neo4j_home.exists():
            print(f"Neo4j not found at: {self.neo4j_home}")
            return False
        
        print("Starting embedded Neo4j server...")
        
        # Configure Neo4j for embedded use
        conf_file = self.neo4j_home / "conf" / "neo4j.conf"
        self._configure_neo4j(conf_file)
        
        try:
            # Use neo4j console (foreground mode) so we can control it
            if sys.platform == 'win32':
                neo4j_exe = self.neo4j_home / "bin" / "neo4j.bat"
                cmd = [str(neo4j_exe), "console"]
            else:
                neo4j_exe = self.neo4j_home / "bin" / "neo4j"
                cmd = [str(neo4j_exe), "console"]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.neo4j_home),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                env={
                    **subprocess.os.environ,
                    "NEO4J_HOME": str(self.neo4j_home),
                    "NEO4J_CONF": str(self.neo4j_home / "conf")
                }
            )
            
            # Wait for Neo4j to be ready
            if self._wait_for_ready():
                print(f"Neo4j started (bolt://localhost:{self.bolt_port})")
                return True
            else:
                print("Neo4j failed to start within timeout")
                self.stop()
                return False
                
        except Exception as e:
            print(f"Could not start Neo4j: {e}")
            return False
    
    def _configure_neo4j(self, conf_file: Path):
        """Write minimal Neo4j configuration."""
        # Ensure conf directory exists
        conf_file.parent.mkdir(parents=True, exist_ok=True)
        
        config = f"""# ECE_Core Embedded Neo4j Configuration
# Generated automatically

# Server ports
server.bolt.enabled=true
server.bolt.listen_address=127.0.0.1:7687
server.http.enabled=true
server.http.listen_address=127.0.0.1:7474

# CRITICAL: Disable authentication completely for embedded use
dbms.security.auth_enabled=false
server.bolt.tls_level=DISABLED
server.https.enabled=false

# Memory settings (conservative for embedded use)
server.memory.heap.initial_size=256m
server.memory.heap.max_size=512m
server.memory.pagecache.size=256m

# Database location  
server.directories.data=data
server.directories.logs=logs
server.directories.import=import

# Disable anonymous usage reporting
dbms.usage_report.enabled=false

# Performance tweaks for local use
dbms.tx_log.rotation.retention_policy=false
dbms.checkpoint.interval.time=5m
"""
        conf_file.write_text(config)
    
    def _wait_for_ready(self, timeout: int = 30) -> bool:
        """Wait for Neo4j to be ready to accept connections."""
        import socket
        
        start = time.time()
        while time.time() - start < timeout:
            # Check if process died
            if self.process.poll() is not None:
                return False
            
            # Try to connect to bolt port
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', self.bolt_port))
                sock.close()
                
                if result == 0:
                    time.sleep(2)  # Extra time for full startup
                    return True
            except:
                pass
            
            time.sleep(1)
        
        return False
    
    def stop(self):
        """Stop Neo4j server."""
        if not self.process:
            return
        
        print("  Stopping Neo4j...")
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("  Force killing Neo4j...")
            self.process.kill()
            self.process.wait()
        
        self.process = None
    
    def is_running(self) -> bool:
        """Check if Neo4j process is running."""
        return self.process is not None and self.process.poll() is None
    
    def get_bolt_uri(self) -> str:
        """Get Neo4j bolt connection URI."""
        return f"bolt://localhost:{self.bolt_port}"
    
    def get_http_uri(self) -> str:
        """Get Neo4j HTTP URI."""
        return f"http://localhost:{self.http_port}"
