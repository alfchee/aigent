"""
Cache Management API Endpoints

Provides endpoints for managing Gemini API prompt caches.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.prompt_cache import (
    get_cache_manager,
    invalidate_all_caches,
    get_caching_status,
    PromptCacheManager
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["cache"])


class CacheStatusResponse(BaseModel):
    """Response model for cache status."""
    enabled: bool
    version: str
    ttl_minutes: int
    model: str
    caches: dict


class InvalidateCacheRequest(BaseModel):
    """Request model for cache invalidation."""
    cache_type: str = "all"  # "agency", "worker", or "all"


class InvalidateCacheResponse(BaseModel):
    """Response model for cache invalidation."""
    deleted: dict
    message: str


@router.get("/status", response_model=CacheStatusResponse)
async def get_cache_status():
    """
    Get the current status of all caches.
    
    Returns information about:
    - Whether caching is enabled
    - Cache version
    - TTL configuration
    - Model used for caching
    - List of active caches with their status
    """
    try:
        status = get_caching_status()
        return CacheStatusResponse(**status)
    except Exception as e:
        logger.error(f"Failed to get cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invalidate", response_model=InvalidateCacheResponse)
async def invalidate_cache(request: InvalidateCacheRequest = InvalidateCacheRequest(cache_type="all")):
    """
    Invalidate caches.
    
    Args:
        cache_type: Type of cache to invalidate:
            - "all": Delete all caches (agency + workers)
            - "agency": Delete only the agency-level cache
            - "worker": Delete only worker-level caches
    
    Returns:
        Dictionary with cache names that were deleted and their status
    """
    try:
        if request.cache_type not in ["all", "agency", "worker"]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid cache_type. Must be 'all', 'agency', or 'worker'"
            )
        
        deleted = invalidate_all_caches() if request.cache_type == "all" else \
                  get_cache_manager().invalidate_cache(request.cache_type)
        
        return InvalidateCacheResponse(
            deleted=deleted,
            message=f"Successfully invalidated {request.cache_type} caches"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to invalidate cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh/{worker_name}")
async def refresh_worker_cache(worker_name: str):
    """
    Manually refresh a worker cache before it expires.
    
    This extends the TTL of the cache.
    
    Args:
        worker_name: Name of the worker cache to refresh
        
    Returns:
        Success message
    """
    try:
        manager = get_cache_manager()
        success = manager.refresh_cache(worker_name)
        
        if success:
            return {"message": f"Successfully refreshed cache for {worker_name}"}
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Cache for worker '{worker_name}' not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invalidate-all-google")
async def invalidate_all_google_caches():
    """
    Invalidate ALL cached contents in Google API.
    
    This is a destructive operation that will delete ALL navibot-related caches
    from Google, regardless of the current version. Use this when you need
    to ensure a complete reset.
    
    Returns:
        Number of caches deleted
    """
    try:
        manager = get_cache_manager()
        count = manager.invalidate_all_google_caches()
        return {
            "message": f"Successfully invalidated {count} caches",
            "deleted_count": count
        }
    except Exception as e:
        logger.error(f"Failed to invalidate all Google caches: {e}")
        raise HTTPException(status_code=500, detail=str(e))
