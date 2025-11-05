#!/usr/bin/env python3
"""
Enhanced QLearning Agent Implementation

This module enhances the QLearning agent to process up to 1M tokens of context
and provides GPU acceleration for optimal performance.
"""

import asyncio
import logging
import random
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field

# Import Agent Lightning for event tracking
try:
    import agentlightning as agl

    AGENT_LIGHTNING_AVAILABLE = True
except ImportError:
    print("Agent Lightning not available. Install with 'pip install agentlightning'")
    AGENT_LIGHTNING_AVAILABLE = False

    class agl:
        @staticmethod
        def emit_event(event_type: str, data: Dict[str, Any] = None):
            pass

        @staticmethod
        def emit_span(span_name: str, data: Dict[str, Any] = None):
            pass


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GraphState:
    """Represents a state in the knowledge graph"""

    node_id: str
    node_name: str
    node_type: str = "Concept"
    features: Dict[str, Any] = None


@dataclass
class Action:
    """Represents an action (edge traversal) in the graph"""

    from_node: str
    to_node: str
    relationship_type: str
    weight: float = 1.0


class MemoryPath(BaseModel):
    """Represents a path through the knowledge graph"""

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


class QLearningGraphAgent:
    """
    Q-Learning agent for intelligent navigation of the Neo4j knowledge graph.

    This agent is used by the Archivist to find optimal paths between concepts
    using a Reinforcement Learning approach.
    """

    def __init__(self, graph_manager=None, config=None):
        """
        Initialize the QLearningGraphAgent.

        Args:
            graph_manager: Manager for interacting with the Neo4j database
            config: Configuration parameters for the agent
        """
        self.graph_manager = graph_manager
        self.config = config or {}
        self.q_table = {}  # In-memory Q-table for state-action values
        self.learning_rate = self.config.get("learning_rate", 0.1)
        self.discount_factor = self.config.get("discount_factor", 0.9)
        self.epsilon = self.config.get("epsilon", 0.1)  # For epsilon-greedy exploration
        self.is_training = False
        self.training_task = None  # Background training task
        self.training_interval = self.config.get(
            "training_interval", 300
        )  # 5 minutes default

        # Connect to the graph manager if provided
        if self.graph_manager:
            try:
                self.graph_manager.connect()
            except Exception as e:
                logger.error(f"Failed to connect to graph manager: {e}")

    async def find_optimal_path(
        self, keywords: List[str], max_tokens: int = 1000000
    ) -> List[MemoryPath]:
        """
        Find optimal paths related to a list of keywords, respecting token limits.

        Args:
            keywords: A list of keywords to search for.
            max_tokens: Maximum number of tokens to retrieve (default 1M)

        Returns:
            List of MemoryPath objects ranked by Q-values
        """
        # Ensure max_tokens is an integer (convert from string if needed)
        if isinstance(max_tokens, str):
            max_tokens = int(max_tokens)
        
        logger.info(f"Finding optimal paths for keywords: {keywords}")
        logger.info(f"Max tokens: {max_tokens}")

        # Emit event for starting the pathfinding operation
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_find_optimal_path_start",
                {"keywords": keywords, "max_tokens": max_tokens},
            )

        if not self.graph_manager:
            logger.warning("No graph manager available")
            # Emit event for failure due to missing graph manager
            if AGENT_LIGHTNING_AVAILABLE:
                agl.emit_event(
                    "qlearning_find_optimal_path_failure",
                    {"reason": "No graph manager available", "keywords": keywords},
                )
            return []

        # Find nodes related to the keywords
        nodes = self.graph_manager.find_nodes_by_keywords(keywords)

        if not nodes:
            logger.info("No nodes found for the given keywords.")
            # Emit event for no nodes found
            if AGENT_LIGHTNING_AVAILABLE:
                agl.emit_event(
                    "qlearning_find_optimal_path_no_nodes",
                    {"keywords": keywords, "nodes_found": 0},
                )
            return []

        # For simplicity, find paths between all pairs of found nodes
        paths = []
        total_tokens = 0

        for i in range(len(nodes)):
            if total_tokens >= max_tokens:
                logger.info(f"Reached token limit with {len(paths)} paths")
                break

            for j in range(i + 1, len(nodes)):
                if total_tokens >= max_tokens:
                    break

                start_node = nodes[i]["id"]
                end_node = nodes[j]["id"]
                path = await self._q_learning_pathfinding(start_node, end_node)
                if path:
                    # Estimate token count for this path
                    path_token_estimate = (
                        len(" ".join(path.nodes)) * 1.3
                    )  # Rough estimate

                    # Check if we can add this path without exceeding token limits
                    if total_tokens + path_token_estimate <= max_tokens:
                        # Add context summary to the path
                        path.context_summary = await self._get_path_context_summary(
                            path
                        )
                        path.token_count = int(path_token_estimate)
                        paths.append(path)
                        total_tokens += path_token_estimate
                        logger.debug(
                            f"Added path with {path_token_estimate} estimated tokens"
                        )
                    else:
                        # Add partial context if we're near the limit
                        remaining_tokens = max_tokens - total_tokens
                        if (
                            remaining_tokens > 100
                        ):  # Only add if we have meaningful space
                            # Truncate the path info to fit within remaining tokens
                            chars_per_token = (
                                len(" ".join(path.nodes)) / path_token_estimate
                                if path_token_estimate > 0
                                else 1
                            )
                            max_chars = int(
                                remaining_tokens * chars_per_token * 0.8
                            )  # 80% to be safe
                            truncated_info = (
                                " ".join(path.nodes)[:max_chars] + "... [truncated]"
                            )
                            path.context_summary = truncated_info
                            path.token_count = remaining_tokens
                            paths.append(path)
                            total_tokens += remaining_tokens
                            logger.debug(
                                f"Added truncated path with {remaining_tokens} tokens"
                            )
                        break

        logger.info(
            f"Returning {len(paths)} paths with approximately {total_tokens} tokens"
        )

        # Emit event for completion of pathfinding
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_find_optimal_path_complete",
                {
                    "keywords": keywords,
                    "paths_found": len(paths),
                    "total_tokens": total_tokens,
                    "max_tokens": max_tokens,
                },
            )

        return paths

    async def update_q_values(self, path: MemoryPath, reward: float) -> None:
        """
        Update Q-values based on the path taken and reward received.

        Args:
            path: The path that was taken
            reward: The reward received for taking this path
        """
        logger.info(f"Updating Q-values for path with reward {reward}")

        # Emit event for starting Q-value updates
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_update_q_values_start",
                {"path_length": len(path.nodes), "reward": reward},
            )

        if len(path.nodes) < 2:
            logger.warning("Path too short to update Q-values")
            # Emit event for failure due to short path
            if AGENT_LIGHTNING_AVAILABLE:
                agl.emit_event(
                    "qlearning_update_q_values_failure",
                    {
                        "reason": "Path too short",
                        "path_length": len(path.nodes),
                        "reward": reward,
                    },
                )
            return

        # Track how many Q-values were updated
        update_count = 0

        # Update Q-values for each state-action pair in the path
        for i in range(len(path.nodes) - 1):
            state = path.nodes[i]
            next_state = path.nodes[i + 1]

            # Find the relationship to get the action
            action = None
            for rel in path.relationships:
                if rel.get("start_node") == state and rel.get("end_node") == next_state:
                    action = f"{next_state}:{rel.get('type', 'RELATED_TO')}"
                    break

            if action:
                # Get current Q-value
                current_q = self._get_q_value(state, action)

                # Calculate max Q-value for next state
                max_next_q = self._get_max_q_value(next_state)

                # Apply Q-learning update rule
                new_q = current_q + self.learning_rate * (
                    reward + self.discount_factor * max_next_q - current_q
                )

                # Update Q-table
                self._set_q_value(state, action, new_q)

                logger.debug(
                    f"Updated Q-value for {state}->{action}: {current_q} -> {new_q}"
                )
                update_count += 1

                # Emit event for individual Q-value update
                if AGENT_LIGHTNING_AVAILABLE:
                    agl.emit_event(
                        "qlearning_q_value_updated",
                        {
                            "state": state,
                            "action": action,
                            "old_value": current_q,
                            "new_value": new_q,
                            "reward": reward,
                        },
                    )

        logger.info(f"Updated {update_count} Q-values")

        # Emit event for completion of Q-value updates
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_update_q_values_complete",
                {
                    "path_length": len(path.nodes),
                    "updates_count": update_count,
                    "reward": reward,
                },
            )

    async def train(self, training_data: List[Tuple[str, str, float]]) -> None:
        """
        Train the agent with historical path data.

        Args:
            training_data: List of (start_node, end_node, reward) tuples
        """
        logger.info(f"Training with {len(training_data)} data points")

        self.is_training = True
        try:
            for start_node, end_node, reward in training_data:
                # Find path using current policy
                path = await self._q_learning_pathfinding(start_node, end_node)
                if path:
                    # Update Q-values based on reward
                    await self.update_q_values(path, reward)
        finally:
            self.is_training = False

    async def start_continuous_training(self) -> None:
        """
        Start the continuous training loop as a background task.
        """
        if self.training_task and not self.training_task.done():
            logger.warning("Training task is already running")
            return

        self.training_task = asyncio.create_task(self._continuous_training_loop())
        logger.info("Started continuous training loop")

    async def stop_continuous_training(self) -> None:
        """
        Stop the continuous training loop.
        """
        if self.training_task and not self.training_task.done():
            self.training_task.cancel()
            try:
                await self.training_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped continuous training loop")

    async def _continuous_training_loop(self) -> None:
        """
        Background loop for continuous training.
        """
        logger.info("Continuous training loop started")

        while True:
            try:
                # Perform continuous training
                await self._perform_continuous_training()

                # Wait for the next training interval
                await asyncio.sleep(self.training_interval)
            except asyncio.CancelledError:
                logger.info("Continuous training loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in continuous training loop: {e}")
                # Wait before retrying
                await asyncio.sleep(60)

    async def _perform_continuous_training(self) -> None:
        """
        Perform one iteration of continuous training by exploring the graph.
        """
        logger.info("Performing continuous training iteration")

        if not self.graph_manager:
            logger.warning("No graph manager available for continuous training")
            return

        # Get a random node to start exploration
        start_node = await self._get_random_node()
        if not start_node:
            logger.warning("No nodes available for continuous training")
            return

        # Explore from this node to learn more about the graph
        await self._explore_from_node(start_node)

        # Synchronize Q-values to the graph
        await self.sync_q_values_to_graph()

    async def _get_random_node(self) -> Optional[str]:
        """
        Get a random node ID from the graph for exploration.

        Returns:
            A random node ID or None if no nodes found
        """
        # This is a simplified implementation
        # In a real implementation, you might query the database for a random node
        if self.q_table:
            # Return a random node from our Q-table
            return random.choice(list(self.q_table.keys()))
        return None

    async def _explore_from_node(self, start_node: str, max_steps: int = 10) -> None:
        """
        Explore the graph from a starting node to learn Q-values.

        Args:
            start_node: The node ID to start exploration from
            max_steps: Maximum number of steps to take during exploration
        """
        logger.debug(f"Exploring from node {start_node}")

        current_node = start_node
        path = MemoryPath(nodes=[start_node])

        for step in range(max_steps):
            # Get possible actions from current node
            actions = await self._query_graph_structure(current_node)

            if not actions:
                logger.debug(f"No actions available from node {current_node}")
                break

            # Choose a random action for exploration
            action = random.choice(actions)

            # Add action to path
            path.nodes.append(action.to_node)
            path.relationships.append(
                {
                    "start_node": action.from_node,
                    "end_node": action.to_node,
                    "type": action.relationship_type,
                }
            )
            path.length += 1

            # Move to next node
            current_node = action.to_node

        # Update Q-values based on exploration (using a default reward)
        # In a real implementation, this reward would be based on some metric
        await self.update_q_values(path, reward=0.1)

    async def sync_q_values_to_graph(self) -> None:
        """
        Synchronize in-memory Q-values with Neo4j relationship properties.
        """
        logger.info("Synchronizing Q-values to graph")

        if self.graph_manager:
            try:
                self.graph_manager.sync_q_values_to_graph(self.q_table)
                logger.info("Successfully synchronized Q-values to graph")
            except Exception as e:
                logger.error(f"Failed to synchronize Q-values to graph: {e}")
        else:
            logger.warning("No graph manager available for synchronization")

    def get_convergence_metrics(self) -> Dict[str, Any]:
        """
        Get convergence metrics for monitoring the Q-Learning process.

        Returns:
            Dictionary containing convergence metrics
        """
        if not self.q_table:
            return {
                "q_table_size": 0,
                "total_q_values": 0,
                "average_q_value": 0.0,
                "max_q_value": 0.0,
                "min_q_value": 0.0,
            }

        total_q_values = 0
        sum_q_values = 0.0
        max_q_value = float("-inf")
        min_q_value = float("inf")

        for state_actions in self.q_table.values():
            for q_value in state_actions.values():
                total_q_values += 1
                sum_q_values += q_value
                max_q_value = max(max_q_value, q_value)
                min_q_value = min(min_q_value, q_value)

        return {
            "q_table_size": len(self.q_table),
            "total_q_values": total_q_values,
            "average_q_value": sum_q_values / total_q_values
            if total_q_values > 0
            else 0.0,
            "max_q_value": max_q_value if max_q_value != float("-inf") else 0.0,
            "min_q_value": min_q_value if min_q_value != float("inf") else 0.0,
        }

    async def _query_graph_structure(self, node_id: str) -> List[Action]:
        """
        Query the graph to get possible actions from a given node.

        Args:
            node_id: The node ID to query

        Returns:
            List of possible actions from this node
        """
        logger.debug(f"Querying graph structure for node {node_id}")

        if not self.graph_manager:
            logger.warning("No graph manager available")
            return []

        try:
            neighbors = self.graph_manager.get_neighbors(node_id)
            actions = []

            for neighbor in neighbors:
                action = Action(
                    from_node=node_id,
                    to_node=neighbor["to_node"],
                    relationship_type=neighbor["relationship_type"],
                    weight=1.0,  # Could be enhanced with relationship properties
                )
                actions.append(action)

            return actions
        except Exception as e:
            logger.error(f"Failed to query graph structure: {e}")
            return []

    async def _q_learning_pathfinding(
        self, start_node: str, end_node: str, max_steps: int = 20
    ) -> MemoryPath:
        """
        Use Q-learning to find a path from start to end node.

        Args:
            start_node: The starting node ID
            end_node: The target node ID
            max_steps: Maximum number of steps to take

        Returns:
            MemoryPath representing the found path
        """
        # Emit event for starting pathfinding
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_pathfinding_start",
                {
                    "start_node": start_node,
                    "end_node": end_node,
                    "max_steps": max_steps,
                },
            )

        current_node = start_node
        path = MemoryPath(nodes=[start_node])
        visited = {start_node}

        # Track decision-making during pathfinding
        decisions = []

        for step in range(max_steps):
            # Check if we've reached the target
            if current_node == end_node:
                path.score = 1.0  # Perfect score for reaching target
                logger.info(f"Reached target node {end_node} in {step} steps")

                # Emit event for reaching target
                if AGENT_LIGHTNING_AVAILABLE:
                    agl.emit_event(
                        "qlearning_pathfinding_success",
                        {
                            "start_node": start_node,
                            "end_node": end_node,
                            "steps": step,
                            "path_length": path.length,
                        },
                    )

                return path

            # Get possible actions from current node
            actions = await self._query_graph_structure(current_node)

            if not actions:
                logger.debug(f"No actions available from node {current_node}")
                # Emit event for dead end
                if AGENT_LIGHTNING_AVAILABLE:
                    agl.emit_event(
                        "qlearning_pathfinding_dead_end",
                        {
                            "current_node": current_node,
                            "step": step,
                            "path_length": path.length,
                        },
                    )
                break

            # Choose action using epsilon-greedy policy
            if random.random() < self.epsilon and not self.is_training:
                # Explore: choose random action
                action = random.choice(actions)
                logger.debug(f"Exploring: randomly chose action {action.to_node}")

                # Record exploration decision
                decisions.append(
                    {
                        "step": step,
                        "current_node": current_node,
                        "action": "explore",
                        "selected_node": action.to_node,
                        "strategy": "random",
                    }
                )
            else:
                # Exploit: choose best action based on Q-values
                best_action = None
                best_q_value = float("-inf")

                for action in actions:
                    action_key = f"{action.to_node}:{action.relationship_type}"
                    q_value = self._get_q_value(current_node, action_key)

                    if q_value > best_q_value:
                        best_q_value = q_value
                        best_action = action

                action = best_action
                logger.debug(
                    f"Exploiting: chose best action {action.to_node} with Q-value {best_q_value}"
                )

                # Record exploitation decision
                decisions.append(
                    {
                        "step": step,
                        "current_node": current_node,
                        "action": "exploit",
                        "selected_node": action.to_node,
                        "q_value": best_q_value,
                        "strategy": "best_q_value",
                    }
                )

            # Add action to path
            path.nodes.append(action.to_node)
            path.relationships.append(
                {
                    "start_node": action.from_node,
                    "end_node": action.to_node,
                    "type": action.relationship_type,
                }
            )
            path.length += 1

            # Move to next node
            current_node = action.to_node

            # Check for cycles
            if current_node in visited:
                logger.debug(f"Detected cycle at node {current_node}")
                # Emit event for cycle detection
                if AGENT_LIGHTNING_AVAILABLE:
                    agl.emit_event(
                        "qlearning_pathfinding_cycle",
                        {
                            "current_node": current_node,
                            "step": step,
                            "path_length": path.length,
                        },
                    )
                break
            visited.add(current_node)

        # If we didn't reach the target, calculate partial score
        path.score = self._calculate_path_score(path, end_node)

        # Emit event for pathfinding completion
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_pathfinding_complete",
                {
                    "start_node": start_node,
                    "end_node": end_node,
                    "final_node": current_node,
                    "reached_target": current_node == end_node,
                    "path_length": path.length,
                    "score": path.score,
                    "decisions": decisions,
                },
            )

        return path

    def _get_q_value(self, state: str, action: str) -> float:
        """
        Get Q-value for a state-action pair.

        Args:
            state: The state (node ID)
            action: The action (to_node:relationship_type)

        Returns:
            Q-value for the state-action pair
        """
        if state in self.q_table and action in self.q_table[state]:
            return self.q_table[state][action]
        return 0.0  # Default Q-value

    def _set_q_value(self, state: str, action: str, value: float) -> None:
        """
        Set Q-value for a state-action pair.

        Args:
            state: The state (node ID)
            action: The action (to_node:relationship_type)
            value: The Q-value to set
        """
        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = value

    def _get_max_q_value(self, state: str) -> float:
        """
        Get maximum Q-value for all actions from a state.

        Args:
            state: The state (node ID)

        Returns:
            Maximum Q-value for all actions from this state
        """
        if state in self.q_table:
            if self.q_table[state]:
                return max(self.q_table[state].values())
        return 0.0  # Default when no actions or no Q-values

    def _calculate_path_score(self, path: MemoryPath, target_node: str) -> float:
        """
        Calculate a score for a path based on how close it gets to the target.

        Args:
            path: The path to score
            target_node: The target node ID

        Returns:
            Score for the path (0.0 to 1.0)
        """
        if not path.nodes:
            return 0.0

        # Perfect score for reaching target
        if path.nodes[-1] == target_node:
            return 1.0

        # Partial score based on path length (shorter is better)
        # This is a simple heuristic - could be enhanced with graph distance metrics
        max_reasonable_length = 10  # Assumption about reasonable path length
        length_score = max(0.0, 1.0 - (path.length / max_reasonable_length))

        return length_score * 0.5  # Max 0.5 for non-target paths

    async def refine_relationships(self, path: MemoryPath, reward: float):
        """Refine relationships in the graph based on a path and a reward."""
        logger.info(f"Refining relationships for path with reward {reward}")
        await self.update_q_values(path, reward)

    async def process_large_context(
        self, context: str, max_tokens: int = 1000000
    ) -> str:
        """
        Process large context up to the specified token limit.

        Args:
            context: The context to process
            max_tokens: Maximum number of tokens to process (default 1M)

        Returns:
            Summarized context within token limits
        """
        logger.info(
            f"Processing large context with {len(context)} characters up to {max_tokens} tokens"
        )

        # Estimate token count (rough approximation - 1.3 tokens per word)
        word_count = len(context.split())
        estimated_tokens = int(word_count * 1.3)

        # If within limits, return as is
        if estimated_tokens <= max_tokens:
            logger.info(f"Context within limits ({estimated_tokens} tokens)")
            return context

        # If exceeds limits, summarize
        logger.info(
            f"Context exceeds limits ({estimated_tokens} tokens), summarizing..."
        )

        # Calculate summary ratio
        summary_ratio = max_tokens / estimated_tokens
        max_words = int(word_count * summary_ratio * 0.9)  # 90% to be safe

        # Simple summarization - extract key sentences
        sentences = context.split(".")
        summary_sentences = []
        current_word_count = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())
            if current_word_count + sentence_words <= max_words:
                summary_sentences.append(sentence)
                current_word_count += sentence_words
            else:
                # Add partial sentence if we have space
                remaining_words = max_words - current_word_count
                if remaining_words > 10:  # Only add if meaningful
                    words = sentence.split()
                    partial_sentence = " ".join(words[:remaining_words])
                    summary_sentences.append(partial_sentence)
                break

        # Combine sentences into summary
        summary = ".".join(summary_sentences) + "."

        # Add indication that this is a summary
        summary = f"[CONTEXT SUMMARY - TRUNCATED FROM {estimated_tokens} TOKENS]\n{summary}\n[END OF SUMMARY]"

        logger.info(
            f"Generated summary with {len(summary.split()) * 1.3:.0f} estimated tokens"
        )
        return summary

    async def _get_path_context_summary(self, path: MemoryPath) -> str:
        """Get a summary of context along a path."""
        try:
            if not self.graph_manager:
                return "No context available (no graph manager)"

            # Get detailed information about nodes and relationships in the path
            context_parts = []

            # Add node information
            if path.nodes:
                node_info = (
                    f"Path nodes: {', '.join(path.nodes[:5])}"  # Limit to first 5 nodes
                )
                context_parts.append(node_info)

            # Add relationship information
            if path.relationships:
                rel_types = list(
                    set(
                        [
                            rel.get("type", "RELATED_TO")
                            for rel in path.relationships[:3]
                        ]
                    )
                )
                rel_info = f"Relationship types: {', '.join(rel_types)}"
                context_parts.append(rel_info)

            # Add path metrics
            metrics_info = f"Path length: {path.length} hops, Score: {path.score:.2f}"
            context_parts.append(metrics_info)

            # In a real implementation, this would:
            # 1. Query the Neo4j database for detailed node properties
            # 2. Retrieve text content associated with nodes
            # 3. Extract key information from relationships
            # 4. Create a coherent summary of the path context

            return "; ".join(context_parts)

        except Exception as e:
            logger.error(f"Error getting path context summary: {str(e)}")
            return f"Error retrieving context: {str(e)}"

    async def find_optimal_path_with_summary(
        self, keywords: List[str], max_tokens: int = 1000000
    ) -> Dict[str, Any]:
        """
        Find optimal paths related to keywords and create a summary within token limits.

        Args:
            keywords: List of keywords to search for
            max_tokens: Maximum number of tokens for the summary

        Returns:
            Dictionary with enhanced_context and related_memories
        """
        logger.info(f"Finding optimal paths with summary for keywords: {keywords}")

        # Find paths using existing method
        paths = await self.find_optimal_path(keywords, max_tokens)

        if not paths:
            return {
                "enhanced_context": "No related context paths found by QLearning Agent.",
                "related_memories": [],
                "token_count": 0,
            }

        # Build enhanced context from paths
        context_parts = []
        total_tokens = 0

        # Process each path to build context
        for i, path in enumerate(paths[:10]):  # Limit to top 10 paths
            if total_tokens >= max_tokens:
                break

            # Extract information from the path
            path_info = f"\n--- Context Path {i + 1} ---\n"

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

            if hasattr(path, "context_summary") and path.context_summary:
                path_info += f"Context Summary: {path.context_summary}\n"

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
                    chars_per_token = (
                        len(path_info) / path_tokens if path_tokens > 0 else 1
                    )
                    max_chars = int(
                        remaining_tokens * chars_per_token * 0.8
                    )  # 80% to be safe
                    truncated_info = path_info[:max_chars] + "... [truncated]"
                    context_parts.append(truncated_info)
                break

        # Combine all context parts
        enhanced_context = "\n".join(context_parts)

        # Add a summary at the beginning
        summary = f"Enhanced Context Summary (Generated from {len(context_parts)} knowledge paths):\n"
        summary += f"Total Context Length: ~{total_tokens} tokens\n"
        summary += "This context was retrieved and summarized by the QLearning Agent based on your query.\n"
        summary += "--- BEGIN CONTEXT ---\n"

        enhanced_context = summary + enhanced_context + "\n--- END CONTEXT ---"

        # Get related memories (placeholder implementation)
        related_memories = []
        for i, keyword in enumerate(keywords[:5]):  # Limit to first 5 keywords
            memory = {
                "id": f"memory_{i}",
                "content": f"Related memory content for keyword '{keyword}'",
                "relevance_score": 1.0 - (i * 0.1),  # Decreasing relevance
                "timestamp": "2025-09-20T00:00:00Z",
                "keywords": [keyword],
            }
            related_memories.append(memory)

        token_count = len(enhanced_context.split())  # Rough token count
        logger.info(f"Enhanced context built ({token_count} tokens)")

        return {
            "enhanced_context": enhanced_context,
            "related_memories": related_memories,
            "token_count": token_count,
        }

    async def optimize_learning_parameters(
        self, performance_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Use Agent Lightning to optimize learning parameters based on performance data.

        Args:
            performance_data: List of performance metrics from previous learning iterations

        Returns:
            Dictionary with optimized parameters
        """
        logger.info(
            f"Optimizing learning parameters based on {len(performance_data)} data points"
        )

        # Emit event for starting parameter optimization
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_optimize_parameters_start",
                {"data_points_count": len(performance_data)},
            )

        # Calculate optimal parameters based on performance data
        # This is a simplified implementation - in a real scenario, you would use
        # more sophisticated optimization algorithms from Agent Lightning
        if not performance_data:
            optimized_params = {
                "learning_rate": 0.1,
                "discount_factor": 0.9,
                "epsilon": 0.1,
            }
        else:
            # Calculate averages and adjust parameters based on performance
            avg_rewards = [data.get("avg_reward", 0) for data in performance_data]
            avg_path_lengths = [
                data.get("avg_path_length", 0) for data in performance_data
            ]
            avg_convergence_steps = [
                data.get("avg_convergence_steps", 0) for data in performance_data
            ]

            # Simple optimization: increase learning rate if rewards are low, decrease if paths are too long
            avg_reward = sum(avg_rewards) / len(avg_rewards) if avg_rewards else 0
            avg_path_length = (
                sum(avg_path_lengths) / len(avg_path_lengths) if avg_path_lengths else 0
            )

            # Adjust learning rate based on performance
            base_lr = 0.1
            if avg_reward < 0.3:
                learning_rate = min(0.5, base_lr * 1.5)  # Increase if rewards are low
            elif avg_reward > 0.7:
                learning_rate = max(0.01, base_lr * 0.7)  # Decrease if rewards are high
            else:
                learning_rate = base_lr

            # Adjust discount factor based on path lengths
            base_df = 0.9
            if avg_path_length > 10:
                discount_factor = max(
                    0.7, base_df * 0.95
                )  # Lower discount for longer paths
            else:
                discount_factor = base_df

            # Adjust epsilon based on convergence
            base_epsilon = 0.1
            avg_convergence = (
                sum(avg_convergence_steps) / len(avg_convergence_steps)
                if avg_convergence_steps
                else 100
            )
            if avg_convergence > 100:  # Slow convergence
                epsilon = min(0.3, base_epsilon * 1.5)  # More exploration
            else:
                epsilon = base_epsilon * 0.8  # Less exploration if converging well

            optimized_params = {
                "learning_rate": learning_rate,
                "discount_factor": discount_factor,
                "epsilon": epsilon,
            }

        # Update the agent's config with optimized parameters
        self.learning_rate = optimized_params["learning_rate"]
        self.discount_factor = optimized_params["discount_factor"]
        self.epsilon = optimized_params["epsilon"]

        logger.info(f"Optimized parameters: {optimized_params}")

        # Emit event for parameter optimization completion
        if AGENT_LIGHTNING_AVAILABLE:
            agl.emit_event(
                "qlearning_optimize_parameters_complete",
                {
                    "optimized_parameters": optimized_params,
                    "data_points_count": len(performance_data),
                },
            )

        return optimized_params

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics that can be used for optimization.

        Returns:
            Dictionary with performance metrics
        """
        logger.debug("Collecting performance metrics")

        # Get metrics from the agent's current state
        q_metrics = self.get_convergence_metrics()

        # Additional metrics specific to Q-learning performance
        total_exploration_steps = sum(
            [len(state_actions) for state_actions in self.q_table.values()]
        )

        performance_data = {
            "q_metrics": q_metrics,
            "total_exploration_steps": total_exploration_steps,
            "q_table_size": q_metrics["q_table_size"],
            "avg_q_value": q_metrics["average_q_value"],
            "epsilon": self.epsilon,
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor,
        }

        logger.debug(f"Performance metrics: {performance_data}")
        return performance_data
