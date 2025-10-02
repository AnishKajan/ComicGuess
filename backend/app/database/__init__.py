"""Database connection and utilities for Azure Cosmos DB"""

from .connection import (
    CosmosDBConnection,
    cosmos_db,
    get_cosmos_db,
    close_cosmos_db
)
from .exceptions import (
    DatabaseError,
    ConnectionError,
    DocumentNotFoundError,
    DocumentAlreadyExistsError,
    ValidationError,
    PartitionKeyError,
    QueryError,
    RateLimitError,
    handle_cosmos_error
)
from .retry import (
    RetryConfig,
    retry_async,
    with_retry,
    with_standard_retry,
    with_aggressive_retry,
    with_gentle_retry
)
from .init import (
    DatabaseInitializer,
    initialize_database,
    cleanup_database
)
from .partition import (
    PartitionKeyManager,
    DocumentRouter,
    document_router,
    get_daily_puzzle_partition_key,
    get_user_guesses_partition_key,
    validate_universe_partition_key,
    create_puzzle_id_from_date_and_universe
)

__all__ = [
    # Connection management
    "CosmosDBConnection",
    "cosmos_db",
    "get_cosmos_db",
    "close_cosmos_db",
    
    # Exception handling
    "DatabaseError",
    "ConnectionError",
    "DocumentNotFoundError",
    "DocumentAlreadyExistsError",
    "ValidationError",
    "PartitionKeyError",
    "QueryError",
    "RateLimitError",
    "handle_cosmos_error",
    
    # Retry logic
    "RetryConfig",
    "retry_async",
    "with_retry",
    "with_standard_retry",
    "with_aggressive_retry",
    "with_gentle_retry",
    
    # Database initialization
    "DatabaseInitializer",
    "initialize_database",
    "cleanup_database",
    
    # Partition key management
    "PartitionKeyManager",
    "DocumentRouter",
    "document_router",
    "get_daily_puzzle_partition_key",
    "get_user_guesses_partition_key",
    "validate_universe_partition_key",
    "create_puzzle_id_from_date_and_universe"
]