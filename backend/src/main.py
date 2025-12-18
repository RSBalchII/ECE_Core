"""Minimal, single-entrypoint for ECE_Core.

This file uses `src.app_factory.create_app_with_routers()` to construct the app; the factory
ensures routers are included and avoids initialization side effects at import time.
"""
from src.app_factory import create_app_with_routers
from src.config import settings
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Ensure logs directory exists
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, settings.ece_log_level),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            log_dir / "server.log",
            maxBytes=500*1024,  # 500KB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

app = create_app_with_routers()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=settings.ece_host, port=settings.ece_port)
