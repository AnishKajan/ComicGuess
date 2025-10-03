"""
Image serving service with CDN integration and fallback handling.
Provides optimized image URLs and handles missing assets gracefully.
"""

import logging
import hashlib
from typing import Optional, Dict, Any
from urllib.parse import urljoin
from datetime import datetime, timezone
from app.storage.blob_storage import blob_storage_service
from app.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

class ImageService:
    """Service for serving character images with CDN optimization."""
    
    def __init__(self):
        """Initialize the image service."""
        self.blob_service = blob_storage_service
        self.cdn_base_url = self._get_cdn_base_url()
        self.fallback_images = {
            "marvel": "marvel/fallback-marvel.jpg",
            "dc": "dc/fallback-dc.jpg", 
            "image": "image/fallback-image.jpg"
        }
        # Version tracking for cache invalidation
        self._image_versions = {}
    
    def _get_cdn_base_url(self) -> Optional[str]:
        """
        Get the CDN base URL for image serving.
        In production, this would be the Cloudflare CDN URL.
        """
        # Extract storage account name from connection string for CDN URL construction
        if settings.azure_storage_connection_string:
            try:
                # Parse connection string to get account name
                conn_parts = dict(part.split('=', 1) for part in settings.azure_storage_connection_string.split(';') if '=' in part)
                account_name = conn_parts.get('AccountName')
                if account_name:
                    return f"https://{account_name}.blob.core.windows.net/{settings.azure_storage_container_name}"
            except Exception as e:
                logger.warning(f"Could not parse CDN URL from connection string: {e}")
        
        return None
    
    async def get_character_image_url(
        self, 
        universe: str, 
        character_name: str,
        use_cdn: bool = True,
        include_cache_headers: bool = True,
        include_version: bool = True
    ) -> Dict[str, Any]:
        """
        Get optimized image URL for a character with fallback handling.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            character_name: Name of the character
            use_cdn: Whether to use CDN URL (default: True)
            include_cache_headers: Whether to include cache control info
            include_version: Whether to include version information for cache busting
            
        Returns:
            Dictionary containing image URL and metadata
        """
        try:
            # First try to get the direct image URL
            image_url = await self.blob_service.get_image_url(universe, character_name)
            
            if image_url:
                # Get or generate version information
                version_info = await self._get_image_version(universe, character_name)
                
                # Use CDN URL if available and requested
                if use_cdn and self.cdn_base_url:
                    blob_path = self.blob_service._get_blob_path(universe, character_name)
                    image_url = f"{self.cdn_base_url}/{blob_path}"
                
                # Add version parameter for cache busting if requested
                if include_version and version_info["version"]:
                    separator = "&" if "?" in image_url else "?"
                    image_url = f"{image_url}{separator}v={version_info['version']}"
                
                response = {
                    "url": image_url,
                    "character_name": character_name,
                    "universe": universe,
                    "is_fallback": False,
                    "version": version_info["version"] if include_version else None,
                    "etag": version_info["etag"] if include_version else None,
                    "last_modified": version_info["last_modified"] if include_version else None,
                    "cache_control": "public, max-age=604800, immutable" if include_cache_headers else None  # 7 days
                }
                
                logger.info(f"Serving image for {character_name} in {universe}: {image_url}")
                return response
            
            else:
                # Image not found, return fallback
                return await self._get_fallback_image(universe, character_name, use_cdn, include_cache_headers)
                
        except Exception as e:
            logger.error(f"Error getting image URL for {character_name} in {universe}: {e}")
            return await self._get_fallback_image(universe, character_name, use_cdn, include_cache_headers)
    
    async def _get_fallback_image(
        self, 
        universe: str, 
        character_name: str,
        use_cdn: bool = True,
        include_cache_headers: bool = True
    ) -> Dict[str, Any]:
        """
        Get fallback image URL when character image is not available.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            character_name: Name of the character (for logging)
            use_cdn: Whether to use CDN URL
            include_cache_headers: Whether to include cache control info
            
        Returns:
            Dictionary containing fallback image URL and metadata
        """
        fallback_path = self.fallback_images.get(universe.lower())
        
        if not fallback_path:
            # Generic fallback if universe-specific fallback not available
            fallback_path = "fallback/generic-character.jpg"
        
        # Construct fallback URL
        if use_cdn and self.cdn_base_url:
            fallback_url = f"{self.cdn_base_url}/{fallback_path}"
        else:
            # Use direct blob storage URL as fallback
            fallback_url = f"https://placeholder.com/300x400/cccccc/666666?text={universe.upper()}+Character"
        
        logger.warning(f"Using fallback image for {character_name} in {universe}: {fallback_url}")
        
        return {
            "url": fallback_url,
            "character_name": character_name,
            "universe": universe,
            "is_fallback": True,
            "cache_control": "public, max-age=86400" if include_cache_headers else None  # 1 day for fallbacks
        }
    
    async def get_optimized_image_url(
        self,
        universe: str,
        character_name: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        quality: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get optimized image URL with specific dimensions and quality.
        This would integrate with image processing services in production.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            character_name: Name of the character
            width: Desired width in pixels
            height: Desired height in pixels
            quality: Image quality (1-100)
            
        Returns:
            Dictionary containing optimized image URL and metadata
        """
        # Get base image info
        image_info = await self.get_character_image_url(universe, character_name)
        
        if not image_info["is_fallback"] and (width or height or quality):
            # In production, this would use Azure Image Processing or similar service
            # For now, we'll append query parameters that could be processed by CDN
            base_url = image_info["url"]
            params = []
            
            if width:
                params.append(f"w={width}")
            if height:
                params.append(f"h={height}")
            if quality:
                params.append(f"q={quality}")
            
            if params:
                separator = "&" if "?" in base_url else "?"
                optimized_url = f"{base_url}{separator}{'&'.join(params)}"
                image_info["url"] = optimized_url
                image_info["optimized"] = True
                image_info["optimization_params"] = {
                    "width": width,
                    "height": height,
                    "quality": quality
                }
        
        return image_info
    
    async def _get_image_version(self, universe: str, character_name: str) -> Dict[str, Any]:
        """
        Get version information for an image to support cache invalidation.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            character_name: Name of the character
            
        Returns:
            Dictionary containing version information
        """
        try:
            # Get image metadata from blob storage
            metadata = await self.blob_service.get_image_metadata(universe, character_name)
            
            if metadata:
                # Use blob's last modified time and etag for versioning
                last_modified = metadata.get("last_modified")
                etag = metadata.get("etag", "").strip('"')
                
                # Generate a short version hash from etag and last modified
                version_string = f"{etag}:{last_modified}" if last_modified else etag
                version_hash = hashlib.md5(version_string.encode()).hexdigest()[:8]
                
                return {
                    "version": version_hash,
                    "etag": etag,
                    "last_modified": last_modified,
                    "source": "blob_metadata"
                }
            else:
                # Fallback version based on character name and universe
                fallback_string = f"{universe}:{character_name}:fallback"
                fallback_hash = hashlib.md5(fallback_string.encode()).hexdigest()[:8]
                
                return {
                    "version": fallback_hash,
                    "etag": fallback_hash,
                    "last_modified": None,
                    "source": "fallback"
                }
                
        except Exception as e:
            logger.warning(f"Error getting image version for {character_name} in {universe}: {e}")
            # Generate a basic version hash as fallback
            basic_string = f"{universe}:{character_name}"
            basic_hash = hashlib.md5(basic_string.encode()).hexdigest()[:8]
            
            return {
                "version": basic_hash,
                "etag": basic_hash,
                "last_modified": None,
                "source": "error_fallback"
            }
    
    async def invalidate_image_version(self, universe: str, character_name: str) -> bool:
        """
        Invalidate cached version information for an image.
        This should be called when an image is updated.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            character_name: Name of the character
            
        Returns:
            True if invalidation was successful
        """
        try:
            # Clear local version cache
            cache_key = f"{universe}:{character_name}"
            if cache_key in self._image_versions:
                del self._image_versions[cache_key]
            
            # Trigger CDN cache invalidation
            await cache_service.invalidate_image_cache(universe, character_name)
            
            logger.info(f"Invalidated image version for {character_name} in {universe}")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating image version for {character_name} in {universe}: {e}")
            return False
    
    async def bulk_invalidate_universe_images(self, universe: str) -> Dict[str, Any]:
        """
        Invalidate all image versions for a universe.
        Useful when doing bulk image updates.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            
        Returns:
            Dictionary containing invalidation results
        """
        try:
            # Clear local version cache for universe
            keys_to_remove = [key for key in self._image_versions.keys() if key.startswith(f"{universe}:")]
            for key in keys_to_remove:
                del self._image_versions[key]
            
            # Trigger CDN cache invalidation for entire universe
            result = await cache_service.invalidate_image_cache(universe)
            
            logger.info(f"Bulk invalidated {len(keys_to_remove)} image versions for {universe}")
            
            return {
                "success": result.success,
                "universe": universe,
                "invalidated_count": len(keys_to_remove),
                "cache_result": result.message
            }
            
        except Exception as e:
            logger.error(f"Error bulk invalidating images for {universe}: {e}")
            return {
                "success": False,
                "universe": universe,
                "invalidated_count": 0,
                "error": str(e)
            }
    
    def get_versioned_cache_headers(self, version: Optional[str] = None, etag: Optional[str] = None) -> Dict[str, str]:
        """
        Get cache headers with versioning information.
        
        Args:
            version: Image version for cache busting
            etag: ETag for conditional requests
            
        Returns:
            Dictionary of cache headers with versioning
        """
        headers = {
            "Cache-Control": "public, max-age=31536000, immutable",  # 1 year for versioned assets
            "Vary": "Accept-Encoding"
        }
        
        if etag:
            headers["ETag"] = f'"{etag}"'
        
        if version:
            headers["X-Image-Version"] = version
        
        return headers
    
    async def preload_universe_images(self, universe: str) -> Dict[str, Any]:
        """
        Get URLs for all images in a universe for preloading.
        Useful for CDN warming and client-side caching.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            
        Returns:
            Dictionary containing preload information
        """
        try:
            character_names = await self.blob_service.list_images_by_universe(universe)
            
            preload_urls = []
            for character_name in character_names:
                image_info = await self.get_character_image_url(universe, character_name)
                preload_urls.append({
                    "character": character_name,
                    "url": image_info["url"],
                    "is_fallback": image_info["is_fallback"]
                })
            
            return {
                "universe": universe,
                "total_images": len(preload_urls),
                "images": preload_urls,
                "cache_strategy": "preload"
            }
            
        except Exception as e:
            logger.error(f"Error preloading images for {universe}: {e}")
            return {
                "universe": universe,
                "total_images": 0,
                "images": [],
                "error": str(e)
            }
    
    def get_cache_headers(self, is_fallback: bool = False) -> Dict[str, str]:
        """
        Get appropriate cache headers for image responses.
        
        Args:
            is_fallback: Whether this is a fallback image
            
        Returns:
            Dictionary of cache headers
        """
        if is_fallback:
            return {
                "Cache-Control": "public, max-age=86400",  # 1 day for fallbacks
                "Expires": "86400",
                "X-Image-Type": "fallback"
            }
        else:
            return {
                "Cache-Control": "public, max-age=604800",  # 7 days for real images
                "Expires": "604800", 
                "X-Image-Type": "character"
            }
    
    async def validate_image_exists(self, universe: str, character_name: str) -> bool:
        """
        Validate that an image exists for a character.
        
        Args:
            universe: The comic universe (marvel, dc, image)
            character_name: Name of the character
            
        Returns:
            True if image exists, False otherwise
        """
        try:
            image_url = await self.blob_service.get_image_url(universe, character_name)
            return image_url is not None
        except Exception as e:
            logger.error(f"Error validating image for {character_name} in {universe}: {e}")
            return False

# Global instance
image_service = ImageService()