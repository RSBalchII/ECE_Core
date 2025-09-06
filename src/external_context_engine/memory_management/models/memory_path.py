"""
MemoryPath model for the Q-Learning Graph Agent
"""
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class MemoryPath(BaseModel):
    """Represents a path through the knowledge graph"""
    nodes: List[str] = Field(default_factory=list, description="Node names in the path")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Relationships in the path")
    score: float = Field(default=0.0, description="Path relevance score")
    length: int = Field(default=0, description="Path length (number of hops)")