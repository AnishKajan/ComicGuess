"""
Tests for Azure Blob Storage utilities.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from io import BytesIO
from azure.core.exceptions import ResourceNotFoundError, AzureError
from app.storage.blob_storage import BlobStorageService
from app.storage.exceptions import StorageError

class TestBlobStorageService:
    """Test cases for BlobStorageService."""
    
    @pytest.fixture
    def mock_blob_service(self):
        """Create a mock blob storage service for testing."""
        with patch('app.storage.blob_storage.settings') as mock_settings:
            mock_settings.azure_storage_connection_string = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test123;EndpointSuffix=core.windows.net"
            mock_settings.azure_storage_container_name = "test-container"
            
            # Mock the Azure SDK components to avoid actual connection
            with patch('app.storage.blob_storage.BlobServiceClient') as mock_client_class:
                service = BlobStorageService()
                # Reset the lazy-loaded clients to None so we can mock them properly
                service._blob_service_client = None
                service._container_client = None
                return service
    
    @pytest.fixture
    def sample_image_data(self):
        """Create sample image data for testing."""
        return BytesIO(b"fake_image_data")
    
    def test_get_blob_path(self, mock_blob_service):
        """Test blob path generation with universe organization."""
        # Test normal character name
        path = mock_blob_service._get_blob_path("marvel", "Spider-Man")
        assert path == "marvel/spider-man.jpg"
        
        # Test character name with apostrophe
        path = mock_blob_service._get_blob_path("dc", "Green Lantern")
        assert path == "dc/green-lantern.jpg"
        
        # Test image universe
        path = mock_blob_service._get_blob_path("image", "Spawn")
        assert path == "image/spawn.jpg"
        
        # Test custom extension
        path = mock_blob_service._get_blob_path("marvel", "Iron Man", "png")
        assert path == "marvel/iron-man.png"
    
    @pytest.mark.asyncio
    async def test_upload_image_success(self, mock_blob_service, sample_image_data):
        """Test successful image upload."""
        # Mock the container client directly
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        result = await mock_blob_service.upload_image(
            "marvel", "Spider-Man", sample_image_data, "image/jpeg"
        )
        
        assert result == "marvel/spider-man.jpg"
        mock_blob_client.upload_blob.assert_called_once()
        
        # Verify upload_blob was called with correct parameters
        call_args = mock_blob_client.upload_blob.call_args
        assert call_args[0][0] == sample_image_data  # image_data
        assert call_args[1]['overwrite'] is True
        assert 'content_settings' in call_args[1]
        assert 'metadata' in call_args[1]
    
    @pytest.mark.asyncio
    async def test_upload_image_failure(self, mock_blob_service, sample_image_data):
        """Test image upload failure handling."""
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_blob_client.upload_blob.side_effect = AzureError("Upload failed")
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        with pytest.raises(AzureError):
            await mock_blob_service.upload_image(
                "marvel", "Spider-Man", sample_image_data
            )
    
    @pytest.mark.asyncio
    async def test_get_image_url_exists(self, mock_blob_service):
        """Test getting image URL when image exists."""
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = True
        mock_blob_client.url = "https://test.blob.core.windows.net/test-container/marvel/spider-man.jpg"
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        url = await mock_blob_service.get_image_url("marvel", "Spider-Man")
        
        assert url == "https://test.blob.core.windows.net/test-container/marvel/spider-man.jpg"
        mock_blob_client.exists.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_image_url_not_exists(self, mock_blob_service):
        """Test getting image URL when image doesn't exist."""
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_blob_client.exists.return_value = False
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        url = await mock_blob_service.get_image_url("marvel", "Spider-Man")
        
        assert url is None
    
    @pytest.mark.asyncio
    async def test_get_image_url_azure_error(self, mock_blob_service):
        """Test getting image URL with Azure error."""
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_blob_client.exists.side_effect = AzureError("Connection failed")
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        url = await mock_blob_service.get_image_url("marvel", "Spider-Man")
        
        assert url is None
    
    @pytest.mark.asyncio
    async def test_delete_image_success(self, mock_blob_service):
        """Test successful image deletion."""
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        result = await mock_blob_service.delete_image("marvel", "Spider-Man")
        
        assert result is True
        mock_blob_client.delete_blob.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_image_not_found(self, mock_blob_service):
        """Test deleting non-existent image."""
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_blob_client.delete_blob.side_effect = ResourceNotFoundError("Not found")
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        result = await mock_blob_service.delete_image("marvel", "Spider-Man")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_image_azure_error(self, mock_blob_service):
        """Test image deletion with Azure error."""
        mock_container = Mock()
        mock_blob_client = Mock()
        mock_blob_client.delete_blob.side_effect = AzureError("Delete failed")
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_blob_service._container_client = mock_container
        
        result = await mock_blob_service.delete_image("marvel", "Spider-Man")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list_images_by_universe(self, mock_blob_service):
        """Test listing images by universe."""
        mock_container = Mock()
        # Mock blob objects
        mock_blob1 = Mock()
        mock_blob1.name = "marvel/spider-man.jpg"
        mock_blob2 = Mock()
        mock_blob2.name = "marvel/iron-man.jpg"
        mock_blob3 = Mock()
        mock_blob3.name = "marvel/captain-america.jpg"
        
        mock_container.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]
        mock_blob_service._container_client = mock_container
        
        characters = await mock_blob_service.list_images_by_universe("marvel")
        
        expected_characters = ["Spider Man", "Iron Man", "Captain America"]
        assert set(characters) == set(expected_characters)
        mock_container.list_blobs.assert_called_once_with(name_starts_with="marvel/")
    
    @pytest.mark.asyncio
    async def test_list_images_azure_error(self, mock_blob_service):
        """Test listing images with Azure error."""
        mock_container = Mock()
        mock_container.list_blobs.side_effect = AzureError("List failed")
        mock_blob_service._container_client = mock_container
        
        characters = await mock_blob_service.list_images_by_universe("marvel")
        
        assert characters == []
    
    @pytest.mark.asyncio
    async def test_ensure_container_exists_already_exists(self, mock_blob_service):
        """Test container existence check when container already exists."""
        mock_container = Mock()
        mock_container.get_container_properties.return_value = {}
        mock_blob_service._container_client = mock_container
        
        result = await mock_blob_service.ensure_container_exists()
        
        assert result is True
        mock_container.get_container_properties.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_container_exists_create_new(self, mock_blob_service):
        """Test container creation when container doesn't exist."""
        mock_container = Mock()
        mock_container.get_container_properties.side_effect = ResourceNotFoundError("Not found")
        mock_container.create_container.return_value = {}
        mock_blob_service._container_client = mock_container
        
        result = await mock_blob_service.ensure_container_exists()
        
        assert result is True
        mock_container.create_container.assert_called_once_with(public_access='blob')
    
    @pytest.mark.asyncio
    async def test_ensure_container_exists_create_failure(self, mock_blob_service):
        """Test container creation failure."""
        mock_container = Mock()
        mock_container.get_container_properties.side_effect = ResourceNotFoundError("Not found")
        mock_container.create_container.side_effect = AzureError("Create failed")
        mock_blob_service._container_client = mock_container
        
        result = await mock_blob_service.ensure_container_exists()
        
        assert result is False
    
    def test_lazy_initialization_blob_service_client(self, mock_blob_service):
        """Test lazy initialization of blob service client."""
        with patch('app.storage.blob_storage.BlobServiceClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.from_connection_string.return_value = mock_client
            
            # First access should create the client
            client1 = mock_blob_service.blob_service_client
            assert client1 == mock_client
            mock_client_class.from_connection_string.assert_called_once()
            
            # Second access should return the same client without creating new one
            client2 = mock_blob_service.blob_service_client
            assert client2 == mock_client
            assert mock_client_class.from_connection_string.call_count == 1
    
    def test_lazy_initialization_container_client(self, mock_blob_service):
        """Test lazy initialization of container client."""
        mock_blob_service_client = Mock()
        mock_container = Mock()
        mock_blob_service_client.get_container_client.return_value = mock_container
        mock_blob_service._blob_service_client = mock_blob_service_client
        
        # First access should create the client
        container1 = mock_blob_service.container_client
        assert container1 == mock_container
        mock_blob_service_client.get_container_client.assert_called_once()
        
        # Second access should return the same client
        container2 = mock_blob_service.container_client
        assert container2 == mock_container
        assert mock_blob_service_client.get_container_client.call_count == 1
    
    def test_missing_connection_string(self):
        """Test error when connection string is not configured."""
        with patch('app.storage.blob_storage.settings') as mock_settings:
            mock_settings.azure_storage_connection_string = ""
            mock_settings.azure_storage_container_name = "test-container"
            
            service = BlobStorageService()
            
            with pytest.raises(ValueError, match="Azure storage connection string not configured"):
                _ = service.blob_service_client