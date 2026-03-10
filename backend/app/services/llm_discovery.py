import httpx
import logging
from typing import List, Dict, Any
from app.core.models import get_available_gemini_models

logger = logging.getLogger(__name__)

class ModelDiscoveryService:
    async def discover_models(self, provider_id: str, credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        if provider_id == "google":
            return await self._discover_google(credentials)
        elif provider_id == "openrouter":
            return await self._discover_openrouter(credentials)
        elif provider_id == "lm_studio":
            return await self._discover_lm_studio(credentials)
        else:
            logger.warning(f"Unknown provider: {provider_id}")
            return []

    async def _discover_google(self, credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Reusing existing logic. Note: get_available_gemini_models uses env var GOOGLE_API_KEY.
        # Ideally we should pass the key, but for now we rely on the env or update the function.
        # The prompt says "Mantener el servicio actual".
        # However, if we want dynamic keys from DB, we might need to patch/update get_available_gemini_models.
        # For now, let's assume Google uses the env var or we set it temporarily.
        # TODO: Refactor get_available_gemini_models to accept api_key.
        return await get_available_gemini_models(api_key=credentials.get("api_key"))

    async def _discover_openrouter(self, credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        api_key = credentials.get("api_key")
        if not api_key:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                models = []
                for item in data.get("data", []):
                    models.append({
                        "id": item.get("id"),
                        "display_name": item.get("name", item.get("id")),
                        "description": item.get("description", ""),
                        "context_length": item.get("context_length", 0),
                        "pricing": item.get("pricing", {})
                    })
                return models
        except Exception as e:
            logger.error(f"Error discovering OpenRouter models: {e}")
            return []

    async def _discover_lm_studio(self, credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        base_url = credentials.get("base_url", "http://localhost:1234/v1")
        api_key = credentials.get("api_key")
        
        # Ensure base_url ends with /v1 or correct path if it looks like a root URL
        # But if user specified something else, respect it? 
        # Standardize: if no path, add /v1. If /api, add /v1. 
        # But simplistic check: if it doesn't end in /v1, add it.
        # FIX: If base_url is http://localhost:1234, we want http://localhost:1234/v1
        # If base_url is http://localhost:1234/api, we might want http://localhost:1234/api/v1?
        # Let's trust the user a bit more but provide a reasonable default.
        
        # If the user provides a base_url like "http://localhost:1234", we append "/v1".
        # If they provide "http://localhost:1234/v1", we leave it.
        # If they provide "http://host.docker.internal:1234/v1", we leave it.
        
        # Also, inside Docker/container, localhost refers to the container itself.
        # If LM Studio is on the host, we might need host.docker.internal (mac/win) or 172.17.0.1 (linux).
        # We can't auto-detect this easily, so we rely on the user setting the correct Base URL.
        # However, we can try to be smart about the path suffix.
        
        if not base_url.endswith("/v1"):
             # If it ends with /api, maybe append /v1 -> /api/v1
             # If it's just the root, append /v1
             if base_url.endswith("/api"):
                 base_url = f"{base_url}/v1"
             else:
                 base_url = f"{base_url.rstrip('/')}/v1"
            
        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
                
            logger.info(f"Discovering LM Studio models at {base_url}/models")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers=headers,
                    timeout=5.0
                )
                response.raise_for_status()
                data = response.json()
                
                models = []
                for item in data.get("data", []):
                    models.append({
                        "id": item.get("id"),
                        "display_name": item.get("id"), # LM Studio often just gives ID
                        "description": "Local model via LM Studio"
                    })
                return models
        except Exception as e:
            logger.error(f"Error discovering LM Studio models at {base_url}: {e}")
            # Fallback: return a generic model if discovery fails but we want to allow manual entry?
            # Or just return empty list.
            return []

_discovery_service = ModelDiscoveryService()

def get_discovery_service() -> ModelDiscoveryService:
    return _discovery_service
