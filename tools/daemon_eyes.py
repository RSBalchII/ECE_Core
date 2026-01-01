#!/usr/bin/env python3
"""
Daemon Eyes - Background Vision Service for Anchor Core

This script provides automated screen observation for the Anchor Core system.
It captures screenshots at regular intervals, performs OCR, and sends the
extracted text to the Anchor Core bridge for automatic memory ingestion.

The goal is to provide "digital proprioception" - automatic awareness of
what the user is looking at without requiring manual input.
"""

import time
import requests
import pyautogui
import pytesseract
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


class DaemonEyes:
    def __init__(self, bridge_url="http://localhost:8000", 
                 interval=5, 
                 token="sovereign-secret",
                 enabled=True):
        """
        Initialize the Daemon Eyes service
        
        Args:
            bridge_url (str): URL of the Anchor Core bridge
            interval (int): Time between screenshots in seconds
            token (str): Authentication token for the bridge
            enabled (bool): Whether the daemon is initially enabled
        """
        self.bridge_url = bridge_url
        self.interval = interval
        self.token = token
        self.enabled = enabled
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - DaemonEyes - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('daemon_eyes.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Validate dependencies
        self._validate_dependencies()
        
        # Track previous content to avoid duplicates
        self.last_content = ""
        self.last_content_hash = ""

    def _validate_dependencies(self):
        """Validate that required dependencies are available"""
        try:
            # Test pyautogui
            pyautogui.size()  # Get screen size
        except Exception as e:
            self.logger.error(f"pyautogui not available: {e}")
            raise RuntimeError("pyautogui is required but not available")
        
        try:
            # Test pytesseract
            pytesseract.get_tesseract_version()
        except Exception as e:
            self.logger.error(f"pytesseract not available: {e}")
            raise RuntimeError("pytesseract is required but not available")
        
        self.logger.info("Dependencies validated successfully")

    def take_screenshot(self):
        """Take a screenshot of the current screen"""
        try:
            screenshot = pyautogui.screenshot()
            return screenshot
        except Exception as e:
            self.logger.error(f"Failed to take screenshot: {e}")
            return None

    def extract_text_ocr(self, image):
        """Extract text from image using OCR"""
        try:
            # Convert image to text using pytesseract
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            self.logger.error(f"OCR extraction failed: {e}")
            return ""

    def send_to_bridge(self, content):
        """Send extracted content to the Anchor Core bridge for ingestion"""
        try:
            # Prepare payload for memory ingestion
            payload = {
                "content": content,
                "source": "daemon_eyes",
                "timestamp": datetime.now().isoformat(),
                "type": "screen_content",
                "tags": ["vision", "automatic", "context"]
            }
            
            # Try different endpoints for memory ingestion
            endpoints = [
                f"{self.bridge_url}/v1/memory/ingest",
                f"{self.bridge_url}/archivist/ingest",
                f"{self.bridge_url}/v1/memory/create",
                f"{self.bridge_url}/v1/memory/store"
            ]
            
            response = None
            for endpoint in endpoints:
                try:
                    response = requests.post(
                        endpoint,
                        headers=self.headers,
                        json=payload,
                        timeout=10
                    )
                    
                    if response.status_code in [200, 201]:
                        self.logger.info(f"Content successfully sent to {endpoint}")
                        return True
                    else:
                        self.logger.debug(f"Endpoint {endpoint} returned {response.status_code}, trying next...")
                except requests.exceptions.RequestException as e:
                    self.logger.debug(f"Failed to reach {endpoint}: {e}")
                    continue
            
            # If all endpoints failed
            if response:
                self.logger.error(f"All ingestion endpoints failed. Last response: {response.status_code} - {response.text}")
            else:
                self.logger.error("All ingestion endpoints failed to connect")
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to send content to bridge: {e}")
            return False

    def should_process_content(self, content):
        """Determine if content should be processed (avoid duplicates)"""
        if not content.strip():
            return False
        
        # Create a hash of the content to detect duplicates
        content_hash = hash(content.strip().lower())
        
        # If content is similar to last processed, skip
        if content_hash == self.last_content_hash:
            return False
        
        # If content is too similar to last (90% match), skip
        if self.last_content and len(content) > 0:
            similarity = self._calculate_similarity(content.lower(), self.last_content.lower())
            if similarity > 0.9:
                return False
        
        return True

    def _calculate_similarity(self, str1, str2):
        """Calculate similarity between two strings"""
        if len(str1) == 0 or len(str2) == 0:
            return 0.0
        
        # Simple character-based similarity
        common_chars = sum(min(str1.count(c), str2.count(c)) for c in set(str1 + str2))
        total_chars = len(str1) + len(str2)
        
        return (2 * common_chars) / total_chars if total_chars > 0 else 0.0

    def process_screenshot(self):
        """Process a single screenshot cycle"""
        if not self.enabled:
            return False
        
        # Take screenshot
        screenshot = self.take_screenshot()
        if not screenshot:
            return False
        
        # Extract text via OCR
        extracted_text = self.extract_text_ocr(screenshot)
        
        if not extracted_text:
            self.logger.debug("No text extracted from screenshot")
            return False
        
        # Check if content should be processed (avoid duplicates)
        if not self.should_process_content(extracted_text):
            self.logger.debug("Content skipped (duplicate or empty)")
            return False
        
        # Send to bridge
        success = self.send_to_bridge(extracted_text)
        
        if success:
            # Update tracking variables
            self.last_content = extracted_text
            self.last_content_hash = hash(extracted_text.strip().lower())
            self.logger.info(f"Processed {len(extracted_text)} characters from screenshot")
        
        return success

    def run(self):
        """Main daemon loop"""
        self.logger.info(f"Daemon Eyes started. Capturing every {self.interval} seconds...")
        self.logger.info(f"Bridge URL: {self.bridge_url}")
        
        try:
            while True:
                if self.enabled:
                    try:
                        self.process_screenshot()
                    except Exception as e:
                        self.logger.error(f"Error in screenshot processing: {e}")
                
                # Wait for the specified interval
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            self.logger.info("Daemon Eyes stopped by user")
        except Exception as e:
            self.logger.error(f"Daemon Eyes crashed: {e}")

    def toggle_enabled(self):
        """Toggle the daemon on/off"""
        self.enabled = not self.enabled
        status = "enabled" if self.enabled else "disabled"
        self.logger.info(f"Daemon Eyes {status}")
        return self.enabled

    def set_interval(self, new_interval):
        """Change the screenshot interval"""
        if new_interval > 0:
            self.interval = new_interval
            self.logger.info(f"Screenshot interval set to {new_interval} seconds")
            return True
        return False


def main():
    """Command line interface for Daemon Eyes"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Daemon Eyes - Background Vision Service")
    parser.add_argument("--interval", type=int, default=5, 
                       help="Screenshot interval in seconds (default: 5)")
    parser.add_argument("--bridge-url", default="http://localhost:8000",
                       help="Anchor Core bridge URL (default: http://localhost:8000)")
    parser.add_argument("--token", default="sovereign-secret",
                       help="Authentication token (default: sovereign-secret)")
    parser.add_argument("--test", action="store_true",
                       help="Run a single screenshot test instead of daemon mode")
    
    args = parser.parse_args()
    
    daemon = DaemonEyes(
        bridge_url=args.bridge_url,
        interval=args.interval,
        token=args.token
    )
    
    if args.test:
        print("Running single screenshot test...")
        success = daemon.process_screenshot()
        print(f"Test {'succeeded' if success else 'failed'}")
    else:
        print(f"Starting Daemon Eyes (interval: {args.interval}s)...")
        daemon.run()


if __name__ == "__main__":
    main()