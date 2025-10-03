"""
Tests for cache service functionality
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import aiohttp

from app.services.cache_service import (
    CloudflareCacheService, 
    CacheHeaderService,
    CacheInvalidationRequest,
    CacheInvalidationResult
)


class TestCloudflareCacheService:
    """Test Cloudflare cache service functionality"""
    
    @pytest.fixture
    def cache_service(self):
        """Create cache service instance for testing"""
        with patch('app.services.cache_service.get_settings') as mock_settings:
            mock_settings.return_value.cloudflare_zone_id = "test-zone-id"
            mock_settings.return_value.cloudflare_api_token = "test-api-token"
            return CloudflareCacheService()
    
    @pytest.mark.asyncio
    async def test_invalidate_puzzle_cache_all_universes(self, cache_service):
        """Test puzzle cache invalidation for all universes"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await cache_service.invalidate_puzzle_cache()
            
            assert result.success is True
            assert "Cache invalidation successful" in result.message
            assert result.timestamp is not None
            
            # Verify API call was made
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "puzzle" in call_args[1]["json"]["files"][0]
    
    @pytest.mark.asyncio
    async def test_invalidate_puzzle_cache_specific_universe(self, cache_service):
        """Test puzzle cache invalidation for specific universe"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await cache_service.invalidate_puzzle_cache("marvel")
            
            assert result.success is True
            
            # Verify universe-specific paths were included
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert any("marvel" in path for path in payload["files"])
            assert "universe-marvel" in payload["tags"]
    
    @pytest.mark.asyncio
    async def test_invalidate_image_cache(self, cache_service):
        """Test image cache invalidation"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await cache_service.invalidate_image_cache("marvel", "Spider-Man")
            
            assert result.success is True
            
            # Verify image-specific paths were included
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert any("Spider-Man" in path for path in payload["files"])
            assert "character-spider-man" in payload["tags"]
    
    @pytest.mark.asyncio
    async def test_purge_all_cache(self, cache_service):
        """Test full cache purge"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await cache_service.purge_all_cache()
            
            assert result.success is True
            
            # Verify purge_everything was set
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["purge_everything"] is True
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_api_error(self, cache_service):
        """Test handling of Cloudflare API errors"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock API error response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.json.return_value = {
                "success": False,
                "errors": [{"message": "Invalid zone ID"}]
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await cache_service.invalidate_puzzle_cache()
            
            assert result.success is False
            assert "Cloudflare API error" in result.message
            assert "Invalid zone ID" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_network_error(self, cache_service):
        """Test handling of network errors"""
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock network error
            mock_post.side_effect = aiohttp.ClientError("Network error")
            
            result = await cache_service.invalidate_puzzle_cache()
            
            assert result.success is False
            assert "Cache invalidation failed" in result.message
    
    @pytest.mark.asyncio
    async def test_missing_cloudflare_config(self):
        """Test behavior when Cloudflare config is missing"""
        with patch('app.services.cache_service.get_settings') as mock_settings:
            mock_settings.return_value.cloudflare_zone_id = None
            mock_settings.return_value.cloudflare_api_token = None
            
            cache_service = CloudflareCacheService()
            
            # The error should occur when trying to make the API call
            result = await cache_service.invalidate_puzzle_cache()
            assert result.success is False
            assert "Cloudflare zone ID and API token must be configured" in result.message


class TestCacheHeaderService:
    """Test cache header service functionality"""
    
    def test_puzzle_cache_headers_public(self):
        """Test public puzzle cache headers"""
        headers = CacheHeaderService.get_puzzle_cache_headers(is_personalized=False)
        
        assert "public" in headers["Cache-Control"]
        assert "max-age=3600" in headers["Cache-Control"]
        assert "puzzle-metadata" in headers["X-Cache-Tags"]
    
    def test_puzzle_cache_headers_private(self):
        """Test private puzzle cache headers"""
        headers = CacheHeaderService.get_puzzle_cache_headers(is_personalized=True)
        
        assert "private" in headers["Cache-Control"]
        assert "max-age=300" in headers["Cache-Control"]
        assert "Authorization" in headers["Vary"]
    
    def test_image_cache_headers(self):
        """Test image cache headers"""
        headers = CacheHeaderService.get_image_cache_headers()
        
        assert "public" in headers["Cache-Control"]
        assert "max-age=604800" in headers["Cache-Control"]  # 7 days
        assert "immutable" in headers["Cache-Control"]
        assert "character-images" in headers["X-Cache-Tags"]
    
    def test_image_cache_headers_with_version(self):
        """Test image cache headers with version"""
        headers = CacheHeaderService.get_image_cache_headers(version="v1.2.3")
        
        assert headers["ETag"] == '"v1.2.3"'
    
    def test_no_cache_headers(self):
        """Test no-cache headers"""
        headers = CacheHeaderService.get_no_cache_headers()
        
        assert "no-cache" in headers["Cache-Control"]
        assert "no-store" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]
        assert headers["Pragma"] == "no-cache"
        assert headers["Expires"] == "0"


class TestCacheInvalidationModels:
    """Test cache invalidation data models"""
    
    def test_cache_invalidation_request_model(self):
        """Test CacheInvalidationRequest model"""
        request = CacheInvalidationRequest(
            files=["/api/puzzle/today"],
            tags=["puzzle-metadata"],
            purge_everything=False
        )
        
        assert request.files == ["/api/puzzle/today"]
        assert request.tags == ["puzzle-metadata"]
        assert request.purge_everything is False
    
    def test_cache_invalidation_result_model(self):
        """Test CacheInvalidationResult model"""
        timestamp = datetime.now(timezone.utc)
        result = CacheInvalidationResult(
            success=True,
            message="Cache cleared successfully",
            purged_files=["/api/puzzle/today"],
            timestamp=timestamp
        )
        
        assert result.success is True
        assert result.message == "Cache cleared successfully"
        assert result.purged_files == ["/api/puzzle/today"]
        assert result.timestamp == timestamp


@pytest.mark.asyncio
async def test_cache_invalidation_timing():
    """Test cache invalidation timing and correctness"""
    with patch('app.services.cache_service.get_settings') as mock_settings:
        mock_settings.return_value.cloudflare_zone_id = "test-zone"
        mock_settings.return_value.cloudflare_api_token = "test-token"
        
        cache_service = CloudflareCacheService()
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Test timing of cache invalidation
            start_time = datetime.now(timezone.utc)
            result = await cache_service.invalidate_puzzle_cache()
            end_time = datetime.now(timezone.utc)
            
            assert result.success is True
            assert start_time <= result.timestamp <= end_time
            
            # Verify the API was called with correct timing
            mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_cache_invalidation_rollover_scenario():
    """Test cache invalidation at puzzle rollover scenario"""
    with patch('app.services.cache_service.get_settings') as mock_settings:
        mock_settings.return_value.cloudflare_zone_id = "test-zone"
        mock_settings.return_value.cloudflare_api_token = "test-token"
        
        cache_service = CloudflareCacheService()
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"success": True}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Simulate midnight rollover cache invalidation
            result = await cache_service.invalidate_puzzle_cache()
            
            assert result.success is True
            
            # Verify all puzzle-related paths are included
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            
            expected_paths = [
                "/api/puzzle/today",
                "/api/daily-progress",
                "/api/streak-status"
            ]
            
            for expected_path in expected_paths:
                assert any(expected_path in path for path in payload["files"])
            
            # Verify cache tags include date-specific tag
            today_tag = f"puzzle-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            assert today_tag in payload["tags"]