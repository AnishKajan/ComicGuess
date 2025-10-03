"""
Custom exceptions for storage operations.
"""

class StorageError(Exception):
    """Base exception for storage operations."""
    pass

class ImageNotFoundError(StorageError):
    """Raised when a requested image is not found."""
    pass

class ImageUploadError(StorageError):
    """Raised when image upload fails."""
    pass

class StorageConnectionError(StorageError):
    """Raised when connection to storage service fails."""
    pass