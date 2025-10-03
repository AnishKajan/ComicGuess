"""
Image serving API endpoints with CDN integration and fallback handling.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional
import logging
from app.services.image_service import image_service
from app.services.cache_service import cache_headers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

@router.get("/character/{universe}/{character_name}")
async def get_character_image(
    universe: str,
    character_name: str,
    width: Optional[int] = Query(None, ge=50, le=2000, description="Image width in pixels"),
    height: Optional[int] = Query(None, ge=50, le=2000, description="Image height in pixels"),
    quality: Optional[int] = Query(None, ge=1, le=100, description="Image quality (1-100)"),
    use_cdn: bool = Query(True, description="Use CDN for image delivery"),
    response: Response = None
):
    """
    Get character image URL with optional optimization parameters.
    
    Args:
        universe: Comic universe (marvel, dc, image)
        character_name: Name of the character
        width: Optional image width
        height: Optional image height
        quality: Optional image quality
        use_cdn: Whether to use CDN URLs
        response: FastAPI response object for headers
        
    Returns:
        Image information with URL and metadata
    """
    # Validate universe
    valid_universes = ["marvel", "dc", "image"]
    if universe.lower() not in valid_universes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid universe. Must be one of: {', '.join(valid_universes)}"
        )
    
    try:
        # Get optimized image URL if parameters provided
        if width or height or quality:
            image_info = await image_service.get_optimized_image_url(
                universe.lower(), character_name, width, height, quality
            )
        else:
            image_info = await image_service.get_character_image_url(
                universe.lower(), character_name, use_cdn
            )
        
        # Set appropriate cache headers with versioning
        if image_info.get("version") and image_info.get("etag"):
            headers = image_service.get_versioned_cache_headers(
                version=image_info["version"],
                etag=image_info["etag"]
            )
        else:
            headers = cache_headers.get_image_cache_headers()
        
        for header, value in headers.items():
            response.headers[header] = value
        
        return {
            "success": True,
            "data": image_info
        }
        
    except Exception as e:
        logger.error(f"Error serving image for {character_name} in {universe}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve character image"
        )

@router.get("/universe/{universe}/preload")
async def preload_universe_images(
    universe: str,
    response: Response = None
):
    """
    Get all image URLs for a universe for preloading.
    
    Args:
        universe: Comic universe (marvel, dc, image)
        response: FastAPI response object for headers
        
    Returns:
        List of all character images in the universe
    """
    # Validate universe
    valid_universes = ["marvel", "dc", "image"]
    if universe.lower() not in valid_universes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid universe. Must be one of: {', '.join(valid_universes)}"
        )
    
    try:
        preload_info = await image_service.preload_universe_images(universe.lower())
        
        # Set cache headers for preload data (shorter cache time)
        response.headers["Cache-Control"] = "public, max-age=3600"  # 1 hour
        response.headers["X-Content-Type"] = "preload-manifest"
        
        return {
            "success": True,
            "data": preload_info
        }
        
    except Exception as e:
        logger.error(f"Error preloading images for {universe}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to preload universe images"
        )

@router.get("/validate/{universe}/{character_name}")
async def validate_character_image(
    universe: str,
    character_name: str
):
    """
    Validate that an image exists for a character.
    
    Args:
        universe: Comic universe (marvel, dc, image)
        character_name: Name of the character
        
    Returns:
        Validation result
    """
    # Validate universe
    valid_universes = ["marvel", "dc", "image"]
    if universe.lower() not in valid_universes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid universe. Must be one of: {', '.join(valid_universes)}"
        )
    
    try:
        exists = await image_service.validate_image_exists(universe.lower(), character_name)
        
        return {
            "success": True,
            "data": {
                "universe": universe.lower(),
                "character_name": character_name,
                "image_exists": exists
            }
        }
        
    except Exception as e:
        logger.error(f"Error validating image for {character_name} in {universe}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to validate character image"
        )