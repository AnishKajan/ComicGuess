"""User management API endpoints"""

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Path
from fastapi.responses import JSONResponse

from app.models.user import User, UserUpdate, UserStats
from app.repositories.user_repository import UserRepository
from app.auth.middleware import get_current_user, require_user_access
from app.database.exceptions import ItemNotFoundError, DuplicateItemError
from app.security.input_validation import ValidationError, InputSanitizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["users"])

# Dependency to get user repository
async def get_user_repository() -> UserRepository:
    """Dependency to get user repository instance"""
    return UserRepository()

@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: Annotated[str, Path(..., description="User ID to retrieve")],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get user data by ID.
    
    Users can only access their own data.
    
    Args:
        user_id: The ID of the user to retrieve
        current_user: The authenticated user (must match user_id)
        user_repo: User repository instance
    
    Returns:
        User: The user data
    
    Raises:
        HTTPException: 404 if user not found, 403 if access denied
    """
    try:
        # Validate and sanitize user_id
        user_id = InputSanitizer.validate_user_id(user_id)
        
        # Check access permission
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot access other user's data"
            )
        
        user = await user_repo.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )
        
        logger.info(f"Retrieved user data for user: {user_id}")
        return user
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except HTTPException:
        raise
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving user"
        )

@router.post("/{user_id}", response_model=User)
async def update_user(
    user_id: Annotated[str, Path(..., description="User ID to update")],
    user_update: UserUpdate,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Update user profile information.
    
    Users can only update their own profile.
    
    Args:
        user_id: The ID of the user to update
        user_update: The user update data
        current_user: The authenticated user (must match user_id)
        user_repo: User repository instance
    
    Returns:
        User: The updated user data
    
    Raises:
        HTTPException: 404 if user not found, 403 if access denied, 400 if validation fails
    """
    try:
        # Check access permission
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot access other user's data"
            )
        
        # Check if user exists
        existing_user = await user_repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )
        
        # Check for email conflicts if email is being updated
        if user_update.email and user_update.email != existing_user.email:
            existing_email_user = await user_repo.get_user_by_email(user_update.email)
            if existing_email_user and existing_email_user.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address is already in use by another user"
                )
        
        # Update user
        updated_user = await user_repo.update_user(user_id, user_update)
        
        logger.info(f"Updated user profile for user: {user_id}")
        return updated_user
        
    except HTTPException:
        raise
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    except DuplicateItemError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while updating user"
        )

@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: Annotated[str, Path(..., description="User ID to get stats for")],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    current_user: Annotated[User, Depends(get_current_user)]
) -> UserStats:
    """
    Get user statistics for display.
    
    Users can only access their own statistics.
    
    Args:
        user_id: The ID of the user to get stats for
        current_user: The authenticated user (must match user_id)
        user_repo: User repository instance
    
    Returns:
        UserStats: The user statistics
    
    Raises:
        HTTPException: 404 if user not found, 403 if access denied
    """
    try:
        # Check access permission
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot access other user's data"
            )
        
        user_stats = await user_repo.get_user_stats(user_id)
        
        logger.info(f"Retrieved user stats for user: {user_id}")
        return user_stats
        
    except HTTPException:
        raise
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving user stats for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving user statistics"
        )

