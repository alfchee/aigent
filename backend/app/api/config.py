from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Any, Dict, List, Literal, Optional
import asyncio
import logging
import time

from app.core.identity import get_identity_manager
from app.core.provider_config import get_provider_config, KNOWN_PROVIDERS

logger = logging.getLogger("navibot.api.config")

router = APIRouter(prefix="/config", tags=["Config"])


# ---------------------------------------------------------------------------
# Soul schemas & endpoints
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Provider schemas
# ---------------------------------------------------------------------------

class ProviderStatus(BaseModel):
    name: str
    label: str
    status: Literal["configured", "missing", "untested"]
    has_key: bool
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    available_models: List[str] = []
    needs_key: bool = True

class ProvidersResponse(BaseModel):
    providers: List[ProviderStatus]

class ProviderUpdate(BaseModel):
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None

class UpdateProvidersRequest(BaseModel):
    providers: List[ProviderUpdate]

class TestProviderResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None

class ModelsResponse(BaseModel):
    provider: str
    models: List[str]


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------

@router.get("/providers", response_model=ProvidersResponse)
async def get_providers():
    """List all providers with their status (configured / missing / untested)."""
    svc = get_provider_config()
    raw = svc.get_providers()
    providers = [ProviderStatus(**p) for p in raw]
    return ProvidersResponse(providers=providers)


@router.put("/providers", response_model=ProvidersResponse)
async def update_providers(request: UpdateProvidersRequest):
    """
    Update API keys and settings for one or many providers.
    Keys are stored encrypted; they are never returned in plain text.
    """
    svc = get_provider_config()
    updates = [u.model_dump(exclude_none=False) for u in request.providers]
    svc.update_providers(updates)
    raw = svc.get_providers()
    providers = [ProviderStatus(**p) for p in raw]
    return ProvidersResponse(providers=providers)


@router.post("/providers/{name}/test", response_model=TestProviderResponse)
async def test_provider(name: str):
    """
    Send a minimal test message to a provider and report success/failure.
    Times out after 10 seconds.
    """
    if name not in KNOWN_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name!r}")

    meta = KNOWN_PROVIDERS[name]
    svc = get_provider_config()

    from app.core.llm import ModelConfig, default_llm

    api_key = svc.get_api_key(name)
    base_url = svc.get_base_url(name) if name == "ollama" else None

    if meta["needs_key"] and not api_key:
        return TestProviderResponse(
            success=False,
            message=f"No API key configured for {name!r}",
        )

    test_model = meta["test_model"]
    # model_id is already prefixed for LiteLLM (e.g. "groq/llama3-8b-8192")
    # except for openai which uses plain model name
    provider_part, _, model_part = test_model.partition("/")
    if not model_part:
        # openai-style: no prefix
        config = ModelConfig(
            provider="openai",
            model_name=test_model,
            temperature=0.0,
            max_tokens=5,
            api_key=api_key,
        )
    else:
        config = ModelConfig(
            provider=provider_part,
            model_name=model_part,
            temperature=0.0,
            max_tokens=5,
            api_key=api_key,
            base_url=base_url,
        )

    try:
        start = time.monotonic()
        await asyncio.wait_for(
            default_llm.generate(
                messages=[{"role": "user", "content": "Hi"}],
                config=config,
            ),
            timeout=10.0,
        )
        latency_ms = (time.monotonic() - start) * 1000
        return TestProviderResponse(
            success=True,
            message="Connection successful",
            latency_ms=round(latency_ms, 1),
        )
    except asyncio.TimeoutError:
        return TestProviderResponse(
            success=False,
            message="Request timed out after 10 seconds",
        )
    except Exception as exc:
        return TestProviderResponse(
            success=False,
            message=str(exc),
        )


@router.get("/providers/{name}/models", response_model=ModelsResponse)
async def get_provider_models(name: str):
    """
    List available models for a provider.
    For Ollama, queries the local server's /api/tags endpoint dynamically.
    For cloud providers, returns a hardcoded list.
    """
    if name not in KNOWN_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name!r}")

    meta = KNOWN_PROVIDERS[name]

    if name == "ollama":
        svc = get_provider_config()
        base_url = svc.get_base_url("ollama") or "http://localhost:11434"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            logger.warning(f"Could not reach Ollama at {base_url}: {exc}")
            models = []
        return ModelsResponse(provider=name, models=models)

    return ModelsResponse(provider=name, models=meta["available_models"])
