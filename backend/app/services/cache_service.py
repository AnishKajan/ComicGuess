"""
Cache management service for Cloudflare CDN integration
Handles cache invalidation at puzzle rollover and asset updates
"""

import logging
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

class CacheInvalidationRequest(BaseModel):
    """Request model for cache invalidation"""
    files: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    hosts: Optional[List[str]] = None
    prefixes: Optional[List[str]] = None
    purge_everything: bool = False

class CacheInvalidationResult(BaseModel):
    """Result model for cache invalidation"""
    success: bool
    message: str
    purged_files: Optional[List[str]] = None
    errors: Optional[List[str]] = None
    timestamp: datetime

class CloudflareCacheService:
    """Service for managing Cloudflare cache invalidation"""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.zone_id = self.settings.cloudflare_zone_id
        self.api_token = self.settings.cloudflare_api_token
        
        # Define puzzle-related cache paths
        self.puzzle_cache_paths = [
            "/api/puzzle/today*",
            "/api/puzzle/*/status*",
            "/api/daily-progress*",
            "/api/streak-status*"
        ]
        
        # Define image cache paths
        self.image_cache_paths = [
            "/images/*",
            "/api/images/*"
        ]
    
    async def invalidate_puzzle_cache(self, universe: Optional[str] = None) -> CacheInvalidationResult:
        """
        Invalidate puzzle-related cache at daily rollover
        
        Args:
            universe: Specific universe to invalidate (optional, defaults to all)
            
        Returns:
            CacheInvalidationResult with success status and details
        """
        try:
            # Build cache invalidation paths
            paths_to_purge = []
            
            if universe:
                # Invalidate specific universe paths
                paths_to_purge.extend([
                    f"/api/puzzle/today?universe={universe}",
                    f"/{universe}/*",
                    f"/api/puzzle/*{universe}*"
                ])
            else:
                # Invalidate all puzzle-related paths
                paths_to_purge.extend(self.puzzle_cache_paths)
                paths_to_purge.extend([
                    "/marvel/*",
                    "/DC/*", 
                    "/image/*"
                ])
            
            # Add cache-busting tags
            cache_tags = [
                "puzzle-metadata",
                "daily-puzzle",
                f"puzzle-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            ]
            
            if universe:
                cache_tags.append(f"universe-{universe}")
            
            request = CacheInvalidationRequest(
                files=paths_to_purge,
                tags=cache_tags
            )
            
            result = await self._purge_cache(request)
            
            logger.info(f"Puzzle cache invalidation completed for {universe or 'all universes'}: {result.success}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error invalidating puzzle cache: {e}")
            return CacheInvalidationResult(
                success=False,
                message=f"Cache invalidation failed: {str(e)}",
                errors=[str(e)],
                timestamp=datetime.now(timezone.utc)
            )
    
    async def invalidate_image_cache(self, universe: str, character_name: Optional[str] = None) -> CacheInvalidationResult:
        """
        Invalidate image cache for character images
        
        Args:
            universe: Comic universe (marvel, DC, image)
            character_name: Specific character name (optional)
            
        Returns:
            CacheInvalidationResult with success status and details
        """
        try:
            paths_to_purge = []
            
            if character_name:
                # Invalidate specific character image
                paths_to_purge.extend([
                    f"/images/{universe}/{character_name}*",
                    f"/api/images/{universe}/{character_name}*"
                ])
            else:
                # Invalidate all images for universe
                paths_to_purge.extend([
                    f"/images/{universe}/*",
                    f"/api/images/{universe}/*"
                ])
            
            # Add image-specific cache tags
            cache_tags = [
                "character-images",
                f"universe-{universe}"
            ]
            
            if character_name:
                cache_tags.append(f"character-{character_name.lower().replace(' ', '-')}")
            
            request = CacheInvalidationRequest(
                files=paths_to_purge,
                tags=cache_tags
            )
            
            result = await self._purge_cache(request)
            
            logger.info(f"Image cache invalidation completed for {universe}/{character_name or 'all'}: {result.success}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error invalidating image cache: {e}")
            return CacheInvalidationResult(
                success=False,
                message=f"Image cache invalidation failed: {str(e)}",
                errors=[str(e)],
                timestamp=datetime.now(timezone.utc)
            )
    
    async def purge_all_cache(self) -> CacheInvalidationResult:
        """
        Purge all cache (emergency use only)
        
        Returns:
            CacheInvalidationResult with success status and details
        """
        try:
            request = CacheInvalidationRequest(purge_everything=True)
            result = await self._purge_cache(request)
            
            logger.warning(f"Full cache purge completed: {result.success}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error purging all cache: {e}")
            return CacheInvalidationResult(
                success=False,
                message=f"Full cache purge failed: {str(e)}",
                errors=[str(e)],
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _purge_cache(self, request: CacheInvalidationRequest) -> CacheInvalidationResult:
        """
        Internal method to execute cache purge via Cloudflare API
        
        Args:
            request: CacheInvalidationRequest with purge parameters
            
        Returns:
            CacheInvalidationResult with API response details
        """
        if not self.zone_id or not self.api_token:
            raise ValueError("Cloudflare zone ID and API token must be configured")
        
        url = f"{self.base_url}/zones/{self.zone_id}/purge_cache"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # Build request payload
        payload = {}
        
        if request.purge_everything:
            payload["purge_everything"] = True
        else:
            if request.files:
                payload["files"] = request.files
            if request.tags:
                payload["tags"] = request.tags
            if request.hosts:
                payload["hosts"] = request.hosts
            if request.prefixes:
                payload["prefixes"] = request.prefixes
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()
                
                if response.status == 200 and response_data.get("success"):
                    return CacheInvalidationResult(
                        success=True,
                        message="Cache invalidation successful",
                        purged_files=request.files,
                        timestamp=datetime.now(timezone.utc)
                    )
                else:
                    error_messages = []
                    if "errors" in response_data:
                        error_messages = [error.get("message", str(error)) for error in response_data["errors"]]
                    
                    return CacheInvalidationResult(
                        success=False,
                        message=f"Cloudflare API error: {response.status}",
                        errors=error_messages or [f"HTTP {response.status}"],
                        timestamp=datetime.now(timezone.utc)
                    )

class CacheHeaderService:
    """Service for managing HTTP cache headers"""
    
    @staticmethod
    def get_puzzle_cache_headers(is_personalized: bool = False) -> Dict[str, str]:
        """
        Get appropriate cache headers for puzzle endpoints
        
        Args:
            is_personalized: Whether the response contains user-specific data
            
        Returns:
            Dictionary of HTTP headers for caching
        """
        if is_personalized:
            # Private cache for user-specific data
            return {
                "Cache-Control": "private, max-age=300, must-revalidate",  # 5 minutes
                "Vary": "Authorization, User-Agent"
            }
        else:
            # Public cache for puzzle metadata
            return {
                "Cache-Control": "public, max-age=3600, s-maxage=3600",  # 1 hour
                "Vary": "Accept-Encoding",
                "X-Cache-Tags": "puzzle-metadata,daily-puzzle"
            }
    
    @staticmethod
    def get_image_cache_headers(version: Optional[str] = None) -> Dict[str, str]:
        """
        Get appropriate cache headers for image assets
        
        Args:
            version: Asset version for cache busting
            
        Returns:
            Dictionary of HTTP headers for caching
        """
        headers = {
            "Cache-Control": "public, max-age=604800, immutable",  # 7 days
            "Vary": "Accept-Encoding",
            "X-Cache-Tags": "character-images"
        }
        
        if version:
            headers["ETag"] = f'"{version}"'
        
        return headers
    
    @staticmethod
    def get_no_cache_headers() -> Dict[str, str]:
        """
        Get headers to prevent caching (for dynamic/sensitive endpoints)
        
        Returns:
            Dictionary of HTTP headers to prevent caching
        """
        return {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }

# Global cache service instance
cache_service = CloudflareCacheService()
cache_headers = CacheHeaderService()