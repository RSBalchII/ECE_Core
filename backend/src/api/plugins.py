from fastapi import APIRouter, HTTPException, Request
from src.bootstrap import get_components

router = APIRouter()


@router.get('/plugins/tools')
async def plugins_tools(request_obj: Request):
    components = get_components(request_obj.app)
    plugin_manager = components.get('plugin_manager')
    if plugin_manager and getattr(plugin_manager, 'enabled', False):
        return {'tools': plugin_manager.list_tools()}
    raise HTTPException(status_code=404, detail='Plugins disabled or not available')
