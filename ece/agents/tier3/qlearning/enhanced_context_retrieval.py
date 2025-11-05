#!/usr/bin/env python3
"""
Enhanced QLearning Agent Implementation

This module enhances the QLearning Agent with improved context retrieval
functionality, supporting up to 1M token limits as requested.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EnhancedMemoryPath(BaseModel):
    """Enhanced memory path with additional context information."""

    nodes: List[str] = Field(default_factory=list, description="Node names in the path")
    relationships: List[Dict[str, Any]] = Field(
        default_factory=list, description="Relationships in the path"
    )
    score: float = Field(default=0.0, description="Path relevance score")
    length: int = Field(default=0, description="Path length (number of hops)")
    context_summary: str = Field(
        default="", description="Summary of context along this path"
    )
    token_count: int = Field(
        default=0, description="Estimated token count for this path"
    )
    keywords: List[str] = Field(
        default_factory=list, description="Keywords associated with this path"
    )


class ContextRetrievalRequest(BaseModel):
    """Request for context retrieval with token limits."""

    keywords: List[str]
    max_tokens: int = 1000000  # Default to 1M tokens
    max_paths: int = 10
    session_id: Optional[str] = None


class ContextRetrievalResponse(BaseModel):
    """Response containing retrieved context within token limits."""

    paths: List[EnhancedMemoryPath]
    total_tokens: int
    session_id: str
    timestamp: str
    summary: str = ""


async def retrieve_enhanced_context(
    qlearning_agent: Any, request: ContextRetrievalRequest
) -> ContextRetrievalResponse:
    """
    Enhanced context retrieval that respects token limits.

    This function:
    1. Finds optimal paths related to keywords
    2. Retrieves context from along those paths
    3. Summarizes context while respecting token limits
    4. Returns enhanced context within specified limits

    Args:
        qlearning_agent: The QLearning agent instance
        request: ContextRetrievalRequest with keywords, token limits, etc.

    Returns:
        ContextRetrievalResponse with enhanced context within token limits
    """
    try:
        keywords = request.keywords
        max_tokens = request.max_tokens
        max_paths = request.max_paths
        session_id = request.session_id or "default"

        logger.info(f"Retrieving enhanced context for keywords: {keywords}")
        logger.info(f"Max tokens: {max_tokens}, Max paths: {max_paths}")

        # Step 1: Find optimal paths related to keywords
        logger.info("Finding optimal paths...")
        paths = await qlearning_agent.find_optimal_path(keywords)

        if not paths:
            logger.warning("No paths found for keywords")
            return ContextRetrievalResponse(
                paths=[],
                total_tokens=0,
                session_id=session_id,
                timestamp="",
                summary="No related paths found for the given keywords.",
            )

        # Limit to max_paths
        paths = paths[:max_paths]
        logger.info(f"Found {len(paths)} paths")

        # Step 2: Enhance paths with context information
        enhanced_paths = []
        total_tokens = 0

        for i, path in enumerate(paths):
            if total_tokens >= max_tokens:
                logger.info(f"Reached token limit at path {i}")
                break

            # Get detailed context for this path
            path_context = await _get_path_context(qlearning_agent, path)

            # Estimate token count for this path
            path_tokens = _estimate_token_count(path_context)

            # Check if we can add this path without exceeding limits
            if total_tokens + path_tokens <= max_tokens:
                # Create enhanced path with context information
                enhanced_path = EnhancedMemoryPath(
                    nodes=path.nodes,
                    relationships=path.relationships,
                    score=path.score,
                    length=path.length,
                    context_summary=path_context,
                    token_count=path_tokens,
                    keywords=keywords,
                )
                enhanced_paths.append(enhanced_path)
                total_tokens += path_tokens
                logger.debug(f"Added path {i} with {path_tokens} tokens")
            else:
                # Add partial context if we're near the limit
                remaining_tokens = max_tokens - total_tokens
                if remaining_tokens > 100:  # Only add if we have meaningful space
                    truncated_context = _truncate_context(
                        path_context, remaining_tokens
                    )
                    truncated_tokens = _estimate_token_count(truncated_context)

                    enhanced_path = EnhancedMemoryPath(
                        nodes=path.nodes[:3],  # Limit nodes for truncated path
                        relationships=path.relationships[:2],  # Limit relationships
                        score=path.score * 0.5,  # Reduced score for truncated path
                        length=min(path.length, 3),  # Limited length
                        context_summary=truncated_context,
                        token_count=truncated_tokens,
                        keywords=keywords[:5],  # Limit keywords
                    )
                    enhanced_paths.append(enhanced_path)
                    total_tokens += truncated_tokens
                    logger.debug(
                        f"Added truncated path {i} with {truncated_tokens} tokens"
                    )
                break

        # Step 3: Create a summary of all retrieved context
        summary = _create_context_summary(enhanced_paths, max_tokens)

        logger.info(
            f"Retrieved enhanced context with {len(enhanced_paths)} paths and {total_tokens} tokens"
        )

        return ContextRetrievalResponse(
            paths=enhanced_paths,
            total_tokens=total_tokens,
            session_id=session_id,
            timestamp="",
            summary=summary,
        )

    except Exception as e:
        logger.error(f"Error retrieving enhanced context: {str(e)}", exc_info=True)
        raise


async def _get_path_context(qlearning_agent: Any, path: Any) -> str:
    """
    Get detailed context information for a path.

    Args:
        qlearning_agent: The QLearning agent instance
        path: The path to get context for

    Returns:
        Detailed context string for the path
    """
    try:
        # This would typically query the Neo4j database for detailed information
        # about nodes and relationships in the path

        context_parts = []

        # Add node information
        if hasattr(path, "nodes") and path.nodes:
            context_parts.append(
                f"Nodes in path: {', '.join(path.nodes[:5])}"
            )  # Limit to first 5 nodes

        # Add relationship information
        if hasattr(path, "relationships") and path.relationships:
            rel_types = list(
                set([rel.get("type", "RELATED_TO") for rel in path.relationships[:3]])
            )
            context_parts.append(f"Relationship types: {', '.join(rel_types)}")

        # Add score information
        if hasattr(path, "score"):
            context_parts.append(f"Path relevance score: {path.score:.2f}")

        # Add length information
        if hasattr(path, "length"):
            context_parts.append(f"Path length: {path.length} hops")

        # In a real implementation, this would retrieve:
        # 1. Detailed properties of nodes in the path
        # 2. Content/text associated with nodes
        # 3. Metadata about relationships
        # 4. Timestamps and other contextual information

        return "; ".join(context_parts) if context_parts else "Path context information"

    except Exception as e:
        logger.error(f"Error getting path context: {str(e)}")
        return "Error retrieving path context"


def _estimate_token_count(text: str) -> int:
    """
    Estimate token count for text (rough approximation).

    Args:
        text: Text to estimate token count for

    Returns:
        Estimated token count
    """
    # Rough approximation: 1.3 tokens per word
    word_count = len(text.split())
    return int(word_count * 1.3)


def _truncate_context(context: str, max_tokens: int) -> str:
    """
    Truncate context to fit within token limits.

    Args:
        context: Context to truncate
        max_tokens: Maximum number of tokens allowed

    Returns:
        Truncated context within token limits
    """
    # Estimate characters per token (roughly 4 characters per token for English)
    chars_per_token = 4
    max_chars = max_tokens * chars_per_token

    if len(context) <= max_chars:
        return context

    # Truncate and add indicator
    truncated = context[: max_chars - 20] + "... [truncated]"
    return truncated


def _create_context_summary(paths: List[EnhancedMemoryPath], max_tokens: int) -> str:
    """
    Create a summary of all retrieved context within token limits.

    Args:
        paths: List of enhanced memory paths
        max_tokens: Maximum number of tokens for summary

    Returns:
        Context summary within token limits
    """
    if not paths:
        return "No context paths retrieved."

    # Create a summary of the most relevant paths
    summary_parts = [
        f"Enhanced Context Summary:",
        f"Total Paths Retrieved: {len(paths)}",
        f"Estimated Total Tokens: {sum(p.token_count for p in paths)}",
        f"Token Limit: {max_tokens}",
    ]

    # Add information about top paths
    summary_parts.append("nTop Paths:")
    for i, path in enumerate(paths[:3]):  # Top 3 paths
        path_summary = f"  Path {i + 1}: "
        if path.nodes:
            path_summary += f"Nodes: {', '.join(path.nodes[:3])}; "
        path_summary += f"Score: {path.score:.2f}; "
        path_summary += f"Tokens: {path.token_count}"
        summary_parts.append(path_summary)

    # Add overall relevance information
    avg_score = sum(p.score for p in paths) / len(paths)
    summary_parts.append(f"nAverage Path Relevance Score: {avg_score:.2f}")

    summary = "n".join(summary_parts)

    # Ensure summary fits within token limits
    if _estimate_token_count(summary) > max_tokens:
        return _truncate_context(summary, max_tokens)

    return summary


# Functions to enhance the existing QLearningGraphAgent class
def enhance_qlearning_agent_with_context_retrieval(agent_class):
    """
    Enhance the QLearningGraphAgent class with context retrieval functionality.

    Args:
        agent_class: The QLearningGraphAgent class to enhance
    """

    # Add the enhanced context retrieval method
    async def retrieve_context_up_to_limit(
        self, keywords: List[str], max_tokens: int = 1000000
    ) -> Dict[str, Any]:
        """
        Retrieve context up to the specified token limit.

        This method:
        1. Finds optimal paths related to keywords
        2. Retrieves detailed context from along those paths
        3. Ensures total context is within token limits
        4. Returns summarized context with metadata

        Args:
            keywords: List of keywords to search for
            max_tokens: Maximum number of tokens to retrieve (default 1M)

        Returns:
            Dictionary containing enhanced context within token limits
        """
        logger.info(
            f"Retrieving context up to {max_tokens} tokens for keywords: {keywords}"
        )

        try:
            # Find optimal paths
            paths = await self.find_optimal_path(keywords)

            if not paths:
                return {
                    "context": "No related paths found for the given keywords.",
                    "total_tokens": 0,
                    "paths_count": 0,
                    "summary": "No context paths found.",
                    "keywords": keywords,
                }

            # Enhance paths with context information while respecting token limits
            enhanced_paths = []
            total_tokens = 0

            for i, path in enumerate(paths):
                if total_tokens >= max_tokens:
                    break

                # Get detailed context for this path
                path_context = await _get_path_context(self, path)
                path_tokens = _estimate_token_count(path_context)

                # Check token limits
                if total_tokens + path_tokens <= max_tokens:
                    # Create enhanced path object
                    enhanced_path = EnhancedMemoryPath(
                        nodes=getattr(path, "nodes", []),
                        relationships=getattr(path, "relationships", []),
                        score=getattr(path, "score", 0.0),
                        length=getattr(path, "length", 0),
                        context_summary=path_context,
                        token_count=path_tokens,
                        keywords=keywords,
                    )
                    enhanced_paths.append(enhanced_path)
                    total_tokens += path_tokens
                else:
                    # Add partial context if near limit
                    remaining_tokens = max_tokens - total_tokens
                    if remaining_tokens > 100:
                        truncated_context = _truncate_context(
                            path_context, remaining_tokens
                        )
                        truncated_tokens = _estimate_token_count(truncated_context)

                        # Create truncated path object
                        truncated_path = EnhancedMemoryPath(
                            nodes=getattr(path, "nodes", [])[:3],  # Limit nodes
                            relationships=getattr(path, "relationships", [])[
                                :2
                            ],  # Limit relationships
                            score=getattr(path, "score", 0.0) * 0.5,  # Reduced score
                            length=min(getattr(path, "length", 0), 3),  # Limited length
                            context_summary=truncated_context,
                            token_count=truncated_tokens,
                            keywords=keywords[:5],  # Limit keywords
                        )
                        enhanced_paths.append(truncated_path)
                        total_tokens += truncated_tokens
                    break

            # Create overall summary
            summary = _create_context_summary(enhanced_paths, max_tokens)

            return {
                "context": summary,
                "total_tokens": total_tokens,
                "paths_count": len(enhanced_paths),
                "paths": [
                    path.dict() for path in enhanced_paths
                ],  # Convert to dict for serialization
                "summary": summary,
                "keywords": keywords,
            }

        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}", exc_info=True)
            return {
                "context": f"Error retrieving context: {str(e)}",
                "total_tokens": 0,
                "paths_count": 0,
                "summary": "Error occurred during context retrieval.",
                "keywords": keywords,
                "error": str(e),
            }

    # Add the new method to the class
    agent_class.retrieve_context_up_to_limit = retrieve_context_up_to_limit

    # Also add a method for summarizing large contexts
    async def summarize_large_context(
        self, context: str, target_tokens: int = 4000
    ) -> str:
        """
        Summarize large context to fit within target token limits.

        Args:
            context: Large context to summarize
            target_tokens: Target number of tokens for summary

        Returns:
            Summarized context within target token limits
        """
        current_tokens = _estimate_token_count(context)

        if current_tokens <= target_tokens:
            return context

        logger.info(
            f"Summarizing context from {current_tokens} tokens to {target_tokens} tokens"
        )

        # For now, use simple truncation
        # In a real implementation, this would use an LLM to create a smart summary
        summarized = _truncate_context(context, target_tokens)

        return summarized

    agent_class.summarize_large_context = summarize_large_context

    logger.info("QLearning agent enhanced with context retrieval functionality")

    return agent_class
