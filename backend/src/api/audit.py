from fastapi import APIRouter, Depends, HTTPException, Request
from src.bootstrap import get_components
from src.security import verify_api_key
from pathlib import Path
from src.config import settings

router = APIRouter()


@router.get('/audit/logs')
async def get_audit_logs(request_obj: Request, limit: int = 50, authenticated: bool = Depends(verify_api_key)):
    try:
        path = Path(settings.audit_log_path)
        if not path.exists():
            return {"logs": [], "message": "No audit log found"}
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            lines = f.read().splitlines()
        tail = lines[-int(limit):] if limit and len(lines) > 0 else lines
        return {"logs": tail, "count": len(tail)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
