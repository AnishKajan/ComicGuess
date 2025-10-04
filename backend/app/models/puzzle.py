from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional
from datetime import datetime
import re

class Puzzle(BaseModel):
    """Puzzle model for daily comic character puzzles"""
    
    id: str = Field(..., description="Puzzle ID in format YYYYMMDD-universe")
    universe: str = Field(..., description="Comic universe: marvel, DC, or image")
    character: str = Field(..., min_length=1, max_length=100, description="Character name (correct answer)")
    character_aliases: List[str] = Field(default_factory=list, description="Alternative names/spellings for the character")
    image_key: str = Field(..., description="Azure Blob Storage path for character image")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Puzzle creation timestamp")
    active_date: str = Field(..., description="Date when puzzle is active (YYYY-MM-DD)")
    
    @field_validator('universe')
    @classmethod
    def validate_universe(cls, v):
        """Validate universe is one of the allowed values"""
        allowed_universes = {"marvel", "DC", "image"}
        if v.lower() not in allowed_universes:
            raise ValueError(f'Universe must be one of: {allowed_universes}')
        return v.lower()
    
    @field_validator('id')
    @classmethod
    def validate_puzzle_id(cls, v):
        """Validate puzzle ID format: YYYYMMDD-universe"""
        pattern = r'^\d{8}-(marvel|DC|image)$'
        if not re.match(pattern, v):
            raise ValueError('Puzzle ID must be in format YYYYMMDD-universe (e.g., 20240115-marvel)')
        
        # Extract date part and validate
        date_part = v.split('-')[0]
        try:
            datetime.strptime(date_part, '%Y%m%d')
        except ValueError:
            raise ValueError('Date part of puzzle ID must be valid YYYYMMDD format')
        
        return v
    
    @field_validator('active_date')
    @classmethod
    def validate_active_date(cls, v):
        """Validate active date format"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Active date must be in YYYY-MM-DD format')
        return v
    
    @field_validator('character')
    @classmethod
    def validate_character(cls, v):
        """Basic character name validation"""
        if not v.strip():
            raise ValueError('Character name cannot be empty')
        # Remove extra whitespace
        return ' '.join(v.split())
    
    @field_validator('character_aliases')
    @classmethod
    def validate_character_aliases(cls, v):
        """Validate character aliases"""
        # Remove empty strings and duplicates, normalize whitespace
        cleaned_aliases = []
        for alias in v:
            if alias and alias.strip():
                normalized = ' '.join(alias.strip().split())
                if normalized not in cleaned_aliases:
                    cleaned_aliases.append(normalized)
        return cleaned_aliases
    
    @model_validator(mode='after')
    def validate_consistency(self):
        """Validate consistency between fields"""
        # Ensure universe in ID matches universe field
        if self.id:
            universe_from_id = self.id.split('-')[1] if '-' in self.id else ''
            if universe_from_id != self.universe:
                raise ValueError('Universe in puzzle ID must match universe field')
        
        # Ensure image key follows universe-based folder structure
        expected_prefix = f"{self.universe}/"
        if not self.image_key.startswith(expected_prefix):
            raise ValueError(f'Image key must start with "{expected_prefix}" for {self.universe} universe')
        
        return self
    
    def get_all_valid_names(self) -> List[str]:
        """Get all valid names for this character (main name + aliases)"""
        return [self.character] + self.character_aliases
    
    def is_correct_guess(self, guess: str) -> bool:
        """Check if a guess matches this puzzle's character"""
        normalized_guess = ' '.join(guess.strip().lower().split())
        valid_names = [name.lower() for name in self.get_all_valid_names()]
        normalized_valid_names = [' '.join(name.split()) for name in valid_names]
        
        return normalized_guess in normalized_valid_names
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class PuzzleCreate(BaseModel):
    """Model for creating a new puzzle"""
    universe: str = Field(...)
    character: str = Field(..., min_length=1, max_length=100)
    character_aliases: List[str] = Field(default_factory=list)
    image_key: str = Field(...)
    active_date: str = Field(...)
    
    @field_validator('universe')
    @classmethod
    def validate_universe(cls, v):
        allowed_universes = {"marvel", "DC", "image"}
        if v.lower() not in allowed_universes:
            raise ValueError(f'Universe must be one of: {allowed_universes}')
        return v.lower()
    
    @field_validator('active_date')
    @classmethod
    def validate_active_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Active date must be in YYYY-MM-DD format')
        return v
    
    @field_validator('character')
    @classmethod
    def validate_character(cls, v):
        if not v.strip():
            raise ValueError('Character name cannot be empty')
        return ' '.join(v.split())
    
    @field_validator('character_aliases')
    @classmethod
    def validate_character_aliases(cls, v):
        cleaned_aliases = []
        for alias in v:
            if alias and alias.strip():
                normalized = ' '.join(alias.strip().split())
                if normalized not in cleaned_aliases:
                    cleaned_aliases.append(normalized)
        return cleaned_aliases

class PuzzleResponse(BaseModel):
    """Model for puzzle API responses (without revealing the answer)"""
    id: str
    universe: str
    active_date: str
    # Note: character and character_aliases are intentionally excluded
    # to prevent revealing the answer before it's solved