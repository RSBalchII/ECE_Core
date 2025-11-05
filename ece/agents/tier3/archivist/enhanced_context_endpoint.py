#!/usr/bin/env python3
"""
Enhanced Context Endpoint Implementation for Archivist Agent

This module implements the /enhanced_context endpoint that coordinates with
the QLearning Agent to provide enhanced context-aware responses.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from pydantic import BaseModel

# Import the existing models and clients
# (These should already be available in the archivist_agent.py file)
# from .archivist_agent import qlearning_client, redis_client

logger = logging.getLogger(__name__)


class EnhancedContextRequest(BaseModel):
    """Model for enhanced context requests."""

    query: str
    keywords: List[str] = []
    max_tokens: int = 1000000  # Allow up to 1M tokens as requested
    session_id: Optional[str] = None
    max_contexts: int = 10


class EnhancedContextResponse(BaseModel):
    """Model for enhanced context responses."""

    enhanced_context: str
    related_memories: List[Dict[str, Any]] = []
    session_id: str
    timestamp: str
    token_count: int = 0


class MemoryPathSummary(BaseModel):
    """Summary of a memory path for context building."""

    nodes: List[str]
    relationships: List[Dict[str, Any]]
    score: float
    summary: str = ""


async def extract_keywords_from_query(query: str) -> List[str]:
    """Extract keywords from a query using simple NLP techniques."""
    import re

    # Split text into words and filter out common stop words
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "was",
        "were",
        "are",
        "be",
        "been",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "what",
        "who",
        "when",
        "where",
        "why",
        "how",
    }
    words = re.findall(r"\b\w+\b", query.lower())
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    return list(set(keywords))[:20]  # Return unique keywords, limit to 20


async def query_qlearning_agent_for_paths(
    keywords: List[str], max_paths: int = 10
) -> List[Any]:
    """
    Query the QLearning Agent for optimal paths related to keywords.

    Args:
        keywords: List of keywords to search for
        max_paths: Maximum number of paths to return

    Returns:
        List of memory paths from the QLearning Agent
    """
    try:
        # This assumes qlearning_client is available from the global scope
        # In practice, this would be imported or passed as a parameter
        if "qlearning_client" not in globals():
            logger.warning("QLearning client not available, returning empty paths")
            return []

        # Find optimal paths using the QLearning Agent
        if keywords and len(keywords) >= 2:
            start_node = keywords[0]
            end_node = keywords[-1]
        else:
            start_node = keywords[0] if keywords else "concept_start"
            end_node = "concept_end"
        paths = await qlearning_client.find_optimal_path(start_node, end_node)

        # Limit to max_paths
        return paths[:max_paths] if paths else []

    except Exception as e:
        logger.error(f"Error querying QLearning Agent: {str(e)}", exc_info=True)
        return []


async def build_context_from_paths(paths: List[Any], max_tokens: int = 1000000) -> str:
    """
    Build enhanced context from QLearning paths, respecting token limits.

    Args:
        paths: List of memory paths from QLearning Agent
        max_tokens: Maximum number of tokens to include in context

    Returns:
        Enhanced context string within token limits
    """
    if not paths:
        return "No related context found."

    context_parts = []
    total_tokens = 0

    # Process each path to build context
    for i, path in enumerate(paths[:10]):  # Limit to top 10 paths
        if total_tokens >= max_tokens:
            break

        # Extract information from the path
        path_info = f"n--- Context Path {i + 1} ---\n"

        if hasattr(path, "nodes") and path.nodes:
            # Limit nodes for brevity (first 5 nodes)
            node_names = (
                path.nodes[:5]
                if isinstance(path.nodes, list)
                else [str(path.nodes)[:100]]
            )
            path_info += f"Nodes: {', '.join(node_names)}\n"

        if hasattr(path, "relationships") and path.relationships:
            # Extract relationship types
            if isinstance(path.relationships, list):
                rel_types = list(
                    set(
                        [
                            rel.get("type", "RELATED_TO")
                            for rel in path.relationships[:3]
                        ]
                    )
                )
                path_info += f"Relationships: {', '.join(rel_types)}\n"
            else:
                path_info += f"Relationships: {str(path.relationships)[:100]}\n"

        if hasattr(path, "score"):
            path_info += f"Relevance Score: {path.score:.2f}\n"

        if hasattr(path, "length"):
            path_info += f"Path Length: {path.length}\n"

        # Estimate token count (rough approximation - 1.3 tokens per word)
        word_count = len(path_info.split())
        path_tokens = int(word_count * 1.3)

        if total_tokens + path_tokens <= max_tokens:
            context_parts.append(path_info)
            total_tokens += path_tokens
        else:
            # Add partial context if we're near the limit
            remaining_tokens = max_tokens - total_tokens
            if remaining_tokens > 100:  # Only add if we have meaningful space
                # Truncate the path info to fit within remaining tokens
                chars_per_token = len(path_info) / path_tokens if path_tokens > 0 else 1
                max_chars = int(
                    remaining_tokens * chars_per_token * 0.8
                )  # 80% to be safe
                truncated_info = path_info[:max_chars] + "... [truncated]"
                context_parts.append(truncated_info)
            break

    # Combine all context parts
    enhanced_context = "n".join(context_parts)

    # Add a summary at the beginning
    summary = f"Enhanced Context Summary (Generated from {len(context_parts)} knowledge paths):\n"
    summary += f"Total Context Length: ~{total_tokens} tokens\n"
    summary += "This context was retrieved and summarized by the QLearning Agent based on your query.\n"
    summary += "--- BEGIN CONTEXT ---\n"

    return summary + enhanced_context + "n--- END CONTEXT ---"


async def get_related_memories(
    keywords: List[str], max_contexts: int = 10
) -> List[Dict[str, Any]]:
    """
    Get related memories from the knowledge graph based on keywords.

    Args:
        keywords: List of keywords to search for
        max_contexts: Maximum number of related memories to return

    Returns:
        List of related memories
    """
    try:
        # This would typically query the Neo4j database for related memories
        # For now, we'll return a placeholder based on keywords
        related_memories = []

        # In a real implementation, this would:
        # 1. Query Neo4j for nodes related to the keywords
        # 2. Use embeddings for semantic search if available
        # 3. Rank results by relevance
        # 4. Return the top max_contexts results

        for i, keyword in enumerate(keywords[:max_contexts]):
            memory = {
                "id": f"memory_{i}",
                "content": f"Related memory content for keyword '{keyword}'",
                "relevance_score": 1.0 - (i * 0.1),  # Decreasing relevance
                "timestamp": datetime.now().isoformat(),
                "keywords": [keyword],
            }
            related_memories.append(memory)

        return related_memories

    except Exception as e:
        logger.error(f"Error retrieving related memories: {str(e)}")
        return []


async def store_enhanced_context_in_cache(
    session_id: str, enhanced_context: str, related_memories: List[Dict[str, Any]]
) -> bool:
    """
    Store enhanced context in Redis cache for other agents to access.

    Args:
        session_id: Session identifier
        enhanced_context: Enhanced context string
        related_memories: List of related memories

    Returns:
        True if successfully stored, False otherwise
    """
    try:
        # This assumes redis_client is available from the global scope
        if "redis_client" not in globals():
            logger.warning("Redis client not available, skipping cache storage")
            return False

        # Store enhanced context
        context_key = f"context_cache:{session_id}:enhanced"
        redis_client.hset(context_key, "value", enhanced_context)
        redis_client.hset(context_key, "created_at", datetime.now().isoformat())
        redis_client.expire(context_key, 3600)  # Expire in 1 hour

        # Store related memories if any
        if related_memories:
            memories_key = f"context_cache:{session_id}:related_memories"
            memories_str = "n".join(
                [mem.get("content", "") for mem in related_memories]
            )
            redis_client.hset(memories_key, "value", memories_str)
            redis_client.hset(memories_key, "created_at", datetime.now().isoformat())
            redis_client.expire(memories_key, 3600)  # Expire in 1 hour

        logger.info(
            f"Enhanced context stored in Redis with keys: {context_key}, {memories_key if related_memories else 'no memories'}"
        )
        return True

    except Exception as e:
        logger.error(
            f"Error storing enhanced context in cache: {str(e)}", exc_info=True
        )
        return False


# The enhanced context endpoint implementation
async def enhanced_context_endpoint(
    request: EnhancedContextRequest,
) -> EnhancedContextResponse:
    """
    Enhanced endpoint that coordinates with QLearning Agent to provide context-aware responses.

    This endpoint:
    1. Receives a query with keywords and token limits
    2. Queries the QLearning Agent for related memory paths
    3. Builds enhanced context from the paths (respecting token limits)
    4. Retrieves related memories from the knowledge graph
    5. Stores the enhanced context in Redis for other agents
    6. Returns the enhanced context and related memories

    Args:
        request: EnhancedContextRequest containing query, keywords, and limits

    Returns:
        EnhancedContextResponse with enhanced context and related memories
    """
    try:
        query = request.query
        keywords = request.keywords
        max_tokens = request.max_tokens
        session_id = request.session_id or "default"
        max_contexts = request.max_contexts

        logger.info(f"Received enhanced context request for query: {query[:100]}...")
        logger.info(
            f"Keywords: {keywords}, Max tokens: {max_tokens}, Session ID: {session_id}"
        )

        # Step 1: Extract keywords from query if not provided
        if not keywords:
            keywords = await extract_keywords_from_query(query)
            logger.info(f"Extracted keywords: {keywords}")

        if not keywords:
            logger.warning("No keywords found in query")
            # Return minimal context
            minimal_context = f"No relevant context found for query: {query}"
            await store_enhanced_context_in_cache(session_id, minimal_context, [])

            return EnhancedContextResponse(
                enhanced_context=minimal_context,
                related_memories=[],
                session_id=session_id,
                timestamp=datetime.now().isoformat(),
                token_count=len(minimal_context.split()),
            )

        # Step 2: Query QLearning Agent for optimal paths
        logger.info(
            f"Querying QLearning Agent for paths related to keywords: {keywords}"
        )
        paths = await query_qlearning_agent_for_paths(keywords, max_contexts)
        logger.info(f"Retrieved {len(paths)} paths from QLearning Agent")

        # Step 3: Build enhanced context from paths
        logger.info(f"Building enhanced context with max {max_tokens} tokens")
        enhanced_context = await build_context_from_paths(paths, max_tokens)
        token_count = len(enhanced_context.split())  # Rough token count
        logger.info(f"Enhanced context built ({token_count} tokens)")

        # Step 4: Get related memories from the knowledge graph
        logger.info(f"Retrieving related memories (max {max_contexts} contexts)")
        related_memories = await get_related_memories(keywords, max_contexts)
        logger.info(f"Retrieved {len(related_memories)} related memories")

        # Step 5: Store the enhanced context in Redis for other agents
        logger.info(
            f"Storing enhanced context in Redis cache for session: {session_id}"
        )
        await store_enhanced_context_in_cache(
            session_id, enhanced_context, related_memories
        )

        # Step 6: Return the enhanced context and related memories
        logger.info("Returning enhanced context response")

        return EnhancedContextResponse(
            enhanced_context=enhanced_context,
            related_memories=related_memories,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            token_count=token_count,
        )

    except Exception as e:
        logger.error(
            f"Error processing enhanced context request: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Helper function to integrate with the existing FastAPI app
def add_enhanced_context_endpoint(app):
    """
    Add the /enhanced_context endpoint to the existing FastAPI app.

    Args:
        app: The FastAPI application instance
    """
    from fastapi import FastAPI

    @app.post("/enhanced_context", response_model=EnhancedContextResponse)
    async def get_enhanced_context(request: EnhancedContextRequest):
        """
        Enhanced endpoint that coordinates with QLearning Agent to provide context-aware responses.

        This endpoint receives a query and coordinates with the QLearning Agent to:
        1. Find optimal paths through the knowledge graph
        2. Build enhanced context from the paths (up to 1M token limit)
        3. Retrieve related memories from the knowledge graph
        4. Store the enhanced context in Redis for other agents
        5. Return the enhanced context and related memories

        Args:
            request: EnhancedContextRequest containing query, keywords, and limits

        Returns:
            EnhancedContextResponse with enhanced context and related memories
        """
        return await enhanced_context_endpoint(request)
