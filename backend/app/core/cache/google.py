"""
Google GenAI Cache Provider

Implements caching for Google GenAI API using the existing prompt_cache module.
"""

import os
import logging
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

load_dotenv()

from . import CacheProvider, CacheResult

logger = logging.getLogger(__name__)


class GoogleCacheProvider(CacheProvider):
    """
    Cache provider for Google GenAI API.
    
    Uses the existing PromptCacheManager to handle Google-specific
    context caching functionality.
    """
    
    def __init__(self):
        """Initialize the Google cache provider."""
        self._cache_manager = None
        self._initialized = False
    
    def _ensure_initialized(self) -> bool:
        """Ensure the cache manager is initialized."""
        if self._initialized:
            return self._cache_manager is not None
        
        try:
            from app.core import prompt_cache
            self._cache_manager = prompt_cache.get_cache_manager()
            self._initialized = True
            logger.debug("Google cache provider initialized")
            return self._cache_manager is not None
        except Exception as e:
            logger.warning(f"Failed to initialize Google cache provider: {e}")
            self._initialized = True
            return False
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    async def get_cache(self, cache_key: str) -> Optional[str]:
        """
        Get cached content by key.
        
        Args:
            cache_key: Unique key for the cache entry
            
        Returns:
            Cache name if found, None otherwise
        """
        if not self._ensure_initialized() or not self._cache_manager:
            return None
        
        try:
            # Extract worker_name from cache_key (format: "worker:session" or just "worker")
            parts = cache_key.split(":")
            worker_name = parts[0] if parts else "GeneralAssistant"
            
            cache = self._cache_manager.get_cache(worker_name)
            return cache if cache else None
        except Exception as e:
            logger.warning(f"Failed to get cache: {e}")
            return None
    
    async def create_cache(
        self,
        cache_key: str,
        system_instruction: str,
        tools_schema: List[Dict[str, Any]],
        model: str
    ) -> CacheResult:
        """
        Create a new cache entry.
        
        Args:
            cache_key: Unique key for the cache
            system_instruction: System prompt to cache
            tools_schema: Tool definitions to cache
            model: Model to use
            
        Returns:
            CacheResult with success status and cache info
        """
        if not self._ensure_initialized() or not self._cache_manager:
            return CacheResult(
                success=False,
                cache_key=cache_key,
                error="Cache manager not available"
            )
        
        try:
            # Extract worker_name from cache_key
            parts = cache_key.split(":")
            worker_name = parts[0] if parts else "GeneralAssistant"
            
            # Create cache using the existing prompt_cache
            cache = self._cache_manager.create_worker_cache(
                worker_name=worker_name,
                system_instruction=system_instruction,
                tools_schema=tools_schema,
                model=model
            )
            
            if cache:
                return CacheResult(
                    success=True,
                    cache_key=cache_key,
                    cache_name=cache.name
                )
            else:
                return CacheResult(
                    success=False,
                    cache_key=cache_key,
                    error="Failed to create cache"
                )
                
        except Exception as e:
            logger.warning(f"Failed to create cache: {e}")
            return CacheResult(
                success=False,
                cache_key=cache_key,
                error=str(e)
            )
    
    async def delete_cache(self, cache_key: str) -> bool:
        """
        Delete a cache entry.
        
        Args:
            cache_key: Cache key to delete
            
        Returns:
            True if deleted, False otherwise
        """
        if not self._ensure_initialized() or not self._cache_manager:
            return False
        
        try:
            parts = cache_key.split(":")
            worker_name = parts[0] if parts else "GeneralAssistant"
            
            result = self._cache_manager.invalidate_cache(worker_name)
            return result.get(worker_name, False)
        except Exception as e:
            logger.warning(f"Failed to delete cache: {e}")
            return False
    
    def is_available(self) -> bool:
        """
        Check if Google cache is available.
        
        Returns:
            True if Google API key is configured
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        return bool(api_key)


# Singleton instance
_google_cache_provider: Optional[GoogleCacheProvider] = None


def get_google_cache_provider() -> GoogleCacheProvider:
    """Get the Google cache provider singleton."""
    global _google_cache_provider
    if _google_cache_provider is None:
        _google_cache_provider = GoogleCacheProvider()
    return _google_cache_provider
