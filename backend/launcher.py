from src.app_factory import create_app_with_routers
from src.config import settings
import logging

logging.basicConfig(level=getattr(logging, settings.ece_log_level), format='%(asctime)s - %(levelname)s - %(message)s')

app = create_app_with_routers()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=settings.ece_host, port=settings.ece_port)
