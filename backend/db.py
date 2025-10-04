"""
Simple Azure Cosmos DB helper functions for FastAPI backend.
This module provides simple helper functions that work with the existing infrastructure.
"""
import asyncio
from typing import Optional, Dict, Any
from app.database import get_cosmos_db
from app.repositories.user_repository import UserRepository
from app.models.user import User, UserCreate
import logging

logger = logging.getLogger(__name__)

# Initialize user repository
user_repo = UserRepository()

async def add_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new user to the database.
    
    Args:
        user: User data dictionary containing username and email
        
    Returns:
        Created user document as dictionary
        
    Example:
        user_data = {"username": "john_doe", "email": "john@example.com"}
        created_user = await add_user(user_data)
    """
    try:
        # Create UserCreate model from dict
        user_create = UserCreate(
            username=user["username"],
            email=user["email"]
        )
        
        # Create user using repository
        created_user = await user_repo.create_user(user_create)
        
        # Return as dictionary
        return created_user.model_dump()
        
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise

async def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user by their ID.
    
    Args:
        user_id: The user's unique identifier
        
    Returns:
        User document as dictionary if found, None otherwise
        
    Example:
        user = await get_user("123e4567-e89b-12d3-a456-426614174000")
        if user:
            print(f"Found user: {user['username']}")
    """
    try:
        user = await user_repo.get_user_by_id(user_id)
        if user:
            return user.model_dump()
        return None
        
    except Exception as e:
        logger.error(f"Failed to retrieve user {user_id}: {e}")
        raise

async def update_user(user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update an existing user.
    
    Args:
        user_id: The user's unique identifier
        updates: Dictionary of fields to update
        
    Returns:
        Updated user document as dictionary if successful, None if user not found
        
    Example:
        updates = {"username": "new_username"}
        updated_user = await update_user(user_id, updates)
    """
    try:
        from app.models.user import UserUpdate
        
        # Create UserUpdate model from dict
        user_update = UserUpdate(**updates)
        
        # Update user using repository
        updated_user = await user_repo.update_user(user_id, user_update)
        
        # Return as dictionary
        return updated_user.model_dump()
        
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        raise

async def delete_user(user_id: str) -> bool:
    """
    Delete a user by their ID.
    
    Args:
        user_id: The user's unique identifier
        
    Returns:
        True if deleted successfully, False if user not found
    """
    try:
        return await user_repo.delete_user(user_id)
        
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}")
        raise

# Test the connection
async def test_connection():
    """Test the Cosmos DB connection."""
    try:
        cosmos_db = await get_cosmos_db()
        health_result = await cosmos_db.health_check()
        logger.info(f"Cosmos DB connection test: {health_result}")
        return health_result
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise