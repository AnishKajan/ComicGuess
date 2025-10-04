"""Streak management endpoints"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Literal

from app.models.user import User
from app.repositories.streak_repository import StreakRepository
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaks", tags=["streaks"])

# Request/Response models
class UpdateStreakRequest(BaseModel):
    publisher: Literal["marvel", "dc", "image"] = Field(..., description="Publisher name")
    result: Literal["success", "fail"] = Field(..., description="Game result")
    playedDateUTC: str = Field(..., description="Date played in YYYY-MM-DD format")

class StreakResponse(BaseModel):
    current: int
    longest: int

class AllStreaksResponse(BaseModel):
    marvel: StreakResponse
    dc: StreakResponse
    image: StreakResponse

# Initialize repository
streak_repo = StreakRepository()

async def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authenticated user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user

@router.get("", response_model=AllStreaksResponse)
async def get_all_streaks(current_user: User = Depends(require_auth)):
    """Get all streaks for the current user"""
    try:
        streaks = await streak_repo.get_user_streaks(current_user.userId)
        
        return AllStreaksResponse(
            marvel=StreakResponse(**streaks["marvel"]),
            dc=StreakResponse(**streaks["dc"]),
            image=StreakResponse(**streaks["image"])
        )
        
    except Exception as e:
        logger.error(f"Error getting streaks for user {current_user.userId}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/publisher", response_model=StreakResponse)
async def get_streak_by_publisher(
    publisher: Literal["marvel", "dc", "image"] = Query(..., description="Publisher name"),
    current_user: User = Depends(require_auth)
):
    """Get streak for a specific publisher"""
    try:
        streak = await streak_repo.get_streak(current_user.userId, publisher)
        
        if streak:
            return StreakResponse(
                current=streak.currentStreak,
                longest=streak.longestStreak
            )
        else:
            return StreakResponse(current=0, longest=0)
            
    except Exception as e:
        logger.error(f"Error getting streak for user {current_user.userId}, publisher {publisher}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("", response_model=StreakResponse)
async def update_streak(
    request: UpdateStreakRequest,
    current_user: User = Depends(require_auth)
):
    """Update streak based on game result"""
    try:
        # Validate date format
        try:
            datetime.strptime(request.playedDateUTC, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Update streak
        streak = await streak_repo.create_or_update_streak(
            user_id=current_user.userId,
            publisher=request.publisher,
            result=request.result,
            played_date_utc=request.playedDateUTC
        )
        
        return StreakResponse(
            current=streak.currentStreak,
            longest=streak.longestStreak
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating streak for user {current_user.userId}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")