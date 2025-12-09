from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

from src.bootstrap import get_components
from src.security import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


class PlanRequest(BaseModel):
    session_id: str
    message: str


@router.post("/plan")
async def plan(request_obj: Request, payload: PlanRequest, authenticated: bool = Depends(verify_api_key)):
    comps = get_components(request_obj.app)
    planner = getattr(request_obj.app.state, 'planner', None)
    plugin_manager = comps.get('plugin_manager')
    if not planner:
        raise HTTPException(status_code=503, detail="Planner not initialized")
    tools = []
    try:
        if plugin_manager and getattr(plugin_manager, 'enabled', False):
            tools = plugin_manager.list_tools()
    except Exception:
        tools = []
    try:
        plan = await planner.create_plan(payload.message, tools)
        return {"plan": plan}
    except Exception as e:
        logger.exception("/plan failed")
        raise HTTPException(status_code=500, detail=str(e))
