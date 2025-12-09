from fastapi import APIRouter

from .memory import router as memory_router
from .reason import router as reason_router
from .health import router as health_router
# from .openai_adapter import router as openai_router
from .plugins import router as plugins_router
from .audit import router as audit_router
from .plan import router as plan_router

__all__ = [
	"memory_router",
	"reason_router",
	"health_router",
	# "openai_router",
	"plugins_router",
	"audit_router",
	"plan_router",
]
