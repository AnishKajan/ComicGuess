"""
Tests for Image API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.api.images import router
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)

class TestImageAPI:
    """Test cases for Image API endpoints."""
    
    @pytest.fixture
    def mock_image_service(self):
        """Mock the image service for testing."""
        with patch('app.api.images.image_service') as mock_service:
            yield mock_service
    
    def test_get_character_image_success(self, mock_image_service):
        """Test successful character image retrieval."""
        # Mock image service response
        mock_image_service.get_character_image_url = AsyncMock(return_value={
            "url": "https://testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg",
            "character_name": "Spider-Man",
            "universe": "marvel",
            "is_fallback": False,
            "cache_control": "public, max-age=604800"
        })
        
        mock_image_service.get_cache_headers.return_value = {
            "Cache-Control": "public, max-age=604800",
            "X-Image-Type": "character"
        }
        
        response = client.get("/images/character/marvel/Spider-Man")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["character_name"] == "Spider-Man"
        assert data["data"]["universe"] == "marvel"
        assert data["data"]["is_fallback"] is False
        
        # Check cache headers
        assert "Cache-Control" in response.headers
        assert "X-Image-Type" in response.headers
    
    def test_get_character_image_with_optimization(self, mock_image_service):
        """Test character image retrieval with optimization parameters."""
        # Mock optimized image service response
        mock_image_service.get_optimized_image_url = AsyncMock(return_value={
            "url": "https://testaccount.blob.core.windows.net/character-images/marvel/spider-man.jpg?w=300&h=400&q=85",
            "character_name": "Spider-Man",
            "universe": "marvel",
            "is_fallback": False,
            "optimized": True,
            "optimization_params": {"width": 300, "height": 400, "quality": 85}
        })
        
        mock_image_service.get_cache_headers.return_value = {
            "Cache-Control": "public, max-age=604800",
            "X-Image-Type": "character"
        }
        
        response = client.get("/images/character/marvel/Spider-Man?width=300&height=400&quality=85")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["optimized"] is True
        assert "w=300" in data["data"]["url"]
        assert "h=400" in data["data"]["url"]
        assert "q=85" in data["data"]["url"]
    
    def test_get_character_image_fallback(self, mock_image_service):
        """Test character image retrieval with fallback."""
        # Mock fallback image service response
        mock_image_service.get_character_image_url = AsyncMock(return_value={
            "url": "https://placeholder.com/300x400/cccccc/666666?text=MARVEL+Character",
            "character_name": "Unknown Character",
            "universe": "marvel",
            "is_fallback": True,
            "cache_control": "public, max-age=86400"
        })
        
        mock_image_service.get_cache_headers.return_value = {
            "Cache-Control": "public, max-age=86400",
            "X-Image-Type": "fallback"
        }
        
        response = client.get("/images/character/marvel/Unknown%20Character")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["is_fallback"] is True
        assert data["data"]["character_name"] == "Unknown Character"
        
        # Check fallback cache headers
        assert response.headers["X-Image-Type"] == "fallback"
    
    def test_get_character_image_invalid_universe(self, mock_image_service):
        """Test character image retrieval with invalid universe."""
        response = client.get("/images/character/invalid/Spider-Man")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid universe" in data["detail"]
    
    def test_get_character_image_service_error(self, mock_image_service):
        """Test character image retrieval when service fails."""
        # Mock service error
        mock_image_service.get_character_image_url = AsyncMock(side_effect=Exception("Service error"))
        
        response = client.get("/images/character/marvel/Spider-Man")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to retrieve character image" in data["detail"]
    
    def test_preload_universe_images_success(self, mock_image_service):
        """Test successful universe image preloading."""
        # Mock preload service response
        mock_image_service.preload_universe_images = AsyncMock(return_value={
            "universe": "marvel",
            "total_images": 3,
            "images": [
                {"character": "Spider-Man", "url": "https://test.com/spider-man.jpg", "is_fallback": False},
                {"character": "Iron Man", "url": "https://test.com/iron-man.jpg", "is_fallback": False},
                {"character": "Captain America", "url": "https://test.com/captain-america.jpg", "is_fallback": False}
            ],
            "cache_strategy": "preload"
        })
        
        response = client.get("/images/universe/marvel/preload")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["universe"] == "marvel"
        assert data["data"]["total_images"] == 3
        assert len(data["data"]["images"]) == 3
        
        # Check preload cache headers
        assert response.headers["Cache-Control"] == "public, max-age=3600"
        assert response.headers["X-Content-Type"] == "preload-manifest"
    
    def test_preload_universe_images_invalid_universe(self, mock_image_service):
        """Test universe preloading with invalid universe."""
        response = client.get("/images/universe/invalid/preload")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid universe" in data["detail"]
    
    def test_preload_universe_images_service_error(self, mock_image_service):
        """Test universe preloading when service fails."""
        # Mock service error
        mock_image_service.preload_universe_images = AsyncMock(side_effect=Exception("Service error"))
        
        response = client.get("/images/universe/marvel/preload")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to preload universe images" in data["detail"]
    
    def test_validate_character_image_exists(self, mock_image_service):
        """Test character image validation when image exists."""
        # Mock validation service response
        mock_image_service.validate_image_exists = AsyncMock(return_value=True)
        
        response = client.get("/images/validate/marvel/Spider-Man")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["universe"] == "marvel"
        assert data["data"]["character_name"] == "Spider-Man"
        assert data["data"]["image_exists"] is True
    
    def test_validate_character_image_not_exists(self, mock_image_service):
        """Test character image validation when image doesn't exist."""
        # Mock validation service response
        mock_image_service.validate_image_exists = AsyncMock(return_value=False)
        
        response = client.get("/images/validate/marvel/Unknown%20Character")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["image_exists"] is False
    
    def test_validate_character_image_invalid_universe(self, mock_image_service):
        """Test character image validation with invalid universe."""
        response = client.get("/images/validate/invalid/Spider-Man")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid universe" in data["detail"]
    
    def test_validate_character_image_service_error(self, mock_image_service):
        """Test character image validation when service fails."""
        # Mock service error
        mock_image_service.validate_image_exists = AsyncMock(side_effect=Exception("Service error"))
        
        response = client.get("/images/validate/marvel/Spider-Man")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to validate character image" in data["detail"]
    
    def test_optimization_parameter_validation(self, mock_image_service):
        """Test optimization parameter validation."""
        # Test invalid width (too small)
        response = client.get("/images/character/marvel/Spider-Man?width=10")
        assert response.status_code == 422  # Validation error
        
        # Test invalid width (too large)
        response = client.get("/images/character/marvel/Spider-Man?width=5000")
        assert response.status_code == 422  # Validation error
        
        # Test invalid quality (too small)
        response = client.get("/images/character/marvel/Spider-Man?quality=0")
        assert response.status_code == 422  # Validation error
        
        # Test invalid quality (too large)
        response = client.get("/images/character/marvel/Spider-Man?quality=150")
        assert response.status_code == 422  # Validation error