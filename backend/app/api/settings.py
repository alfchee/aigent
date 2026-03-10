from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.persistence import get_persistence_db as get_db, LLMProvider
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
    emergency_mode: bool | None = None
    system_prompt: str | None = None
    routing_config: dict[str, Any] | None = None
    role_config: dict[str, Any] | None = None
    limits_config: dict[str, Any] | None = None
    model_routing_json: dict[str, Any] | None = None


class SessionSettingsRequest(BaseModel):
    model_name: str


@router.get("/api/available-models")
async def list_models(db: Session = Depends(get_db)):
    # 1. Default Gemini models (always available if env var is set)
    models = await get_available_gemini_models()
    
    # 2. Check for active provider
    try:
        active_provider = db.query(LLMProvider).filter(LLMProvider.is_active == True).first()
        if active_provider and active_provider.provider_id != "google":
            from app.services.llm_discovery import get_discovery_service
            
            # Decrypt API Key
            from app.core.security.encryption import get_encryption_service
            encryption = get_encryption_service()
            api_key = None
            if active_provider.api_key_enc:
                api_key = encryption.decrypt(active_provider.api_key_enc)
            
            credentials = {
                "api_key": api_key,
                "base_url": active_provider.base_url
            }
            
            discovery = get_discovery_service()
            provider_models = await discovery.discover_models(active_provider.provider_id, credentials)
            
            if provider_models:
                 models = provider_models

    except Exception as e:
        print(f"Error fetching active provider models: {e}")
        # Fallback to Gemini models if something breaks
        
    return {"models": models}

@router.get("/api/settings")
def get_app_settings(db: Session = Depends(get_db)):
    s = get_settings()
    
    # Enrich models list with active provider's models if applicable
    # The default get_settings() only returns hardcoded models or cached ones.
    # We want to dynamically inject the available models from the active provider into the "models" list
    # so the frontend dropdowns can see them.
    
    try:
        # Check active provider
        active_provider = db.query(LLMProvider).filter(LLMProvider.is_active == True).first()
        if active_provider and active_provider.provider_id != "google":
             # If using external provider, we should fetch its models to populate the list
             # However, fetching on every settings load might be slow.
             # Ideally the frontend uses /api/available-models to populate dropdowns.
             # But the "models" key in settings response is used for validation?
             # Or just strictly for the list of keys in s.models?
             
             # The frontend SettingsView.vue uses:
             # const dynamicModels = computed(() => {
             #   if (availableModels.value.length > 0) {
             #     return availableModels.value.map((m) => m.id)
             #   }
             #   return models.value
             # })
             
             # availableModels comes from store.availableModels which comes from /api/available-models.
             # So if we fixed /api/available-models above, the frontend should see them!
             pass
    except Exception:
        pass

    return {
        "settings": {
            "current_model": s.current_model,
            "fallback_model": s.fallback_model,
            "auto_escalate": s.auto_escalate,
            "emergency_mode": s.emergency_mode,
            "system_prompt": s.system_prompt,
            "models": list(s.models.keys()),
            "tiers": {"fast": FAST_MODELS, "fallback": FALLBACK_MODELS},
            "routing_config": s.routing_config.model_dump(),
            "role_config": s.role_config.model_dump(),
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
            "emergency_mode": updated.emergency_mode,
            "system_prompt": updated.system_prompt,
            "models": list(updated.models.keys()),
            "tiers": {"fast": FAST_MODELS, "fallback": FALLBACK_MODELS},
            "routing_config": updated.routing_config.model_dump(),
            "role_config": updated.role_config.model_dump(),
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
