"""Azure services integration"""

from .blob_client import blob_client, get_blob_client

__all__ = [
    "blob_client",
    "get_blob_client"
]