# Data access repositories

from .base import BaseRepository
from .user_repository import UserRepository
from .puzzle_repository import PuzzleRepository
from .guess_repository import GuessRepository

__all__ = [
    "BaseRepository",
    "UserRepository", 
    "PuzzleRepository",
    "GuessRepository"
]