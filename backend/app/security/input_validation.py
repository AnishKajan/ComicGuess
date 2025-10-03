"""Input validation and sanitization utilities"""

import re
import html
import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class InputSanitizer:
    """Utility class for sanitizing user input"""
    
    # Regex patterns for validation
    PATTERNS = {
        "username": re.compile(r"^[a-zA-Z0-9_-]{3,30}$"),
        "email": re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]*[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$|^[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$"),
        "character_name": re.compile(r"^[a-zA-Z0-9\s\-'\.()]{1,100}$"),
        "universe": re.compile(r"^(marvel|dc|image)$"),
        "puzzle_id": re.compile(r"^\d{8}-(marvel|dc|image)$"),
        "user_id": re.compile(r"^[a-zA-Z0-9_-]{1,50}$"),
        "alphanumeric": re.compile(r"^[a-zA-Z0-9]+$"),
        "safe_string": re.compile(r"^[a-zA-Z0-9\s\-_.,!?()]{0,500}$")
    }
    
    # Dangerous characters and patterns
    DANGEROUS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL),
        re.compile(r"<object[^>]*>.*?</object>", re.IGNORECASE | re.DOTALL),
        re.compile(r"<embed[^>]*>", re.IGNORECASE),
        re.compile(r"<link[^>]*>", re.IGNORECASE),
        re.compile(r"<meta[^>]*>", re.IGNORECASE),
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)", re.IGNORECASE),
        re.compile(r"(\b(OR|AND)\s+\d+\s*=\s*\d+)", re.IGNORECASE),
        re.compile(r"'.*?'", re.IGNORECASE),
        re.compile(r"--", re.IGNORECASE),
        re.compile(r"/\*.*?\*/", re.IGNORECASE | re.DOTALL),
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 500, allow_html: bool = False) -> str:
        """
        Sanitize a string input
        
        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML (will be escaped)
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError: If input is invalid or dangerous
        """
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        
        # Check length
        if len(value) > max_length:
            raise ValueError(f"Input too long (max {max_length} characters)")
        
        # Remove null bytes and control characters
        value = value.replace('\x00', '').replace('\r', '').replace('\n', ' ')
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(value):
                logger.warning(f"Dangerous pattern detected in input: {value[:50]}...")
                raise ValueError("Input contains potentially dangerous content")
        
        # Check for SQL injection patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                logger.warning(f"SQL injection pattern detected in input: {value[:50]}...")
                raise ValueError("Input contains potentially dangerous SQL patterns")
        
        # HTML escape if not allowing HTML
        if not allow_html:
            value = html.escape(value)
        
        # Trim whitespace
        value = value.strip()
        
        return value
    
    @classmethod
    def validate_username(cls, username: str) -> str:
        """Validate and sanitize username"""
        username = cls.sanitize_string(username, max_length=30)
        
        if not cls.PATTERNS["username"].match(username):
            raise ValueError("Username must be 3-30 characters, alphanumeric, underscore, or hyphen only")
        
        return username
    
    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate and sanitize email address"""
        email = cls.sanitize_string(email, max_length=254).lower()
        
        if not cls.PATTERNS["email"].match(email):
            raise ValueError("Invalid email format")
        
        return email
    
    @classmethod
    def validate_character_name(cls, name: str) -> str:
        """Validate and sanitize character name for guesses"""
        name = cls.sanitize_string(name, max_length=100)
        
        if not name:
            raise ValueError("Character name cannot be empty")
        
        if not cls.PATTERNS["character_name"].match(name):
            raise ValueError("Character name contains invalid characters")
        
        # Normalize whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    @classmethod
    def validate_universe(cls, universe: str) -> str:
        """Validate universe parameter"""
        universe = cls.sanitize_string(universe, max_length=10).lower()
        
        if not cls.PATTERNS["universe"].match(universe):
            raise ValueError("Universe must be one of: marvel, dc, image")
        
        return universe
    
    @classmethod
    def validate_puzzle_id(cls, puzzle_id: str) -> str:
        """Validate puzzle ID format"""
        puzzle_id = cls.sanitize_string(puzzle_id, max_length=20)
        
        if not cls.PATTERNS["puzzle_id"].match(puzzle_id):
            raise ValueError("Invalid puzzle ID format (expected: YYYYMMDD-universe)")
        
        return puzzle_id
    
    @classmethod
    def validate_user_id(cls, user_id: str) -> str:
        """Validate user ID"""
        user_id = cls.sanitize_string(user_id, max_length=50)
        
        if not cls.PATTERNS["user_id"].match(user_id):
            raise ValueError("Invalid user ID format")
        
        return user_id
    
    @classmethod
    def validate_url(cls, url: str, allowed_schemes: List[str] = None) -> str:
        """Validate URL format and scheme"""
        if allowed_schemes is None:
            allowed_schemes = ["http", "https"]
        
        url = cls.sanitize_string(url, max_length=2048)
        
        try:
            parsed = urlparse(url)
            if parsed.scheme not in allowed_schemes:
                raise ValueError(f"URL scheme must be one of: {allowed_schemes}")
            
            if not parsed.netloc:
                raise ValueError("URL must have a valid domain")
            
            return url
        except Exception as e:
            raise ValueError(f"Invalid URL format: {str(e)}")
    
    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any], allowed_keys: List[str] = None) -> Dict[str, Any]:
        """
        Sanitize dictionary input by validating keys and values
        
        Args:
            data: Dictionary to sanitize
            allowed_keys: List of allowed keys (if None, all keys allowed)
            
        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary")
        
        sanitized = {}
        
        for key, value in data.items():
            # Validate key
            if not isinstance(key, str):
                raise ValueError("Dictionary keys must be strings")
            
            key = cls.sanitize_string(key, max_length=100)
            
            if allowed_keys and key not in allowed_keys:
                logger.warning(f"Unexpected key in input: {key}")
                continue  # Skip unexpected keys
            
            # Sanitize value based on type
            if isinstance(value, str):
                value = cls.sanitize_string(value, max_length=1000)
            elif isinstance(value, (int, float, bool)):
                pass  # These types are safe
            elif isinstance(value, list):
                value = cls.sanitize_list(value)
            elif isinstance(value, dict):
                value = cls.sanitize_dict(value)
            else:
                raise ValueError(f"Unsupported value type: {type(value)}")
            
            sanitized[key] = value
        
        return sanitized
    
    @classmethod
    def sanitize_list(cls, data: List[Any], max_items: int = 100) -> List[Any]:
        """Sanitize list input"""
        if not isinstance(data, list):
            raise ValueError("Input must be a list")
        
        if len(data) > max_items:
            raise ValueError(f"List too long (max {max_items} items)")
        
        sanitized = []
        
        for item in data:
            if isinstance(item, str):
                item = cls.sanitize_string(item, max_length=500)
            elif isinstance(item, (int, float, bool)):
                pass  # These types are safe
            elif isinstance(item, dict):
                item = cls.sanitize_dict(item)
            else:
                raise ValueError(f"Unsupported list item type: {type(item)}")
            
            sanitized.append(item)
        
        return sanitized

class ValidationError(HTTPException):
    """Custom exception for validation errors"""
    
    def __init__(self, detail: str, field: str = None):
        super().__init__(
            status_code=400,
            detail={
                "error": "Validation Error",
                "message": detail,
                "field": field
            }
        )

def validate_request_data(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate request data against a schema
    
    Args:
        data: Request data to validate
        schema: Validation schema with field rules
        
    Returns:
        Validated and sanitized data
        
    Raises:
        ValidationError: If validation fails
    """
    try:
        sanitizer = InputSanitizer()
        validated = {}
        
        for field, rules in schema.items():
            value = data.get(field)
            
            # Check required fields
            if rules.get("required", False) and value is None:
                raise ValidationError(f"Field '{field}' is required", field)
            
            if value is None:
                continue
            
            # Apply field-specific validation
            field_type = rules.get("type", "string")
            
            if field_type == "string":
                max_length = rules.get("max_length", 500)
                pattern = rules.get("pattern")
                
                value = sanitizer.sanitize_string(value, max_length)
                
                if pattern and not re.match(pattern, value):
                    raise ValidationError(f"Field '{field}' format is invalid", field)
            
            elif field_type == "username":
                value = sanitizer.validate_username(value)
            
            elif field_type == "email":
                value = sanitizer.validate_email(value)
            
            elif field_type == "character_name":
                value = sanitizer.validate_character_name(value)
            
            elif field_type == "universe":
                value = sanitizer.validate_universe(value)
            
            elif field_type == "puzzle_id":
                value = sanitizer.validate_puzzle_id(value)
            
            elif field_type == "user_id":
                value = sanitizer.validate_user_id(value)
            
            elif field_type == "integer":
                if not isinstance(value, int):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise ValidationError(f"Field '{field}' must be an integer", field)
                
                min_val = rules.get("min")
                max_val = rules.get("max")
                
                if min_val is not None and value < min_val:
                    raise ValidationError(f"Field '{field}' must be at least {min_val}", field)
                
                if max_val is not None and value > max_val:
                    raise ValidationError(f"Field '{field}' must be at most {max_val}", field)
            
            elif field_type == "boolean":
                if not isinstance(value, bool):
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes", "on")
                    else:
                        raise ValidationError(f"Field '{field}' must be a boolean", field)
            
            validated[field] = value
        
        return validated
    
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected validation error: {e}")
        raise ValidationError("Invalid input data")

# Validation schemas for common endpoints
VALIDATION_SCHEMAS = {
    "guess_request": {
        "user_id": {"type": "user_id", "required": True},
        "universe": {"type": "universe", "required": True},
        "guess": {"type": "character_name", "required": True}
    },
    "user_update": {
        "username": {"type": "username", "required": False},
        "email": {"type": "email", "required": False},
        "preferences": {"type": "string", "max_length": 1000, "required": False}
    },
    "puzzle_query": {
        "universe": {"type": "universe", "required": True},
        "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "required": False}
    }
}

def validate_guess_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate guess request data"""
    return validate_request_data(data, VALIDATION_SCHEMAS["guess_request"])

def validate_user_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate user update data"""
    return validate_request_data(data, VALIDATION_SCHEMAS["user_update"])

def validate_puzzle_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate puzzle query parameters"""
    return validate_request_data(data, VALIDATION_SCHEMAS["puzzle_query"])