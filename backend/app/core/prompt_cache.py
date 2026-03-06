"""
Prompt Caching Module for Gemini API

This module provides Context Caching functionality for Gemini API to reduce costs
and improve response times by caching system prompts and tool definitions.

Architecture:
- Agency-level cache: Common tools shared across all workers
- Worker-level cache: Individual caches for each worker type (WebNavigator, CalendarManager, etc.)

Usage:
    from app.core.prompt_cache import PromptCacheManager, create_worker_cache
    
    # Get or create cache for a worker
    cache = PromptCacheManager.get_cache("GeneralAssistant")
    
    # Use cached content when creating model
    model = GenerativeModel(model_name="gemini-2.0-flash", cached_content=cache.name)
"""

import os
import logging
import hashlib
import json
import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class CacheStatus(Enum):
    """Status of a cached content."""
    ACTIVE = "active"
    EXPIRED = "expired"
    EXPIRING_SOON = "expiring_soon"
    INVALID = "invalid"


# Cache TTL configuration (in minutes)
DEFAULT_CACHE_TTL_MINUTES = int(os.getenv("NAVIBOT_CACHE_TTL_MINUTES", "60"))
MIN_CACHE_TOKENS = 32000  # Minimum tokens required for efficient caching

# Model configuration
DEFAULT_CACHE_MODEL = os.getenv("NAVIBOT_CACHE_MODEL", "gemini-1.5-flash-001")


@dataclass
class CacheInfo:
    """Information about a cached content."""
    name: str  # Cache resource name
    display_name: str
    model: str
    status: CacheStatus
    created_at: datetime.datetime
    expires_at: datetime.datetime
    last_used_at: Optional[datetime.datetime] = None
    token_count: Optional[int] = None
    version: str = ""  # For cache invalidation tracking


class PromptCacheManager:
    """
    Manages Gemini API Prompt Caching for the multi-agent system.
    
    Implements both:
    - Agency-level cache: Common tools shared across all workers
    - Worker-level cache: Individual caches for each worker type
    """
    
    # Singleton instance
    _instance: Optional['PromptCacheManager'] = None
    _caches: Dict[str, CacheInfo] = {}
    _lock = None  # Will be initialized lazily
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._lock = logging.getLogger(f"{__name__}.lock")
        self._google_api_key = os.getenv("GOOGLE_API_KEY")
        self._cache_ttl = DEFAULT_CACHE_TTL_MINUTES
        self._cache_model = DEFAULT_CACHE_MODEL
        self._enabled = os.getenv("NAVIBOT_CACHE_ENABLED", "true").lower() == "true"
        self._version = os.getenv("NAVIBOT_CACHE_VERSION", "1.0.0")  # Bump to invalidate all caches
        
        # Import here to avoid circular imports
        try:
            from google.generativeai import caching
            self._caching_module = caching
        except ImportError:
            logger.warning("google-generativeai not installed. Caching disabled.")
            self._caching_module = None
            self._enabled = False
        
        logger.info(f"PromptCacheManager initialized: enabled={self._enabled}, ttl={self._cache_ttl}min, model={self._cache_model}")
    
    @property
    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled and self._caching_module is not None
    
    def _get_cache_key(self, cache_type: str, worker_name: Optional[str] = None) -> str:
        """Generate a unique cache key."""
        if worker_name:
            return f"cache_{cache_type}_{worker_name}_{self._version}"
        return f"cache_{cache_type}_{self._version}"
    
    def _hash_content(self, content: str) -> str:
        """Generate hash for content validation."""
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _list_existing_caches(self) -> List[Any]:
        """List all existing cached contents."""
        if not self.is_enabled:
            return []
        
        try:
            return list(self._caching_module.CachedContent.list())
        except Exception as e:
            logger.warning(f"Failed to list existing caches: {e}")
            return []
    
    def _find_existing_cache(self, display_name: str) -> Optional[Any]:
        """Find an existing cache by display name."""
        for cache in self._list_existing_caches():
            if cache.display_name == display_name:
                return cache
        return None
    
    def _get_ttl_delta(self) -> datetime.timedelta:
        """Get the TTL as a timedelta."""
        return datetime.timedelta(minutes=self._cache_ttl)
    
    def create_agency_cache(
        self,
        system_instruction: str,
        tools_schema: List[Dict[str, Any]],
        contents: Optional[List[Any]] = None
    ) -> Optional[CacheInfo]:
        """
        Create a cache for the agency (common tools shared by all workers).
        
        This cache contains:
        - System prompt with base instructions
        - Common tool definitions that all workers might use
        
        Args:
            system_instruction: The system prompt to cache
            tools_schema: List of tool definitions
            contents: Optional static contents to include
            
        Returns:
            CacheInfo if successful, None otherwise
        """
        if not self.is_enabled:
            logger.info("Caching disabled, skipping agency cache creation")
            return None
        
        display_name = f"navibot_agency_cache_v{self._version}"
        
        # Check if cache already exists
        existing = self._find_existing_cache(display_name)
        if existing:
            logger.info(f"Agency cache already exists: {existing.name}")
            cache_info = self._get_cache_info(existing)
            self._caches["agency"] = cache_info
            return cache_info
        
        try:
            # Estimate token count (rough approximation: ~4 chars per token)
            estimated_tokens = len(system_instruction) // 4 + sum(
                len(json.dumps(tool)) for tool in tools_schema
            ) // 4
            
            if estimated_tokens < MIN_CACHE_TOKENS:
                logger.warning(
                    f"Agency cache content ({estimated_tokens} tokens) is below "
                    f"recommended minimum ({MIN_CACHE_TOKENS} tokens). "
                    f"Consider adding more static content for efficiency."
                )
            
            cache = self._caching_module.CachedContent.create(
                model=self._cache_model,
                display_name=display_name,
                system_instruction=system_instruction,
                contents=contents or [],
                ttl=self._get_ttl_delta(),
            )
            
            cache_info = CacheInfo(
                name=cache.name,
                display_name=display_name,
                model=self._cache_model,
                status=CacheStatus.ACTIVE,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                expires_at=datetime.datetime.now(datetime.timezone.utc) + self._get_ttl_delta(),
                token_count=estimated_tokens,
                version=self._version
            )
            
            self._caches["agency"] = cache_info
            logger.info(f"Created agency cache: {cache.name} ({estimated_tokens} estimated tokens)")
            return cache_info
            
        except Exception as e:
            logger.error(f"Failed to create agency cache: {e}", exc_info=True)
            return None
    
    def create_worker_cache(
        self,
        worker_name: str,
        system_instruction: str,
        tools_schema: List[Dict[str, Any]],
        contents: Optional[List[Any]] = None
    ) -> Optional[CacheInfo]:
        """
        Create a cache for a specific worker.
        
        Each worker (WebNavigator, CalendarManager, GeneralAssistant, ImageGenerator)
        gets its own cache with worker-specific system prompt and tool set.
        
        Args:
            worker_name: Name of the worker (e.g., "GeneralAssistant")
            system_instruction: Worker's system prompt
            tools_schema: List of tool definitions for this worker
            contents: Optional static contents
            
        Returns:
            CacheInfo if successful, None otherwise
        """
        if not self.is_enabled:
            logger.info(f"Caching disabled, skipping worker cache for {worker_name}")
            return None
        
        display_name = f"navibot_worker_{worker_name}_v{self._version}"
        
        # Check if cache already exists
        existing = self._find_existing_cache(display_name)
        if existing:
            logger.info(f"Worker cache already exists for {worker_name}: {existing.name}")
            cache_info = self._get_cache_info(existing)
            self._caches[worker_name] = cache_info
            return cache_info
        
        try:
            # Estimate token count
            estimated_tokens = len(system_instruction) // 4 + sum(
                len(json.dumps(tool)) for tool in tools_schema
            ) // 4
            
            if estimated_tokens < MIN_CACHE_TOKENS:
                logger.warning(
                    f"Worker {worker_name} cache content ({estimated_tokens} tokens) is below "
                    f"recommended minimum ({MIN_CACHE_TOKENS} tokens)."
                )
            
            cache = self._caching_module.CachedContent.create(
                model=self._cache_model,
                display_name=display_name,
                system_instruction=system_instruction,
                contents=contents or [],
                ttl=self._get_ttl_delta(),
            )
            
            cache_info = CacheInfo(
                name=cache.name,
                display_name=display_name,
                model=self._cache_model,
                status=CacheStatus.ACTIVE,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                expires_at=datetime.datetime.now(datetime.timezone.utc) + self._get_ttl_delta(),
                token_count=estimated_tokens,
                version=self._version
            )
            
            self._caches[worker_name] = cache_info
            logger.info(f"Created worker cache for {worker_name}: {cache.name} ({estimated_tokens} estimated tokens)")
            return cache_info
            
        except Exception as e:
            logger.error(f"Failed to create worker cache for {worker_name}: {e}", exc_info=True)
            return None
    
    def _get_cache_info(self, cache: Any) -> CacheInfo:
        """Extract CacheInfo from a cached content object."""
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Try to get expiration time
        try:
            if hasattr(cache, 'ttl') and cache.ttl:
                expires_at = now + cache.ttl
            elif hasattr(cache, 'expiration') and cache.expiration:
                expires_at = cache.expiration
            else:
                expires_at = now + self._get_ttl_delta()
        except Exception:
            expires_at = now + self._get_ttl_delta()
        
        # Determine status
        if expires_at < now:
            status = CacheStatus.EXPIRED
        elif expires_at < now + datetime.timedelta(minutes=5):
            status = CacheStatus.EXPIRING_SOON
        else:
            status = CacheStatus.ACTIVE
        
        return CacheInfo(
            name=cache.name,
            display_name=cache.display_name,
            model=cache.model,
            status=status,
            created_at=now,  # Exact creation time not exposed
            expires_at=expires_at,
            version=self._version
        )
    
    def get_cache(self, worker_name: str) -> Optional[str]:
        """
        Get the cache resource name for a worker.
        
        Returns the cached content name to use with GenerativeModel.
        
        Args:
            worker_name: Name of the worker
            
        Returns:
            Cache resource name or None if not available
        """
        if worker_name in self._caches:
            cache_info = self._caches[worker_name]
            # Check if cache is still valid
            if cache_info.status in [CacheStatus.ACTIVE, CacheStatus.EXPIRING_SOON]:
                return cache_info.name
            elif cache_info.status == CacheStatus.EXPIRED:
                # Try to refresh the cache
                logger.info(f"Cache for {worker_name} expired, will recreate on next request")
                del self._caches[worker_name]
        
        return None
    
    def get_or_create_worker_cache(
        self,
        worker_name: str,
        system_instruction: str,
        tools_schema: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Get existing cache or create new one for a worker.
        
        This is the main entry point for workers to get cached content.
        
        Args:
            worker_name: Name of the worker
            system_instruction: Worker's system prompt
            tools_schema: List of tool definitions
            
        Returns:
            Cache resource name or None
        """
        # Try to get existing cache
        existing_cache = self.get_cache(worker_name)
        if existing_cache:
            return existing_cache
        
        # Check if there's an existing cache in Google that we haven't tracked
        display_name = f"navibot_worker_{worker_name}_v{self._version}"
        existing = self._find_existing_cache(display_name)
        if existing:
            cache_info = self._get_cache_info(existing)
            if cache_info.status != CacheStatus.EXPIRED:
                self._caches[worker_name] = cache_info
                return cache_info.name
        
        # Create new cache
        cache_info = self.create_worker_cache(worker_name, system_instruction, tools_schema)
        return cache_info.name if cache_info else None
    
    def invalidate_cache(self, cache_type: str = "all") -> Dict[str, bool]:
        """
        Invalidate caches.
        
        Args:
            cache_type: Type of cache to invalidate ("agency", "worker", or "all")
            
        Returns:
            Dict with cache names and their deletion status
        """
        results = {}
        
        if cache_type in ["agency", "all"]:
            if "agency" in self._caches:
                cache_info = self._caches["agency"]
                try:
                    cache = self._caching_module.CachedContent.get(cache_info.name)
                    cache.delete()
                    results[cache_info.name] = True
                    logger.info(f"Deleted agency cache: {cache_info.name}")
                except Exception as e:
                    results[cache_info.name] = False
                    logger.warning(f"Failed to delete agency cache: {e}")
                del self._caches["agency"]
        
        if cache_type in ["worker", "all"]:
            workers_to_delete = [
                k for k in self._caches.keys() 
                if k != "agency"
            ]
            for worker in workers_to_delete:
                cache_info = self._caches[worker]
                try:
                    cache = self._caching_module.CachedContent.get(cache_info.name)
                    cache.delete()
                    results[cache_info.name] = True
                    logger.info(f"Deleted worker cache for {worker}: {cache_info.name}")
                except Exception as e:
                    results[cache_info.name] = False
                    logger.warning(f"Failed to delete worker cache for {worker}: {e}")
                del self._caches[worker]
        
        return results
    
    def invalidate_all_google_caches(self) -> int:
        """
        Invalidate ALL cached contents in Google API.
        
        Use this when you need to ensure a complete reset.
        
        Returns:
            Number of caches deleted
        """
        count = 0
        for cache in self._list_existing_caches():
            try:
                if cache.display_name.startswith("navibot_"):
                    cache.delete()
                    count += 1
                    logger.info(f"Deleted cache: {cache.display_name}")
            except Exception as e:
                logger.warning(f"Failed to delete cache {cache.display_name}: {e}")
        
        # Clear local tracking
        self._caches.clear()
        return count
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get status of all caches."""
        status = {
            "enabled": self.is_enabled,
            "version": self._version,
            "ttl_minutes": self._cache_ttl,
            "model": self._cache_model,
            "caches": {}
        }
        
        # Refresh cache status from Google
        for cache in self._list_existing_caches():
            if cache.display_name.startswith("navibot_"):
                cache_info = self._get_cache_info(cache)
                status["caches"][cache.display_name] = {
                    "name": cache_info.name,
                    "status": cache_info.status.value,
                    "expires_at": cache_info.expires_at.isoformat() if cache_info.expires_at else None,
                }
        
        return status
    
    def refresh_cache(self, worker_name: str) -> bool:
        """
        Manually refresh a cache before it expires.
        
        This extends the TTL of the cache.
        
        Args:
            worker_name: Name of the worker cache to refresh
            
        Returns:
            True if successful, False otherwise
        """
        if worker_name not in self._caches:
            logger.warning(f"Cache for {worker_name} not found")
            return False
        
        cache_info = self._caches[worker_name]
        try:
            cache = self._caching_module.CachedContent.get(cache_info.name)
            # Update TTL (this extends the expiration)
            cache.update(ttl=self._get_ttl_delta())
            logger.info(f"Refreshed cache for {worker_name}: {cache.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh cache for {worker_name}: {e}")
            return False


def get_cache_manager() -> PromptCacheManager:
    """Get the singleton PromptCacheManager instance."""
    return PromptCacheManager()


def convert_tools_to_schema(tools: List[Any]) -> List[Dict[str, Any]]:
    """
    Convert LangChain tools to Gemini function declaration schema.
    
    Args:
        tools: List of LangChain tools (StructuredTool or Tool)
        
    Returns:
        List of function declaration dictionaries
    """
    schema = []
    
    for tool in tools:
        try:
            # Get tool metadata
            name = tool.name if hasattr(tool, 'name') else tool.__name__
            description = tool.description if hasattr(tool, 'description') else ""
            
            # Get input schema
            if hasattr(tool, 'args_schema') and tool.args_schema:
                # Try to get JSON schema from Pydantic model
                try:
                    if hasattr(tool.args_schema, 'model_json_schema'):
                        input_schema = tool.args_schema.model_json_schema()
                    elif hasattr(tool.args_schema, 'schema'):
                        input_schema = tool.args_schema.schema()
                    else:
                        input_schema = {}
                except Exception:
                    input_schema = {}
            else:
                input_schema = {}
            
            schema.append({
                "name": name,
                "description": description,
                "parameters": input_schema
            })
        except Exception as e:
            logger.warning(f"Failed to convert tool to schema: {e}")
            continue
    
    return schema


# Module-level convenience functions

def create_agency_cache(system_instruction: str, tools_schema: List[Dict[str, Any]]) -> Optional[str]:
    """
    Create or get agency-level cache.
    
    Args:
        system_instruction: System prompt
        tools_schema: Tool definitions
        
    Returns:
        Cache resource name or None
    """
    manager = get_cache_manager()
    cache_info = manager.create_agency_cache(system_instruction, tools_schema)
    return cache_info.name if cache_info else None


def create_worker_cache(
    worker_name: str, 
    system_instruction: str, 
    tools_schema: List[Dict[str, Any]]
) -> Optional[str]:
    """
    Create or get worker-level cache.
    
    Args:
        worker_name: Name of the worker
        system_instruction: Worker's system prompt
        tools_schema: Tool definitions
        
    Returns:
        Cache resource name or None
    """
    manager = get_cache_manager()
    return manager.get_or_create_worker_cache(worker_name, system_instruction, tools_schema)


def get_worker_cache(worker_name: str) -> Optional[str]:
    """
    Get existing worker cache.
    
    Args:
        worker_name: Name of the worker
        
    Returns:
        Cache resource name or None
    """
    manager = get_cache_manager()
    return manager.get_cache(worker_name)


def invalidate_all_caches() -> Dict[str, bool]:
    """Invalidate all caches."""
    manager = get_cache_manager()
    return manager.invalidate_cache("all")


def get_caching_status() -> Dict[str, Any]:
    """Get caching status."""
    manager = get_cache_manager()
    return manager.get_cache_status()
