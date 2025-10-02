"""Database-specific exceptions and error handling"""

from typing import Optional, Any
from azure.cosmos.exceptions import CosmosHttpResponseError


class DatabaseError(Exception):
    """Base exception for database operations"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class ConnectionError(DatabaseError):
    """Raised when database connection fails"""
    pass


class DocumentNotFoundError(DatabaseError):
    """Raised when a document is not found"""
    pass


class DocumentAlreadyExistsError(DatabaseError):
    """Raised when trying to create a document that already exists"""
    pass


class ValidationError(DatabaseError):
    """Raised when document validation fails"""
    pass


class PartitionKeyError(DatabaseError):
    """Raised when partition key operations fail"""
    pass


class QueryError(DatabaseError):
    """Raised when database queries fail"""
    pass


class RateLimitError(DatabaseError):
    """Raised when rate limits are exceeded"""
    pass


def handle_cosmos_error(error: CosmosHttpResponseError) -> DatabaseError:
    """Convert Cosmos DB errors to application-specific errors"""
    
    status_code = error.status_code
    message = str(error)
    
    # Map Cosmos DB status codes to application errors
    if status_code == 404:
        return DocumentNotFoundError(f"Document not found: {message}", error)
    elif status_code == 409:
        return DocumentAlreadyExistsError(f"Document already exists: {message}", error)
    elif status_code == 400:
        return ValidationError(f"Invalid request: {message}", error)
    elif status_code == 429:
        return RateLimitError(f"Rate limit exceeded: {message}", error)
    elif status_code in [500, 502, 503, 504]:
        return ConnectionError(f"Service unavailable: {message}", error)
    else:
        return DatabaseError(f"Database operation failed: {message}", error)