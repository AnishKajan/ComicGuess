import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models import (
    User, UserCreate, UserUpdate, UserStats,
    Puzzle, PuzzleCreate, PuzzleResponse,
    Guess, GuessCreate, GuessResponse, GuessHistory
)


class TestUserModel:
    """Test cases for User model validation"""
    
    def test_user_creation_valid(self):
        """Test creating a valid user"""
        user = User(
            username="test_user",
            email="test@example.com"
        )
        
        assert user.username == "test_user"
        assert user.email == "test@example.com"
        assert user.total_games == 0
        assert user.total_wins == 0
        assert user.streaks == {"marvel": 0, "dc": 0, "image": 0}
        assert user.last_played == {"marvel": None, "dc": None, "image": None}
        assert isinstance(user.created_at, datetime)
        assert len(user.id) > 0
    
    def test_user_username_validation(self):
        """Test username validation rules"""
        # Valid usernames
        valid_usernames = ["test_user", "user123", "comic-fan", "user.name"]
        for username in valid_usernames:
            user = User(username=username, email="test@example.com")
            assert user.username == username
        
        # Invalid usernames
        with pytest.raises(ValidationError):
            User(username="", email="test@example.com")  # Empty
        
        with pytest.raises(ValidationError):
            User(username="   ", email="test@example.com")  # Whitespace only
        
        with pytest.raises(ValidationError):
            User(username="ab", email="test@example.com")  # Too short
        
        with pytest.raises(ValidationError):
            User(username="a" * 51, email="test@example.com")  # Too long
        
        with pytest.raises(ValidationError):
            User(username="user@name", email="test@example.com")  # Invalid character
    
    def test_user_email_validation(self):
        """Test email validation rules"""
        # Valid emails
        valid_emails = ["test@example.com", "user.name@domain.co.uk", "123@test.org"]
        for email in valid_emails:
            user = User(username="testuser", email=email)
            assert user.email == email.lower()
        
        # Invalid emails
        invalid_emails = ["invalid", "test@", "@example.com", "test.example.com"]
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                User(username="testuser", email=email)
    
    def test_user_streaks_validation(self):
        """Test streaks validation"""
        # Valid streaks
        user = User(
            username="testuser",
            email="test@example.com",
            streaks={"marvel": 5, "dc": 2, "image": 0}
        )
        assert user.streaks["marvel"] == 5
        
        # Missing universe should be added
        user = User(
            username="testuser",
            email="test@example.com",
            streaks={"marvel": 3}
        )
        assert user.streaks["dc"] == 0
        assert user.streaks["image"] == 0
        
        # Invalid streak values
        with pytest.raises(ValidationError):
            User(
                username="testuser",
                email="test@example.com",
                streaks={"marvel": -1, "dc": 0, "image": 0}
            )
    
    def test_user_total_wins_validation(self):
        """Test that total wins cannot exceed total games"""
        # Valid case
        user = User(
            username="testuser",
            email="test@example.com",
            total_games=10,
            total_wins=7
        )
        assert user.total_wins == 7
        
        # Invalid case - wins exceed games
        with pytest.raises(ValidationError):
            User(
                username="testuser",
                email="test@example.com",
                total_games=5,
                total_wins=10
            )
    
    def test_user_stats_creation(self):
        """Test UserStats creation from User"""
        user = User(
            username="testuser",
            email="test@example.com",
            total_games=10,
            total_wins=7,
            streaks={"marvel": 5, "dc": 2, "image": 0}
        )
        
        stats = UserStats.from_user(user)
        assert stats.total_games == 10
        assert stats.total_wins == 7
        assert stats.win_rate == 0.7
        assert stats.streaks == {"marvel": 5, "dc": 2, "image": 0}


class TestPuzzleModel:
    """Test cases for Puzzle model validation"""
    
    def test_puzzle_creation_valid(self):
        """Test creating a valid puzzle"""
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker"],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        )
        
        assert puzzle.id == "20240115-marvel"
        assert puzzle.universe == "marvel"
        assert puzzle.character == "Spider-Man"
        assert "Spiderman" in puzzle.character_aliases
        assert puzzle.image_key == "marvel/spider-man.jpg"
    
    def test_puzzle_universe_validation(self):
        """Test universe validation"""
        # Valid universes
        for universe in ["marvel", "dc", "image"]:
            puzzle = Puzzle(
                id=f"20240115-{universe}",
                universe=universe,
                character="Test Character",
                image_key=f"{universe}/test.jpg",
                active_date="2024-01-15"
            )
            assert puzzle.universe == universe
        
        # Invalid universe
        with pytest.raises(ValidationError):
            Puzzle(
                id="20240115-invalid",
                universe="invalid",
                character="Test Character",
                image_key="invalid/test.jpg",
                active_date="2024-01-15"
            )
    
    def test_puzzle_id_validation(self):
        """Test puzzle ID format validation"""
        # Valid ID
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Test Character",
            image_key="marvel/test.jpg",
            active_date="2024-01-15"
        )
        assert puzzle.id == "20240115-marvel"
        
        # Invalid ID formats
        invalid_ids = [
            "2024115-marvel",  # Wrong date format
            "20240115-invalid",  # Invalid universe
            "invalid-marvel",  # Invalid date
            "20240115marvel",  # Missing hyphen
        ]
        
        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                Puzzle(
                    id=invalid_id,
                    universe="marvel",
                    character="Test Character",
                    image_key="marvel/test.jpg",
                    active_date="2024-01-15"
                )
    
    def test_puzzle_character_validation(self):
        """Test character name validation"""
        # Valid characters
        valid_characters = ["Spider-Man", "Iron Man", "Dr. Strange", "X-23"]
        for character in valid_characters:
            puzzle = Puzzle(
                id="20240115-marvel",
                universe="marvel",
                character=character,
                image_key="marvel/test.jpg",
                active_date="2024-01-15"
            )
            assert puzzle.character == character
        
        # Invalid characters
        with pytest.raises(ValidationError):
            Puzzle(
                id="20240115-marvel",
                universe="marvel",
                character="",  # Empty
                image_key="marvel/test.jpg",
                active_date="2024-01-15"
            )
        
        with pytest.raises(ValidationError):
            Puzzle(
                id="20240115-marvel",
                universe="marvel",
                character="Test@Character",  # Invalid character
                image_key="marvel/test.jpg",
                active_date="2024-01-15"
            )
    
    def test_puzzle_aliases_validation(self):
        """Test character aliases validation"""
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker", "Web-Slinger", ""],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        )
        
        # Empty alias should be filtered out
        assert "" not in puzzle.character_aliases
        assert "Spiderman" in puzzle.character_aliases
        
        # Duplicates should be removed
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "spiderman", "SPIDERMAN"],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        )
        
        # Should only have one version (case-insensitive deduplication)
        assert len(puzzle.character_aliases) == 1
    
    def test_puzzle_matches_guess(self):
        """Test guess matching functionality"""
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker"],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        )
        
        # Should match main character name
        assert puzzle.matches_guess("Spider-Man") == True
        assert puzzle.matches_guess("spider-man") == True  # Case insensitive
        assert puzzle.matches_guess("SPIDER-MAN") == True
        
        # Should match aliases
        assert puzzle.matches_guess("Spiderman") == True
        assert puzzle.matches_guess("Peter Parker") == True
        assert puzzle.matches_guess("peter parker") == True
        
        # Should not match incorrect guesses
        assert puzzle.matches_guess("Iron Man") == False
        assert puzzle.matches_guess("") == False
        assert puzzle.matches_guess(None) == False
    
    def test_puzzle_generate_id(self):
        """Test puzzle ID generation"""
        puzzle_id = Puzzle.generate_id("2024-01-15", "marvel")
        assert puzzle_id == "20240115-marvel"
        
        puzzle_id = Puzzle.generate_id("2024-12-31", "dc")
        assert puzzle_id == "20241231-dc"


class TestGuessModel:
    """Test cases for Guess model validation"""
    
    def test_guess_creation_valid(self):
        """Test creating a valid guess"""
        guess = Guess(
            user_id="user123",
            puzzle_id="20240115-marvel",
            guess="Spider-Man",
            is_correct=True,
            attempt_number=1
        )
        
        assert guess.user_id == "user123"
        assert guess.puzzle_id == "20240115-marvel"
        assert guess.guess == "Spider-Man"
        assert guess.is_correct == True
        assert guess.attempt_number == 1
        assert isinstance(guess.timestamp, datetime)
    
    def test_guess_validation(self):
        """Test guess text validation"""
        # Valid guesses
        valid_guesses = ["Spider-Man", "Iron Man", "Dr. Strange"]
        for guess_text in valid_guesses:
            guess = Guess(
                user_id="user123",
                puzzle_id="20240115-marvel",
                guess=guess_text,
                is_correct=False,
                attempt_number=1
            )
            assert guess.guess == guess_text
        
        # Invalid guesses
        with pytest.raises(ValidationError):
            Guess(
                user_id="user123",
                puzzle_id="20240115-marvel",
                guess="",  # Empty
                is_correct=False,
                attempt_number=1
            )
        
        with pytest.raises(ValidationError):
            Guess(
                user_id="user123",
                puzzle_id="20240115-marvel",
                guess="   ",  # Whitespace only
                is_correct=False,
                attempt_number=1
            )
    
    def test_guess_attempt_number_validation(self):
        """Test attempt number validation"""
        # Valid attempt numbers
        for attempt in range(1, 7):  # 1-6
            guess = Guess(
                user_id="user123",
                puzzle_id="20240115-marvel",
                guess="Spider-Man",
                is_correct=False,
                attempt_number=attempt
            )
            assert guess.attempt_number == attempt
        
        # Invalid attempt numbers
        invalid_attempts = [0, 7, -1, 10]
        for attempt in invalid_attempts:
            with pytest.raises(ValidationError):
                Guess(
                    user_id="user123",
                    puzzle_id="20240115-marvel",
                    guess="Spider-Man",
                    is_correct=False,
                    attempt_number=attempt
                )
    
    def test_guess_puzzle_id_validation(self):
        """Test puzzle ID validation in guess"""
        # Valid puzzle ID
        guess = Guess(
            user_id="user123",
            puzzle_id="20240115-marvel",
            guess="Spider-Man",
            is_correct=True,
            attempt_number=1
        )
        assert guess.puzzle_id == "20240115-marvel"
        
        # Invalid puzzle IDs
        invalid_ids = [
            "invalid",
            "20240115",
            "marvel",
            "2024115-marvel",
            "20240115-invalid"
        ]
        
        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                Guess(
                    user_id="user123",
                    puzzle_id=invalid_id,
                    guess="Spider-Man",
                    is_correct=True,
                    attempt_number=1
                )


class TestModelIntegration:
    """Integration tests for model interactions"""
    
    def test_user_puzzle_guess_flow(self):
        """Test complete flow of user, puzzle, and guess models"""
        # Create user
        user = User(
            username="comic_fan",
            email="fan@example.com"
        )
        
        # Create puzzle
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker"],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        )
        
        # Create guess
        guess = Guess(
            user_id=user.id,
            puzzle_id=puzzle.id,
            guess="Spider-Man",
            is_correct=puzzle.matches_guess("Spider-Man"),
            attempt_number=1
        )
        
        assert guess.is_correct == True
        assert guess.user_id == user.id
        assert guess.puzzle_id == puzzle.id
    
    def test_character_alias_handling(self):
        """Test comprehensive character alias handling"""
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=[
                "Spiderman",
                "Peter Parker", 
                "Web-Slinger",
                "Your Friendly Neighborhood Spider-Man",
                "Amazing Spider-Man"
            ],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        )
        
        # Test various guess formats
        valid_guesses = [
            "Spider-Man",
            "spider-man",
            "SPIDER-MAN",
            "Spiderman",
            "spiderman",
            "Peter Parker",
            "peter parker",
            "Web-Slinger",
            "web-slinger",
            "Your Friendly Neighborhood Spider-Man",
            "Amazing Spider-Man"
        ]
        
        for guess_text in valid_guesses:
            assert puzzle.matches_guess(guess_text) == True, f"Failed for guess: {guess_text}"
        
        # Test invalid guesses
        invalid_guesses = [
            "Iron Man",
            "Captain America",
            "Spider",
            "Man",
            "",
            "Spider-Woman"
        ]
        
        for guess_text in invalid_guesses:
            assert puzzle.matches_guess(guess_text) == False, f"Should have failed for: {guess_text}""""Unit tests for ComicGuess data models"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.user import User, UserCreate, UserUpdate
from app.models.puzzle import Puzzle, PuzzleCreate, PuzzleResponse
from app.models.guess import Guess, GuessCreate, GuessResponse, GuessHistory
from app.models.validation import (
    CharacterNameValidator,
    UniverseValidator,
    PuzzleIdValidator,
    GuessValidator,
    validate_email,
    validate_username
)

class TestUserModel:
    """Test cases for User model"""
    
    def test_user_creation_valid(self):
        """Test creating a valid user"""
        user_data = {
            "username": "test_user",
            "email": "test@example.com"
        }
        user = User(**user_data)
        
        assert user.username == "test_user"
        assert user.email == "test@example.com"
        assert user.total_games == 0
        assert user.total_wins == 0
        assert user.streaks == {"marvel": 0, "dc": 0, "image": 0}
        assert user.last_played == {"marvel": None, "dc": None, "image": None}
    
    def test_user_invalid_email(self):
        """Test user creation with invalid email"""
        with pytest.raises(ValidationError):
            User(username="test_user", email="invalid-email")
    
    def test_user_invalid_username(self):
        """Test user creation with invalid username"""
        with pytest.raises(ValidationError):
            User(username="ab", email="test@example.com")  # Too short
        
        with pytest.raises(ValidationError):
            User(username="user@name", email="test@example.com")  # Invalid characters
    
    def test_user_total_wins_validation(self):
        """Test that total wins cannot exceed total games"""
        with pytest.raises(ValidationError):
            User(
                username="test_user",
                email="test@example.com",
                total_games=5,
                total_wins=10  # More wins than games
            )

class TestPuzzleModel:
    """Test cases for Puzzle model"""
    
    def test_puzzle_creation_valid(self):
        """Test creating a valid puzzle"""
        puzzle_data = {
            "id": "20240115-marvel",
            "universe": "marvel",
            "character": "Spider-Man",
            "character_aliases": ["Spiderman", "Peter Parker"],
            "image_key": "marvel/spider-man-001.jpg",
            "active_date": "2024-01-15"
        }
        puzzle = Puzzle(**puzzle_data)
        
        assert puzzle.id == "20240115-marvel"
        assert puzzle.universe == "marvel"
        assert puzzle.character == "Spider-Man"
        assert "Spiderman" in puzzle.character_aliases
        assert "Peter Parker" in puzzle.character_aliases
    
    def test_puzzle_invalid_universe(self):
        """Test puzzle creation with invalid universe"""
        with pytest.raises(ValidationError):
            Puzzle(
                id="20240115-invalid",
                universe="invalid",
                character="Test Character",
                image_key="invalid/test.jpg",
                active_date="2024-01-15"
            )
    
    def test_puzzle_invalid_id_format(self):
        """Test puzzle creation with invalid ID format"""
        with pytest.raises(ValidationError):
            Puzzle(
                id="invalid-id",
                universe="marvel",
                character="Test Character",
                image_key="marvel/test.jpg",
                active_date="2024-01-15"
            )
    
    def test_puzzle_guess_validation(self):
        """Test puzzle guess validation logic"""
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker", "Web-Slinger"],
            image_key="marvel/spider-man-001.jpg",
            active_date="2024-01-15"
        )
        
        # Test correct guesses
        assert puzzle.is_correct_guess("Spider-Man")
        assert puzzle.is_correct_guess("spider-man")  # Case insensitive
        assert puzzle.is_correct_guess("SPIDER-MAN")
        assert puzzle.is_correct_guess("Spiderman")
        assert puzzle.is_correct_guess("Peter Parker")
        assert puzzle.is_correct_guess("web-slinger")
        
        # Test incorrect guesses
        assert not puzzle.is_correct_guess("Iron Man")
        assert not puzzle.is_correct_guess("Batman")
        assert not puzzle.is_correct_guess("")

class TestGuessModel:
    """Test cases for Guess model"""
    
    def test_guess_creation_valid(self):
        """Test creating a valid guess"""
        guess_data = {
            "user_id": "user-123",
            "puzzle_id": "20240115-marvel",
            "guess": "Spider-Man",
            "is_correct": True,
            "attempt_number": 1
        }
        guess = Guess(**guess_data)
        
        assert guess.user_id == "user-123"
        assert guess.puzzle_id == "20240115-marvel"
        assert guess.guess == "Spider-Man"
        assert guess.is_correct is True
        assert guess.attempt_number == 1
    
    def test_guess_invalid_attempt_number(self):
        """Test guess creation with invalid attempt number"""
        with pytest.raises(ValidationError):
            Guess(
                user_id="user-123",
                puzzle_id="20240115-marvel",
                guess="Spider-Man",
                is_correct=True,
                attempt_number=0  # Too low
            )
        
        with pytest.raises(ValidationError):
            Guess(
                user_id="user-123",
                puzzle_id="20240115-marvel",
                guess="Spider-Man",
                is_correct=True,
                attempt_number=7  # Too high
            )
    
    def test_guess_empty_guess(self):
        """Test guess creation with empty guess"""
        with pytest.raises(ValidationError):
            Guess(
                user_id="user-123",
                puzzle_id="20240115-marvel",
                guess="",
                is_correct=False,
                attempt_number=1
            )

class TestValidationUtilities:
    """Test cases for validation utilities"""
    
    def test_character_name_validator(self):
        """Test character name validation"""
        # Valid names
        assert CharacterNameValidator.is_valid_character_name("Spider-Man")
        assert CharacterNameValidator.is_valid_character_name("Jean Grey")
        assert CharacterNameValidator.is_valid_character_name("X-23")
        assert CharacterNameValidator.is_valid_character_name("Dr. Strange")
        
        # Invalid names
        assert not CharacterNameValidator.is_valid_character_name("")
        assert not CharacterNameValidator.is_valid_character_name("   ")
        
        # Test normalization
        assert CharacterNameValidator.normalize_name("  Spider-Man  ") == "Spider-Man"
        assert CharacterNameValidator.normalize_name("Spider–Man") == "Spider-Man"  # En dash to hyphen
    
    def test_universe_validator(self):
        """Test universe validation"""
        assert UniverseValidator.is_valid_universe("marvel")
        assert UniverseValidator.is_valid_universe("MARVEL")
        assert UniverseValidator.is_valid_universe("dc")
        assert UniverseValidator.is_valid_universe("image")
        
        assert not UniverseValidator.is_valid_universe("invalid")
        assert not UniverseValidator.is_valid_universe("")
        
        # Test normalization
        assert UniverseValidator.normalize_universe("MARVEL") == "marvel"
        assert UniverseValidator.normalize_universe("DC") == "dc"
    
    def test_puzzle_id_validator(self):
        """Test puzzle ID validation"""
        # Valid IDs
        assert PuzzleIdValidator.is_valid_puzzle_id("20240115-marvel")
        assert PuzzleIdValidator.is_valid_puzzle_id("20241231-dc")
        assert PuzzleIdValidator.is_valid_puzzle_id("20240229-image")  # Leap year
        
        # Invalid IDs
        assert not PuzzleIdValidator.is_valid_puzzle_id("invalid-id")
        assert not PuzzleIdValidator.is_valid_puzzle_id("20240115-invalid")
        assert not PuzzleIdValidator.is_valid_puzzle_id("20240230-marvel")  # Invalid date
        assert not PuzzleIdValidator.is_valid_puzzle_id("")
        
        # Test generation
        date = datetime(2024, 1, 15)
        puzzle_id = PuzzleIdValidator.generate_puzzle_id(date, "marvel")
        assert puzzle_id == "20240115-marvel"
        
        # Test parsing
        parsed_date, universe = PuzzleIdValidator.parse_puzzle_id("20240115-marvel")
        assert parsed_date.year == 2024
        assert parsed_date.month == 1
        assert parsed_date.day == 15
        assert universe == "marvel"
    
    def test_guess_validator(self):
        """Test guess validation"""
        # Valid guesses
        assert GuessValidator.is_valid_guess("Spider-Man")
        assert GuessValidator.is_valid_guess("X")  # Single character
        
        # Invalid guesses
        assert not GuessValidator.is_valid_guess("")
        assert not GuessValidator.is_valid_guess("   ")
        assert not GuessValidator.is_valid_guess("a" * 101)  # Too long
        
        # Test normalization
        assert GuessValidator.normalize_guess("  Spider-Man  ") == "Spider-Man"
        
        # Test attempt number validation
        assert GuessValidator.is_valid_attempt_number(1)
        assert GuessValidator.is_valid_attempt_number(6)
        assert not GuessValidator.is_valid_attempt_number(0)
        assert not GuessValidator.is_valid_attempt_number(7)
    
    def test_email_validation(self):
        """Test email validation utility"""
        assert validate_email("test@example.com")
        assert validate_email("user.name@domain.co.uk")
        
        assert not validate_email("invalid-email")
        assert not validate_email("@example.com")
        assert not validate_email("test@")
        assert not validate_email("")
    
    def test_username_validation(self):
        """Test username validation utility"""
        assert validate_username("test_user")
        assert validate_username("user123")
        assert validate_username("test-user")
        
        assert not validate_username("ab")  # Too short
        assert not validate_username("a" * 51)  # Too long
        assert not validate_username("user@name")  # Invalid character
        assert not validate_username("")

if __name__ == "__main__":
    pytest.main([__file__])