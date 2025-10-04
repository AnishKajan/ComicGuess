from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import uuid
import re

class Guess(BaseModel):
    """Guess model for user puzzle attempts"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique guess identifier")
    user_id: str = Field(..., description="ID of the user making the guess")
    puzzle_id: str = Field(..., description="ID of the puzzle being guessed")
    guess: str = Field(..., min_length=1, max_length=100, description="The character name guess")
    is_correct: bool = Field(..., description="Whether the guess was correct")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the guess was made")
    attempt_number: int = Field(..., ge=1, le=6, description="Attempt number for this puzzle (1-6)")
    
    @field_validator('guess')
    @classmethod
    def validate_guess(cls, v):
        """Validate and normalize the guess"""
        if not v.strip():
            raise ValueError('Guess cannot be empty')
        # Normalize whitespace
        return ' '.join(v.strip().split())
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """Validate user ID format"""
        if not v.strip():
            raise ValueError('User ID cannot be empty')
        return v
    
    @field_validator('puzzle_id')
    @classmethod
    def validate_puzzle_id(cls, v):
        """Validate puzzle ID format"""
        if not v.strip():
            raise ValueError('Puzzle ID cannot be empty')
        # Should match YYYYMMDD-universe format
        pattern = r'^\d{8}-(marvel|DC|image)$'
        if not re.match(pattern, v):
            raise ValueError('Puzzle ID must be in format YYYYMMDD-universe')
        return v
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class GuessCreate(BaseModel):
    """Model for creating a new guess"""
    user_id: str = Field(...)
    puzzle_id: str = Field(...)
    guess: str = Field(..., min_length=1, max_length=100)
    
    @field_validator('guess')
    @classmethod
    def validate_guess(cls, v):
        if not v.strip():
            raise ValueError('Guess cannot be empty')
        return ' '.join(v.strip().split())
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        if not v.strip():
            raise ValueError('User ID cannot be empty')
        return v
    
    @field_validator('puzzle_id')
    @classmethod
    def validate_puzzle_id(cls, v):
        if not v.strip():
            raise ValueError('Puzzle ID cannot be empty')
        pattern = r'^\d{8}-(marvel|DC|image)$'
        if not re.match(pattern, v):
            raise ValueError('Puzzle ID must be in format YYYYMMDD-universe')
        return v

class GuessResponse(BaseModel):
    """Model for guess API responses"""
    correct: bool = Field(..., description="Whether the guess was correct")
    character: Optional[str] = Field(None, description="Character name (only if correct)")
    character_name: Optional[str] = Field(None, description="Character name (only if correct)")
    image_url: Optional[str] = Field(None, description="Character image URL (only if correct)")
    character_image_url: Optional[str] = Field(None, description="Character image URL (only if correct)")
    image_is_fallback: bool = Field(default=False, description="Whether the image is a fallback placeholder")
    streak: int = Field(..., description="Current streak for this universe")
    attempt_number: int = Field(..., description="Current attempt number")
    max_attempts: int = Field(default=6, description="Maximum attempts allowed")
    game_over: bool = Field(default=False, description="Whether the game is over (won or max attempts reached)")

class GuessHistory(BaseModel):
    """Model for user's guess history for a specific puzzle"""
    puzzle_id: str
    guesses: list[str] = Field(default_factory=list, description="List of guesses made")
    is_solved: bool = Field(default=False, description="Whether the puzzle has been solved")
    attempts_used: int = Field(default=0, description="Number of attempts used")