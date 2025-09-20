from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import uvicorn
import logging
import uuid # Import uuid for session_id
import os
import sys

# Add the orchestrator agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ece", "agents", "tier1", "orchestrator"))

from orchestrator_agent import OrchestratorAgent

# Set up logging
logging.basicConfig(level=logging.DEBUG) # Keep DEBUG for now
logger = logging.getLogger(__name__)

# Add a filter to exclude /v1/models from the logs
class NoModelsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/v1/models" not in record.getMessage()

# Add the filter to the uvicorn.access logger
logging.getLogger("uvicorn.access").addFilter(NoModelsFilter())


# Create the FastAPI app
app = FastAPI(
    title="ECE Orchestrator Agent",
    description="The Orchestrator is responsible for coordinating other ECE agents.",
    version="1.0.0"
)

# Initialize OrchestratorAgent
# For now, use a fixed session_id or generate a new one per app instance
# In a real application, session_id would come from user session management
orchestrator_agent = OrchestratorAgent(session_id=str(uuid.uuid4()))


@app.on_event("startup")
async def startup_event():
    """Start the cohesion loop when the application starts"""
    orchestrator_agent.start_cohesion_loop()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the cohesion loop when the application shuts down"""
    orchestrator_agent.stop_cohesion_loop()

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Orchestrator Agent is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/v1/models")
async def get_models():
    """
    Placeholder endpoint to mimic the Ollama /v1/models endpoint.
    Returns an empty list of models to prevent 404 errors.
    """
    return {"data": []}

@app.get("/process_prompt") # Change to GET
async def process_prompt(prompt: str = Query(...)):
    """
    Endpoint to process a user prompt using the OrchestratorAgent.
    """
    logger.debug(f"Received prompt: {prompt}")
    try:
        response = await orchestrator_agent.process_prompt(prompt)
        logger.info(f"Sending response: {response}")
        return {"response": response}
    except Exception as e:
        logger.error(f"Error processing prompt with OrchestratorAgent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/get_analysis_result")
async def get_analysis_result(analysis_id: str = Query(...)):
    """
    Endpoint to retrieve the result of a complex reasoning analysis.
    """
    logger.debug(f"Received request for analysis result with ID: {analysis_id}")
    try:
        response = await orchestrator_agent.get_analysis_result(analysis_id)
        if response:
            return {"status": "complete", "response": response}
        else:
            return {"status": "pending"}
    except Exception as e:
        logger.error(f"Error retrieving analysis result: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug" # Keep debug log level
    )