"""User repository for managing user data in Cosmos DB"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.repositories.base import BaseRepository
from app.models.user import User, UserCreate, UserUpdate, UserStats
from app.config import settings
from app.database.exceptions import ItemNotFoundError, DuplicateItemError

logger = logging.getLogger(__name__)

class UserRepository(BaseRepository[User]):
    """Repository for user data operations"""
    
    def __init__(self):
        super().__init__(settings.cosmos_container_users)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key (userId for users)"""
        return 'userId' in item and item['userId'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item (userId for users)"""
        item['userId'] = partition_key
        # Also set id for backward compatibility
        if 'id' not in item:
            item['id'] = partition_key
        return item
    
    async def create_user(self, user_data: UserCreate, password_hash: str) -> User:
        """Create a new user"""
        # Check if user with email already exists
        existing_user = await self.get_user_by_email(user_data.email)
        if existing_user:
            raise DuplicateItemError(f"User with email {user_data.email} already exists")
        
        # Create user model
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=password_hash
        )
        
        # Convert to dict for storage
        user_dict = user.model_dump()
        
        # Create in database using userId as partition key
        result = await self.create(user_dict, user.userId)
        
        # Return User model
        return User(**result)
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        result = await self.get_by_id(user_id, user_id)  # Using user_id as both id and partition key
        if result:
            return User(**result)
        return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address"""
        query = "SELECT * FROM c WHERE c.email = @email"
        parameters = [{"name": "@email", "value": email.lower().strip()}]
        
        results = await self.query(query, parameters)
        if results:
            return User(**results[0])
        return None
    
    async def update_user(self, user_id: str, user_update: UserUpdate) -> User:
        """Update user information"""
        # Get existing user
        existing_user = await self.get_user_by_id(user_id)
        if not existing_user:
            raise ItemNotFoundError(f"User with id {user_id} not found")
        
        # Update fields
        update_data = user_update.model_dump(exclude_unset=True)
        user_dict = existing_user.model_dump()
        user_dict.update(update_data)
        
        # Update in database
        result = await self.update(user_dict, user_id)
        
        return User(**result)
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user"""
        return await self.delete(user_id, user_id)
    
    async def update_user_streak(self, user_id: str, universe: str, increment: bool = True) -> User:
        """Update user's streak for a specific universe"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ItemNotFoundError(f"User with id {user_id} not found")
        
        # Update streak
        if increment:
            user.streaks[universe] = user.streaks.get(universe, 0) + 1
        else:
            user.streaks[universe] = 0
        
        # Update last played date
        today = datetime.utcnow().strftime('%Y-%m-%d')
        user.last_played[universe] = today
        
        # Convert to dict and update
        user_dict = user.model_dump()
        result = await self.update(user_dict, user_id)
        
        return User(**result)
    
    async def update_user_stats(self, user_id: str, won: bool = False) -> User:
        """Update user's game statistics"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ItemNotFoundError(f"User with id {user_id} not found")
        
        # Update stats
        user.total_games += 1
        if won:
            user.total_wins += 1
        
        # Convert to dict and update
        user_dict = user.model_dump()
        result = await self.update(user_dict, user_id)
        
        return User(**result)
    
    async def get_user_stats(self, user_id: str) -> UserStats:
        """Get user statistics"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ItemNotFoundError(f"User with id {user_id} not found")
        
        return UserStats.from_user(user)
    
    async def get_users_by_username_pattern(self, pattern: str, limit: int = 10) -> List[User]:
        """Get users matching a username pattern (for search/autocomplete)"""
        query = "SELECT * FROM c WHERE CONTAINS(LOWER(c.username), @pattern) ORDER BY c.username OFFSET 0 LIMIT @limit"
        parameters = [
            {"name": "@pattern", "value": pattern.lower()},
            {"name": "@limit", "value": limit}
        ]
        
        results = await self.query(query, parameters)
        return [User(**result) for result in results]
    
    async def get_top_users_by_universe(self, universe: str, limit: int = 10) -> List[User]:
        """Get top users by streak for a specific universe"""
        query = f"SELECT * FROM c WHERE c.streaks.{universe} > 0 ORDER BY c.streaks.{universe} DESC OFFSET 0 LIMIT @limit"
        parameters = [{"name": "@limit", "value": limit}]
        
        results = await self.query(query, parameters)
        return [User(**result) for result in results]
    
    async def get_users_count(self) -> int:
        """Get total number of users"""
        query = "SELECT VALUE COUNT(1) FROM c"
        results = await self.query(query)
        return results[0] if results else 0
    
    async def get_user_count(self) -> int:
        """Alias for get_users_count for consistency"""
        return await self.get_users_count()
    
    async def get_users_paginated(self, limit: int = 50, offset: int = 0) -> List[User]:
        """Get users with pagination"""
        query = "SELECT * FROM c ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
        parameters = [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit}
        ]
        
        results = await self.query(query, parameters)
        return [User(**result) for result in results]
    
    async def cleanup_inactive_users(self, days_inactive: int = 365) -> int:
        """Clean up users who haven't played in specified days"""
        cutoff_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        # This is a simplified version - in production you'd want more sophisticated cleanup
        query = """
        SELECT c.id FROM c 
        WHERE (c.last_played.marvel IS NULL OR c.last_played.marvel < @cutoff_date)
        AND (c.last_played.DC IS NULL OR c.last_played.DC < @cutoff_date)  
        AND (c.last_played.image IS NULL OR c.last_played.image < @cutoff_date)
        AND c.total_games = 0
        """
        parameters = [{"name": "@cutoff_date", "value": cutoff_date}]
        
        inactive_users = await self.query(query, parameters)
        
        deleted_count = 0
        for user_data in inactive_users:
            if await self.delete_user(user_data['id']):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} inactive users")
        return deleted_count