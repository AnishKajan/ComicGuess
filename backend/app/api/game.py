"""Game API endpoints for puzzle and guess operations"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from pydantic import BaseModel, Field

from app.services.puzzle_service import PuzzleService
from app.services.guess_service import GuessValidationService
from app.services.image_service import image_service
from app.services.cache_service import cache_headers
from app.models.guess import GuessResponse, GuessHistory
from app.models.puzzle import PuzzleResponse
from app.auth.middleware import get_current_user
from app.database.exceptions import ItemNotFoundError
from app.middleware.rate_limiting import guess_rate_limit
from app.security.input_validation import (
    validate_guess_request, 
    ValidationError, 
    InputSanitizer
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["game"])

# Initialize services
puzzle_service = PuzzleService()
guess_service = GuessValidationService()

class GuessRequest(BaseModel):
    """Request model for submitting a guess"""
    user_id: str = Field(..., description="ID of the user making the guess")
    universe: str = Field(..., description="Comic universe (marvel, dc, image)")
    guess: str = Field(..., min_length=1, max_length=100, description="Character name guess")

class PuzzleStatusResponse(BaseModel):
    """Response model for puzzle status"""
    puzzle_id: str
    universe: str
    active_date: str
    can_guess: bool
    is_solved: bool
    attempts_used: int
    attempts_remaining: int
    max_attempts: int

@router.post("/guess", response_model=GuessResponse)
async def submit_guess(
    guess_request: GuessRequest,
    response: Response,
    current_user: dict = Depends(get_current_user),
    _rate_limit: bool = Depends(guess_rate_limit)
) -> GuessResponse:
    """
    Submit a character name guess for today's puzzle
    
    - **user_id**: ID of the user making the guess
    - **universe**: Comic universe (marvel, dc, or image)
    - **guess**: Character name guess
    
    Returns guess result with correctness, streak, and game status
    """
    try:
        # Validate and sanitize input
        validated_data = validate_guess_request({
            "user_id": guess_request.user_id,
            "universe": guess_request.universe,
            "guess": guess_request.guess
        })
        
        # Use validated data
        user_id = validated_data["user_id"]
        universe = validated_data["universe"]
        guess = validated_data["guess"]
        
        # Get today's puzzle ID
        today_date = puzzle_service.get_today_date()
        puzzle_id = puzzle_service.generate_puzzle_id(today_date, universe)
        
        # Check if puzzle exists
        puzzle = await puzzle_service.get_daily_puzzle(universe, today_date)
        if not puzzle:
            raise HTTPException(
                status_code=404,
                detail=f"No puzzle available for {universe} today"
            )
        
        # Validate and process guess
        result = await guess_service.validate_guess(
            user_id=user_id,
            puzzle_id=puzzle_id,
            guess=guess
        )
        
        # If guess is correct, add character image information
        if result.correct and result.character_name:
            try:
                image_info = await image_service.get_character_image_url(
                    universe, result.character_name
                )
                result.character_image_url = image_info["url"]
                result.image_is_fallback = image_info["is_fallback"]
            except Exception as e:
                logger.warning(f"Failed to get image for {result.character_name}: {e}")
                # Don't fail the guess if image retrieval fails
                result.character_image_url = None
                result.image_is_fallback = True
        
        logger.info(f"Guess submitted by user {user_id} for {puzzle_id}: {guess} -> {result.correct}")
        
        # Set cache headers for personalized response
        headers = cache_headers.get_no_cache_headers()
        for key, value in headers.items():
            response.headers[key] = value
        
        return result
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ItemNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing guess: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/puzzle/today", response_model=PuzzleResponse)
async def get_today_puzzle(
    response: Response,
    universe: str = Query(..., description="Comic universe (marvel, dc, image)"),
    current_user: dict = Depends(get_current_user)
) -> PuzzleResponse:
    """
    Get today's puzzle for a specific universe
    
    - **universe**: Comic universe (marvel, dc, or image)
    
    Returns puzzle information without revealing the answer
    """
    try:
        # Validate and sanitize universe parameter
        universe = InputSanitizer.validate_universe(universe)
        
        # Get today's puzzle
        puzzle_response = await puzzle_service.get_daily_puzzle_response(universe)
        
        if not puzzle_response:
            raise HTTPException(
                status_code=404,
                detail=f"No puzzle available for {universe} today"
            )
        
        logger.info(f"Puzzle requested for {universe}: {puzzle_response.id}")
        
        # Set cache headers for puzzle metadata (public cache)
        headers = cache_headers.get_puzzle_cache_headers(is_personalized=False)
        for key, value in headers.items():
            response.headers[key] = value
        
        return puzzle_response
        
    except ValidationError:
        raise  # Re-raise validation errors as-is
    except Exception as e:
        logger.error(f"Error getting today's puzzle: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/puzzle/{puzzle_id}/status", response_model=PuzzleStatusResponse)
async def get_puzzle_status(
    puzzle_id: str,
    response: Response,
    user_id: str = Query(..., description="User ID to check status for"),
    current_user: dict = Depends(get_current_user)
) -> PuzzleStatusResponse:
    """
    Get puzzle status for a specific user
    
    - **puzzle_id**: Puzzle ID in format YYYYMMDD-universe
    - **user_id**: User ID to check status for
    
    Returns puzzle status including attempts and solve status
    """
    try:
        # Validate puzzle ID format
        if '-' not in puzzle_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid puzzle ID format. Expected YYYYMMDD-universe"
            )
        
        universe = puzzle_id.split('-')[1]
        if universe not in ["marvel", "dc", "image"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid universe in puzzle ID"
            )
        
        # Check if puzzle exists
        puzzle = await puzzle_service.puzzle_repository.get_puzzle_by_id(puzzle_id)
        if not puzzle:
            raise HTTPException(
                status_code=404,
                detail=f"Puzzle {puzzle_id} not found"
            )
        
        # Get user's guess status
        guess_status = await guess_service.can_user_guess(user_id, puzzle_id)
        
        # Set cache headers for personalized response
        headers = cache_headers.get_puzzle_cache_headers(is_personalized=True)
        for key, value in headers.items():
            response.headers[key] = value
        
        return PuzzleStatusResponse(
            puzzle_id=puzzle_id,
            universe=universe,
            active_date=puzzle.active_date,
            can_guess=guess_status["can_guess"],
            is_solved=guess_status["is_solved"],
            attempts_used=guess_status["attempts_used"],
            attempts_remaining=guess_status["attempts_remaining"],
            max_attempts=guess_status["max_attempts"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting puzzle status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/puzzle/{puzzle_id}/history", response_model=GuessHistory)
async def get_guess_history(
    puzzle_id: str,
    user_id: str = Query(..., description="User ID to get history for"),
    current_user: dict = Depends(get_current_user)
) -> GuessHistory:
    """
    Get user's guess history for a specific puzzle
    
    - **puzzle_id**: Puzzle ID in format YYYYMMDD-universe
    - **user_id**: User ID to get history for
    
    Returns list of guesses made by the user for this puzzle
    """
    try:
        # Validate puzzle ID format
        if '-' not in puzzle_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid puzzle ID format. Expected YYYYMMDD-universe"
            )
        
        # Check if puzzle exists
        puzzle = await puzzle_service.puzzle_repository.get_puzzle_by_id(puzzle_id)
        if not puzzle:
            raise HTTPException(
                status_code=404,
                detail=f"Puzzle {puzzle_id} not found"
            )
        
        # Get guess history
        history = await guess_service.get_user_guess_history(user_id, puzzle_id)
        
        return history
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting guess history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/daily-progress", response_model=dict)
async def get_daily_progress(
    user_id: str = Query(..., description="User ID to get progress for"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get user's daily progress across all universes
    
    - **user_id**: User ID to get progress for
    - **date**: Date in YYYY-MM-DD format (optional, defaults to today)
    
    Returns progress status for all three universes
    """
    try:
        progress = await guess_service.get_daily_progress(user_id, date)
        
        return {
            "date": date or puzzle_service.get_today_date(),
            "user_id": user_id,
            "universes": progress
        }
        
    except Exception as e:
        logger.error(f"Error getting daily progress: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/streak-status", response_model=dict)
async def get_streak_status(
    user_id: str = Query(..., description="User ID to get streak status for"),
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Get user's current streak status and maintenance requirements
    
    - **user_id**: User ID to get streak status for
    
    Returns current streaks and today's completion status
    """
    try:
        # Get streak statistics
        streak_stats = await guess_service.calculate_streak_statistics(user_id)
        
        # Get streak maintenance status
        maintenance_status = await guess_service.check_streak_maintenance(user_id)
        
        return {
            "user_id": user_id,
            "streak_statistics": streak_stats,
            "maintenance_status": maintenance_status,
            "date": puzzle_service.get_today_date()
        }
        
    except ItemNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting streak status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/simulate-guess", response_model=dict)
async def simulate_guess(
    guess_request: GuessRequest,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Simulate a guess without recording it (for testing/preview)
    
    - **user_id**: ID of the user making the guess
    - **universe**: Comic universe (marvel, dc, image)
    - **guess**: Character name guess
    
    Returns what the outcome would be without actually recording the guess
    """
    try:
        # Validate universe
        if guess_request.universe not in ["marvel", "dc", "image"]:
            raise HTTPException(
                status_code=400,
                detail="Universe must be one of: marvel, dc, image"
            )
        
        # Get today's puzzle ID
        today_date = puzzle_service.get_today_date()
        puzzle_id = puzzle_service.generate_puzzle_id(today_date, guess_request.universe)
        
        # Check if puzzle exists
        puzzle = await puzzle_service.get_daily_puzzle(guess_request.universe, today_date)
        if not puzzle:
            raise HTTPException(
                status_code=404,
                detail=f"No puzzle available for {guess_request.universe} today"
            )
        
        # Simulate guess
        result = await guess_service.simulate_guess_outcome(
            user_id=guess_request.user_id,
            puzzle_id=puzzle_id,
            guess=guess_request.guess
        )
        
        return {
            "simulation": True,
            "puzzle_id": puzzle_id,
            "guess": guess_request.guess,
            **result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ItemNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error simulating guess: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint for the game API"""
    return {
        "status": "healthy",
        "service": "game-api",
        "timestamp": puzzle_service.get_today_date()
    }