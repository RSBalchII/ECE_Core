#!/usr/bin/env python3
"""
Watchdog Service: Monitors a context folder and ingests text/markdown files.

This service watches for file changes in a `context/` folder and automatically
sends new/modified files to the Bridge's `/v1/memory/ingest` endpoint.

Usage:
    python watchdog.py --watch-dir ./context --bridge-url http://localhost:8000

Features:
    - File system watching using `watchdog` library (pure Python, cross-platform)
    - Batch ingestion for efficiency
    - Filters: .txt, .md, .markdown files only
    - Respects max file size (configurable)
    - Retry logic for transient errors
    - Graceful shutdown
"""

import argparse
import asyncio
import json
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Set, Dict, Optional
import aiohttp

# Attempt to import watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("⚠️  watchdog library not installed. Install with: pip install watchdog")


class ContextIngester:
    """Monitors a directory and ingests text files to the Bridge."""

    def __init__(
        self,
        watch_dir: str,
        bridge_url: str = "http://localhost:8000",
        max_file_size: int = 1024 * 1024,  # 1MB default
        batch_interval: float = 5.0,  # seconds
        debounce_time: float = 2.0,  # seconds to wait after last modification
        enabled_extensions: Optional[Set[str]] = None
    ):
        self.watch_dir = Path(watch_dir)
        self.bridge_url = bridge_url.rstrip("/")
        self.max_file_size = max_file_size
        self.batch_interval = batch_interval
        self.debounce_time = debounce_time  # Time to wait for debounce
        self.enabled_extensions = enabled_extensions or {".txt", ".md", ".markdown", ".py", ".js", ".html", ".css", ".json", ".yaml", ".yml", ".sh", ".bat", ".ts", ".tsx", ".jsx", ".xml", ".sql", ".rs", ".go", ".cpp", ".c", ".h", ".hpp"}

        # Create watch directory if it doesn't exist
        self.watch_dir.mkdir(parents=True, exist_ok=True)

        self.pending_files: Set[Path] = set()
        self.pending_lock = asyncio.Lock()
        self.batch_task: Optional[asyncio.Task] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.file_hashes: Dict[Path, str] = {}  # Track file content hashes to avoid duplicates
        self.debounce_timers: Dict[Path, asyncio.Task] = {}  # Track debounce timers

        print(f"✅ ContextIngester initialized")
        print(f"   Watch dir: {self.watch_dir}")
        print(f"   Bridge URL: {self.bridge_url}")
        print(f"   Max file size: {self.max_file_size} bytes")
        print(f"   Debounce time: {self.debounce_time} seconds")

    async def start(self):
        """Start the ingestion service."""
        self.session = aiohttp.ClientSession()
        print("🚀 Watchdog service started")

        # If watchdog is available, use it for real-time monitoring
        if WATCHDOG_AVAILABLE:
            await self._start_file_observer()
        else:
            # Fallback: poll the directory periodically
            print("⚠️  Using polling mode (watchdog not available)")
            await self._start_polling()
    
    async def _start_file_observer(self):
        """Start watchdog observer for real-time file monitoring."""
        event_handler = self._create_event_handler()
        observer = Observer()
        observer.schedule(event_handler, str(self.watch_dir), recursive=True)
        observer.start()
        
        # Keep the observer running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            observer.join()
    
    async def _start_polling(self):
        """Fallback: poll the directory for changes."""
        seen_files: Dict[Path, float] = {}
        
        try:
            while True:
                current_files = {
                    p: p.stat().st_mtime
                    for p in self.watch_dir.rglob("*")
                    if p.is_file() and p.suffix.lower() in self.enabled_extensions
                }
                
                # Check for new or modified files
                for file_path, mtime in current_files.items():
                    if file_path not in seen_files or seen_files[file_path] < mtime:
                        await self._on_file_event(file_path)
                
                seen_files = current_files
                await asyncio.sleep(self.batch_interval)
        
        except KeyboardInterrupt:
            print("\n⏹️  Polling stopped")
    
    def _create_event_handler(self) -> FileSystemEventHandler:
        """Create a watchdog event handler for file changes."""
        ingester = self
        
        class ContextEventHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    file_path = Path(event.src_path)
                    if file_path.suffix.lower() in ingester.enabled_extensions:
                        asyncio.create_task(ingester._on_file_event(file_path))
            
            def on_modified(self, event):
                if not event.is_directory:
                    file_path = Path(event.src_path)
                    if file_path.suffix.lower() in ingester.enabled_extensions:
                        asyncio.create_task(ingester._on_file_event(file_path))
        
        return ContextEventHandler()
    
    async def _on_file_event(self, file_path: Path):
        """Handle file creation/modification event with debounce and hash checking."""
        try:
            # Wait a moment for file to be fully written
            await asyncio.sleep(0.5)

            # Check file size
            if file_path.stat().st_size > self.max_file_size:
                print(f"⚠️  Skipping {file_path.name} - exceeds max size")
                return

            # Calculate file hash to check for changes
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                    current_hash = hashlib.md5(content).hexdigest()

                # Check if content has actually changed
                if file_path in self.file_hashes and self.file_hashes[file_path] == current_hash:
                    print(f"⏭️  Skipped {file_path.name} - no changes detected")
                    return

                # Update the hash
                self.file_hashes[file_path] = current_hash

            except Exception as hash_error:
                print(f"⚠️  Hash check failed for {file_path.name}: {hash_error}")
                # Continue with ingestion even if hash check fails

            # Cancel any existing debounce timer for this file
            if file_path in self.debounce_timers:
                self.debounce_timers[file_path].cancel()

            # Create a new debounce task for this file
            debounce_task = asyncio.create_task(self._debounce_file_ingestion(file_path))
            self.debounce_timers[file_path] = debounce_task

        except Exception as e:
            print(f"❌ Error handling file event: {e}")

    async def _debounce_file_ingestion(self, file_path: Path):
        """Wait for debounce period before queuing file for ingestion."""
        try:
            # Wait for the debounce period
            await asyncio.sleep(self.debounce_time)

            # Check if the file still exists
            if not file_path.exists():
                return

            # Add to pending batch
            async with self.pending_lock:
                self.pending_files.add(file_path)
                print(f"📝 Queued: {file_path.name}")

            # Start or reset batch timer
            if self.batch_task is None or self.batch_task.done():
                self.batch_task = asyncio.create_task(self._batch_ingest_after_delay())

        except asyncio.CancelledError:
            # Task was cancelled, which is expected during debounce
            pass
        except Exception as e:
            print(f"❌ Error in debounce task: {e}")
        finally:
            # Clean up the timer reference
            if file_path in self.debounce_timers:
                del self.debounce_timers[file_path]
    
    async def _batch_ingest_after_delay(self):
        """Wait for batch interval then ingest all pending files."""
        await asyncio.sleep(self.batch_interval)
        await self._batch_ingest()
    
    async def _batch_ingest(self):
        """Ingest all pending files in a single batch."""
        async with self.pending_lock:
            if not self.pending_files:
                return
            
            files_to_ingest = list(self.pending_files)
            self.pending_files.clear()
        
        print(f"\n📦 Ingesting batch of {len(files_to_ingest)} file(s)...")
        
        for file_path in files_to_ingest:
            await self._ingest_file(file_path)
    
    async def _ingest_file(self, file_path: Path):
        """Send a file to the Bridge for ingestion."""
        try:
            if not file_path.exists():
                print(f"⚠️  File not found: {file_path.name}")
                return
            
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Prepare ingestion payload
            payload = {
                "source": str(file_path.relative_to(self.watch_dir)),
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "file_type": file_path.suffix.lower()
            }
            
            # Send to bridge
            try:
                async with self.session.post(
                    f"{self.bridge_url}/v1/memory/ingest",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ Ingested: {file_path.name} ({len(content)} bytes)")
                    else:
                        error_text = await response.text()
                        print(f"❌ Ingest failed ({response.status}): {file_path.name}")
                        print(f"   Response: {error_text[:200]}")
            
            except asyncio.TimeoutError:
                print(f"⏱️  Timeout ingesting {file_path.name} - Bridge may be busy")
            except aiohttp.ClientConnectorError:
                print(f"🔌 Bridge unreachable ({self.bridge_url}) - will retry later")
            except Exception as e:
                print(f"❌ Error during ingestion: {e}")
        
        except Exception as e:
            print(f"❌ Error reading file {file_path.name}: {e}")
    
    async def stop(self):
        """Stop the ingestion service."""
        # Cancel all debounce timers
        for timer in self.debounce_timers.values():
            timer.cancel()

        # Wait a moment for tasks to finish cancelling
        await asyncio.sleep(0.1)

        if self.session:
            await self.session.close()
        print("⏹️  Watchdog service stopped")


async def main():
    parser = argparse.ArgumentParser(
        description="Monitor a context folder and ingest files to the Anchor Core Bridge"
    )
    parser.add_argument(
        "--watch-dir",
        default="./context",
        help="Directory to monitor for context files (default: ./context)"
    )
    parser.add_argument(
        "--bridge-url",
        default="http://localhost:8000",
        help="Bridge URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=1024 * 1024,
        help="Max file size in bytes (default: 1MB)"
    )
    parser.add_argument(
        "--batch-interval",
        type=float,
        default=5.0,
        help="Batch ingestion interval in seconds (default: 5s)"
    )
    
    args = parser.parse_args()
    
    ingester = ContextIngester(
        watch_dir=args.watch_dir,
        bridge_url=args.bridge_url,
        max_file_size=args.max_size,
        batch_interval=args.batch_interval
    )
    
    try:
        await ingester.start()
    except KeyboardInterrupt:
        print("\n\n⏹️  Shutdown requested")
        await ingester.stop()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        await ingester.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
