"""
Image version management API endpoints
Handles versioned asset management and cache invalidation for character images
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from pydantic import BaseModel, Field

from app.services.image_service import image_service
from app.auth.middleware import get_current_user
from app.security.input_validation import InputSanitizer, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["image-versions"])

class ImageVersionRequest(BaseModel):
    """Request model for image version operations"""
    universe: str = Field(..., description="Comic universe (marvel, DC, image)")
    character_name: Optional[str] = Field(None, description="Specific character name (optional)")
    force_refresh: bool = Field(False, description="Force refresh of version information")

class ImageVersionResponse(BaseModel):
    """Response model for image version information"""
    universe: str
    character_name: str
    version: str
    etag: str
    last_modified: Optional[str] = None
    url: str
    cache_headers: dict

class BulkVersionResponse(BaseModel):
    """Response model for bulk version operations"""
    success: bool
    universe: str
    processed_count: int
    results: List[dict]
    errors: Optional[List[str]] = None

@router.get("/version/{universe}/{character_name}", response_model=ImageVersionResponse)
async def get_image_version(
    universe: str,
    character_name: str,
    response: Response,
    current_user: dict = Depends(get_current_user)
) -> ImageVersionResponse:
    """
    Get version information for a specific character image
    
    - **universe**: Comic universe (marvel, DC, image)
    - **character_name**: Name of the character
    
    Returns image version information including ETag and cache headers
    """
    try:
        # Validate universe
        universe = InputSanitizer.validate_universe(universe)
        
        # Sanitize character name
        character_name = InputSanitizer.sanitize_string(character_name, max_length=100)
        
        # Get image information with versioning
        image_info = await image_service.get_character_image_url(
            universe, character_name, include_version=True
        )
        
        if not image_info:
            raise HTTPException(
                status_code=404,
                detail=f"Image not found for {character_name} in {universe}"
            )
        
        # Set version-aware cache headers
        if image_info.get("version") and image_info.get("etag"):
            headers = image_service.get_versioned_cache_headers(
                version=image_info["version"],
                etag=image_info["etag"]
            )
            for header, value in headers.items():
                response.headers[header] = value
        
        return ImageVersionResponse(
            universe=universe,
            character_name=character_name,
            version=image_info["version"],
            etag=image_info["etag"],
            last_modified=image_info.get("last_modified"),
            url=image_info["url"],
            cache_headers=headers if image_info.get("version") else {}
        )
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error getting image version for {character_name} in {universe}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get image version information")

@router.post("/invalidate-version", response_model=dict)
async def invalidate_image_version(
    request: ImageVersionRequest,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Invalidate version cache for character images
    
    - **universe**: Comic universe (marvel, DC, image)
    - **character_name**: Specific character name (optional, defaults to all in universe)
    - **force_refresh**: Force refresh of version information
    
    Returns invalidation result
    """
    try:
        # Validate universe
        universe = InputSanitizer.validate_universe(request.universe)
        
        # Validate character name if provided
        character_name = None
        if request.character_name:
            character_name = InputSanitizer.sanitize_string(request.character_name, max_length=100)
        
        if character_name:
            # Invalidate specific character image
            success = await image_service.invalidate_image_version(universe, character_name)
            
            return {
                "success": success,
                "message": f"Version invalidated for {character_name} in {universe}",
                "universe": universe,
                "character_name": character_name
            }
        else:
            # Bulk invalidate universe images
            result = await image_service.bulk_invalidate_universe_images(universe)
            
            return {
                "success": result["success"],
                "message": f"Bulk invalidation completed for {universe}",
                "universe": universe,
                "invalidated_count": result["invalidated_count"],
                "cache_result": result.get("cache_result")
            }
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error invalidating image version: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate image version")

@router.get("/versions/{universe}", response_model=BulkVersionResponse)
async def get_universe_image_versions(
    universe: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of images to return"),
    offset: int = Query(0, ge=0, description="Number of images to skip"),
    current_user: dict = Depends(get_current_user)
) -> BulkVersionResponse:
    """
    Get version information for all images in a universe
    
    - **universe**: Comic universe (marvel, DC, image)
    - **limit**: Maximum number of images to return (1-200)
    - **offset**: Number of images to skip for pagination
    
    Returns version information for all images in the universe
    """
    try:
        # Validate universe
        universe = InputSanitizer.validate_universe(universe)
        
        # Get list of character names in universe
        character_names = await image_service.blob_service.list_images_by_universe(universe)
        
        # Apply pagination
        paginated_names = character_names[offset:offset + limit]
        
        results = []
        errors = []
        
        for character_name in paginated_names:
            try:
                image_info = await image_service.get_character_image_url(
                    universe, character_name, include_version=True
                )
                
                results.append({
                    "character_name": character_name,
                    "version": image_info.get("version"),
                    "etag": image_info.get("etag"),
                    "last_modified": image_info.get("last_modified"),
                    "url": image_info["url"],
                    "is_fallback": image_info["is_fallback"]
                })
                
            except Exception as e:
                error_msg = f"Failed to get version for {character_name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)
        
        return BulkVersionResponse(
            success=len(errors) == 0,
            universe=universe,
            processed_count=len(results),
            results=results,
            errors=errors if errors else None
        )
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error getting universe image versions for {universe}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get universe image versions")

@router.post("/refresh-versions/{universe}", response_model=BulkVersionResponse)
async def refresh_universe_versions(
    universe: str,
    current_user: dict = Depends(get_current_user)
) -> BulkVersionResponse:
    """
    Refresh version information for all images in a universe
    
    - **universe**: Comic universe (marvel, DC, image)
    
    Forces refresh of version information and cache invalidation
    """
    try:
        # Validate universe
        universe = InputSanitizer.validate_universe(universe)
        
        # Get list of character names in universe
        character_names = await image_service.blob_service.list_images_by_universe(universe)
        
        results = []
        errors = []
        
        for character_name in character_names:
            try:
                # Invalidate existing version
                await image_service.invalidate_image_version(universe, character_name)
                
                # Get fresh version information
                image_info = await image_service.get_character_image_url(
                    universe, character_name, include_version=True
                )
                
                results.append({
                    "character_name": character_name,
                    "version": image_info.get("version"),
                    "etag": image_info.get("etag"),
                    "refreshed": True
                })
                
            except Exception as e:
                error_msg = f"Failed to refresh version for {character_name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(error_msg)
        
        logger.info(f"Refreshed versions for {len(results)} images in {universe}")
        
        return BulkVersionResponse(
            success=len(errors) == 0,
            universe=universe,
            processed_count=len(results),
            results=results,
            errors=errors if errors else None
        )
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error refreshing universe versions for {universe}: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh universe versions")

@router.get("/cache-validation/{universe}/{character_name}")
async def validate_image_cache(
    universe: str,
    character_name: str,
    if_none_match: Optional[str] = Query(None, description="ETag for conditional request"),
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Validate image cache using ETag for conditional requests
    
    - **universe**: Comic universe (marvel, DC, image)
    - **character_name**: Name of the character
    - **if_none_match**: ETag value for conditional request
    
    Returns cache validation result
    """
    try:
        # Validate universe
        universe = InputSanitizer.validate_universe(universe)
        
        # Sanitize character name
        character_name = InputSanitizer.sanitize_string(character_name, max_length=100)
        
        # Get current image version
        image_info = await image_service.get_character_image_url(
            universe, character_name, include_version=True
        )
        
        if not image_info:
            raise HTTPException(
                status_code=404,
                detail=f"Image not found for {character_name} in {universe}"
            )
        
        current_etag = image_info.get("etag")
        
        # Check if cache is still valid
        cache_valid = if_none_match and if_none_match.strip('"') == current_etag
        
        return {
            "cache_valid": cache_valid,
            "current_etag": current_etag,
            "provided_etag": if_none_match,
            "character_name": character_name,
            "universe": universe,
            "last_modified": image_info.get("last_modified"),
            "recommendation": "use_cache" if cache_valid else "fetch_new"
        }
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error validating image cache for {character_name} in {universe}: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate image cache")

# Health check for image versioning service
@router.get("/version-health")
async def image_version_health_check():
    """Health check endpoint for image versioning service"""
    try:
        return {
            "status": "healthy",
            "service": "image-versioning",
            "features": [
                "etag_support",
                "version_tracking",
                "cache_invalidation",
                "bulk_operations"
            ]
        }
        
    except Exception as e:
        logger.error(f"Image version health check failed: {e}")
        raise HTTPException(status_code=503, detail="Image versioning service unhealthy")