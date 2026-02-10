from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config_manager import (
    FAST_MODELS,
    FALLBACK_MODELS,
    get_session_model,
    get_settings,
    provider_status,
    set_session_model,
    update_settings,
)
from app.core.models import get_available_gemini_models


router = APIRouter(tags=["settings"])


def _validate_session_id(session_id: str) -> str:
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id vacío")
    if any(ch in sid for ch in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="session_id inválido")
    return sid


class UpdateSettingsRequest(BaseModel):
    current_model: str | None = None
    fallback_model: str | None = None
    auto_escalate: bool | None = None
    system_prompt: str | None = None
    routing_config: dict[str, Any] | None = None
    limits_config: dict[str, Any] | None = None
    model_routing_json: dict[str, Any] | None = None


class SessionSettingsRequest(BaseModel):
    model_name: str


@router.get("/api/available-models")
async def list_models():
    models = await get_available_gemini_models()
    return {"models": models}


@router.get("/api/settings")
def get_app_settings():
    s = get_settings()
    return {
        "settings": {
            "current_model": s.current_model,
            "fallback_model": s.fallback_model,
            "auto_escalate": s.auto_escalate,
            "system_prompt": s.system_prompt,
            "models": list(s.models.keys()),
            "tiers": {"fast": FAST_MODELS, "fallback": FALLBACK_MODELS},
            "routing_config": s.routing_config.model_dump(),
            "limits_config": s.limits_config.model_dump(),
            "model_routing_json": s.model_routing_json,
        },
        "providers": provider_status(),
    }


@router.put("/api/settings")
def put_app_settings(payload: UpdateSettingsRequest):
    try:
        updated = update_settings(payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "settings": {
            "current_model": updated.current_model,
            "fallback_model": updated.fallback_model,
            "auto_escalate": updated.auto_escalate,
            "system_prompt": updated.system_prompt,
            "models": list(updated.models.keys()),
            "tiers": {"fast": FAST_MODELS, "fallback": FALLBACK_MODELS},
            "routing_config": updated.routing_config.model_dump(),
            "limits_config": updated.limits_config.model_dump(),
            "model_routing_json": updated.model_routing_json,
        },
        "providers": provider_status(),
    }


@router.get("/api/sessions/{session_id}/settings")
def get_session_settings(session_id: str):
    sid = _validate_session_id(session_id)
    return {"session_id": sid, "model_name": get_session_model(sid)}


@router.put("/api/sessions/{session_id}/settings")
def put_session_settings(session_id: str, payload: SessionSettingsRequest):
    sid = _validate_session_id(session_id)
    name = (payload.model_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="model_name vacío")
    try:
        set_session_model(sid, name)
        return {"session_id": sid, "model_name": name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
