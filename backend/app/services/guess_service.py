"""Guess validation and streak management service"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import re

from app.models.guess import Guess, GuessCreate, GuessResponse, GuessHistory
from app.models.user import User
from app.repositories.guess_repository import GuessRepository
from app.repositories.user_repository import UserRepository
from app.services.puzzle_service import PuzzleService
from app.database.exceptions import ItemNotFoundError

logger = logging.getLogger(__name__)

class GuessValidationService:
    """Service for guess validation and streak management"""
    
    def __init__(self):
        self.guess_repository = GuessRepository()
        self.user_repository = UserRepository()
        self.puzzle_service = PuzzleService()
        self.max_attempts = 6
        self.universes = ["marvel", "dc", "image"]
    
    def normalize_guess(self, guess: str) -> str:
        """Normalize a guess for comparison"""
        # Remove extra whitespace and convert to lowercase
        normalized = ' '.join(guess.strip().lower().split())
        
        # Remove common punctuation that might interfere with matching
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        
        # Handle common variations
        normalized = normalized.replace('-', ' ')  # Convert hyphens to spaces
        normalized = ' '.join(normalized.split())  # Remove extra spaces again
        
        return normalized
    
    def character_name_matches(self, guess: str, character_name: str, aliases: List[str]) -> bool:
        """Check if a guess matches a character name or any of its aliases"""
        normalized_guess = self.normalize_guess(guess)
        
        # Check main character name
        normalized_character = self.normalize_guess(character_name)
        if normalized_guess == normalized_character:
            return True
        
        # Check aliases
        for alias in aliases:
            normalized_alias = self.normalize_guess(alias)
            if normalized_guess == normalized_alias:
                return True
        
        # Check partial matches for common cases
        return self._check_partial_matches(normalized_guess, normalized_character, aliases)
    
    def _check_partial_matches(self, guess: str, character: str, aliases: List[str]) -> bool:
        """Check for partial matches that should be considered correct"""
        # Handle cases like "spider man" vs "spider-man"
        guess_no_spaces = guess.replace(' ', '')
        character_no_spaces = character.replace(' ', '')
        
        if guess_no_spaces == character_no_spaces:
            return True
        
        # Check aliases without spaces
        for alias in aliases:
            alias_no_spaces = self.normalize_guess(alias).replace(' ', '')
            if guess_no_spaces == alias_no_spaces:
                return True
        
        return False
    
    async def validate_guess(self, user_id: str, puzzle_id: str, guess: str) -> GuessResponse:
        """Validate a guess and return comprehensive response"""
        # Get user
        user = await self.user_repository.get_user_by_id(user_id)
        if not user:
            raise ItemNotFoundError(f"User {user_id} not found")
        
        # Extract universe from puzzle ID
        universe = puzzle_id.split('-')[1] if '-' in puzzle_id else None
        if not universe or universe not in self.universes:
            raise ValueError(f"Invalid puzzle ID format: {puzzle_id}")
        
        # Check if user can make a guess
        can_guess = await self.guess_repository.can_user_make_guess(user_id, puzzle_id, self.max_attempts)
        if not can_guess:
            # Check if already solved
            is_solved = await self.guess_repository.has_user_solved_puzzle(user_id, puzzle_id)
            if is_solved:
                raise ValueError("Puzzle already solved")
            else:
                raise ValueError(f"Maximum attempts ({self.max_attempts}) reached")
        
        # Get current attempt number
        attempt_number = await self.guess_repository.get_next_attempt_number(user_id, puzzle_id)
        
        # Validate guess against puzzle
        is_correct, character_name, image_key = await self.puzzle_service.validate_puzzle_guess(puzzle_id, guess)
        
        # Create guess record
        guess_data = GuessCreate(
            user_id=user_id,
            puzzle_id=puzzle_id,
            guess=guess
        )
        
        await self.guess_repository.create_guess(guess_data, is_correct, attempt_number)
        
        # Update user streak
        current_streak = await self._update_user_streak(user_id, universe, is_correct)
        
        # Determine if game is over
        game_over = is_correct or attempt_number >= self.max_attempts
        
        # Build image URL if correct
        image_url = None
        if is_correct and image_key:
            image_url = self._build_image_url(image_key)
        
        return GuessResponse(
            correct=is_correct,
            character=character_name,
            image_url=image_url,
            streak=current_streak,
            attempt_number=attempt_number,
            max_attempts=self.max_attempts,
            game_over=game_over
        )
    
    async def _update_user_streak(self, user_id: str, universe: str, is_correct: bool) -> int:
        """Update user's streak for a universe"""
        user = await self.user_repository.get_user_by_id(user_id)
        if not user:
            raise ItemNotFoundError(f"User {user_id} not found")
        
        current_streaks = user.streaks.copy()
        
        if is_correct:
            # Increment streak
            current_streaks[universe] = current_streaks.get(universe, 0) + 1
        else:
            # Check if this was the final attempt
            attempts_count = await self.guess_repository.get_user_attempts_count(user_id, 
                                                                               self._get_today_puzzle_id(universe))
            if attempts_count >= self.max_attempts:
                # Reset streak on failure to solve
                current_streaks[universe] = 0
        
        # Update user streaks
        await self.user_repository.update_user(user_id, {"streaks": current_streaks})
        
        return current_streaks.get(universe, 0)
    
    def _get_today_puzzle_id(self, universe: str) -> str:
        """Get today's puzzle ID for a universe"""
        today = datetime.utcnow().strftime('%Y%m%d')
        return f"{today}-{universe}"
    
    def _build_image_url(self, image_key: str) -> str:
        """Build full image URL from image key"""
        # This would typically use your CDN/blob storage base URL
        # For now, return a placeholder structure
        base_url = "https://your-cdn-domain.com"  # Replace with actual CDN URL
        return f"{base_url}/{image_key}"
    
    async def get_user_guess_history(self, user_id: str, puzzle_id: str) -> GuessHistory:
        """Get user's guess history for a puzzle"""
        return await self.guess_repository.get_user_guess_history(user_id, puzzle_id)
    
    async def can_user_guess(self, user_id: str, puzzle_id: str) -> Dict[str, Any]:
        """Check if user can make a guess and return status"""
        is_solved = await self.guess_repository.has_user_solved_puzzle(user_id, puzzle_id)
        attempts_count = await self.guess_repository.get_user_attempts_count(user_id, puzzle_id)
        can_guess = await self.guess_repository.can_user_make_guess(user_id, puzzle_id, self.max_attempts)
        
        return {
            "can_guess": can_guess,
            "is_solved": is_solved,
            "attempts_used": attempts_count,
            "attempts_remaining": max(0, self.max_attempts - attempts_count),
            "max_attempts": self.max_attempts
        }
    
    async def get_daily_progress(self, user_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Get user's progress for all universes on a specific date"""
        if date is None:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        progress = {}
        
        for universe in self.universes:
            puzzle_id = self.puzzle_service.generate_puzzle_id(date, universe)
            
            # Check if puzzle exists
            puzzle = await self.puzzle_service.get_daily_puzzle(universe, date)
            if not puzzle:
                progress[universe] = {
                    "puzzle_available": False,
                    "puzzle_id": puzzle_id
                }
                continue
            
            # Get guess status
            guess_status = await self.can_user_guess(user_id, puzzle_id)
            guess_history = await self.get_user_guess_history(user_id, puzzle_id)
            
            progress[universe] = {
                "puzzle_available": True,
                "puzzle_id": puzzle_id,
                "is_solved": guess_status["is_solved"],
                "attempts_used": guess_status["attempts_used"],
                "attempts_remaining": guess_status["attempts_remaining"],
                "can_guess": guess_status["can_guess"],
                "guesses": guess_history.guesses
            }
        
        return progress
    
    async def calculate_streak_statistics(self, user_id: str) -> Dict[str, Any]:
        """Calculate comprehensive streak statistics for a user"""
        user = await self.user_repository.get_user_by_id(user_id)
        if not user:
            raise ItemNotFoundError(f"User {user_id} not found")
        
        current_streaks = user.streaks
        
        # Calculate additional statistics
        stats = {
            "current_streaks": current_streaks,
            "total_current_streak": sum(current_streaks.values()),
            "best_universe": max(current_streaks.items(), key=lambda x: x[1])[0] if current_streaks else None,
            "best_streak_value": max(current_streaks.values()) if current_streaks else 0
        }
        
        # Get historical data for max streaks (would need additional tracking)
        # For now, current streaks are the max streaks
        stats["max_streaks"] = current_streaks.copy()
        
        return stats
    
    async def reset_streak(self, user_id: str, universe: str) -> int:
        """Reset streak for a specific universe"""
        user = await self.user_repository.get_user_by_id(user_id)
        if not user:
            raise ItemNotFoundError(f"User {user_id} not found")
        
        current_streaks = user.streaks.copy()
        current_streaks[universe] = 0
        
        await self.user_repository.update_user(user_id, {"streaks": current_streaks})
        
        return 0
    
    async def validate_bulk_guesses(self, guesses: List[Dict[str, Any]]) -> List[GuessResponse]:
        """Validate multiple guesses (for testing or batch operations)"""
        responses = []
        
        for guess_data in guesses:
            try:
                response = await self.validate_guess(
                    user_id=guess_data["user_id"],
                    puzzle_id=guess_data["puzzle_id"],
                    guess=guess_data["guess"]
                )
                responses.append(response)
            except Exception as e:
                logger.error(f"Error validating guess {guess_data}: {e}")
                # Create error response
                error_response = GuessResponse(
                    correct=False,
                    character=None,
                    image_url=None,
                    streak=0,
                    attempt_number=0,
                    max_attempts=self.max_attempts,
                    game_over=True
                )
                responses.append(error_response)
        
        return responses
    
    async def get_guess_analytics(self, puzzle_id: str) -> Dict[str, Any]:
        """Get analytics for guesses on a specific puzzle"""
        return await self.guess_repository.get_puzzle_guess_statistics(puzzle_id)
    
    async def get_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get analytics for a specific user's guessing patterns"""
        base_stats = await self.guess_repository.get_user_guess_statistics(user_id)
        streak_stats = await self.calculate_streak_statistics(user_id)
        
        return {
            **base_stats,
            **streak_stats
        }
    
    async def check_streak_maintenance(self, user_id: str) -> Dict[str, Any]:
        """Check if user needs to play today to maintain streaks"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        progress = await self.get_daily_progress(user_id, today)
        
        streak_status = {}
        
        for universe in self.universes:
            universe_progress = progress.get(universe, {})
            
            if not universe_progress.get("puzzle_available", False):
                streak_status[universe] = {
                    "status": "no_puzzle",
                    "message": "No puzzle available today"
                }
                continue
            
            if universe_progress.get("is_solved", False):
                streak_status[universe] = {
                    "status": "completed",
                    "message": "Puzzle solved - streak maintained"
                }
            elif universe_progress.get("can_guess", False):
                streak_status[universe] = {
                    "status": "pending",
                    "message": "Puzzle not attempted - streak at risk",
                    "attempts_remaining": universe_progress.get("attempts_remaining", 0)
                }
            else:
                # Max attempts reached without solving
                streak_status[universe] = {
                    "status": "failed",
                    "message": "Puzzle failed - streak will be reset"
                }
        
        return streak_status
    
    async def simulate_guess_outcome(self, user_id: str, puzzle_id: str, guess: str) -> Dict[str, Any]:
        """Simulate a guess without actually recording it (for testing/preview)"""
        # Get puzzle
        is_correct, character_name, image_key = await self.puzzle_service.validate_puzzle_guess(puzzle_id, guess)
        
        # Get current attempt number
        attempt_number = await self.guess_repository.get_next_attempt_number(user_id, puzzle_id)
        
        # Get current user streak
        user = await self.user_repository.get_user_by_id(user_id)
        universe = puzzle_id.split('-')[1] if '-' in puzzle_id else None
        current_streak = user.streaks.get(universe, 0) if user else 0
        
        # Calculate what streak would be
        if is_correct:
            new_streak = current_streak + 1
        else:
            # Would reset if this is the final attempt
            if attempt_number >= self.max_attempts:
                new_streak = 0
            else:
                new_streak = current_streak
        
        return {
            "would_be_correct": is_correct,
            "character_name": character_name if is_correct else None,
            "current_streak": current_streak,
            "new_streak": new_streak,
            "attempt_number": attempt_number,
            "game_would_end": is_correct or attempt_number >= self.max_attempts
        }