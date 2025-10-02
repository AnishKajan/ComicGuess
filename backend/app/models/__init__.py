"""Data models for ComicGuess application"""

from .user import User, UserCreate, UserUpdate, UserStats
from .puzzle import Puzzle, PuzzleCreate, PuzzleResponse
from .guess import Guess, GuessCreate, GuessResponse, GuessHistory
from .validation import (
    CharacterNameValidator,
    UniverseValidator, 
    PuzzleIdValidator,
    GuessValidator,
    validate_email,
    validate_username
)

__all__ = [
    # User models
    "User",
    "UserCreate", 
    "UserUpdate",
    "UserStats",
    
    # Puzzle models
    "Puzzle",
    "PuzzleCreate",
    "PuzzleResponse",
    
    # Guess models
    "Guess",
    "GuessCreate",
    "GuessResponse",
    "GuessHistory",
    
    # Validation utilities
    "CharacterNameValidator",
    "UniverseValidator",
    "PuzzleIdValidator", 
    "GuessValidator",
    "validate_email",
    "validate_username"
]