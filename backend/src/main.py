"""Minimal, single-entrypoint for ECE_Core.

This file uses `src.app_factory.create_app_with_routers()` to construct the app; the factory
ensures routers are included and avoids initialization side effects at import time.
"""
from src.app_factory import create_app_with_routers
from src.config import settings
import logging

logging.basicConfig(level=getattr(logging, settings.ece_log_level), format='%(asctime)s - %(levelname)s - %(message)s')

app = create_app_with_routers()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=settings.ece_host, port=settings.ece_port)
