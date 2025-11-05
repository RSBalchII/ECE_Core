# chimaera-multi-modal-agent/external-context-engine-ece/chimaera-multi-modal-agent-External-Context-Engine-ECE-5350fdcd697ef19de30a88acf572d9cfa56e536e/ece/agents/tier1/orchestrator/main.py
"""
Main entry point for the ECE Orchestrator Agent's FastAPI server.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from xml.etree import ElementTree as ET
import json
import uuid
import httpx
import os
import logging

# --- CRITICAL CHANGE: Use a relative import to find the agent file ---
from .orchestrator_agent import EnhancedOrchestratorAgent
from ece.agents.common.model_loader import ModelManager

import json
import uuid
import httpx
import logging

# Import and set up ECE logging system
try:
    from ece.common.logging_config import get_logger

    logger = get_logger("orchestrator")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")

# Suppress INFO level logs for httpx and uvicorn.access
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


async def log_request(request: httpx.Request):
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")


async def log_response(response: httpx.Response):
    request = response.request
    logger.info(
        f"Response: {request.method} {request.url} - Status {response.status_code}"
    )
    logger.info(f"Response Headers: {response.headers}")
    # Optionally log response body for debugging, but be careful with sensitive data
    # logger.info(f"Response Body: {response.text}")


# Create a default httpx client with event hooks
# This client will be used by default for any httpx requests that don't specify a client
httpx_client = httpx.AsyncClient(
    event_hooks={"request": [log_request], "response": [log_response]}
)

# Initialize the FastAPI app
app = FastAPI(
    title="ECE Orchestrator Agent",
    description="The central cognitive unit for the External Context Engine v2.0",
    version="2.0.0",
)

# Create a singleton instance of the EnhancedOrchestratorAgent - REMOVED TO FIX SESSION ID ISSUE
# orchestrator = EnhancedOrchestratorAgent()


@app.on_event("startup")
async def startup_event():
    """
    Event handler for application startup.
    """
    global model_manager
    try:
        print("Orchestrator agent (ECE v2.0) initializing...")
        # Initialize the model manager during startup
        model_manager = ModelManager()
        print("Orchestrator initialized and ready to receive requests.")
    except Exception as e:
        import traceback

        error_details = (
            f"Error during startup: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        )
        print(error_details)
        # Log error using appropriate logger
        try:
            logger.error(f"Error during startup: {e}")
        except:
            import logging

            logging.basicConfig(level=logging.INFO)
            default_logger = logging.getLogger(__name__)
            default_logger.error(f"Error during startup: {e}")


@app.post("/process_prompt", response_class=PlainTextResponse)
async def process_prompt_endpoint(request: Request):
    """
    The primary endpoint for processing user prompts.
    """
    logger.debug("Entering process_prompt_endpoint")
    try:
        logger.debug("Inside try block of process_prompt_endpoint")
        # --- FIX: Instantiate EnhancedOrchestratorAgent per request with a unique session ID ---
        session_id = str(uuid.uuid4())
        logger.debug(f"Generated session_id: {session_id}")
        orchestrator = EnhancedOrchestratorAgent(session_id=session_id)
        logger.debug("EnhancedOrchestratorAgent instantiated successfully")

        body = await request.body()
        logger.debug(f"Request body received: {body}")
        poml_string = body.decode("utf-8")
        logger.debug(f"Decoded body: {poml_string}")

        try:
            root = ET.fromstring(poml_string)
            prompt_element = root.find(".//prompt")
            if prompt_element is None or not prompt_element.text:
                raise ValueError("Prompt not found in POML payload")
            user_prompt = prompt_element.text.strip()
        except ET.ParseError:
            try:
                data = json.loads(poml_string)
                user_prompt = data.get("prompt")
                if not user_prompt:
                    raise ValueError("Prompt not found in JSON payload")
            except json.JSONDecodeError:
                raise ValueError("Invalid POML or JSON payload")

        logger.debug(f"Parsed user prompt: {user_prompt}")
        final_response = await orchestrator.process_prompt_with_context_management(
            user_prompt
        )
        logger.debug(f"Final response: {final_response}")

        return PlainTextResponse(content=final_response)

    except ValueError as e:
        logger.error(f"ValueError caught: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Bad Request: {str(e)}")
    except Exception as e:
        import traceback

        error_details = f"An unexpected error occurred: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        logger.error(error_details)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/v1/models")
async def get_ollama_models():
    """
    Returns a list of models available from the configured LLM provider.
    """
    from ece.common.config_loader import get_config

    # Load active provider from config loader to determine if we should expect Ollama to be available
    config = get_config()
    active_provider = config.get_active_provider()

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_base_url}/api/tags", timeout=5.0)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            models_data = response.json()
            # Extract model names and return them
            models = [
                {"id": model["model"], "object": "model"}
                for model in models_data.get("models", [])
            ]
            return JSONResponse(
                content={
                    "success": True,
                    "data": models,
                    "object": "list",
                    "provider": active_provider,
                }
            )
    except httpx.RequestError as e:
        # Only log error if the active provider is actually Ollama or Docker Desktop (not llama.cpp)
        if active_provider in ["ollama", "docker_desktop"]:
            logger.error(f"Error connecting to Ollama at {ollama_base_url}: {e}")
            return JSONResponse(
                content={
                    "success": False,
                    "error": f"Error connecting to Ollama at {ollama_base_url}: {e}",
                    "provider": active_provider,
                },
                status_code=503,
            )
        else:
            # For llama_cpp provider, this is expected behavior, so only log as debug
            logger.debug(
                f"Connection to Ollama at {ollama_base_url} failed (this is expected if using {active_provider}): {e}"
            )
            return JSONResponse(
                content={
                    "success": False,
                    "error": f"Connection to Ollama at {ollama_base_url} failed (this is expected if using {active_provider}): {e}",
                    "provider": active_provider,
                },
                status_code=503,
            )
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching LLM models: {e}")
        return JSONResponse(
            content={
                "success": False,
                "error": f"Internal server error: {e}",
                "provider": active_provider,
            },
            status_code=500,
        )


# Global model manager instance for the orchestrator - initialize as None, will be set in startup
model_manager = None


@app.get("/models/available")
async def get_available_models():
    """Get list of available models from the models directory."""
    global model_manager
    try:
        if model_manager is None:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Model manager not initialized yet",
                    "available_models": [],
                    "count": 0,
                },
                status_code=503,
            )

        available_models = model_manager.get_available_models()
        return JSONResponse(
            content={
                "success": True,
                "available_models": available_models,
                "count": len(available_models),
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": f"Error retrieving available models: {str(e)}",
                "available_models": [],
                "count": 0,
            },
            status_code=500,
        )


@app.get("/models/current")
async def get_current_model():
    """Get the currently active model."""
    global model_manager
    try:
        if model_manager is None:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Model manager not initialized yet",
                    "current_model": None,
                    "is_running": False,
                },
                status_code=503,
            )

        current_model = model_manager.get_current_model()
        return JSONResponse(
            content={
                "success": True,
                "current_model": current_model,
                "is_running": current_model != "No model currently running",
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": f"Error retrieving current model: {str(e)}",
                "current_model": None,
                "is_running": False,
            },
            status_code=500,
        )


@app.post("/models/select")
async def select_model(request: Request):
    """Select a model by name and start it if not already running."""
    global model_manager
    try:
        if model_manager is None:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Model manager not initialized yet",
                    "selected_model": None,
                },
                status_code=503,
            )

        data = await request.json()
        model_name = data.get("model_name")

        if not model_name:
            raise HTTPException(status_code=400, detail="Model name is required")

        # Select and start the specified model using the new select_model method
        success = model_manager.select_model(model_name)

        if success:
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Model {model_name} selected and started successfully",
                    "selected_model": model_name,
                    "details": {
                        "model_name": model_name,
                        "port": model_manager.model_server_port,
                        "api_base": model_manager.api_base,
                    },
                }
            )
        else:
            return JSONResponse(
                content={
                    "success": False,
                    "error": f"Failed to select and start model: {model_name}",
                    "selected_model": model_name,
                },
                status_code=500,
            )
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": f"Error selecting model: {str(e)}",
                "selected_model": model_name if "model_name" in locals() else None,
            },
            status_code=500,
        )


@app.post("/models/start")
async def start_model_endpoint(request: Request):
    """Start a specific model server."""
    global model_manager
    try:
        if model_manager is None:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Model manager not initialized yet",
                    "model": None,
                },
                status_code=503,
            )

        data = await request.json()
        model_name = data.get("model_name")
        port = data.get("port")  # Optional port parameter

        if not model_name:
            raise HTTPException(status_code=400, detail="Model name is required")

        success = model_manager.start_model(model_name, port)

        if success:
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Model {model_name} started successfully",
                    "model": model_name,
                    "details": {
                        "model_name": model_name,
                        "port": model_manager.model_server_port,
                        "api_base": model_manager.api_base,
                    },
                }
            )
        else:
            return JSONResponse(
                content={
                    "success": False,
                    "error": f"Failed to start model: {model_name}",
                    "model": model_name,
                },
                status_code=500,
            )
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": f"Error starting model: {str(e)}",
                "model": model_name if "model_name" in locals() else None,
            },
            status_code=500,
        )


@app.post("/models/stop")
async def stop_model_endpoint():
    """Stop the currently running model server."""
    global model_manager
    try:
        if model_manager is None:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Model manager not initialized yet",
                },
                status_code=503,
            )

        success = model_manager.stop_model()

        if success:
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Model server stopped successfully",
                }
            )
        else:
            return JSONResponse(
                content={"success": False, "error": "Failed to stop model server"},
                status_code=500,
            )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": f"Error stopping model: {str(e)}"},
            status_code=500,
        )


@app.get("/models/status")
async def get_model_status():
    """Get the status of the model management system."""
    global model_manager
    try:
        if model_manager is None:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Model manager not initialized yet",
                    "status": {},
                },
                status_code=503,
            )

        status = model_manager.get_model_status()
        return JSONResponse(content={"success": True, "status": status})
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": f"Error getting model status: {str(e)}",
                "status": {},
            },
            status_code=500,
        )


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify orchestrator is running and healthy.
    """
    global model_manager
    try:
        # Check if model_manager is initialized
        if model_manager is None:
            return JSONResponse(
                content={
                    "status": "starting_up",
                    "model_healthy": False,
                    "message": "Orchestrator is still starting up",
                }
            )

        # Check model health - await the async method
        model_healthy = (
            await model_manager.check_model_health() if model_manager else False
        )
        model_status = model_manager.get_model_status() if model_manager else {}

        return JSONResponse(
            content={
                "status": "ok",
                "model_healthy": model_healthy,
                "model_status": model_status,
                "message": "Orchestrator is running and healthy",
            }
        )
    except Exception as e:
        import traceback

        error_details = f"Health check error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_details)
        return JSONResponse(
            content={
                "status": "error",
                "model_healthy": False,
                "message": f"Health check error: {str(e)}",
            }
        )
