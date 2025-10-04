"""
Data rights API endpoints for GDPR/COPPA compliance.
Handles user data export, deletion, and rights management.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
from datetime import datetime, timezone

from ..auth.middleware import get_current_user
from ..models.user import User
from ..repositories.user_repository import UserRepository
from ..repositories.guess_repository import GuessRepository
from ..repositories.puzzle_repository import PuzzleRepository
from ..database.connection import get_database

router = APIRouter(prefix="/api/user", tags=["data-rights"])

@router.get("/{user_id}/export")
async def export_user_data(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Response:
    """
    Export all user data in JSON format for data portability rights.
    
    Args:
        user_id: The user ID to export data for
        current_user: The authenticated user making the request
        db: Database connection
        
    Returns:
        JSON file containing all user data
        
    Raises:
        HTTPException: If user not found or unauthorized
    """
    # Verify user can only export their own data
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only export your own data"
        )
    
    try:
        user_repo = UserRepository(db)
        guess_repo = GuessRepository(db)
        puzzle_repo = PuzzleRepository(db)
        
        # Get user data
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get all user guesses
        guesses = await guess_repo.get_by_user_id(user_id)
        
        # Get puzzle details for guesses
        puzzle_ids = list(set(guess.puzzle_id for guess in guesses))
        puzzles = {}
        for puzzle_id in puzzle_ids:
            puzzle = await puzzle_repo.get_by_id(puzzle_id)
            if puzzle:
                puzzles[puzzle_id] = {
                    "id": puzzle.id,
                    "universe": puzzle.universe,
                    "character": puzzle.character,
                    "active_date": puzzle.active_date
                }
        
        # Compile export data
        export_data = {
            "export_info": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "data_version": "1.0"
            },
            "user_profile": {
                "id": user.id,
                "username": user.username,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "streaks": user.streaks,
                "last_played": user.last_played,
                "total_games": user.total_games,
                "total_wins": user.total_wins
            },
            "gameplay_history": [
                {
                    "guess_id": guess.id,
                    "puzzle_id": guess.puzzle_id,
                    "puzzle_info": puzzles.get(guess.puzzle_id, {}),
                    "guess": guess.guess,
                    "is_correct": guess.is_correct,
                    "timestamp": guess.timestamp.isoformat() if guess.timestamp else None,
                    "attempt_number": guess.attempt_number
                }
                for guess in guesses
            ],
            "statistics": {
                "total_guesses": len(guesses),
                "correct_guesses": sum(1 for g in guesses if g.is_correct),
                "accuracy_rate": (
                    sum(1 for g in guesses if g.is_correct) / len(guesses) * 100
                    if guesses else 0
                ),
                "universes_played": list(set(
                    puzzles.get(g.puzzle_id, {}).get("universe", "unknown")
                    for g in guesses
                )),
                "first_game": min(
                    (g.timestamp for g in guesses if g.timestamp),
                    default=None
                ),
                "last_game": max(
                    (g.timestamp for g in guesses if g.timestamp),
                    default=None
                )
            }
        }
        
        # Convert to JSON string
        json_data = json.dumps(export_data, indent=2, default=str)
        
        # Return as downloadable file
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=comicguess-data-{user_id}-{datetime.now().strftime('%Y%m%d')}.json"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export user data: {str(e)}"
        )

@router.delete("/{user_id}")
async def delete_user_account(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Delete user account and all associated data for right to erasure.
    
    Args:
        user_id: The user ID to delete
        current_user: The authenticated user making the request
        db: Database connection
        
    Returns:
        Confirmation of deletion
        
    Raises:
        HTTPException: If user not found or unauthorized
    """
    # Verify user can only delete their own account
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own account"
        )
    
    try:
        user_repo = UserRepository(db)
        guess_repo = GuessRepository(db)
        
        # Verify user exists
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete all user guesses first (foreign key constraint)
        await guess_repo.delete_by_user_id(user_id)
        
        # Delete user account
        await user_repo.delete(user_id)
        
        return {
            "success": True,
            "message": "Account and all associated data have been permanently deleted",
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete user account: {str(e)}"
        )

@router.get("/{user_id}/data-summary")
async def get_user_data_summary(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get a summary of what data we have for the user.
    
    Args:
        user_id: The user ID to get summary for
        current_user: The authenticated user making the request
        db: Database connection
        
    Returns:
        Summary of user data
        
    Raises:
        HTTPException: If user not found or unauthorized
    """
    # Verify user can only view their own data summary
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only view your own data summary"
        )
    
    try:
        user_repo = UserRepository(db)
        guess_repo = GuessRepository(db)
        
        # Get user data
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get guess count
        guesses = await guess_repo.get_by_user_id(user_id)
        
        return {
            "user_id": user_id,
            "data_categories": {
                "profile_data": {
                    "description": "Username, creation date, and account preferences",
                    "items": ["username", "created_at", "account_settings"]
                },
                "game_statistics": {
                    "description": "Puzzle completion streaks and performance metrics",
                    "items": ["streaks", "total_games", "total_wins", "last_played"]
                },
                "gameplay_history": {
                    "description": "Individual guesses and puzzle attempts",
                    "count": len(guesses),
                    "items": ["guesses", "timestamps", "puzzle_results"]
                }
            },
            "data_retention": {
                "active_retention": "Data retained while account is active",
                "inactive_deletion": "Account automatically deleted after 2 years of inactivity",
                "manual_deletion": "Can be deleted immediately upon request"
            },
            "your_rights": [
                "Access your data",
                "Export your data",
                "Correct inaccurate data", 
                "Delete your account",
                "Restrict data processing",
                "Object to data processing"
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get data summary: {str(e)}"
        )