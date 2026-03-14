"""
Abstract Cache Provider Module

Provides a provider-agnostic interface for caching system prompts and context.
This allows the cache to work with multiple LLM providers (Google, OpenRouter, etc.)

Architecture:
- CacheProvider (ABC): Abstract interface
- GoogleCacheProvider: Implementation for Google GenAI
- OpenRouterCacheProvider: Implementation for OpenRouter (future)
- LiteLLMCacheProvider: Implementation for LiteLLM (future)

Usage:
    from app.core.cache import get_cache_provider, register_provider
    
    # Register providers
    from app.core.cache.google import get_google_cache_provider
    register_provider(get_google_cache_provider())
    
    # Use provider
    provider = get_cache_provider("google")
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Try to import and register Google provider
try:
    from app.core.cache.google import get_google_cache_provider, GoogleCacheProvider
    _google_provider = get_google_cache_provider()
except ImportError:
    _google_provider = None


@dataclass
class CacheResult:
    """Result of a cache operation."""
    success: bool
    cache_key: str
    cache_name: Optional[str] = None
    error: Optional[str] = None


class CacheProvider(ABC):
    """
    Abstract base class for cache providers.
    
    Each provider implements caching specific to its LLM API.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'google', 'openrouter')."""
        pass
    
    @abstractmethod
    async def get_cache(self, cache_key: str) -> Optional[str]:
        """
        Get cached content by key.
        
        Args:
            cache_key: Unique key for the cache entry
            
        Returns:
            Cache name/identifier if found, None otherwise
        """
        pass
    
    @abstractmethod
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
            model: Model to use for the cache
            
        Returns:
            CacheResult with success status and cache info
        """
        pass
    
    @abstractmethod
    async def delete_cache(self, cache_key: str) -> bool:
        """
        Delete a cache entry.
        
        Args:
            cache_key: Cache key to delete
            
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available/configured.
        
        Returns:
            True if provider can be used
        """
        pass


class NoOpCacheProvider(CacheProvider):
    """
    No-op cache provider for providers that don't support caching.
    
    This is a fallback provider that doesn't actually cache anything.
    """
    
    @property
    def provider_name(self) -> str:
        return "noop"
    
    async def get_cache(self, cache_key: str) -> Optional[str]:
        return None
    
    async def create_cache(
        self,
        cache_key: str,
        system_instruction: str,
        tools_schema: List[Dict[str, Any]],
        model: str
    ) -> CacheResult:
        return CacheResult(
            success=False,
            cache_key=cache_key,
            error="No-op provider: caching not supported"
        )
    
    async def delete_cache(self, cache_key: str) -> bool:
        return True
    
    def is_available(self) -> bool:
        return True  # Always available as fallback


# Provider registry
_cache_providers: Dict[str, CacheProvider] = {}
_default_provider: Optional[CacheProvider] = None


def register_provider(provider: CacheProvider) -> None:
    """
    Register a cache provider.
    
    Args:
        provider: Cache provider instance to register
    """
    _cache_providers[provider.provider_name] = provider
    logger.info(f"Registered cache provider: {provider.provider_name}")


def get_provider(name: str) -> Optional[CacheProvider]:
    """
    Get a cache provider by name.
    
    Args:
        name: Provider name
        
    Returns:
        Cache provider or None if not found
    """
    return _cache_providers.get(name)


def get_default_provider() -> CacheProvider:
    """
    Get the default cache provider.
    
    Returns:
        Default provider, or NoOpCacheProvider if none configured
    """
    global _default_provider
    if _default_provider is None:
        # Try to find a suitable provider
        if _google_provider and _google_provider.is_available():
            _default_provider = _google_provider
        else:
            _default_provider = NoOpCacheProvider()
    return _default_provider


def set_default_provider(provider: CacheProvider) -> None:
    """
    Set the default cache provider.
    
    Args:
        provider: Provider to use as default
    """
    global _default_provider
    _default_provider = provider


# Initialize with available providers
register_provider(NoOpCacheProvider())
if _google_provider:
    register_provider(_google_provider)
    logger.info(f"Google cache provider registered: available={_google_provider.is_available()}")
