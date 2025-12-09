from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from src.bootstrap import get_components
from src.config import settings
from typing import Any, Dict
from pydantic import BaseModel

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    components = get_components(request.app)
    memory = components.get("memory")
    llm = components.get("llm")
    plugin_manager = components.get("plugin_manager")

    health = {"status": "healthy", "components": {}, "version": getattr(settings, 'ece_version', 'dev')}

    # Redis
    try:
        health["components"]["redis"] = bool(getattr(memory, "redis", None))
    except Exception:
        health["components"]["redis"] = False

    # Neo4j
    try:
        neo4j_store = getattr(memory, "neo4j", None)
        health["components"]["neo4j"] = bool(neo4j_store and getattr(neo4j_store, "neo4j_driver", None))
    except Exception:
        health["components"]["neo4j"] = False
    # Attempt counter
    try:
        health["components"]["neo4j_reconnect_attempts"] = getattr(neo4j_store, "_neo4j_reconnect_attempts", 0)
        health["components"]["neo4j_reconnecting"] = getattr(neo4j_store, "_neo4j_reconnect_task", None) is not None
        # Expose auth error for Neo4j so admins can take action
        health["components"]["neo4j_auth_error"] = getattr(neo4j_store, "_neo4j_auth_error", False)
    except Exception:
        health["components"]["neo4j_reconnect_attempts"] = 0
        health["components"]["neo4j_reconnecting"] = False

    # LLM: check if API is reachable or local model is loaded
    try:
        llm_status = {"api": False, "local": False}
        if llm:
            # If a model detection has been attempted, we might have `_detected_model`
            try:
                detected = await llm.detect_model()
                llm_status["api"] = bool(detected)
            except Exception:
                llm_status["api"] = False
            # Check local model availability without initializing heavy loads
            local = getattr(llm, "_local_llm", None) is not None
            llm_status["local"] = local
        health["components"]["llm"] = llm_status
    except Exception:
        health["components"]["llm"] = {"api": False, "local": False}

    # Plugin manager
    try:
        health["components"]["plugins"] = bool(plugin_manager and getattr(plugin_manager, 'enabled', False))
    except Exception:
        health["components"]["plugins"] = False

    return health


class ReconnectRequest(BaseModel):
    force: bool = False


class Neo4jConfigUpdate(BaseModel):
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None


@router.post("/admin/neo4j/reconnect")
async def admin_neo4j_reconnect(request: Request, body: ReconnectRequest | None = None):
    components = get_components(request.app)
    memory = components.get("memory")
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory component not found")

    # If the DB is disabled by config, return a helpful message
    if not getattr(getattr(memory, 'neo4j', None), "neo4j_uri", None):
        return {"status": "disabled", "message": "Neo4j not configured in memory component"}

    force = bool(body.force) if body else False
    result = await memory.trigger_reconnect(force=force)
    return {"status": "ok", "result": result}


def _mask(val: str | None, show: int = 2) -> str:
    if not val:
        return ""
    if len(val) <= show:
        return "*" * len(val)
    return val[:1] + "*" * (len(val) - show - 1) + val[-show:]


@router.get("/admin/neo4j/config")
async def admin_neo4j_config(request: Request) -> Dict[str, Any]:
    """Return the Neo4j config being used by the running app (masked password)."""
    components = get_components(request.app)
    memory = components.get("memory")
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory component not found")

    return {
        "neo4j_enabled": getattr(getattr(memory, 'neo4j', None), "neo4j_driver", None) is not None or getattr(getattr(memory, 'neo4j', None), "neo4j_uri", None) is not None,
        "neo4j_uri": getattr(getattr(memory, 'neo4j', None), "neo4j_uri", None),
        "neo4j_user": getattr(getattr(memory, 'neo4j', None), "neo4j_user", None),
        "neo4j_password_masked": _mask(getattr(getattr(memory, 'neo4j', None), "neo4j_password", None)),
        "neo4j_auth_error": getattr(getattr(memory, 'neo4j', None), "_neo4j_auth_error", False),
        "neo4j_reconnect_attempts": getattr(getattr(memory, 'neo4j', None), "_neo4j_reconnect_attempts", 0),
        "neo4j_reconnecting": getattr(getattr(memory, 'neo4j', None), "_neo4j_reconnect_task", None) is not None,
    }


@router.post("/admin/neo4j/config")
async def admin_neo4j_config_update(request: Request, body: Neo4jConfigUpdate):
    """Update Neo4j connection settings for the running app and trigger reconnect.

    NOTE: This endpoint updates the in-memory values on the `memory` object. It does not persist changes to `.env`.
    Use this to quickly correct credentials and test reconnects without restarting the app.
    """
    components = get_components(request.app)
    memory = components.get("memory")
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory component not found")

    # Update runtime values
    changed = {}
    if body.neo4j_uri:
        memory.neo4j.neo4j_uri = body.neo4j_uri
        changed['neo4j_uri'] = body.neo4j_uri
    if body.neo4j_user:
        memory.neo4j.neo4j_user = body.neo4j_user
        changed['neo4j_user'] = body.neo4j_user
    if body.neo4j_password:
        memory.neo4j.neo4j_password = body.neo4j_password
        changed['neo4j_password'] = '***'  # do not echo back password

    # If we changed credentials, force a reconnect
    result = await memory.trigger_reconnect(force=True)
    return {"status": "ok", "changed": changed, "reconnect_result": result}
