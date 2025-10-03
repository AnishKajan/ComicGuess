"""Validation utilities for ComicGuess models"""

import re
from typing import List, Set
from datetime import datetime

class CharacterNameValidator:
    """Utility class for validating and normalizing character names"""
    
    # Common character name patterns that should be allowed
    ALLOWED_PATTERNS = [
        r'^[a-zA-Z0-9\s\-\'\.]+$',  # Letters, numbers, spaces, hyphens, apostrophes, periods
    ]
    
    # Characters that should be normalized
    NORMALIZATION_MAP = {
        "'": "'",  # Smart apostrophe to regular apostrophe
        '"': '"',  # Smart quotes to regular quotes
        '"': '"',
        '–': '-',  # En dash to hyphen
        '—': '-',  # Em dash to hyphen
    }
    
    @classmethod
    def normalize_name(cls, name: str) -> str:
        """Normalize a character name for consistent comparison"""
        if not name:
            return ""
        
        # Apply character normalization
        normalized = name
        for old_char, new_char in cls.NORMALIZATION_MAP.items():
            normalized = normalized.replace(old_char, new_char)
        
        # Normalize whitespace
        normalized = ' '.join(normalized.strip().split())
        
        return normalized
    
    @classmethod
    def is_valid_character_name(cls, name: str) -> bool:
        """Check if a character name is valid"""
        if not name or not name.strip():
            return False
        
        normalized = cls.normalize_name(name)
        
        # Check against allowed patterns
        for pattern in cls.ALLOWED_PATTERNS:
            if re.match(pattern, normalized):
                return True
        
        return False
    
    @classmethod
    def validate_aliases(cls, aliases: List[str]) -> List[str]:
        """Validate and clean a list of character aliases"""
        cleaned_aliases = []
        seen_aliases = set()
        
        for alias in aliases:
            if not alias or not alias.strip():
                continue
            
            normalized = cls.normalize_name(alias)
            
            if not cls.is_valid_character_name(normalized):
                continue
            
            # Avoid duplicates (case-insensitive)
            lower_normalized = normalized.lower()
            if lower_normalized not in seen_aliases:
                cleaned_aliases.append(normalized)
                seen_aliases.add(lower_normalized)
        
        return cleaned_aliases

class UniverseValidator:
    """Utility class for validating comic universes"""
    
    VALID_UNIVERSES: Set[str] = {"marvel", "dc", "image"}
    
    @classmethod
    def is_valid_universe(cls, universe: str) -> bool:
        """Check if a universe is valid"""
        return universe.lower() in cls.VALID_UNIVERSES
    
    @classmethod
    def normalize_universe(cls, universe: str) -> str:
        """Normalize universe name to lowercase"""
        return universe.lower() if universe else ""

class PuzzleIdValidator:
    """Utility class for validating puzzle IDs"""
    
    PUZZLE_ID_PATTERN = re.compile(r'^(\d{8})-(marvel|dc|image)$')
    
    @classmethod
    def is_valid_puzzle_id(cls, puzzle_id: str) -> bool:
        """Check if a puzzle ID is valid"""
        if not puzzle_id:
            return False
        
        match = cls.PUZZLE_ID_PATTERN.match(puzzle_id)
        if not match:
            return False
        
        date_part = match.group(1)
        
        # Validate the date part
        try:
            datetime.strptime(date_part, '%Y%m%d')
            return True
        except ValueError:
            return False
    
    @classmethod
    def generate_puzzle_id(cls, date: datetime, universe: str) -> str:
        """Generate a puzzle ID from date and universe"""
        if not UniverseValidator.is_valid_universe(universe):
            raise ValueError(f"Invalid universe: {universe}")
        
        date_str = date.strftime('%Y%m%d')
        normalized_universe = UniverseValidator.normalize_universe(universe)
        
        return f"{date_str}-{normalized_universe}"
    
    @classmethod
    def parse_puzzle_id(cls, puzzle_id: str) -> tuple[datetime, str]:
        """Parse a puzzle ID into date and universe components"""
        if not cls.is_valid_puzzle_id(puzzle_id):
            raise ValueError(f"Invalid puzzle ID format: {puzzle_id}")
        
        match = cls.PUZZLE_ID_PATTERN.match(puzzle_id)
        date_part = match.group(1)
        universe_part = match.group(2)
        
        date = datetime.strptime(date_part, '%Y%m%d')
        
        return date, universe_part

class GuessValidator:
    """Utility class for validating guesses"""
    
    MAX_ATTEMPTS = 6
    MIN_GUESS_LENGTH = 1
    MAX_GUESS_LENGTH = 100
    
    @classmethod
    def is_valid_guess(cls, guess: str) -> bool:
        """Check if a guess is valid"""
        if not guess or not guess.strip():
            return False
        
        normalized = CharacterNameValidator.normalize_name(guess)
        
        if len(normalized) < cls.MIN_GUESS_LENGTH or len(normalized) > cls.MAX_GUESS_LENGTH:
            return False
        
        return CharacterNameValidator.is_valid_character_name(normalized)
    
    @classmethod
    def normalize_guess(cls, guess: str) -> str:
        """Normalize a guess for comparison"""
        return CharacterNameValidator.normalize_name(guess)
    
    @classmethod
    def is_valid_attempt_number(cls, attempt_number: int) -> bool:
        """Check if an attempt number is valid"""
        return 1 <= attempt_number <= cls.MAX_ATTEMPTS

def validate_email(email: str) -> bool:
    """Basic email validation"""
    if not email or '@' not in email:
        return False
    
    parts = email.split('@')
    if len(parts) != 2:
        return False
    
    local, domain = parts
    if not local or not domain:
        return False
    
    if '.' not in domain:
        return False
    
    return True

def validate_username(username: str) -> bool:
    """Validate username format"""
    if not username or len(username) < 3 or len(username) > 50:
        return False
    
    # Allow letters, numbers, hyphens, underscores, and periods
    return re.match(r'^[a-zA-Z0-9_\-\.]+$', username) is not None