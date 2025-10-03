"""Base repository class with common database operations"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, TypeVar, Generic
from abc import ABC, abstractmethod
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from azure.cosmos.container import ContainerProxy

from app.database.connection import get_cosmos_db
from app.database.exceptions import DatabaseError, ItemNotFoundError, DuplicateItemError

logger = logging.getLogger(__name__)

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    """Base repository class with common CRUD operations"""
    
    def __init__(self, container_name: str):
        self.container_name = container_name
        self._container: Optional[ContainerProxy] = None
    
    async def _get_container(self) -> ContainerProxy:
        """Get the container for this repository"""
        if self._container is None:
            cosmos_db = await get_cosmos_db()
            self._container = cosmos_db.get_container(self.container_name)
        return self._container
    
    async def create(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Create a new item in the database"""
        try:
            container = await self._get_container()
            
            # Add partition key to item if not present
            if not self._has_partition_key(item, partition_key):
                item = self._add_partition_key(item, partition_key)
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                container.create_item,
                item
            )
            
            logger.info(f"Created item with id: {item.get('id')} in {self.container_name}")
            return result
            
        except CosmosHttpResponseError as e:
            if e.status_code == 409:  # Conflict - item already exists
                raise DuplicateItemError(f"Item with id {item.get('id')} already exists")
            else:
                logger.error(f"Error creating item in {self.container_name}: {e}")
                raise DatabaseError(f"Failed to create item: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating item in {self.container_name}: {e}")
            raise DatabaseError(f"Unexpected error: {str(e)}")
    
    async def get_by_id(self, item_id: str, partition_key: str) -> Optional[Dict[str, Any]]:
        """Get an item by ID and partition key"""
        try:
            container = await self._get_container()
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                container.read_item,
                item_id,
                partition_key
            )
            
            return result
            
        except CosmosResourceNotFoundError:
            return None
        except CosmosHttpResponseError as e:
            logger.error(f"Error reading item {item_id} from {self.container_name}: {e}")
            raise DatabaseError(f"Failed to read item: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error reading item {item_id} from {self.container_name}: {e}")
            raise DatabaseError(f"Unexpected error: {str(e)}")
    
    async def update(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Update an existing item"""
        try:
            container = await self._get_container()
            
            # Ensure partition key is in item
            if not self._has_partition_key(item, partition_key):
                item = self._add_partition_key(item, partition_key)
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                container.replace_item,
                item['id'],
                item
            )
            
            logger.info(f"Updated item with id: {item.get('id')} in {self.container_name}")
            return result
            
        except CosmosResourceNotFoundError:
            raise ItemNotFoundError(f"Item with id {item.get('id')} not found")
        except CosmosHttpResponseError as e:
            logger.error(f"Error updating item {item.get('id')} in {self.container_name}: {e}")
            raise DatabaseError(f"Failed to update item: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error updating item {item.get('id')} in {self.container_name}: {e}")
            raise DatabaseError(f"Unexpected error: {str(e)}")
    
    async def delete(self, item_id: str, partition_key: str) -> bool:
        """Delete an item by ID and partition key"""
        try:
            container = await self._get_container()
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                container.delete_item,
                item_id,
                partition_key
            )
            
            logger.info(f"Deleted item with id: {item_id} from {self.container_name}")
            return True
            
        except CosmosResourceNotFoundError:
            return False
        except CosmosHttpResponseError as e:
            logger.error(f"Error deleting item {item_id} from {self.container_name}: {e}")
            raise DatabaseError(f"Failed to delete item: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error deleting item {item_id} from {self.container_name}: {e}")
            raise DatabaseError(f"Unexpected error: {str(e)}")
    
    async def query(self, query: str, parameters: Optional[List[Dict[str, Any]]] = None, partition_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query against the container"""
        try:
            container = await self._get_container()
            
            query_kwargs = {
                'query': query,
                'enable_cross_partition_query': partition_key is None
            }
            
            if parameters:
                query_kwargs['parameters'] = parameters
            
            if partition_key:
                query_kwargs['partition_key'] = partition_key
            
            items = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: list(container.query_items(**query_kwargs))
            )
            
            return items
            
        except CosmosHttpResponseError as e:
            logger.error(f"Error executing query in {self.container_name}: {e}")
            raise DatabaseError(f"Failed to execute query: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error executing query in {self.container_name}: {e}")
            raise DatabaseError(f"Unexpected error: {str(e)}")
    
    async def exists(self, item_id: str, partition_key: str) -> bool:
        """Check if an item exists"""
        item = await self.get_by_id(item_id, partition_key)
        return item is not None
    
    @abstractmethod
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key"""
        pass
    
    @abstractmethod
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item"""
        pass