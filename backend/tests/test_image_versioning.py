"""
Tests for image versioning and asset management
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.services.image_service import ImageService


class TestImageVersioning:
    """Test image versioning functionality"""
    
    @pytest.fixture
    def image_service(self):
        """Create image service instance for testing"""
        return ImageService()
    
    @pytest.fixture
    def mock_blob_metadata(self):
        """Mock blob metadata for testing"""
        return {
            "etag": "0x8D9A1B2C3D4E5F6",
            "last_modified": "2024-01-15T10:30:00Z",
            "content_length": 1024000,
            "content_type": "image/jpeg",
            "metadata": {"universe": "marvel", "character_name": "Spider-Man"},
            "blob_path": "marvel/spider-man.jpg",
            "url": "https://storage.blob.core.windows.net/images/marvel/spider-man.jpg"
        }
    
    @pytest.mark.asyncio
    async def test_get_image_version_with_metadata(self, image_service, mock_blob_metadata):
        """Test getting image version information from blob metadata"""
        with patch.object(image_service.blob_service, 'get_image_metadata', return_value=mock_blob_metadata):
            version_info = await image_service._get_image_version("marvel", "Spider-Man")
            
            assert version_info["version"] is not None
            assert len(version_info["version"]) == 8  # MD5 hash truncated to 8 chars
            assert version_info["etag"] == "0x8D9A1B2C3D4E5F6"
            assert version_info["last_modified"] == "2024-01-15T10:30:00Z"
            assert version_info["source"] == "blob_metadata"
    
    @pytest.mark.asyncio
    async def test_get_image_version_fallback(self, image_service):
        """Test getting image version when metadata is not available"""
        with patch.object(image_service.blob_service, 'get_image_metadata', return_value=None):
            version_info = await image_service._get_image_version("marvel", "Spider-Man")
            
            assert version_info["version"] is not None
            assert len(version_info["version"]) == 8
            assert version_info["source"] == "fallback"
            assert version_info["last_modified"] is None
    
    @pytest.mark.asyncio
    async def test_get_image_version_error_handling(self, image_service):
        """Test error handling in image version retrieval"""
        with patch.object(image_service.blob_service, 'get_image_metadata', side_effect=Exception("Blob error")):
            version_info = await image_service._get_image_version("marvel", "Spider-Man")
            
            assert version_info["version"] is not None
            assert version_info["source"] == "error_fallback"
    
    @pytest.mark.asyncio
    async def test_get_character_image_url_with_versioning(self, image_service, mock_blob_metadata):
        """Test getting character image URL with version information"""
        with patch.object(image_service.blob_service, 'get_image_url', return_value="https://example.com/image.jpg"):
            with patch.object(image_service.blob_service, 'get_image_metadata', return_value=mock_blob_metadata):
                image_info = await image_service.get_character_image_url(
                    "marvel", "Spider-Man", include_version=True
                )
                
                assert image_info["version"] is not None
                assert image_info["etag"] is not None
                assert image_info["last_modified"] is not None
                assert "v=" in image_info["url"]  # Version parameter added to URL
                assert image_info["is_fallback"] is False
    
    @pytest.mark.asyncio
    async def test_get_character_image_url_without_versioning(self, image_service):
        """Test getting character image URL without version information"""
        with patch.object(image_service.blob_service, 'get_image_url', return_value="https://example.com/image.jpg"):
            image_info = await image_service.get_character_image_url(
                "marvel", "Spider-Man", include_version=False
            )
            
            assert image_info["version"] is None
            assert image_info["etag"] is None
            assert "v=" not in image_info["url"]  # No version parameter
    
    @pytest.mark.asyncio
    async def test_invalidate_image_version(self, image_service):
        """Test invalidating image version cache"""
        with patch('app.services.image_service.cache_service') as mock_cache_service:
            # Create a proper async mock
            async def mock_invalidate(*args, **kwargs):
                return MagicMock(success=True)
            
            mock_cache_service.invalidate_image_cache = mock_invalidate
            
            # Add some cached version data
            image_service._image_versions["marvel:Spider-Man"] = {"version": "abc12345"}
            
            result = await image_service.invalidate_image_version("marvel", "Spider-Man")
            
            assert result is True
            assert "marvel:Spider-Man" not in image_service._image_versions
    
    @pytest.mark.asyncio
    async def test_bulk_invalidate_universe_images(self, image_service):
        """Test bulk invalidation of universe image versions"""
        with patch('app.services.image_service.cache_service') as mock_cache_service:
            # Create a proper async mock
            async def mock_invalidate(*args, **kwargs):
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.message = "Cache invalidated successfully"
                return mock_result
            
            mock_cache_service.invalidate_image_cache = mock_invalidate
            
            # Add some cached version data
            image_service._image_versions["marvel:Spider-Man"] = {"version": "abc12345"}
            image_service._image_versions["marvel:Iron-Man"] = {"version": "def67890"}
            image_service._image_versions["dc:Batman"] = {"version": "ghi11111"}
            
            result = await image_service.bulk_invalidate_universe_images("marvel")
            
            assert result["success"] is True
            assert result["universe"] == "marvel"
            assert result["invalidated_count"] == 2
            
            # Marvel entries should be removed, DC entry should remain
            assert "marvel:Spider-Man" not in image_service._image_versions
            assert "marvel:Iron-Man" not in image_service._image_versions
            assert "dc:Batman" in image_service._image_versions
    
    def test_get_versioned_cache_headers(self, image_service):
        """Test getting versioned cache headers"""
        headers = image_service.get_versioned_cache_headers(
            version="abc12345",
            etag="0x8D9A1B2C3D4E5F6"
        )
        
        assert "public" in headers["Cache-Control"]
        assert "max-age=31536000" in headers["Cache-Control"]  # 1 year
        assert "immutable" in headers["Cache-Control"]
        assert headers["ETag"] == '"0x8D9A1B2C3D4E5F6"'
        assert headers["X-Image-Version"] == "abc12345"
    
    def test_get_versioned_cache_headers_minimal(self, image_service):
        """Test getting versioned cache headers with minimal information"""
        headers = image_service.get_versioned_cache_headers()
        
        assert "Cache-Control" in headers
        assert "Vary" in headers
        assert "ETag" not in headers
        assert "X-Image-Version" not in headers


class TestImageVersionAPI:
    """Test image version API endpoints"""
    
    @pytest.fixture
    def mock_current_user(self):
        """Mock current user for authentication"""
        return {"user_id": "test-user-123", "username": "testuser"}
    
    def test_get_image_version_endpoint(self, client, mock_current_user):
        """Test getting image version information via API"""
        mock_image_info = {
            "url": "https://example.com/image.jpg?v=abc12345",
            "version": "abc12345",
            "etag": "0x8D9A1B2C3D4E5F6",
            "last_modified": "2024-01-15T10:30:00Z",
            "is_fallback": False
        }
        
        with patch('app.api.image_versions.get_current_user', return_value=mock_current_user):
            with patch('app.api.image_versions.image_service.get_character_image_url', return_value=mock_image_info):
                with patch('app.api.image_versions.image_service.get_versioned_cache_headers', return_value={"Cache-Control": "public, max-age=31536000"}):
                    response = client.get("/api/images/version/marvel/Spider-Man")
        
        assert response.status_code == 200
        data = response.json()
        assert data["universe"] == "marvel"
        assert data["character_name"] == "Spider-Man"
        assert data["version"] == "abc12345"
        assert data["etag"] == "0x8D9A1B2C3D4E5F6"
    
    def test_get_image_version_not_found(self, client, mock_current_user):
        """Test getting version for non-existent image"""
        with patch('app.api.image_versions.get_current_user', return_value=mock_current_user):
            with patch('app.api.image_versions.image_service.get_character_image_url', return_value=None):
                response = client.get("/api/images/version/marvel/NonExistent")
        
        assert response.status_code == 404
        assert "Image not found" in response.json()["detail"]
    
    def test_invalidate_image_version_specific(self, client, mock_current_user):
        """Test invalidating specific image version"""
        with patch('app.api.image_versions.get_current_user', return_value=mock_current_user):
            with patch('app.api.image_versions.image_service.invalidate_image_version', return_value=True):
                response = client.post(
                    "/api/images/invalidate-version",
                    json={"universe": "marvel", "character_name": "Spider-Man"}
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["universe"] == "marvel"
        assert data["character_name"] == "Spider-Man"
    
    def test_invalidate_image_version_bulk(self, client, mock_current_user):
        """Test bulk invalidation of universe images"""
        mock_result = {
            "success": True,
            "invalidated_count": 5,
            "cache_result": "Cache invalidated successfully"
        }
        
        with patch('app.api.image_versions.get_current_user', return_value=mock_current_user):
            with patch('app.api.image_versions.image_service.bulk_invalidate_universe_images', return_value=mock_result):
                response = client.post(
                    "/api/images/invalidate-version",
                    json={"universe": "marvel"}
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["universe"] == "marvel"
        assert data["invalidated_count"] == 5
    
    def test_get_universe_image_versions(self, client, mock_current_user):
        """Test getting version information for all images in universe"""
        mock_character_names = ["Spider-Man", "Iron-Man", "Captain-America"]
        mock_image_info = {
            "url": "https://example.com/image.jpg",
            "version": "abc12345",
            "etag": "0x8D9A1B2C3D4E5F6",
            "last_modified": "2024-01-15T10:30:00Z",
            "is_fallback": False
        }
        
        with patch('app.api.image_versions.get_current_user', return_value=mock_current_user):
            with patch('app.api.image_versions.image_service.blob_service.list_images_by_universe', return_value=mock_character_names):
                with patch('app.api.image_versions.image_service.get_character_image_url', return_value=mock_image_info):
                    response = client.get("/api/images/versions/marvel?limit=10&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["universe"] == "marvel"
        assert data["processed_count"] == 3
        assert len(data["results"]) == 3
    
    def test_validate_image_cache_valid(self, client, mock_current_user):
        """Test cache validation with matching ETag"""
        mock_image_info = {
            "url": "https://example.com/image.jpg",
            "etag": "0x8D9A1B2C3D4E5F6",
            "last_modified": "2024-01-15T10:30:00Z"
        }
        
        with patch('app.api.image_versions.get_current_user', return_value=mock_current_user):
            with patch('app.api.image_versions.image_service.get_character_image_url', return_value=mock_image_info):
                response = client.get(
                    "/api/images/cache-validation/marvel/Spider-Man?if_none_match=0x8D9A1B2C3D4E5F6"
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cache_valid"] is True
        assert data["current_etag"] == "0x8D9A1B2C3D4E5F6"
        assert data["recommendation"] == "use_cache"
    
    def test_validate_image_cache_invalid(self, client, mock_current_user):
        """Test cache validation with non-matching ETag"""
        mock_image_info = {
            "url": "https://example.com/image.jpg",
            "etag": "0x8D9A1B2C3D4E5F6",
            "last_modified": "2024-01-15T10:30:00Z"
        }
        
        with patch('app.api.image_versions.get_current_user', return_value=mock_current_user):
            with patch('app.api.image_versions.image_service.get_character_image_url', return_value=mock_image_info):
                response = client.get(
                    "/api/images/cache-validation/marvel/Spider-Man?if_none_match=old-etag-value"
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cache_valid"] is False
        assert data["current_etag"] == "0x8D9A1B2C3D4E5F6"
        assert data["recommendation"] == "fetch_new"
    
    def test_image_version_health_check(self, client):
        """Test image versioning health check endpoint"""
        response = client.get("/api/images/version-health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "image-versioning"
        assert "etag_support" in data["features"]
        assert "version_tracking" in data["features"]


class TestAssetVersioningIntegration:
    """Test integration of asset versioning with cache invalidation"""
    
    @pytest.mark.asyncio
    async def test_image_update_triggers_cache_invalidation(self):
        """Test that image updates trigger proper cache invalidation"""
        image_service = ImageService()
        
        with patch('app.services.image_service.cache_service') as mock_cache_service:
            # Create a proper async mock
            async def mock_invalidate(*args, **kwargs):
                return MagicMock(success=True)
            
            mock_cache_service.invalidate_image_cache = mock_invalidate
            
            # Simulate image update
            result = await image_service.invalidate_image_version("marvel", "Spider-Man")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_version_consistency_across_requests(self):
        """Test that version information is consistent across multiple requests"""
        image_service = ImageService()
        
        mock_metadata = {
            "etag": "0x8D9A1B2C3D4E5F6",
            "last_modified": "2024-01-15T10:30:00Z"
        }
        
        with patch.object(image_service.blob_service, 'get_image_metadata', return_value=mock_metadata):
            # Get version information twice
            version1 = await image_service._get_image_version("marvel", "Spider-Man")
            version2 = await image_service._get_image_version("marvel", "Spider-Man")
            
            # Versions should be identical for same metadata
            assert version1["version"] == version2["version"]
            assert version1["etag"] == version2["etag"]
    
    def test_cache_header_immutability_with_versioning(self):
        """Test that versioned assets get immutable cache headers"""
        image_service = ImageService()
        
        headers = image_service.get_versioned_cache_headers(
            version="abc12345",
            etag="0x8D9A1B2C3D4E5F6"
        )
        
        # Versioned assets should have long cache times and be immutable
        assert "immutable" in headers["Cache-Control"]
        assert "max-age=31536000" in headers["Cache-Control"]  # 1 year
        assert headers["ETag"] == '"0x8D9A1B2C3D4E5F6"'