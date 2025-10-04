"""
Azure Blob Storage utilities for character images.
Handles image upload, retrieval, and organization by universe.
"""

import logging
from typing import Optional, List, BinaryIO
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, AzureError
from app.config import settings

logger = logging.getLogger(__name__)

class BlobStorageService:
    """Service for managing character images in Azure Blob Storage."""
    
    def __init__(self):
        """Initialize the blob storage service with connection string."""
        self.connection_string = settings.azure_storage_connection_string
        self.container_name = settings.azure_storage_container_name
        self._blob_service_client: Optional[BlobServiceClient] = None
        self._container_client: Optional[ContainerClient] = None
    
    @property
    def blob_service_client(self) -> BlobServiceClient:
        """Lazy initialization of blob service client."""
        if self._blob_service_client is None:
            if not self.connection_string:
                raise ValueError("Azure storage connection string not configured")
            self._blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
        return self._blob_service_client
    
    @property
    def container_client(self) -> ContainerClient:
        """Lazy initialization of container client."""
        if self._container_client is None:
            self._container_client = self.blob_service_client.get_container_client(
                self.container_name
            )
        return self._container_client
    
    def _get_blob_path(self, universe: str, character_name: str, file_extension: str = "jpg") -> str:
        """
        Generate blob path with universe-based folder organization.
        
        Args:
            universe: The comic universe (marvel, DC, image)
            character_name: Name of the character
            file_extension: File extension (default: jpg)
            
        Returns:
            Blob path in format: {universe}/{character_name}.{extension}
        """
        # Sanitize character name for file system
        safe_character_name = character_name.lower().replace(" ", "-").replace("'", "")
        return f"{universe.lower()}/{safe_character_name}.{file_extension}"
    
    async def upload_image(
        self, 
        universe: str, 
        character_name: str, 
        image_data: BinaryIO,
        content_type: str = "image/jpeg"
    ) -> str:
        """
        Upload a character image to blob storage.
        
        Args:
            universe: The comic universe (marvel, DC, image)
            character_name: Name of the character
            image_data: Binary image data
            content_type: MIME type of the image
            
        Returns:
            The blob path of the uploaded image
            
        Raises:
            AzureError: If upload fails
        """
        try:
            blob_path = self._get_blob_path(universe, character_name)
            
            # Upload the blob with metadata
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Set content settings for proper image serving
            content_settings = {
                'content_type': content_type,
                'cache_control': 'public, max-age=604800'  # 7 days cache
            }
            
            # Upload with metadata
            metadata = {
                'universe': universe,
                'character_name': character_name,
                'uploaded_by': 'system'
            }
            
            blob_client.upload_blob(
                image_data,
                overwrite=True,
                content_settings=content_settings,
                metadata=metadata
            )
            
            logger.info(f"Successfully uploaded image for {character_name} in {universe} universe")
            return blob_path
            
        except AzureError as e:
            logger.error(f"Failed to upload image for {character_name}: {str(e)}")
            raise
    
    async def get_image_url(self, universe: str, character_name: str) -> Optional[str]:
        """
        Get the public URL for a character image.
        
        Args:
            universe: The comic universe (marvel, DC, image)
            character_name: Name of the character
            
        Returns:
            Public URL of the image or None if not found
        """
        try:
            blob_path = self._get_blob_path(universe, character_name)
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Check if blob exists
            if blob_client.exists():
                return blob_client.url
            else:
                logger.warning(f"Image not found for {character_name} in {universe} universe")
                return None
                
        except AzureError as e:
            logger.error(f"Failed to get image URL for {character_name}: {str(e)}")
            return None
    
    async def delete_image(self, universe: str, character_name: str) -> bool:
        """
        Delete a character image from blob storage.
        
        Args:
            universe: The comic universe (marvel, DC, image)
            character_name: Name of the character
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            blob_path = self._get_blob_path(universe, character_name)
            blob_client = self.container_client.get_blob_client(blob_path)
            
            blob_client.delete_blob()
            logger.info(f"Successfully deleted image for {character_name} in {universe} universe")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"Image not found for deletion: {character_name} in {universe}")
            return False
        except AzureError as e:
            logger.error(f"Failed to delete image for {character_name}: {str(e)}")
            return False
    
    async def get_image_metadata(self, universe: str, character_name: str) -> Optional[dict]:
        """
        Get metadata for a character image including version information.
        
        Args:
            universe: The comic universe (marvel, DC, image)
            character_name: Name of the character
            
        Returns:
            Dictionary containing image metadata or None if not found
        """
        try:
            blob_path = self._get_blob_path(universe, character_name)
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Get blob properties which include etag and last modified
            properties = blob_client.get_blob_properties()
            
            return {
                "etag": properties.etag,
                "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
                "content_length": properties.size,
                "content_type": properties.content_settings.content_type if properties.content_settings else None,
                "metadata": properties.metadata or {},
                "blob_path": blob_path,
                "url": blob_client.url
            }
            
        except ResourceNotFoundError:
            logger.warning(f"Image metadata not found for {character_name} in {universe}")
            return None
        except AzureError as e:
            logger.error(f"Failed to get image metadata for {character_name}: {str(e)}")
            return None
    
    async def update_image_metadata(self, universe: str, character_name: str, metadata: dict) -> bool:
        """
        Update metadata for a character image.
        
        Args:
            universe: The comic universe (marvel, DC, image)
            character_name: Name of the character
            metadata: Dictionary of metadata to update
            
        Returns:
            True if metadata was updated successfully
        """
        try:
            blob_path = self._get_blob_path(universe, character_name)
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Update blob metadata
            blob_client.set_blob_metadata(metadata)
            
            logger.info(f"Updated metadata for {character_name} in {universe}")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"Cannot update metadata - image not found: {character_name} in {universe}")
            return False
        except AzureError as e:
            logger.error(f"Failed to update metadata for {character_name}: {str(e)}")
            return False
    
    async def list_images_by_universe(self, universe: str) -> List[str]:
        """
        List all character images in a specific universe.
        
        Args:
            universe: The comic universe (marvel, DC, image)
            
        Returns:
            List of character names that have images
        """
        try:
            prefix = f"{universe.lower()}/"
            blob_list = self.container_client.list_blobs(name_starts_with=prefix)
            
            character_names = []
            for blob in blob_list:
                # Extract character name from blob path
                blob_name = blob.name
                if blob_name.startswith(prefix):
                    # Remove universe prefix and file extension
                    character_part = blob_name[len(prefix):]
                    character_name = character_part.rsplit('.', 1)[0]  # Remove extension
                    # Convert back from safe name format
                    display_name = character_name.replace("-", " ").title()
                    character_names.append(display_name)
            
            return character_names
            
        except AzureError as e:
            logger.error(f"Failed to list images for {universe} universe: {str(e)}")
            return []
    
    async def ensure_container_exists(self) -> bool:
        """
        Ensure the blob storage container exists, create if it doesn't.
        
        Returns:
            True if container exists or was created successfully
        """
        try:
            # Try to get container properties (this will fail if container doesn't exist)
            self.container_client.get_container_properties()
            return True
            
        except ResourceNotFoundError:
            # Container doesn't exist, create it
            try:
                self.container_client.create_container(public_access='blob')
                logger.info(f"Created blob storage container: {self.container_name}")
                return True
            except AzureError as e:
                logger.error(f"Failed to create container {self.container_name}: {str(e)}")
                return False
        except AzureError as e:
            logger.error(f"Failed to check container {self.container_name}: {str(e)}")
            return False

# Global instance
blob_storage_service = BlobStorageService()