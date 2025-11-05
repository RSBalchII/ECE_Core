"""
Mock TRM (Tokenized Reasoning Model) Service

This module implements a mock version of the TRM Service for iterative refinement
of thought processes. This allows testing the Markovian thinking workflow without
requiring a separate specialized model service.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import logging
import re


app = FastAPI(title="TRM Mock Service", version="1.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RefineRequest(BaseModel):
    query: str
    current_thought: str
    carryover: str
    task: str


class CritiqueRequest(BaseModel):
    query: str
    thought: str
    task: str


class ProcessChunkRequest(BaseModel):
    query: str
    context_chunk: str
    carryover: str
    task: str


@app.get("/health")
async def health_check():
    """Health check endpoint for the TRM service."""
    return {"status": "healthy", "service": "TRM Mock Service"}


@app.post("/refine")
async def refine_thought(request: RefineRequest) -> Dict[str, Any]:
    """Refine a given thought based on the query and carryover context."""
    logger.info(f"Refining thought for query: {request.query[:50]}...")

    # This is a mock implementation - in a real service, this would use a specialized model
    refined_thought = _mock_refine_thought(
        request.query, request.current_thought, request.carryover
    )

    return {
        "refined_thought": refined_thought,
        "query": request.query,
        "original_thought": request.current_thought,
    }


@app.post("/critique")
async def critique_thought(request: CritiqueRequest) -> Dict[str, Any]:
    """Critique a given thought based on the query."""
    logger.info(f"Critiquing thought for query: {request.query[:50]}...")

    # This is a mock implementation - in a real service, this would use a specialized model
    critique = _mock_critique_thought(request.query, request.thought)

    return critique


@app.post("/process_chunk")
async def process_chunk(request: ProcessChunkRequest) -> Dict[str, Any]:
    """Process a chunk of context with the TRM service."""
    logger.info(f"Processing chunk for query: {request.query[:50]}...")

    # This is a mock implementation - in a real service, this would use a specialized model
    processed_chunk = _mock_process_chunk(
        request.query, request.context_chunk, request.carryover
    )

    return {"processed_chunk": processed_chunk, "query": request.query}


def _mock_refine_thought(query: str, current_thought: str, carryover: str) -> str:
    """
    Mock implementation of thought refinement.
    In a real implementation, this would use a specialized model for refinement.
    """
    import random

    # Add some context from the carryover if provided
    if carryover.strip():
        context_addition = f"\n\nAdditional context from previous thought: {carryover}"
    else:
        context_addition = ""

    # Make some minor improvements to the thought
    refined = current_thought

    # Expand on key points
    if "consider" in refined.lower():
        refined = refined.replace("consider", "carefully consider and analyze", 1)

    if "important" in refined.lower():
        refined = refined.replace("important", "critically important", 1)

    # Add logical flow
    if "because" not in refined.lower():
        refined += (
            " This approach is methodical because it builds on established principles."
        )

    # Add a conclusion if it seems to be missing
    if not refined.lower().endswith((".", "!", "?")):
        refined += (
            ". This refined approach addresses the core requirements of the query."
        )

    # Randomly inject some improvement
    if random.random() > 0.7:
        refined = f"REFINED: {refined} [Enhanced with additional considerations based on the query: {query[:50]}...]"

    return refined + context_addition


def _mock_critique_thought(query: str, thought: str) -> Dict[str, Any]:
    """
    Mock implementation of thought critique.
    In a real implementation, this would use a specialized model for critique.
    """
    import random

    # Analyze the thought for potential issues
    issues = []
    suggestions = []

    # Check for common issues
    if len(thought.split()) < 10:
        issues.append("Thought is too brief and lacks detail")
        suggestions.append("Expand on the key points with more explanation")

    if (
        "perhaps" in thought.lower()
        or "maybe" in thought.lower()
        or "might" in thought.lower()
    ):
        issues.append("Thought contains uncertain language")
        suggestions.append("Replace uncertain language with more definitive statements")

    if not any(
        word in thought.lower()
        for word in ["because", "therefore", "consequently", "hence"]
    ):
        issues.append("Lacks logical connections")
        suggestions.append("Add logical connectors to improve reasoning flow")

    # Generate a random critique for demonstration
    if random.random() > 0.5:
        issues.append("Could benefit from more specific examples")
        suggestions.append("Include concrete examples to support the reasoning")

    # Calculate a validity score
    base_score = 0.8 if not issues else 0.8 - (len(issues) * 0.1)
    validity_score = max(0.1, min(1.0, base_score + random.uniform(-0.1, 0.1)))

    return {
        "valid": len(issues) == 0,
        "validity_score": validity_score,
        "issues": issues,
        "suggestions": suggestions,
        "query": query,
        "original_thought": thought,
    }


def _mock_process_chunk(query: str, context_chunk: str, carryover: str) -> str:
    """
    Mock implementation of chunk processing.
    In a real implementation, this would use a specialized model for processing.
    """
    # Combine context and carryover
    full_context = f"{carryover} {context_chunk}".strip()

    # Process the chunk in the context of the query
    processed = f"PROCESSED CHUNK: {full_context}"

    # Add query-specific processing
    if "analyze" in query.lower():
        processed += f" (Analysis specific to query: {query[:30]}...)"
    elif "summarize" in query.lower():
        processed += f" (Summary optimized for query: {query[:30]}...)"
    else:
        processed += f" (Processed in context of query: {query[:30]}...)"

    return processed


@app.on_event("startup")
async def startup_event():
    """Startup event for the TRM service."""
    logger.info("TRM Mock Service is starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event for the TRM service."""
    logger.info("TRM Mock Service is shutting down...")


if __name__ == "__main__":
    import uvicorn

    # Run the mock TRM service on port 8081 (as specified in the reasoning flow)
    uvicorn.run(app, host="0.0.0.0", port=8081)
