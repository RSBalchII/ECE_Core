"""Small wrapper to provide a clean app import for tests and tools.
This module avoids pulling in legacy `src.main` content and provides a
single `app` object to import in tests or external tooling.
"""
from src.bootstrap import create_app
from src.config import settings
import logging

logging.basicConfig(level=getattr(logging, settings.ece_log_level), format='%(asctime)s - %(levelname)s - %(message)s')

def create_app_with_routers():
	"""Create the FastAPI app and include all API routers.

	Use this factory to create an app instance after pytest autouse fixtures have run
	to ensure that patches (fake LLM, fake Redis) are applied before the app lifecycle
	creates real clients.
	"""
	app = create_app()
	from src.api import (
	memory_router,
	reason_router,
	health_router,
	# openai_router,
	plugins_router,
	audit_router,
    plan_router,
	)

	# Import browser bridge plugin
	from src.plugins.browser_bridge.plugin import router as browser_bridge_router
	# Import Coda Chat Recipe
	from src.recipes.coda_chat import router as coda_chat_router
	# Import Archivist Recipe
	from src.recipes.archivist import router as archivist_router

	from fastapi import Depends
	from src.security import verify_api_key

	app.include_router(health_router)  # Public
	app.include_router(health_router)  # Public
	# app.include_router(openai_router, dependencies=[Depends(verify_api_key)])
	app.include_router(reason_router, dependencies=[Depends(verify_api_key)])
	app.include_router(plugins_router, dependencies=[Depends(verify_api_key)])
	app.include_router(audit_router, dependencies=[Depends(verify_api_key)])
	app.include_router(plan_router, dependencies=[Depends(verify_api_key)])

	# Include browser bridge router
	app.include_router(browser_bridge_router)

	# Temporarily remove dependencies to debug 403
	app.include_router(coda_chat_router, prefix="/chat") #, dependencies=[Depends(verify_api_key)])

	# Include Archivist Recipe
	app.include_router(archivist_router, prefix="/archivist", dependencies=[Depends(verify_api_key)])

	return app


# Backwards compatible app instance for import-time use (rare)
app = None
