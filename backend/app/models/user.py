from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, Optional
from datetime import datetime
import uuid


class User(BaseModel):
    """User model for ComicGuess application"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique user identifier")
    username: str = Field(..., min_length=3, max_length=50, description="User's display name")
    email: str = Field(..., description="User's email address")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Account creation timestamp")
    streaks: Dict[str, int] = Field(
        default_factory=lambda: {"marvel": 0, "DC": 0, "image": 0},
        description="Current streaks per universe"
    )
    last_played: Dict[str, Optional[str]] = Field(
        default_factory=lambda: {"marvel": None, "DC": None, "image": None},
        description="Last played date per universe (YYYY-MM-DD)"
    )
    total_games: int = Field(default=0, ge=0, description="Total number of games played")
    total_wins: int = Field(default=0, ge=0, description="Total number of games won")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Basic email validation"""
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email format')
        return v.lower().strip()
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Username validation - alphanumeric and basic characters only"""
        if not v.strip():
            raise ValueError('Username cannot be empty')
        
        # Allow letters, numbers, hyphens, underscores, and periods
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.')
        if not all(c in allowed_chars for c in v):
            raise ValueError('Username can only contain letters, numbers, hyphens, underscores, and periods')
        
        return v.strip()
    
    @field_validator('streaks')
    @classmethod
    def validate_streaks(cls, v):
        """Ensure all required universes are present in streaks"""
        required_universes = {"marvel", "DC", "image"}
        if not isinstance(v, dict):
            raise ValueError('Streaks must be a dictionary')
        
        # Ensure all required universes are present
        for universe in required_universes:
            if universe not in v:
                v[universe] = 0
            elif not isinstance(v[universe], int) or v[universe] < 0:
                raise ValueError(f'Streak for {universe} must be a non-negative integer')
        
        return v
    
    @field_validator('last_played')
    @classmethod
    def validate_last_played(cls, v):
        """Ensure all required universes are present in last_played"""
        required_universes = {"marvel", "DC", "image"}
        if not isinstance(v, dict):
            raise ValueError('Last played must be a dictionary')
        
        # Ensure all required universes are present
        for universe in required_universes:
            if universe not in v:
                v[universe] = None
            elif v[universe] is not None:
                # Validate date format YYYY-MM-DD
                try:
                    datetime.strptime(v[universe], '%Y-%m-%d')
                except ValueError:
                    raise ValueError(f'Invalid date format for {universe}. Use YYYY-MM-DD')
        
        return v
    
    @model_validator(mode='after')
    def validate_total_wins(self):
        """Ensure total wins doesn't exceed total games"""
        if self.total_wins > self.total_games:
            raise ValueError('Total wins cannot exceed total games')
        return self
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class UserCreate(BaseModel):
    """Model for creating a new user"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(...)
    
    @field_validator('email')
    @classmethod
    def validate_email_create(cls, v):
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email format')
        return v.lower().strip()
    
    @field_validator('username')
    @classmethod
    def validate_username_create(cls, v):
        if not v.strip():
            raise ValueError('Username cannot be empty')
        
        # Allow letters, numbers, hyphens, underscores, and periods
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.')
        if not all(c in allowed_chars for c in v):
            raise ValueError('Username can only contain letters, numbers, hyphens, underscores, and periods')
        
        return v.strip()


class UserUpdate(BaseModel):
    """Model for updating user information"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = None
    
    @field_validator('email')
    @classmethod
    def validate_email_update(cls, v):
        if v and ('@' not in v or '.' not in v.split('@')[-1]):
            raise ValueError('Invalid email format')
        return v.lower().strip() if v else v
    
    @field_validator('username')
    @classmethod
    def validate_username_update(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError('Username cannot be empty')
            
            # Allow letters, numbers, hyphens, underscores, and periods
            allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.')
            if not all(c in allowed_chars for c in v):
                raise ValueError('Username can only contain letters, numbers, hyphens, underscores, and periods')
            
            return v.strip()
        return v


class UserStats(BaseModel):
    """Model for user statistics display"""
    total_games: int
    total_wins: int
    win_rate: float = Field(..., ge=0.0, le=1.0)
    streaks: Dict[str, int]
    last_played: Dict[str, Optional[str]]
    
    @classmethod
    def from_user(cls, user: User) -> 'UserStats':
        """Create UserStats from User model"""
        win_rate = user.total_wins / user.total_games if user.total_games > 0 else 0.0
        return cls(
            total_games=user.total_games,
            total_wins=user.total_wins,
            win_rate=win_rate,
            streaks=user.streaks,
            last_played=user.last_played
        )