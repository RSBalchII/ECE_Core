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
from .orchestrator_agent import OrchestratorAgent

import json
import uuid
import httpx
import logging

# Configure logging for httpx requests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress INFO level logs for httpx and uvicorn.access
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

async def log_request(request: httpx.Request):
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")

async def log_response(response: httpx.Response):
    request = response.request
    logger.info(f"Response: {request.method} {request.url} - Status {response.status_code}")
    logger.info(f"Response Headers: {response.headers}")
    # Optionally log response body for debugging, but be careful with sensitive data
    # logger.info(f"Response Body: {response.text}")

# Create a default httpx client with event hooks
# This client will be used by default for any httpx requests that don't specify a client
httpx_client = httpx.AsyncClient(event_hooks={'request': [log_request], 'response': [log_response]})

# Initialize the FastAPI app
app = FastAPI(
    title="ECE Orchestrator Agent",
    description="The central cognitive unit for the External Context Engine v2.0",
    version="2.0.0"
)

# Create a singleton instance of the OrchestratorAgent - REMOVED TO FIX SESSION ID ISSUE
# orchestrator = OrchestratorAgent()

@app.on_event("startup")
async def startup_event():
    """
    Event handler for application startup.
    """
    print("Orchestrator agent (ECE v2.0) initializing...")
    print("Orchestrator initialized and ready to receive requests.")

@app.post("/process_prompt", response_class=PlainTextResponse)
async def process_prompt_endpoint(request: Request):
    """
    The primary endpoint for processing user prompts.
    """
    try:
        # --- FIX: Instantiate OrchestratorAgent per request with a unique session ID ---
        session_id = str(uuid.uuid4())
        orchestrator = OrchestratorAgent(session_id=session_id)
        
        body = await request.body()
        poml_string = body.decode('utf-8')
        
        try:
            root = ET.fromstring(poml_string)
            prompt_element = root.find('.//prompt')
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

        final_response = await orchestrator.process_prompt(user_prompt)
        
        return PlainTextResponse(content=final_response)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Bad Request: {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/v1/models")
async def get_ollama_models():
    """
    Returns a list of models available from the configured Ollama instance.
    """
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_base_url}/api/tags", timeout=5.0)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            models_data = response.json()
            # Extract model names and return them
            models = [{"id": model["model"], "object": "model"} for model in models_data.get("models", [])]
            return JSONResponse(content={"data": models, "object": "list"})
    except httpx.RequestError as e:
        logger.error(f"Error connecting to Ollama at {ollama_base_url}: {e}")
        raise HTTPException(status_code=503, detail=f"Could not connect to Ollama: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching Ollama models: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/health")
def health_check():
    return JSONResponse(content={"status": "ok"})