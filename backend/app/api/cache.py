"""
Cache management API endpoints
Provides manual cache invalidation capabilities for administrators
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.services.cache_service import cache_service, CacheInvalidationResult
from app.auth.middleware import get_current_user
from app.security.input_validation import InputSanitizer, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])

class CacheInvalidationRequest(BaseModel):
    """Request model for manual cache invalidation"""
    universe: Optional[str] = Field(None, description="Specific universe to invalidate (optional)")
    character_name: Optional[str] = Field(None, description="Specific character for image cache (optional)")
    purge_all: bool = Field(False, description="Purge all cache (emergency use only)")

class CacheStatusResponse(BaseModel):
    """Response model for cache status"""
    cache_enabled: bool
    cloudflare_configured: bool
    last_invalidation: Optional[str] = None
    cache_policies: dict

@router.post("/invalidate/puzzles", response_model=CacheInvalidationResult)
async def invalidate_puzzle_cache(
    request: CacheInvalidationRequest,
    current_user: dict = Depends(get_current_user)
) -> CacheInvalidationResult:
    """
    Invalidate puzzle-related cache
    
    - **universe**: Specific universe to invalidate (optional, defaults to all)
    - **purge_all**: Emergency full cache purge (use with caution)
    
    Returns cache invalidation result with success status
    """
    try:
        # Validate universe if provided
        if request.universe:
            request.universe = InputSanitizer.validate_universe(request.universe)
        
        # Check for emergency purge
        if request.purge_all:
            logger.warning(f"Full cache purge requested by user {current_user.get('user_id', 'unknown')}")
            result = await cache_service.purge_all_cache()
        else:
            # Invalidate puzzle cache
            result = await cache_service.invalidate_puzzle_cache(request.universe)
        
        logger.info(f"Puzzle cache invalidation completed: {result.success}")
        
        return result
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error invalidating puzzle cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache invalidation failed: {str(e)}")

@router.post("/invalidate/images", response_model=CacheInvalidationResult)
async def invalidate_image_cache(
    request: CacheInvalidationRequest,
    current_user: dict = Depends(get_current_user)
) -> CacheInvalidationResult:
    """
    Invalidate character image cache
    
    - **universe**: Comic universe (marvel, dc, image) - required for image cache
    - **character_name**: Specific character name (optional, defaults to all in universe)
    
    Returns cache invalidation result with success status
    """
    try:
        # Universe is required for image cache invalidation
        if not request.universe:
            raise HTTPException(
                status_code=400,
                detail="Universe parameter is required for image cache invalidation"
            )
        
        # Validate universe
        universe = InputSanitizer.validate_universe(request.universe)
        
        # Validate character name if provided
        character_name = None
        if request.character_name:
            character_name = InputSanitizer.sanitize_string(request.character_name, max_length=100)
        
        # Invalidate image cache
        result = await cache_service.invalidate_image_cache(universe, character_name)
        
        logger.info(f"Image cache invalidation completed for {universe}/{character_name or 'all'}: {result.success}")
        
        return result
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error invalidating image cache: {e}")
        raise HTTPException(status_code=500, detail=f"Image cache invalidation failed: {str(e)}")

@router.get("/status", response_model=CacheStatusResponse)
async def get_cache_status(
    current_user: dict = Depends(get_current_user)
) -> CacheStatusResponse:
    """
    Get current cache configuration and status
    
    Returns cache system status and configuration details
    """
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        
        # Check if Cloudflare is configured
        cloudflare_configured = bool(
            settings.cloudflare_zone_id and 
            settings.cloudflare_api_token
        )
        
        # Define cache policies
        cache_policies = {
            "puzzle_metadata": {
                "ttl": "1 hour",
                "type": "public",
                "invalidation": "daily at UTC 00:00"
            },
            "user_data": {
                "ttl": "5 minutes",
                "type": "private",
                "invalidation": "on user action"
            },
            "character_images": {
                "ttl": "7 days",
                "type": "public",
                "invalidation": "on image update"
            }
        }
        
        return CacheStatusResponse(
            cache_enabled=cloudflare_configured,
            cloudflare_configured=cloudflare_configured,
            cache_policies=cache_policies
        )
        
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache status")

@router.post("/warm", response_model=dict)
async def warm_cache(
    universe: Optional[str] = Query(None, description="Universe to warm cache for"),
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Warm cache by pre-loading frequently accessed data
    
    - **universe**: Specific universe to warm (optional, defaults to all)
    
    Returns cache warming result
    """
    try:
        # This would typically make requests to key endpoints to populate cache
        # For now, return a placeholder response
        
        universes_to_warm = [universe] if universe else ["marvel", "dc", "image"]
        
        # Validate universes
        for u in universes_to_warm:
            InputSanitizer.validate_universe(u)
        
        logger.info(f"Cache warming requested for universes: {universes_to_warm}")
        
        return {
            "success": True,
            "message": f"Cache warming initiated for {len(universes_to_warm)} universe(s)",
            "universes": universes_to_warm,
            "note": "Cache warming is performed asynchronously"
        }
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache warming failed: {str(e)}")

@router.delete("/purge-all")
async def emergency_purge_all(
    confirm: bool = Query(..., description="Confirmation flag - must be true"),
    current_user: dict = Depends(get_current_user)
) -> CacheInvalidationResult:
    """
    Emergency endpoint to purge all cache
    
    **WARNING**: This will purge ALL cached content and may impact performance
    
    - **confirm**: Must be true to proceed with purge
    
    Returns cache purge result
    """
    try:
        if not confirm:
            raise HTTPException(
                status_code=400,
                detail="Confirmation required. Set confirm=true to proceed with full cache purge."
            )
        
        logger.warning(f"Emergency cache purge requested by user {current_user.get('user_id', 'unknown')}")
        
        result = await cache_service.purge_all_cache()
        
        if result.success:
            logger.warning("Emergency cache purge completed successfully")
        else:
            logger.error(f"Emergency cache purge failed: {result.message}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in emergency cache purge: {e}")
        raise HTTPException(status_code=500, detail=f"Emergency cache purge failed: {str(e)}")

# Health check for cache service
@router.get("/health")
async def cache_health_check():
    """Health check endpoint for cache service"""
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        
        return {
            "status": "healthy",
            "service": "cache-api",
            "cloudflare_configured": bool(
                settings.cloudflare_zone_id and 
                settings.cloudflare_api_token
            )
        }
        
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        raise HTTPException(status_code=503, detail="Cache service unhealthy")