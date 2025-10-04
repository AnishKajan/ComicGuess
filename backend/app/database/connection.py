"""Azure Cosmos DB connection management"""

import asyncio
import logging
from typing import Optional, Dict, Any
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from azure.cosmos.database import DatabaseProxy
from azure.cosmos.container import ContainerProxy

from app.config import settings

logger = logging.getLogger(__name__)

class CosmosDBConnection:
    """Manages Azure Cosmos DB connections and operations"""
    
    def __init__(self):
        self._client: Optional[CosmosClient] = None
        self._database: Optional[DatabaseProxy] = None
        self._containers: Dict[str, ContainerProxy] = {}
        self._connection_lock = asyncio.Lock()
        
    async def connect(self) -> None:
        """Establish connection to Cosmos DB"""
        async with self._connection_lock:
            if self._client is not None:
                return
            
            try:
                logger.info("Connecting to Azure Cosmos DB...")
                
                # Create Cosmos client
                self._client = CosmosClient(
                    url=settings.effective_cosmos_endpoint,
                    credential=settings.effective_cosmos_key
                )
                
                # Get or create database
                self._database = await self._get_or_create_database()
                
                # Initialize containers
                await self._initialize_containers()
                
                logger.info("Successfully connected to Azure Cosmos DB")
                
            except Exception as e:
                logger.error(f"Failed to connect to Cosmos DB: {e}")
                await self.disconnect()
                raise
    
    async def disconnect(self) -> None:
        """Close Cosmos DB connection"""
        async with self._connection_lock:
            if self._client:
                try:
                    # Cosmos client doesn't need explicit closing in Python SDK
                    self._client = None
                    self._database = None
                    self._containers.clear()
                    logger.info("Disconnected from Azure Cosmos DB")
                except Exception as e:
                    logger.error(f"Error during disconnect: {e}")
    
    async def _get_or_create_database(self) -> DatabaseProxy:
        """Get or create the database"""
        try:
            # Try to get existing database
            database = self._client.get_database_client(settings.effective_cosmos_database_name)
            
            # Test if database exists by reading its properties
            await asyncio.get_event_loop().run_in_executor(
                None, database.read
            )
            
            logger.info(f"Using existing database: {settings.effective_cosmos_database_name}")
            return database
            
        except CosmosResourceNotFoundError:
            # Database doesn't exist, create it
            logger.info(f"Creating database: {settings.effective_cosmos_database_name}")
            
            database = await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.create_database,
                settings.effective_cosmos_database_name
            )
            
            return database
    
    async def _initialize_containers(self) -> None:
        """Initialize all required containers"""
        container_configs = [
            {
                "name": settings.cosmos_container_users,
                "partition_key": PartitionKey(path="/userId"),
                "default_ttl": None  # Users don't expire
            },
            {
                "name": settings.cosmos_container_puzzles,
                "partition_key": PartitionKey(path="/universe"),
                "default_ttl": None  # Puzzles don't expire
            },
            {
                "name": settings.cosmos_container_guesses,
                "partition_key": PartitionKey(path="/user_id"),
                "default_ttl": 60 * 60 * 24 * 365  # Keep guesses for 1 year
            },
            {
                "name": settings.cosmos_container_streaks,
                "partition_key": PartitionKey(path="/userId"),
                "default_ttl": None  # Streaks don't expire
            }
        ]
        
        for config in container_configs:
            container = await self._get_or_create_container(
                config["name"],
                config["partition_key"],
                config["default_ttl"]
            )
            self._containers[config["name"]] = container
    
    async def _get_or_create_container(
        self, 
        container_name: str, 
        partition_key: PartitionKey,
        default_ttl: Optional[int] = None
    ) -> ContainerProxy:
        """Get or create a container"""
        try:
            # Try to get existing container
            container = self._database.get_container_client(container_name)
            
            # Test if container exists by reading its properties
            await asyncio.get_event_loop().run_in_executor(
                None, container.read
            )
            
            logger.info(f"Using existing container: {container_name}")
            return container
            
        except CosmosResourceNotFoundError:
            # Container doesn't exist, create it
            logger.info(f"Creating container: {container_name}")
            
            container_settings = {
                "id": container_name,
                "partition_key": partition_key
            }
            
            if default_ttl is not None:
                container_settings["default_ttl"] = default_ttl
            
            container = await asyncio.get_event_loop().run_in_executor(
                None,
                self._database.create_container,
                container_settings
            )
            
            return container
    
    def get_container(self, container_name: str) -> ContainerProxy:
        """Get a container by name"""
        if container_name not in self._containers:
            raise ValueError(f"Container '{container_name}' not initialized")
        return self._containers[container_name]
    
    @property
    def users_container(self) -> ContainerProxy:
        """Get the users container"""
        return self.get_container(settings.cosmos_container_users)
    
    @property
    def puzzles_container(self) -> ContainerProxy:
        """Get the puzzles container"""
        return self.get_container(settings.cosmos_container_puzzles)
    
    @property
    def guesses_container(self) -> ContainerProxy:
        """Get the guesses container"""
        return self.get_container(settings.cosmos_container_guesses)
    
    @property
    def streaks_container(self) -> ContainerProxy:
        """Get the streaks container"""
        return self.get_container(settings.cosmos_container_streaks)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on database connection"""
        try:
            if not self._client or not self._database:
                return {
                    "status": "unhealthy",
                    "error": "Not connected to database"
                }
            
            # Test database connection
            await asyncio.get_event_loop().run_in_executor(
                None, self._database.read
            )
            
            # Test container access
            container_status = {}
            for name, container in self._containers.items():
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, container.read
                    )
                    container_status[name] = "healthy"
                except Exception as e:
                    container_status[name] = f"error: {str(e)}"
            
            return {
                "status": "healthy",
                "database": settings.effective_cosmos_database_name,
                "containers": container_status
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Global connection instance
cosmos_db = CosmosDBConnection()

async def get_cosmos_db() -> CosmosDBConnection:
    """Get the Cosmos DB connection instance"""
    if cosmos_db._client is None:
        await cosmos_db.connect()
    return cosmos_db

async def close_cosmos_db() -> None:
    """Close the Cosmos DB connection"""
    await cosmos_db.disconnect()