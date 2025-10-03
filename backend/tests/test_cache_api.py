"""
Tests for cache API endpoints
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.services.cache_service import CacheInvalidationResult


@pytest.fixture
def mock_cache_service():
    """Mock cache service for testing"""
    with patch('app.api.cache.cache_service') as mock:
        yield mock


@pytest.fixture
def mock_current_user():
    """Mock current user for authentication"""
    return {"user_id": "test-user-123", "username": "testuser"}


class TestCacheInvalidationEndpoints:
    """Test cache invalidation API endpoints"""
    
    def test_invalidate_puzzle_cache_all_universes(self, client, mock_cache_service, mock_current_user):
        """Test puzzle cache invalidation for all universes"""
        # Mock successful cache invalidation
        mock_result = CacheInvalidationResult(
            success=True,
            message="Cache invalidation successful",
            purged_files=["/api/puzzle/today"],
            timestamp=datetime.now(timezone.utc)
        )
        mock_cache_service.invalidate_puzzle_cache.return_value = mock_result
        
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post(
                "/api/cache/invalidate/puzzles",
                json={"universe": None, "purge_all": False}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Cache invalidation successful"
        
        # Verify cache service was called correctly
        mock_cache_service.invalidate_puzzle_cache.assert_called_once_with(None)
    
    def test_invalidate_puzzle_cache_specific_universe(self, client, mock_cache_service, mock_current_user):
        """Test puzzle cache invalidation for specific universe"""
        mock_result = CacheInvalidationResult(
            success=True,
            message="Cache invalidation successful",
            timestamp=datetime.now(timezone.utc)
        )
        mock_cache_service.invalidate_puzzle_cache.return_value = mock_result
        
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post(
                "/api/cache/invalidate/puzzles",
                json={"universe": "marvel", "purge_all": False}
            )
        
        assert response.status_code == 200
        
        # Verify cache service was called with correct universe
        mock_cache_service.invalidate_puzzle_cache.assert_called_once_with("marvel")
    
    def test_invalidate_puzzle_cache_purge_all(self, client, mock_cache_service, mock_current_user):
        """Test full cache purge"""
        mock_result = CacheInvalidationResult(
            success=True,
            message="Full cache purge successful",
            timestamp=datetime.now(timezone.utc)
        )
        mock_cache_service.purge_all_cache.return_value = mock_result
        
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post(
                "/api/cache/invalidate/puzzles",
                json={"purge_all": True}
            )
        
        assert response.status_code == 200
        
        # Verify purge_all_cache was called instead of invalidate_puzzle_cache
        mock_cache_service.purge_all_cache.assert_called_once()
        mock_cache_service.invalidate_puzzle_cache.assert_not_called()
    
    def test_invalidate_image_cache(self, client, mock_cache_service, mock_current_user):
        """Test image cache invalidation"""
        mock_result = CacheInvalidationResult(
            success=True,
            message="Image cache invalidation successful",
            timestamp=datetime.now(timezone.utc)
        )
        mock_cache_service.invalidate_image_cache.return_value = mock_result
        
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post(
                "/api/cache/invalidate/images",
                json={"universe": "marvel", "character_name": "Spider-Man"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify cache service was called correctly
        mock_cache_service.invalidate_image_cache.assert_called_once_with("marvel", "Spider-Man")
    
    def test_invalidate_image_cache_missing_universe(self, client, mock_current_user):
        """Test image cache invalidation without universe parameter"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post(
                "/api/cache/invalidate/images",
                json={"character_name": "Spider-Man"}
            )
        
        assert response.status_code == 400
        assert "Universe parameter is required" in response.json()["detail"]
    
    def test_invalidate_cache_invalid_universe(self, client, mock_current_user):
        """Test cache invalidation with invalid universe"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post(
                "/api/cache/invalidate/puzzles",
                json={"universe": "invalid-universe"}
            )
        
        assert response.status_code == 400
        assert "Invalid universe" in response.json()["detail"]
    
    def test_cache_invalidation_service_error(self, client, mock_cache_service, mock_current_user):
        """Test handling of cache service errors"""
        # Mock cache service error
        mock_cache_service.invalidate_puzzle_cache.side_effect = Exception("Cache service error")
        
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post(
                "/api/cache/invalidate/puzzles",
                json={"universe": "marvel"}
            )
        
        assert response.status_code == 500
        assert "Cache invalidation failed" in response.json()["detail"]


class TestCacheStatusEndpoints:
    """Test cache status and management endpoints"""
    
    def test_get_cache_status(self, client, mock_current_user):
        """Test cache status endpoint"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            with patch('app.api.cache.get_settings') as mock_settings:
                # Mock settings with Cloudflare configured
                mock_settings.return_value.cloudflare_zone_id = "test-zone"
                mock_settings.return_value.cloudflare_api_token = "test-token"
                
                response = client.get("/api/cache/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["cache_enabled"] is True
        assert data["cloudflare_configured"] is True
        assert "cache_policies" in data
        assert "puzzle_metadata" in data["cache_policies"]
    
    def test_get_cache_status_not_configured(self, client, mock_current_user):
        """Test cache status when Cloudflare is not configured"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            with patch('app.api.cache.get_settings') as mock_settings:
                # Mock settings without Cloudflare
                mock_settings.return_value.cloudflare_zone_id = None
                mock_settings.return_value.cloudflare_api_token = None
                
                response = client.get("/api/cache/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["cache_enabled"] is False
        assert data["cloudflare_configured"] is False
    
    def test_warm_cache(self, client, mock_current_user):
        """Test cache warming endpoint"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post("/api/cache/warm?universe=marvel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "marvel" in data["universes"]
    
    def test_warm_cache_all_universes(self, client, mock_current_user):
        """Test cache warming for all universes"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post("/api/cache/warm")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["universes"]) == 3  # marvel, dc, image
    
    def test_warm_cache_invalid_universe(self, client, mock_current_user):
        """Test cache warming with invalid universe"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.post("/api/cache/warm?universe=invalid")
        
        assert response.status_code == 400
        assert "Invalid universe" in response.json()["detail"]


class TestEmergencyCachePurge:
    """Test emergency cache purge endpoint"""
    
    def test_emergency_purge_all_with_confirmation(self, client, mock_cache_service, mock_current_user):
        """Test emergency cache purge with confirmation"""
        mock_result = CacheInvalidationResult(
            success=True,
            message="Emergency cache purge successful",
            timestamp=datetime.now(timezone.utc)
        )
        mock_cache_service.purge_all_cache.return_value = mock_result
        
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.delete("/api/cache/purge-all?confirm=true")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify purge_all_cache was called
        mock_cache_service.purge_all_cache.assert_called_once()
    
    def test_emergency_purge_all_without_confirmation(self, client, mock_current_user):
        """Test emergency cache purge without confirmation"""
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.delete("/api/cache/purge-all?confirm=false")
        
        assert response.status_code == 400
        assert "Confirmation required" in response.json()["detail"]
    
    def test_emergency_purge_all_service_error(self, client, mock_cache_service, mock_current_user):
        """Test emergency cache purge with service error"""
        # Mock cache service error
        mock_cache_service.purge_all_cache.side_effect = Exception("Purge failed")
        
        with patch('app.api.cache.get_current_user', return_value=mock_current_user):
            response = client.delete("/api/cache/purge-all?confirm=true")
        
        assert response.status_code == 500
        assert "Emergency cache purge failed" in response.json()["detail"]


class TestCacheHealthCheck:
    """Test cache service health check"""
    
    def test_cache_health_check_healthy(self, client):
        """Test cache health check when service is healthy"""
        with patch('app.api.cache.get_settings') as mock_settings:
            mock_settings.return_value.cloudflare_zone_id = "test-zone"
            mock_settings.return_value.cloudflare_api_token = "test-token"
            
            response = client.get("/api/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "cache-api"
        assert data["cloudflare_configured"] is True
    
    def test_cache_health_check_not_configured(self, client):
        """Test cache health check when Cloudflare is not configured"""
        with patch('app.api.cache.get_settings') as mock_settings:
            mock_settings.return_value.cloudflare_zone_id = None
            mock_settings.return_value.cloudflare_api_token = None
            
            response = client.get("/api/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["cloudflare_configured"] is False
    
    def test_cache_health_check_error(self, client):
        """Test cache health check with service error"""
        with patch('app.api.cache.get_settings', side_effect=Exception("Settings error")):
            response = client.get("/api/cache/health")
        
        assert response.status_code == 503
        assert "Cache service unhealthy" in response.json()["detail"]


class TestCacheAuthenticationRequired:
    """Test that cache endpoints require authentication"""
    
    def test_cache_endpoints_require_auth(self, client):
        """Test that cache endpoints return 401 without authentication"""
        # Test puzzle cache invalidation
        response = client.post(
            "/api/cache/invalidate/puzzles",
            json={"universe": "marvel"}
        )
        assert response.status_code == 401
        
        # Test image cache invalidation
        response = client.post(
            "/api/cache/invalidate/images",
            json={"universe": "marvel"}
        )
        assert response.status_code == 401
        
        # Test cache status
        response = client.get("/api/cache/status")
        assert response.status_code == 401
        
        # Test emergency purge
        response = client.delete("/api/cache/purge-all?confirm=true")
        assert response.status_code == 401