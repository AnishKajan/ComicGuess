"""
Azure Blob Storage client (stub implementation)
"""

import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class BlobClient:
    """Azure Blob Storage client wrapper (stub)"""
    
    def __init__(self):
        """Initialize blob client with environment variables"""
        self.blob_account_url = os.getenv("BLOB_ACCOUNT_URL")
        self.blob_sas_token = os.getenv("BLOB_SAS_TOKEN")
        
        if not self.blob_account_url or not self.blob_sas_token:
            logger.warning("Blob storage credentials not configured - using stub implementation")
    
    async def upload_blob(self, container_name: str, blob_name: str, data: bytes) -> str:
        """Upload blob to storage (stub)"""
        logger.info(f"STUB: Would upload blob {blob_name} to container {container_name}")
        return f"https://stub.blob.core.windows.net/{container_name}/{blob_name}"
    
    async def download_blob(self, container_name: str, blob_name: str) -> Optional[bytes]:
        """Download blob from storage (stub)"""
        logger.info(f"STUB: Would download blob {blob_name} from container {container_name}")
        return None
    
    async def delete_blob(self, container_name: str, blob_name: str) -> bool:
        """Delete blob from storage (stub)"""
        logger.info(f"STUB: Would delete blob {blob_name} from container {container_name}")
        return True
    
    async def list_blobs(self, container_name: str, prefix: Optional[str] = None) -> List[str]:
        """List blobs in container (stub)"""
        logger.info(f"STUB: Would list blobs in container {container_name} with prefix {prefix}")
        return []
    
    async def get_blob_url(self, container_name: str, blob_name: str) -> str:
        """Get blob URL (stub)"""
        return f"https://stub.blob.core.windows.net/{container_name}/{blob_name}"
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for blob storage (stub)"""
        return {
            "status": "stub",
            "message": "Blob storage client is in stub mode",
            "configured": bool(self.blob_account_url and self.blob_sas_token)
        }

# Global instance
blob_client = BlobClient()

async def get_blob_client() -> BlobClient:
    """Get the blob client instance"""
    return blob_client