"""agents package - exports are lazily imported to avoid heavy dependencies at import time
This avoids importing Neo4j and other heavy libs during test collection or module import.
"""
from importlib import import_module
from typing import TYPE_CHECKING

__all__ = ["VerifierAgent", "ArchivistAgent", "PlannerAgent"]

if TYPE_CHECKING:
	# Type hints only - avoid executing imports at runtime
	from .verifier import VerifierAgent  # noqa: F401
	from .archivist import ArchivistAgent  # noqa: F401
	from .planner import PlannerAgent  # noqa: F401


def __getattr__(name: str):
	if name == "VerifierAgent":
		return import_module(".verifier", __package__).VerifierAgent
	if name == "ArchivistAgent":
		return import_module(".archivist", __package__).ArchivistAgent
	if name == "PlannerAgent":
		return import_module(".planner", __package__).PlannerAgent
	raise AttributeError(name)
