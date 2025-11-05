from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum


class DirectiveType(str, Enum):
    DATA_REQUEST = "DataRequest"
    TASK_DIRECTIVE = "TaskDirective"
    MEMORY_NODE = "MemoryNode"


class Identity(BaseModel):
    name: str
    version: str
    type: str


class OperationalContext(BaseModel):
    project: str
    objective: Optional[str] = None


class Constraint(BaseModel):
    language: Optional[str] = None
    frameworks: Optional[List[str]] = None
    style: Optional[str] = None


class BaseDirective(BaseModel):
    goal: str
    task: Optional[Dict[str, Any]] = None
    constraints: Optional[Constraint] = None
    deliverables: Optional[List[str]] = None


class POML(BaseModel):
    identity: Identity
    operational_context: OperationalContext
    directive: BaseDirective
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DataRequest(POML):
    data_query: str
    data_format: Optional[str] = None


class TaskDirective(POML):
    task_name: str
    steps: List[str]


class MemoryNode(POML):
    node_data: Dict[str, Any]
    node_type: str
