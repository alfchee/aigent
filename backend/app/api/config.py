from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from app.core.identity import get_identity_manager

router = APIRouter(prefix="/config", tags=["Config"])

class SoulResponse(BaseModel):
    status: str
    soul: str

class UpdateSoulRequest(BaseModel):
    soul: str

@router.get("/soul", response_model=SoulResponse)
async def get_soul():
    """Retrieve the current base identity prompt (Soul)."""
    identity = get_identity_manager()
    soul = identity.get_soul()
    return SoulResponse(status="ok", soul=soul)

@router.put("/soul", response_model=SoulResponse)
async def update_soul(request: UpdateSoulRequest):
    """Update the base identity prompt (Soul)."""
    identity = get_identity_manager()
    try:
        identity.update_soul(request.soul)
        return SoulResponse(status="ok", soul=identity.get_soul())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
