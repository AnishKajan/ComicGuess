"""
Tests for Image Service with CDN integration and fallback handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.image_service import ImageService
from app.storage.exceptions import StorageError

class TestImageService:
    """Test cases for ImageService."""
    
    @pytest.fixture
    def mock_image_service(self):
        """Create a mock image service for testing."""
        with patch('app.services.image_service.blob_storage_service') as mock_blob_service:
            with patch('app.services.image_service.settings') as mock_settings:
                mock_settings.azure_storage_connection_string = "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=testkey;EndpointSuffix=core.windows.net"
                mock_settings.azure_storage_container_name = "character-images"
                
                service = ImageService()
                service.blob_service = mock_blob_service
                return service, mock_blob_service
    
    @pytest.mark.asyncio
    async def test_get_character_image_url_success(self, mock_image_service):
        """Test getting character image URL when image exists."""
        service, mock_blob_service = mock_image_service
        
        # Mock successful image retrieval
        mock_blob_service.get_image_url = AsyncMock(return_value="https://testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg")
        mock_blob_service._get_blob_path.return_value = "marvel/spider-man.jpg"
        
        result = await service.get_character_image_url("marvel", "Spider-Man")
        
        assert result["url"] == "https://testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg"
        assert result["character_name"] == "Spider-Man"
        assert result["universe"] == "marvel"
        assert result["is_fallback"] is False
        assert result["cache_control"] == "public, max-age=604800"
    
    @pytest.mark.asyncio
    async def test_get_character_image_url_with_cdn(self, mock_image_service):
        """Test getting character image URL with CDN optimization."""
        service, mock_blob_service = mock_image_service
        
        # Mock successful image retrieval
        mock_blob_service.get_image_url = AsyncMock(return_value="https://testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg")
        mock_blob_service._get_blob_path.return_value = "marvel/spider-man.jpg"
        
        result = await service.get_character_image_url("marvel", "Spider-Man", use_cdn=True)
        
        # Should use CDN URL
        assert "testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg" in result["url"]
        assert result["is_fallback"] is False
    
    @pytest.mark.asyncio
    async def test_get_character_image_url_fallback(self, mock_image_service):
        """Test fallback when character image doesn't exist."""
        service, mock_blob_service = mock_image_service
        
        # Mock image not found
        mock_blob_service.get_image_url = AsyncMock(return_value=None)
        
        result = await service.get_character_image_url("marvel", "Unknown Character")
        
        assert result["character_name"] == "Unknown Character"
        assert result["universe"] == "marvel"
        assert result["is_fallback"] is True
        assert "placeholder.com" in result["url"] or "fallback" in result["url"]
        assert result["cache_control"] == "public, max-age=86400"
    
    @pytest.mark.asyncio
    async def test_get_character_image_url_error_handling(self, mock_image_service):
        """Test error handling when blob service fails."""
        service, mock_blob_service = mock_image_service
        
        # Mock blob service error
        mock_blob_service.get_image_url = AsyncMock(side_effect=Exception("Storage error"))
        
        result = await service.get_character_image_url("marvel", "Spider-Man")
        
        assert result["is_fallback"] is True
        assert result["character_name"] == "Spider-Man"
        assert result["universe"] == "marvel"
    
    @pytest.mark.asyncio
    async def test_get_fallback_image_marvel(self, mock_image_service):
        """Test Marvel-specific fallback image."""
        service, mock_blob_service = mock_image_service
        
        result = await service._get_fallback_image("marvel", "Test Character")
        
        assert result["is_fallback"] is True
        assert result["universe"] == "marvel"
        assert result["character_name"] == "Test Character"
        assert result["cache_control"] == "public, max-age=86400"
    
    @pytest.mark.asyncio
    async def test_get_fallback_image_dc(self, mock_image_service):
        """Test DC-specific fallback image."""
        service, mock_blob_service = mock_image_service
        
        result = await service._get_fallback_image("dc", "Test Character")
        
        assert result["is_fallback"] is True
        assert result["universe"] == "dc"
        assert "DC" in result["url"] or "dc" in result["url"]
    
    @pytest.mark.asyncio
    async def test_get_fallback_image_image_comics(self, mock_image_service):
        """Test Image Comics-specific fallback image."""
        service, mock_blob_service = mock_image_service
        
        result = await service._get_fallback_image("image", "Test Character")
        
        assert result["is_fallback"] is True
        assert result["universe"] == "image"
        assert "IMAGE" in result["url"] or "image" in result["url"]
    
    @pytest.mark.asyncio
    async def test_get_optimized_image_url_with_params(self, mock_image_service):
        """Test getting optimized image URL with dimensions and quality."""
        service, mock_blob_service = mock_image_service
        
        # Mock successful image retrieval
        mock_blob_service.get_image_url = AsyncMock(return_value="https://testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg")
        mock_blob_service._get_blob_path.return_value = "marvel/spider-man.jpg"
        
        result = await service.get_optimized_image_url(
            "marvel", "Spider-Man", width=300, height=400, quality=85
        )
        
        assert result["is_fallback"] is False
        assert "w=300" in result["url"]
        assert "h=400" in result["url"]
        assert "q=85" in result["url"]
        assert result["optimized"] is True
        assert result["optimization_params"]["width"] == 300
        assert result["optimization_params"]["height"] == 400
        assert result["optimization_params"]["quality"] == 85
    
    @pytest.mark.asyncio
    async def test_get_optimized_image_url_fallback_no_optimization(self, mock_image_service):
        """Test that fallback images are not optimized."""
        service, mock_blob_service = mock_image_service
        
        # Mock image not found (will use fallback)
        mock_blob_service.get_image_url = AsyncMock(return_value=None)
        
        result = await service.get_optimized_image_url(
            "marvel", "Unknown Character", width=300, height=400
        )
        
        assert result["is_fallback"] is True
        # Fallback URLs should not have optimization parameters
        assert "w=300" not in result["url"]
        assert "h=400" not in result["url"]
        assert "optimized" not in result
    
    @pytest.mark.asyncio
    async def test_preload_universe_images_success(self, mock_image_service):
        """Test preloading images for a universe."""
        service, mock_blob_service = mock_image_service
        
        # Mock character list
        mock_blob_service.list_images_by_universe = AsyncMock(return_value=["Spider-Man", "Iron Man", "Captain America"])
        
        # Mock image URLs
        async def mock_get_image_url(universe, character):
            return f"https://testaccount.blob.core.windows.net/character-images/{universe}/{character.lower().replace(' ', '-')}.jpg"
        
        mock_blob_service.get_image_url = mock_get_image_url
        mock_blob_service._get_blob_path.side_effect = lambda u, c: f"{u}/{c.lower().replace(' ', '-')}.jpg"
        
        result = await service.preload_universe_images("marvel")
        
        assert result["universe"] == "marvel"
        assert result["total_images"] == 3
        assert len(result["images"]) == 3
        assert result["cache_strategy"] == "preload"
        
        # Check individual image entries
        character_names = [img["character"] for img in result["images"]]
        assert "Spider-Man" in character_names
        assert "Iron Man" in character_names
        assert "Captain America" in character_names
    
    @pytest.mark.asyncio
    async def test_preload_universe_images_error(self, mock_image_service):
        """Test preloading images when blob service fails."""
        service, mock_blob_service = mock_image_service
        
        # Mock blob service error
        mock_blob_service.list_images_by_universe = AsyncMock(side_effect=Exception("Storage error"))
        
        result = await service.preload_universe_images("marvel")
        
        assert result["universe"] == "marvel"
        assert result["total_images"] == 0
        assert result["images"] == []
        assert "error" in result
    
    def test_get_cache_headers_normal_image(self, mock_image_service):
        """Test cache headers for normal images."""
        service, _ = mock_image_service
        
        headers = service.get_cache_headers(is_fallback=False)
        
        assert headers["Cache-Control"] == "public, max-age=604800"  # 7 days
        assert headers["Expires"] == "604800"
        assert headers["X-Image-Type"] == "character"
    
    def test_get_cache_headers_fallback_image(self, mock_image_service):
        """Test cache headers for fallback images."""
        service, _ = mock_image_service
        
        headers = service.get_cache_headers(is_fallback=True)
        
        assert headers["Cache-Control"] == "public, max-age=86400"  # 1 day
        assert headers["Expires"] == "86400"
        assert headers["X-Image-Type"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_validate_image_exists_true(self, mock_image_service):
        """Test image validation when image exists."""
        service, mock_blob_service = mock_image_service
        
        mock_blob_service.get_image_url = AsyncMock(return_value="https://testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg")
        
        result = await service.validate_image_exists("marvel", "Spider-Man")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_image_exists_false(self, mock_image_service):
        """Test image validation when image doesn't exist."""
        service, mock_blob_service = mock_image_service
        
        mock_blob_service.get_image_url = AsyncMock(return_value=None)
        
        result = await service.validate_image_exists("marvel", "Unknown Character")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_image_exists_error(self, mock_image_service):
        """Test image validation when blob service fails."""
        service, mock_blob_service = mock_image_service
        
        mock_blob_service.get_image_url = AsyncMock(side_effect=Exception("Storage error"))
        
        result = await service.validate_image_exists("marvel", "Spider-Man")
        
        assert result is False
    
    def test_get_cdn_base_url_parsing(self, mock_image_service):
        """Test CDN base URL parsing from connection string."""
        service, _ = mock_image_service
        
        # The CDN base URL should be constructed from the connection string
        assert service.cdn_base_url is not None
        assert "testaccount.blob.core.windows.net" in service.cdn_base_url
        assert "character-images" in service.cdn_base_url
    
    def test_get_cdn_base_url_invalid_connection_string(self):
        """Test CDN base URL parsing with invalid connection string."""
        with patch('app.services.image_service.settings') as mock_settings:
            mock_settings.azure_storage_connection_string = "invalid_connection_string"
            mock_settings.azure_storage_container_name = "character-images"
            
            service = ImageService()
            
            # Should handle invalid connection string gracefully
            assert service.cdn_base_url is None
    
    def test_get_cdn_base_url_empty_connection_string(self):
        """Test CDN base URL parsing with empty connection string."""
        with patch('app.services.image_service.settings') as mock_settings:
            mock_settings.azure_storage_connection_string = ""
            mock_settings.azure_storage_container_name = "character-images"
            
            service = ImageService()
            
            # Should handle empty connection string gracefully
            assert service.cdn_base_url is None