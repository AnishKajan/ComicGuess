"""Database initialization and setup scripts"""

import asyncio
import logging
from typing import List, Dict, Any
from azure.cosmos import PartitionKey
from azure.cosmos.exceptions import CosmosResourceExistsError

from app.config import settings
from .connection import get_cosmos_db
from .exceptions import handle_cosmos_error

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database and container initialization"""
    
    def __init__(self):
        self.cosmos_db = None
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the entire database structure"""
        logger.info("Starting database initialization...")
        
        try:
            # Get database connection
            self.cosmos_db = await get_cosmos_db()
            
            # Initialize containers with proper configuration
            results = await self._initialize_containers()
            
            # Create indexes for better query performance
            await self._create_indexes()
            
            # Seed initial data if needed
            await self._seed_initial_data()
            
            logger.info("Database initialization completed successfully")
            
            return {
                "status": "success",
                "database": settings.cosmos_db_database_name,
                "containers": results
            }
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def _initialize_containers(self) -> Dict[str, str]:
        """Initialize all required containers"""
        results = {}
        
        container_configs = [
            {
                "name": settings.cosmos_db_container_users,
                "partition_key": "/id",
                "unique_keys": [
                    {"paths": ["/email"]},  # Ensure unique emails
                    {"paths": ["/username"]}  # Ensure unique usernames
                ],
                "indexing_policy": {
                    "indexingMode": "consistent",
                    "automatic": True,
                    "includedPaths": [
                        {"path": "/*"}
                    ],
                    "excludedPaths": [
                        {"path": "/\"_etag\"/?"}
                    ],
                    "compositeIndexes": [
                        [
                            {"path": "/email", "order": "ascending"},
                            {"path": "/created_at", "order": "descending"}
                        ]
                    ]
                }
            },
            {
                "name": settings.cosmos_db_container_puzzles,
                "partition_key": "/universe",
                "unique_keys": [
                    {"paths": ["/id"]}  # Ensure unique puzzle IDs
                ],
                "indexing_policy": {
                    "indexingMode": "consistent",
                    "automatic": True,
                    "includedPaths": [
                        {"path": "/*"}
                    ],
                    "excludedPaths": [
                        {"path": "/\"_etag\"/?"}
                    ],
                    "compositeIndexes": [
                        [
                            {"path": "/universe", "order": "ascending"},
                            {"path": "/active_date", "order": "descending"}
                        ]
                    ]
                }
            },
            {
                "name": settings.cosmos_db_container_guesses,
                "partition_key": "/user_id",
                "default_ttl": 60 * 60 * 24 * 365,  # 1 year TTL
                "indexing_policy": {
                    "indexingMode": "consistent",
                    "automatic": True,
                    "includedPaths": [
                        {"path": "/*"}
                    ],
                    "excludedPaths": [
                        {"path": "/\"_etag\"/?"}
                    ],
                    "compositeIndexes": [
                        [
                            {"path": "/user_id", "order": "ascending"},
                            {"path": "/puzzle_id", "order": "ascending"},
                            {"path": "/timestamp", "order": "descending"}
                        ]
                    ]
                }
            }
        ]
        
        for config in container_configs:
            result = await self._create_container(config)
            results[config["name"]] = result
        
        return results
    
    async def _create_container(self, config: Dict[str, Any]) -> str:
        """Create a single container with the given configuration"""
        container_name = config["name"]
        
        try:
            # Check if container already exists
            existing_container = self.cosmos_db.get_container(container_name)
            await asyncio.get_event_loop().run_in_executor(
                None, existing_container.read
            )
            
            logger.info(f"Container '{container_name}' already exists")
            return "exists"
            
        except Exception:
            # Container doesn't exist, create it
            try:
                logger.info(f"Creating container '{container_name}'...")
                
                container_definition = {
                    "id": container_name,
                    "partitionKey": PartitionKey(path=config["partition_key"])
                }
                
                # Add unique key constraints if specified
                if "unique_keys" in config:
                    container_definition["uniqueKeyPolicy"] = {
                        "uniqueKeys": config["unique_keys"]
                    }
                
                # Add indexing policy if specified
                if "indexing_policy" in config:
                    container_definition["indexingPolicy"] = config["indexing_policy"]
                
                # Add TTL if specified
                if "default_ttl" in config:
                    container_definition["defaultTtl"] = config["default_ttl"]
                
                # Create the container
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.cosmos_db._database.create_container,
                    container_definition
                )
                
                logger.info(f"Container '{container_name}' created successfully")
                return "created"
                
            except CosmosResourceExistsError:
                logger.info(f"Container '{container_name}' was created by another process")
                return "exists"
            except Exception as e:
                logger.error(f"Failed to create container '{container_name}': {e}")
                raise
    
    async def _create_indexes(self) -> None:
        """Create additional indexes for better query performance"""
        logger.info("Creating additional indexes...")
        
        # Note: In Cosmos DB, indexes are defined at container creation time
        # Additional indexes would be created through the indexing policy
        # This method is kept for future custom index operations
        
        logger.info("Index creation completed")
    
    async def _seed_initial_data(self) -> None:
        """Seed initial data if needed"""
        logger.info("Checking for initial data seeding...")
        
        # This method can be used to seed initial data like:
        # - Default admin users
        # - Sample puzzles for testing
        # - Configuration data
        
        # For now, we'll skip seeding in production
        # In development, you might want to add sample data here
        
        logger.info("Initial data seeding completed")
    
    async def cleanup(self) -> Dict[str, Any]:
        """Clean up database resources (use with caution!)"""
        logger.warning("Starting database cleanup - this will delete all data!")
        
        try:
            containers_deleted = []
            
            for container_name in [
                settings.cosmos_db_container_users,
                settings.cosmos_db_container_puzzles,
                settings.cosmos_db_container_guesses
            ]:
                try:
                    container = self.cosmos_db.get_container(container_name)
                    await asyncio.get_event_loop().run_in_executor(
                        None, container.delete_container
                    )
                    containers_deleted.append(container_name)
                    logger.info(f"Deleted container: {container_name}")
                except Exception as e:
                    logger.warning(f"Could not delete container {container_name}: {e}")
            
            return {
                "status": "success",
                "containers_deleted": containers_deleted
            }
            
        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }


# Convenience functions
async def initialize_database() -> Dict[str, Any]:
    """Initialize the database structure"""
    initializer = DatabaseInitializer()
    return await initializer.initialize()


async def cleanup_database() -> Dict[str, Any]:
    """Clean up the database (use with caution!)"""
    initializer = DatabaseInitializer()
    return await initializer.cleanup()


# CLI script support
async def main():
    """Main function for running initialization from command line"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        print("WARNING: This will delete all database data!")
        confirm = input("Type 'DELETE' to confirm: ")
        if confirm == "DELETE":
            result = await cleanup_database()
            print(f"Cleanup result: {result}")
        else:
            print("Cleanup cancelled")
    else:
        result = await initialize_database()
        print(f"Initialization result: {result}")


if __name__ == "__main__":
    asyncio.run(main())