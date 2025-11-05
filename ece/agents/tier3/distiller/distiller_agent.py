import yaml
import redis
import spacy
import os
from typing import Dict, Any, List
from fastapi import FastAPI
from pydantic import BaseModel
import logging
import uvicorn

# Import UTCP data models for manual creation
from utcp.data.utcp_manual import UtcpManual
from utcp.data.tool import Tool
from utcp_http.http_call_template import HttpCallTemplate

# Import and set up ECE logging system
try:
    from ece.common.logging_config import get_logger

    logger = get_logger("distiller")
except ImportError:
    # Fallback if logging config not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Could not import ECE logging system, using default logging")

# Initialize FastAPI app
app = FastAPI(
    title="ECE Distiller Agent",
    description="The Distiller is responsible for processing raw text from the context cache.",
    version="1.0.0",
)


class DistillerData(BaseModel):
    text: str
    source: str
    timestamp: str


class DistillerAgent:
    """
    The Distiller Agent is responsible for processing raw text from the context cache,
    extracting entities and relationships, and structuring the data for the Archivist.
    """

    def __init__(self):
        """Initialize the DistillerAgent."""
        self.name = "Distiller"
        self.version = "1.0.0"
        self.config = self._load_config()
        self.redis_client = self._connect_to_redis()
        self.nlp = self._load_spacy_model()

    def _load_config(self) -> Dict[str, Any]:
        """Load the agent configuration from a YAML file."""
        config_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "..", "config.yaml"
            )
        )
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _connect_to_redis(self) -> redis.Redis:
        """Connect to the Redis cache."""
        redis_url = self.config.get("cache", {}).get(
            "redis_url", "redis://localhost:6379"
        )
        return redis.from_url(redis_url)

    def _load_spacy_model(self) -> Any:
        """Load the spaCy NLP model."""
        return spacy.load("en_core_web_sm")

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from the given text."""
        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            entities.append(
                {
                    "text": ent.text,
                    "label": ent.label_,
                    "description": spacy.explain(ent.label_),
                }
            )
        return entities

    def identify_relationships(
        self, text: str, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify relationships between entities in the text."""
        # This is a placeholder for a more sophisticated relationship extraction logic
        return []

    def structure_data(
        self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Structure the extracted entities and relationships."""
        return {
            "timestamp": self.get_current_timestamp(),
            "entities": entities,
            "relationships": relationships,
            "summary": {
                "total_entities": len(entities),
                "total_relationships": len(relationships),
            },
        }

    def read_context_cache(self) -> Dict[str, str]:
        """Read all data from the context cache."""
        cache_data = {}
        processed_keys = self.redis_client.smembers("distiller:processed_entries")
        for key in self.redis_client.keys("context_cache:*"):
            if key.decode("utf-8") not in processed_keys:
                cache_data[key.decode("utf-8")] = self.redis_client.get(key).decode(
                    "utf-8"
                )
        return cache_data

    def mark_entry_as_processed(self, key: str):
        """Mark a cache entry as processed."""
        self.redis_client.sadd("distiller:processed_entries", key)

    def get_current_timestamp(self) -> str:
        """Get the current timestamp in ISO 8601 format."""
        return __import__("datetime").datetime.now().isoformat()

    def distill_context(self, cache_manager) -> str:
        """Distill the context from the cache."""
        all_text = ""
        keys = cache_manager.redis_client.keys("context_cache:*")
        for key in keys:
            entry = cache_manager.retrieve(
                key.decode("utf-8").replace("context_cache:", "")
            )
            if entry:
                all_text += entry.value + "n"

        if not all_text:
            return "No new context to distill."

        # For the MVP, we'll just return a simple summary.
        summary = f"Distilled context from {len(keys)} entries. Total length: {len(all_text)} characters."

        return summary


# Initialize the DistillerAgent
distiller_agent = DistillerAgent()


@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "ECE Distiller Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/utcp")
async def utcp_manual():
    """UTCP Manual endpoint for tool discovery."""
    # Create UTCP Manual with tools provided by this agent
    manual = UtcpManual(
        manual_version="1.0.0",
        utcp_version="1.0.2",
        tools=[
            Tool(
                name="process_text",
                description="Process raw text to extract entities and relationships",
                tags=["processing", "nlp", "distiller"],
                inputs={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The raw text to process",
                        },
                        "source": {
                            "type": "string",
                            "description": "The source of the text",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "The timestamp of the text processing",
                        },
                    },
                    "required": ["text", "source", "timestamp"],
                },
                outputs={
                    "type": "object",
                    "properties": {
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp of processing",
                        },
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "label": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                            },
                        },
                        "relationships": {"type": "array", "items": {"type": "object"}},
                        "summary": {
                            "type": "object",
                            "properties": {
                                "total_entities": {"type": "integer"},
                                "total_relationships": {"type": "integer"},
                            },
                        },
                    },
                },
                tool_call_template=HttpCallTemplate(
                    name="distiller_process_text",
                    call_template_type="http",
                    url="http://localhost:8001/process_text",
                    http_method="POST",
                ),
            )
        ],
    )
    return manual


@app.post("/process_text")
async def process_text(data: DistillerData):
    """
    Endpoint to receive raw text, extract entities and relationships, and return structured data.
    """
    logger.info(f"Received text for distillation from {data.source}")

    entities = distiller_agent.extract_entities(data.text)
    relationships = distiller_agent.identify_relationships(data.text, entities)

    structured_data = distiller_agent.structure_data(entities, relationships)

    return structured_data


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
