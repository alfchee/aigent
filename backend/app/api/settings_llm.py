from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
import json

from app.core.persistence import LLMProvider, get_persistence_db as get_db
from app.core.security.encryption import get_encryption_service
from app.services.llm_discovery import get_discovery_service
from app.core.bot_pool import bot_pool

router = APIRouter(prefix="/api/settings/llm", tags=["settings-llm"])

class ProviderConfig(BaseModel):
    provider_id: str
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

class ActivateProviderRequest(BaseModel):
    provider_id: str

@router.post("/provider")
def save_provider_config(config: ProviderConfig, db: Session = Depends(get_db)):
    encryption = get_encryption_service()
    
    # Check if exists
    provider = db.query(LLMProvider).filter(LLMProvider.provider_id == config.provider_id).first()
    if not provider:
        provider = LLMProvider(provider_id=config.provider_id)
        db.add(provider)
    
    provider.name = config.name
    if config.api_key:
        provider.api_key_enc = encryption.encrypt(config.api_key)
    if config.base_url:
        provider.base_url = config.base_url
    if config.config:
        provider.config_json = json.dumps(config.config)
    
    db.commit()
    db.refresh(provider)
    return {"status": "success", "message": f"Provider {config.provider_id} saved."}

@router.get("/models/{provider_id}")
async def list_provider_models(provider_id: str, db: Session = Depends(get_db)):
    provider = db.query(LLMProvider).filter(LLMProvider.provider_id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    encryption = get_encryption_service()
    api_key = encryption.decrypt(provider.api_key_enc) if provider.api_key_enc else None
    
    credentials = {
        "api_key": api_key,
        "base_url": provider.base_url
    }
    
    discovery = get_discovery_service()
    models = await discovery.discover_models(provider_id, credentials)
    return {"models": models}

@router.patch("/activate")
def activate_provider(request: ActivateProviderRequest, db: Session = Depends(get_db)):
    # Allow multiple active providers
    # db.query(LLMProvider).update({LLMProvider.is_active: False})
    
    # Activate target
    provider = db.query(LLMProvider).filter(LLMProvider.provider_id == request.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider.is_active = True
    db.commit()
    
    # Clear bot pool to force re-initialization with new provider
    bot_pool.clear()
    
    return {"status": "success", "message": f"Provider {request.provider_id} activated."}

@router.patch("/deactivate")
def deactivate_provider(request: ActivateProviderRequest, db: Session = Depends(get_db)):
    # Deactivate target
    provider = db.query(LLMProvider).filter(LLMProvider.provider_id == request.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    provider.is_active = False
    db.commit()
    
    # Clear bot pool to force re-initialization with new provider
    bot_pool.clear()
    
    return {"status": "success", "message": f"Provider {request.provider_id} deactivated."}

@router.get("/providers")
def list_providers(db: Session = Depends(get_db)):
    providers = db.query(LLMProvider).all()
    result = []
    for p in providers:
        result.append({
            "provider_id": p.provider_id,
            "name": p.name,
            "base_url": p.base_url,
            "is_active": p.is_active,
            "has_key": bool(p.api_key_enc)
        })
    return {"providers": result}

@router.get("/available-models")
async def list_available_models(db: Session = Depends(get_db)):
    """
    Lists models from ALL active providers.
    Also merges native Google models if GOOGLE_API_KEY is present,
    even if Google provider is not explicitly configured in DB.
    """
    active_providers = db.query(LLMProvider).filter(LLMProvider.is_active == True).all()
    
    discovery = get_discovery_service()
    models = []
    encryption = get_encryption_service()
    
    # 1. Iterate over all active providers
    for provider in active_providers:
        api_key = encryption.decrypt(provider.api_key_enc) if provider.api_key_enc else None
        
        credentials = {
            "api_key": api_key,
            "base_url": provider.base_url
        }
        
        try:
            provider_models = await discovery.discover_models(provider.provider_id, credentials)
            models.extend(provider_models)
        except Exception as e:
            print(f"Error fetching models from {provider.provider_id}: {e}")

    # 2. Add native Google models if key is present (Hybrid mode)
    # Check if we already fetched them via active_providers
    has_google_active = any(p.provider_id == "google" for p in active_providers)
    
    if not has_google_active:
        import os
        if os.getenv("GOOGLE_API_KEY"):
            try:
                # Use _discover_google logic via discover_models
                google_models = await discovery.discover_models("google", {"api_key": os.getenv("GOOGLE_API_KEY")})
                models.extend(google_models)
            except Exception as e:
                print(f"Error fetching fallback Google models: {e}")

    # Deduplicate by ID
    unique_models = {}
    for m in models:
        unique_models[m["id"]] = m
        
    # Sort by display name
    sorted_models = sorted(unique_models.values(), key=lambda x: x.get("display_name", "").lower())
    
    return {"models": sorted_models}
