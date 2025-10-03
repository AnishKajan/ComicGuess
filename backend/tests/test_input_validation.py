"""Tests for input validation and sanitization utilities"""

import pytest
from unittest.mock import patch

from app.security.input_validation import (
    InputSanitizer,
    ValidationError,
    validate_request_data,
    validate_guess_request,
    validate_user_update,
    validate_puzzle_query,
    VALIDATION_SCHEMAS
)

class TestInputSanitizer:
    """Test the InputSanitizer class methods"""
    
    def test_sanitize_string_valid(self):
        """Test sanitizing valid strings"""
        result = InputSanitizer.sanitize_string("Hello World", max_length=20)
        assert result == "Hello World"
        
        result = InputSanitizer.sanitize_string("  Test  ", max_length=20)
        assert result == "Test"
    
    def test_sanitize_string_html_escape(self):
        """Test HTML escaping in string sanitization"""
        # Test safe HTML that gets escaped
        result = InputSanitizer.sanitize_string("<b>Bold Text</b>", max_length=100)
        assert result == "&lt;b&gt;Bold Text&lt;/b&gt;"
        
        # Test that dangerous patterns are rejected
        with pytest.raises(ValueError, match="dangerous content"):
            InputSanitizer.sanitize_string("<script>alert('xss')</script>", max_length=100)
    
    def test_sanitize_string_too_long(self):
        """Test string length validation"""
        with pytest.raises(ValueError, match="too long"):
            InputSanitizer.sanitize_string("a" * 501, max_length=500)
    
    def test_sanitize_string_not_string(self):
        """Test non-string input"""
        with pytest.raises(ValueError, match="must be a string"):
            InputSanitizer.sanitize_string(123)
    
    def test_sanitize_string_dangerous_patterns(self):
        """Test detection of dangerous patterns"""
        dangerous_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<iframe src='evil.com'></iframe>",
            "onclick='alert(1)'",
            "<object data='evil.swf'></object>"
        ]
        
        for dangerous_input in dangerous_inputs:
            with pytest.raises(ValueError, match="dangerous content"):
                InputSanitizer.sanitize_string(dangerous_input)
    
    def test_sanitize_string_sql_injection(self):
        """Test detection of SQL injection patterns"""
        sql_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "UNION SELECT * FROM passwords",
            "/* comment */ SELECT",
            "admin'--"
        ]
        
        for sql_input in sql_inputs:
            with pytest.raises(ValueError, match="SQL patterns"):
                InputSanitizer.sanitize_string(sql_input)
    
    def test_validate_username_valid(self):
        """Test valid username validation"""
        valid_usernames = ["user123", "test_user", "user-name", "abc"]
        
        for username in valid_usernames:
            result = InputSanitizer.validate_username(username)
            assert result == username
    
    def test_validate_username_invalid(self):
        """Test invalid username validation"""
        invalid_usernames = [
            "ab",  # Too short
            "a" * 31,  # Too long
            "user@name",  # Invalid character
            "user name",  # Space not allowed
            "user.name",  # Dot not allowed
            ""  # Empty
        ]
        
        for username in invalid_usernames:
            with pytest.raises(ValueError):
                InputSanitizer.validate_username(username)
    
    def test_validate_email_valid(self):
        """Test valid email validation"""
        valid_emails = [
            "user@example.com",
            "test.user+tag@domain.co.uk",
            "user123@test-domain.org"
        ]
        
        for email in valid_emails:
            result = InputSanitizer.validate_email(email)
            assert result == email.lower()
    
    def test_validate_email_invalid(self):
        """Test invalid email validation"""
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@",
            "user@domain"
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid email format"):
                InputSanitizer.validate_email(email)
        
        # Test empty email separately as it might raise a different error
        with pytest.raises(ValueError):
            InputSanitizer.validate_email("")
    
    def test_validate_character_name_valid(self):
        """Test valid character name validation"""
        valid_names = [
            "Spider-Man",
            "Iron Man",
            "Dr. Strange",
            "Jean Grey",
            "X-23",
            "Wolverine (Logan)"
        ]
        
        for name in valid_names:
            result = InputSanitizer.validate_character_name(name)
            assert result == name
    
    def test_validate_character_name_invalid(self):
        """Test invalid character name validation"""
        invalid_names = [
            "",  # Empty
            "Character@Name",  # Invalid character
            "a" * 101,  # Too long
        ]
        
        for name in invalid_names:
            with pytest.raises(ValueError):
                InputSanitizer.validate_character_name(name)
    
    def test_validate_character_name_whitespace_normalization(self):
        """Test character name whitespace normalization"""
        result = InputSanitizer.validate_character_name("  Spider   Man  ")
        assert result == "Spider Man"
        
        result = InputSanitizer.validate_character_name("Iron\t\tMan")
        assert result == "Iron Man"
    
    def test_validate_universe_valid(self):
        """Test valid universe validation"""
        valid_universes = ["marvel", "dc", "image", "MARVEL", "DC", "IMAGE"]
        expected = ["marvel", "dc", "image", "marvel", "dc", "image"]
        
        for universe, expected_result in zip(valid_universes, expected):
            result = InputSanitizer.validate_universe(universe)
            assert result == expected_result
    
    def test_validate_universe_invalid(self):
        """Test invalid universe validation"""
        invalid_universes = ["disney", "vertigo", "", "marvel comics", "dc-comics"]
        
        for universe in invalid_universes:
            with pytest.raises(ValueError):
                InputSanitizer.validate_universe(universe)
    
    def test_validate_puzzle_id_valid(self):
        """Test valid puzzle ID validation"""
        valid_ids = [
            "20240101-marvel",
            "20231225-dc",
            "20240229-image"  # Leap year
        ]
        
        for puzzle_id in valid_ids:
            result = InputSanitizer.validate_puzzle_id(puzzle_id)
            assert result == puzzle_id
    
    def test_validate_puzzle_id_invalid(self):
        """Test invalid puzzle ID validation"""
        invalid_ids = [
            "2024-01-01-marvel",  # Wrong format
            "20240101-disney",  # Invalid universe
            "20240101",  # Missing universe
            "marvel-20240101",  # Wrong order
            "",  # Empty
            "20240101-marvel-extra"  # Extra parts
        ]
        
        for puzzle_id in invalid_ids:
            with pytest.raises(ValueError):
                InputSanitizer.validate_puzzle_id(puzzle_id)
    
    def test_validate_user_id_valid(self):
        """Test valid user ID validation"""
        valid_ids = ["user123", "test_user", "user-name", "a", "a" * 50]
        
        for user_id in valid_ids:
            result = InputSanitizer.validate_user_id(user_id)
            assert result == user_id
    
    def test_validate_user_id_invalid(self):
        """Test invalid user ID validation"""
        invalid_ids = [
            "",  # Empty
            "a" * 51,  # Too long
            "user@name",  # Invalid character
            "user name",  # Space not allowed
            "user.name"  # Dot not allowed
        ]
        
        for user_id in invalid_ids:
            with pytest.raises(ValueError):
                InputSanitizer.validate_user_id(user_id)
    
    def test_validate_url_valid(self):
        """Test valid URL validation"""
        valid_urls = [
            "https://example.com",
            "http://test.domain.org/path",
            "https://sub.domain.com:8080/path?query=value"
        ]
        
        for url in valid_urls:
            result = InputSanitizer.validate_url(url)
            assert result == url
    
    def test_validate_url_invalid_scheme(self):
        """Test URL validation with invalid schemes"""
        with pytest.raises(ValueError):
            InputSanitizer.validate_url("ftp://example.com")
        
        with pytest.raises(ValueError):
            InputSanitizer.validate_url("javascript:alert(1)")
    
    def test_validate_url_custom_schemes(self):
        """Test URL validation with custom allowed schemes"""
        result = InputSanitizer.validate_url("ftp://example.com", allowed_schemes=["ftp"])
        assert result == "ftp://example.com"
    
    def test_validate_url_no_domain(self):
        """Test URL validation without domain"""
        with pytest.raises(ValueError):
            InputSanitizer.validate_url("https://")
    
    def test_sanitize_dict_valid(self):
        """Test dictionary sanitization"""
        data = {
            "name": "Test User",
            "age": 25,
            "active": True
        }
        
        result = InputSanitizer.sanitize_dict(data)
        assert result["name"] == "Test User"
        assert result["age"] == 25
        assert result["active"] is True
    
    def test_sanitize_dict_with_allowed_keys(self):
        """Test dictionary sanitization with allowed keys"""
        data = {
            "name": "Test User",
            "age": 25,
            "secret": "should be filtered"
        }
        
        result = InputSanitizer.sanitize_dict(data, allowed_keys=["name", "age"])
        assert "name" in result
        assert "age" in result
        assert "secret" not in result
    
    def test_sanitize_dict_invalid_key_type(self):
        """Test dictionary sanitization with invalid key type"""
        data = {123: "invalid key"}
        
        with pytest.raises(ValueError, match="keys must be strings"):
            InputSanitizer.sanitize_dict(data)
    
    def test_sanitize_dict_nested(self):
        """Test nested dictionary sanitization"""
        data = {
            "user": {
                "name": "Test User",
                "preferences": {
                    "theme": "dark"
                }
            }
        }
        
        result = InputSanitizer.sanitize_dict(data)
        assert result["user"]["name"] == "Test User"
        assert result["user"]["preferences"]["theme"] == "dark"
    
    def test_sanitize_dict_not_dict(self):
        """Test dictionary sanitization with non-dict input"""
        with pytest.raises(ValueError, match="must be a dictionary"):
            InputSanitizer.sanitize_dict("not a dict")
    
    def test_sanitize_list_valid(self):
        """Test list sanitization"""
        data = ["item1", "item2", 123, True]
        
        result = InputSanitizer.sanitize_list(data)
        assert result == ["item1", "item2", 123, True]
    
    def test_sanitize_list_too_long(self):
        """Test list sanitization with too many items"""
        data = ["item"] * 101
        
        with pytest.raises(ValueError, match="too long"):
            InputSanitizer.sanitize_list(data, max_items=100)
    
    def test_sanitize_list_invalid_item_type(self):
        """Test list sanitization with invalid item type"""
        data = [object()]  # Unsupported type
        
        with pytest.raises(ValueError, match="Unsupported list item type"):
            InputSanitizer.sanitize_list(data)
    
    def test_sanitize_list_not_list(self):
        """Test list sanitization with non-list input"""
        with pytest.raises(ValueError, match="must be a list"):
            InputSanitizer.sanitize_list("not a list")

class TestValidationError:
    """Test the ValidationError exception"""
    
    def test_validation_error_creation(self):
        """Test creating ValidationError"""
        error = ValidationError("Test error", "test_field")
        
        assert error.status_code == 400
        assert error.detail["error"] == "Validation Error"
        assert error.detail["message"] == "Test error"
        assert error.detail["field"] == "test_field"
    
    def test_validation_error_no_field(self):
        """Test creating ValidationError without field"""
        error = ValidationError("Test error")
        
        assert error.detail["field"] is None

class TestValidateRequestData:
    """Test the validate_request_data function"""
    
    def test_validate_request_data_valid(self):
        """Test validating valid request data"""
        data = {"name": "Test User", "age": 25}
        schema = {
            "name": {"type": "string", "required": True, "max_length": 50},
            "age": {"type": "integer", "required": True, "min": 0, "max": 150}
        }
        
        result = validate_request_data(data, schema)
        assert result["name"] == "Test User"
        assert result["age"] == 25
    
    def test_validate_request_data_missing_required(self):
        """Test validation with missing required field"""
        data = {"age": 25}
        schema = {
            "name": {"type": "string", "required": True},
            "age": {"type": "integer", "required": False}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_request_data(data, schema)
        
        assert "required" in str(exc_info.value.detail["message"])
        assert exc_info.value.detail["field"] == "name"
    
    def test_validate_request_data_integer_validation(self):
        """Test integer field validation"""
        data = {"age": "not_an_integer"}
        schema = {"age": {"type": "integer", "required": True}}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_request_data(data, schema)
        
        assert "integer" in str(exc_info.value.detail["message"])
    
    def test_validate_request_data_integer_range(self):
        """Test integer range validation"""
        data = {"age": 200}
        schema = {"age": {"type": "integer", "required": True, "min": 0, "max": 150}}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_request_data(data, schema)
        
        assert "at most" in str(exc_info.value.detail["message"])
    
    def test_validate_request_data_boolean_conversion(self):
        """Test boolean field conversion"""
        data = {"active": "true"}
        schema = {"active": {"type": "boolean", "required": True}}
        
        result = validate_request_data(data, schema)
        assert result["active"] is True
        
        data = {"active": "false"}
        result = validate_request_data(data, schema)
        assert result["active"] is False
    
    def test_validate_request_data_pattern_validation(self):
        """Test pattern validation"""
        data = {"code": "invalid-format"}
        schema = {"code": {"type": "string", "pattern": r"^\d{4}$", "required": True}}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_request_data(data, schema)
        
        assert "format is invalid" in str(exc_info.value.detail["message"])

class TestSpecificValidators:
    """Test specific validation functions"""
    
    def test_validate_guess_request_valid(self):
        """Test valid guess request validation"""
        data = {
            "user_id": "test_user_123",
            "universe": "marvel",
            "guess": "Spider-Man"
        }
        
        result = validate_guess_request(data)
        assert result["user_id"] == "test_user_123"
        assert result["universe"] == "marvel"
        assert result["guess"] == "Spider-Man"
    
    def test_validate_guess_request_invalid(self):
        """Test invalid guess request validation"""
        data = {
            "user_id": "test_user_123",
            "universe": "invalid_universe",
            "guess": "Spider-Man"
        }
        
        with pytest.raises(ValidationError):
            validate_guess_request(data)
    
    def test_validate_user_update_valid(self):
        """Test valid user update validation"""
        data = {
            "username": "new_username",
            "email": "new@example.com"
        }
        
        result = validate_user_update(data)
        assert result["username"] == "new_username"
        assert result["email"] == "new@example.com"
    
    def test_validate_user_update_partial(self):
        """Test partial user update validation"""
        data = {"username": "new_username"}
        
        result = validate_user_update(data)
        assert result["username"] == "new_username"
        assert "email" not in result
    
    def test_validate_puzzle_query_valid(self):
        """Test valid puzzle query validation"""
        data = {
            "universe": "marvel",
            "date": "2024-01-01"
        }
        
        result = validate_puzzle_query(data)
        assert result["universe"] == "marvel"
        assert result["date"] == "2024-01-01"
    
    def test_validate_puzzle_query_invalid_date(self):
        """Test puzzle query with invalid date format"""
        data = {
            "universe": "marvel",
            "date": "01/01/2024"  # Wrong format
        }
        
        with pytest.raises(ValidationError):
            validate_puzzle_query(data)

class TestValidationSchemas:
    """Test validation schemas"""
    
    def test_validation_schemas_exist(self):
        """Test that validation schemas are properly defined"""
        assert "guess_request" in VALIDATION_SCHEMAS
        assert "user_update" in VALIDATION_SCHEMAS
        assert "puzzle_query" in VALIDATION_SCHEMAS
        
        # Check guess_request schema
        guess_schema = VALIDATION_SCHEMAS["guess_request"]
        assert "user_id" in guess_schema
        assert "universe" in guess_schema
        assert "guess" in guess_schema
        assert guess_schema["user_id"]["required"] is True
        assert guess_schema["universe"]["required"] is True
        assert guess_schema["guess"]["required"] is True
    
    def test_guess_request_schema_types(self):
        """Test guess request schema field types"""
        schema = VALIDATION_SCHEMAS["guess_request"]
        assert schema["user_id"]["type"] == "user_id"
        assert schema["universe"]["type"] == "universe"
        assert schema["guess"]["type"] == "character_name"