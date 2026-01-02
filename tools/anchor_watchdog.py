import sys, time, os, requests, hashlib, logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "context"))
BRIDGE_INGEST_URL = "http://localhost:8000/v1/memory/ingest"
ALLOWED = {'.md', '.txt', '.json', '.yaml', '.py', '.js', '.html', '.css'}

# Setup Logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "watchdog.log"), mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class Handler(FileSystemEventHandler):
    def __init__(self):
        self.hashes = {}
        self.last_mod = {}

    def process(self, filepath):
        _, ext = os.path.splitext(filepath)
        if ext.lower() not in ALLOWED: return
        
        # Debounce & Hash Check
        now = time.time()
        if filepath in self.last_mod and now - self.last_mod[filepath] < 1.0: return
        self.last_mod[filepath] = now
        time.sleep(0.1)
        
        hasher = hashlib.md5()
        try:
            with open(filepath, 'rb') as f: hasher.update(f.read())
            new_hash = hasher.hexdigest()
        except: return
        
        if self.hashes.get(filepath) == new_hash: return
        self.hashes[filepath] = new_hash

        logger.info(f"👀 Change: {os.path.basename(filepath)}")
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            payload = { "filename": os.path.relpath(filepath, WATCH_DIR), "content": content, "filetype": ext }
            requests.post(BRIDGE_INGEST_URL, json=payload, timeout=5)
            logger.info(f"✅ Ingested")
        except Exception as e: 
            logger.error(f"❌ Error ingesting {os.path.basename(filepath)}: {e}")

    def on_modified(self, event): 
        if not event.is_directory: self.process(event.src_path)
    def on_created(self, event):
        if not event.is_directory: self.process(event.src_path)

def wait_for_bridge():
    """Wait for the bridge to become available."""
    logger.info("⏳ Waiting for Bridge to come online...")
    url = "http://localhost:8000/health"
    for i in range(30): # Wait up to 30 seconds
        try:
            requests.get(url, timeout=2)
            logger.info("🟢 Bridge is Online!")
            return True
        except:
            time.sleep(1)
    logger.error("❌ Bridge unreachable after 30s. Exiting.")
    return False

if __name__ == "__main__":
    if not os.path.exists(WATCH_DIR): os.makedirs(WATCH_DIR)
    
    # Wait for Bridge
    if not wait_for_bridge():
        sys.exit(1)

    handler = Handler()
    
    # Initial Indexing
    logger.info("🔍 Starting Initial Index Walk...")
    for root, dirs, files in os.walk(WATCH_DIR):
        for file in files:
            handler.process(os.path.join(root, file))
    logger.info("✅ Initial Indexing Complete")

    obs = Observer()
    obs.schedule(handler, WATCH_DIR, recursive=True)
    obs.start()
    logger.info(f"🐕 Watchdog Active: {WATCH_DIR}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: obs.stop()
    obs.join()
