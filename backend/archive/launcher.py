"""
ECE_Core Launcher - Starts Redis + Neo4j + MCP Services + FastAPI server as single process.
Can be bundled into .exe with PyInstaller.
"""
import subprocess
import sys
import os
import logging
import signal
from pathlib import Path
from utils.neo4j_embedded import EmbeddedNeo4j
from core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.ece_log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ECELauncher:
    def __init__(self):
        self.redis_process = None
        self.neo4j_manager = None
        self.ece_process = None
        self.mcp_processes = {}  # Track MCP services
        
        # Determine if running as bundled exe or script
        if getattr(sys, 'frozen', False):
            # Running as bundled exe
            self.app_dir = Path(sys._MEIPASS)
            self.data_dir = Path(os.getcwd())
            self.redis_exe = self.app_dir / "db" / "redis-server.exe"
        else:
            # Running as script - look for Redis in External-Context-Engine-ECE
            self.app_dir = Path(__file__).parent
            self.data_dir = self.app_dir
            external_redis = self.app_dir.parent / "External-Context-Engine-ECE" / "dist" / "db" / "redis-server.exe"
            if external_redis.exists():
                self.redis_exe = external_redis
            else:
                self.redis_exe = None  # Will skip Redis startup
        
        self.redis_conf = self.data_dir / "redis.conf"
        
        # Single MCP server that provides all tools
        self.mcp_server_port = 8008
    
    def start_neo4j(self):
        """Start Neo4j server."""
        try:
            from utils.neo4j_embedded import EmbeddedNeo4j
            self.neo4j_manager = EmbeddedNeo4j()
            neo4j_ok = self.neo4j_manager.start()
            return neo4j_ok
        except Exception as e:
            logger.error(f"Could not start Neo4j: {e}")
            return False
    
    def start_redis(self):
        """Start Redis server."""
        if not self.redis_exe:
            logger.info("Redis exe not bundled - assuming global Redis is running")
            return True
        
        if not self.redis_exe.exists():
            logger.warning(f"Redis not found at: {self.redis_exe}")
            logger.info("Continuing without embedded Redis (will use global if available)")
            return True
        
        logger.info("Starting embedded Redis server...")
        
        # Create minimal redis.conf if it doesn't exist
        if not self.redis_conf.exists():
            self.redis_conf.write_text("""# ECE_Core Redis Configuration
port 6379
bind 127.0.0.1
protected-mode yes
save ""
appendonly no
dir ./
""")
        
        try:
            import time
            self.redis_process = subprocess.Popen(
                [str(self.redis_exe), str(self.redis_conf)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            time.sleep(2)  # Give Redis time to start
            
            if self.redis_process.poll() is None:
                logger.info("Redis server started (port 6379)")
                return True
            else:
                logger.warning("Redis failed to start")
                return False
        except Exception as e:
            logger.warning(f"Could not start Redis: {e}")
            return False
    
    def start_mcp_server(self):
        """Start the unified MCP server (now moved to Anchor)."""
        logger.info("MCP server moved to Anchor CLI - no longer started from ECE_Core")
        logger.info("ECE_Core will connect to MCP server at http://localhost:8008")
    
    def start_ece(self):
        """Start ECE_Core FastAPI server."""
        logger.info("Starting ECE_Core...")
        
        # Import and run main.py
        try:
            import uvicorn
            from main import app
            
            # Check port availability before we attempt to bind
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind((settings.ece_host, settings.ece_port))
                s.close()
            except Exception:
                # Port in use – try to identify the process
                logger.error(f"Port {settings.ece_port} is already in use. Cannot start ECE_Core.")
                try:
                    import psutil
                    for conn in psutil.net_connections(kind='inet'):
                        if conn.laddr and conn.laddr.port == settings.ece_port:
                            pid = conn.pid
                            proc = psutil.Process(pid) if pid else None
                            logger.error(f"    Bound by PID: {pid}, process: {proc.name() if proc else 'Unknown'}")
                            break
                except Exception:
                    logger.error("Failed to inspect processes for port ownership (psutil not installed or insufficient privileges)")
                raise RuntimeError(f"Port {settings.ece_port} is already bound; stop the process or change settings.ece_port")

            # Run in same process
            uvicorn.run(
                app, 
                host=settings.ece_host, 
                port=settings.ece_port,
                log_level=settings.ece_log_level.lower()
            )
        except Exception as e:
            logger.error(f"ECE_Core failed: {e}")
            raise
    
    def cleanup(self, signum=None, frame=None):
        """Stop all processes."""
        logger.info("Shutting down...")
        
        # Stop MCP services
        if self.mcp_processes:
            logger.info("Stopping MCP services...")
            for service_id, process in self.mcp_processes.items():
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except Exception:
                    process.kill()
        
        # Stop Neo4j
        if self.neo4j_manager:
            self.neo4j_manager.stop()
        
        # Stop Redis
        if self.redis_process:
            logger.info("Stopping Redis...")
            self.redis_process.terminate()
            try:
                self.redis_process.wait(timeout=5)
            except Exception:
                self.redis_process.kill()
        
        sys.exit(0)
    
    def run(self):
        """Main launcher."""
        logger.info("=" * 50)
        logger.info("  ECE_Core - External Context Engine")
        logger.info("=" * 50)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        # Start Neo4j
        neo4j_ok = self.start_neo4j()
        if not neo4j_ok:
            logger.warning("Continuing without Neo4j (graph features disabled)")
        
        # Start Redis
        redis_ok = self.start_redis()
        if not redis_ok:
            logger.warning("Continuing without Redis (will use fallback)")
        
        # Start MCP server
        self.start_mcp_server()
        
        logger.info("")
        
        # Start ECE_Core (blocking)
        try:
            self.start_ece()
        except KeyboardInterrupt:
            self.cleanup()
        except Exception as e:
            logger.error(f"Error: {e}")
            self.cleanup()


if __name__ == "__main__":
    launcher = ECELauncher()
    launcher.run()

