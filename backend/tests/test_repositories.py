"""Unit tests for repository classes"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.repositories.user_repository import UserRepository
from app.repositories.puzzle_repository import PuzzleRepository
from app.repositories.guess_repository import GuessRepository
from app.models.user import User, UserCreate, UserUpdate
from app.models.puzzle import Puzzle, PuzzleCreate
from app.models.guess import Guess, GuessCreate
from app.database.exceptions import ItemNotFoundError, DuplicateItemError, DatabaseError


class TestUserRepository:
    """Test cases for UserRepository"""
    
    @pytest.fixture
    def user_repo(self):
        return UserRepository()
    
    @pytest.fixture
    def sample_user_data(self):
        return {
            "id": "test-user-123",
            "username": "testuser",
            "email": "test@example.com",
            "created_at": datetime.utcnow().isoformat(),
            "streaks": {"marvel": 5, "dc": 3, "image": 0},
            "last_played": {"marvel": "2024-01-15", "dc": "2024-01-14", "image": None},
            "total_games": 10,
            "total_wins": 8
        }
    
    @pytest.fixture
    def sample_user_create(self):
        return UserCreate(
            username="newuser",
            email="new@example.com"
        )
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, user_repo, sample_user_create):
        """Test successful user creation"""
        with patch.object(user_repo, 'get_user_by_email', return_value=None), \
             patch.object(user_repo, 'create') as mock_create:
            
            # Mock the create method to return user data
            mock_create.return_value = {
                "id": "new-user-123",
                "username": "newuser",
                "email": "new@example.com",
                "created_at": datetime.utcnow().isoformat(),
                "streaks": {"marvel": 0, "dc": 0, "image": 0},
                "last_played": {"marvel": None, "dc": None, "image": None},
                "total_games": 0,
                "total_wins": 0
            }
            
            result = await user_repo.create_user(sample_user_create)
            
            assert isinstance(result, User)
            assert result.username == "newuser"
            assert result.email == "new@example.com"
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, user_repo, sample_user_create, sample_user_data):
        """Test user creation with duplicate email"""
        with patch.object(user_repo, 'get_user_by_email', return_value=User(**sample_user_data)):
            
            with pytest.raises(DuplicateItemError):
                await user_repo.create_user(sample_user_create)
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, user_repo, sample_user_data):
        """Test successful user retrieval by ID"""
        with patch.object(user_repo, 'get_by_id', return_value=sample_user_data):
            
            result = await user_repo.get_user_by_id("test-user-123")
            
            assert isinstance(result, User)
            assert result.id == "test-user-123"
            assert result.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_repo):
        """Test user retrieval when user doesn't exist"""
        with patch.object(user_repo, 'get_by_id', return_value=None):
            
            result = await user_repo.get_user_by_id("nonexistent")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_success(self, user_repo, sample_user_data):
        """Test successful user retrieval by email"""
        with patch.object(user_repo, 'query', return_value=[sample_user_data]):
            
            result = await user_repo.get_user_by_email("test@example.com")
            
            assert isinstance(result, User)
            assert result.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, user_repo):
        """Test user retrieval by email when user doesn't exist"""
        with patch.object(user_repo, 'query', return_value=[]):
            
            result = await user_repo.get_user_by_email("nonexistent@example.com")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_user_success(self, user_repo, sample_user_data):
        """Test successful user update"""
        user_update = UserUpdate(username="updateduser")
        
        with patch.object(user_repo, 'get_user_by_id', return_value=User(**sample_user_data)), \
             patch.object(user_repo, 'update') as mock_update:
            
            updated_data = sample_user_data.copy()
            updated_data["username"] = "updateduser"
            mock_update.return_value = updated_data
            
            result = await user_repo.update_user("test-user-123", user_update)
            
            assert isinstance(result, User)
            assert result.username == "updateduser"
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_not_found(self, user_repo):
        """Test user update when user doesn't exist"""
        user_update = UserUpdate(username="updateduser")
        
        with patch.object(user_repo, 'get_user_by_id', return_value=None):
            
            with pytest.raises(ItemNotFoundError):
                await user_repo.update_user("nonexistent", user_update)
    
    @pytest.mark.asyncio
    async def test_update_user_streak_increment(self, user_repo, sample_user_data):
        """Test user streak increment"""
        with patch.object(user_repo, 'get_user_by_id', return_value=User(**sample_user_data)), \
             patch.object(user_repo, 'update') as mock_update:
            
            updated_data = sample_user_data.copy()
            updated_data["streaks"]["marvel"] = 6
            updated_data["last_played"]["marvel"] = datetime.utcnow().strftime('%Y-%m-%d')
            mock_update.return_value = updated_data
            
            result = await user_repo.update_user_streak("test-user-123", "marvel", increment=True)
            
            assert result.streaks["marvel"] == 6
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_streak_reset(self, user_repo, sample_user_data):
        """Test user streak reset"""
        with patch.object(user_repo, 'get_user_by_id', return_value=User(**sample_user_data)), \
             patch.object(user_repo, 'update') as mock_update:
            
            updated_data = sample_user_data.copy()
            updated_data["streaks"]["marvel"] = 0
            updated_data["last_played"]["marvel"] = datetime.utcnow().strftime('%Y-%m-%d')
            mock_update.return_value = updated_data
            
            result = await user_repo.update_user_streak("test-user-123", "marvel", increment=False)
            
            assert result.streaks["marvel"] == 0
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_stats(self, user_repo, sample_user_data):
        """Test user stats update"""
        with patch.object(user_repo, 'get_user_by_id', return_value=User(**sample_user_data)), \
             patch.object(user_repo, 'update') as mock_update:
            
            updated_data = sample_user_data.copy()
            updated_data["total_games"] = 11
            updated_data["total_wins"] = 9
            mock_update.return_value = updated_data
            
            result = await user_repo.update_user_stats("test-user-123", won=True)
            
            assert result.total_games == 11
            assert result.total_wins == 9
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_repo):
        """Test successful user deletion"""
        with patch.object(user_repo, 'delete', return_value=True):
            
            result = await user_repo.delete_user("test-user-123")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_get_users_count(self, user_repo):
        """Test getting total users count"""
        with patch.object(user_repo, 'query', return_value=[42]):
            
            result = await user_repo.get_users_count()
            
            assert result == 42


class TestPuzzleRepository:
    """Test cases for PuzzleRepository"""
    
    @pytest.fixture
    def puzzle_repo(self):
        return PuzzleRepository()
    
    @pytest.fixture
    def sample_puzzle_data(self):
        return {
            "id": "20240115-marvel",
            "universe": "marvel",
            "character": "Spider-Man",
            "character_aliases": ["Spiderman", "Peter Parker"],
            "image_key": "marvel/spider-man.jpg",
            "created_at": datetime.utcnow().isoformat(),
            "active_date": "2024-01-15"
        }
    
    @pytest.fixture
    def sample_puzzle_create(self):
        return PuzzleCreate(
            universe="marvel",
            character="Iron Man",
            character_aliases=["Tony Stark"],
            image_key="marvel/iron-man.jpg",
            active_date="2024-01-16"
        )
    
    @pytest.mark.asyncio
    async def test_create_puzzle_success(self, puzzle_repo, sample_puzzle_create):
        """Test successful puzzle creation"""
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=None), \
             patch.object(puzzle_repo, 'create') as mock_create:
            
            mock_create.return_value = {
                "id": "20240116-marvel",
                "universe": "marvel",
                "character": "Iron Man",
                "character_aliases": ["Tony Stark"],
                "image_key": "marvel/iron-man.jpg",
                "created_at": datetime.utcnow().isoformat(),
                "active_date": "2024-01-16"
            }
            
            result = await puzzle_repo.create_puzzle(sample_puzzle_create)
            
            assert isinstance(result, Puzzle)
            assert result.character == "Iron Man"
            assert result.universe == "marvel"
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_puzzle_duplicate(self, puzzle_repo, sample_puzzle_create, sample_puzzle_data):
        """Test puzzle creation with duplicate date/universe"""
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=Puzzle(**sample_puzzle_data)):
            
            with pytest.raises(DuplicateItemError):
                await puzzle_repo.create_puzzle(sample_puzzle_create)
    
    @pytest.mark.asyncio
    async def test_get_puzzle_by_id_success(self, puzzle_repo, sample_puzzle_data):
        """Test successful puzzle retrieval by ID"""
        with patch.object(puzzle_repo, 'get_by_id', return_value=sample_puzzle_data):
            
            result = await puzzle_repo.get_puzzle_by_id("20240115-marvel")
            
            assert isinstance(result, Puzzle)
            assert result.id == "20240115-marvel"
            assert result.character == "Spider-Man"
    
    @pytest.mark.asyncio
    async def test_get_puzzle_by_id_invalid_format(self, puzzle_repo):
        """Test puzzle retrieval with invalid ID format"""
        result = await puzzle_repo.get_puzzle_by_id("invalid-id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_daily_puzzle_success(self, puzzle_repo, sample_puzzle_data):
        """Test successful daily puzzle retrieval"""
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=Puzzle(**sample_puzzle_data)):
            
            result = await puzzle_repo.get_daily_puzzle("marvel", "2024-01-15")
            
            assert isinstance(result, Puzzle)
            assert result.universe == "marvel"
    
    @pytest.mark.asyncio
    async def test_get_daily_puzzle_today(self, puzzle_repo, sample_puzzle_data):
        """Test daily puzzle retrieval for today"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        today_id = f"{datetime.utcnow().strftime('%Y%m%d')}-marvel"
        
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=Puzzle(**sample_puzzle_data)):
            
            result = await puzzle_repo.get_daily_puzzle("marvel")
            
            assert isinstance(result, Puzzle)
    
    @pytest.mark.asyncio
    async def test_validate_guess_correct(self, puzzle_repo, sample_puzzle_data):
        """Test correct guess validation"""
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=Puzzle(**sample_puzzle_data)):
            
            is_correct, character = await puzzle_repo.validate_guess("20240115-marvel", "Spider-Man")
            
            assert is_correct is True
            assert character == "Spider-Man"
    
    @pytest.mark.asyncio
    async def test_validate_guess_incorrect(self, puzzle_repo, sample_puzzle_data):
        """Test incorrect guess validation"""
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=Puzzle(**sample_puzzle_data)):
            
            is_correct, character = await puzzle_repo.validate_guess("20240115-marvel", "Iron Man")
            
            assert is_correct is False
            assert character is None
    
    @pytest.mark.asyncio
    async def test_validate_guess_alias(self, puzzle_repo, sample_puzzle_data):
        """Test guess validation with character alias"""
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=Puzzle(**sample_puzzle_data)):
            
            is_correct, character = await puzzle_repo.validate_guess("20240115-marvel", "Peter Parker")
            
            assert is_correct is True
            assert character == "Spider-Man"
    
    @pytest.mark.asyncio
    async def test_validate_guess_puzzle_not_found(self, puzzle_repo):
        """Test guess validation when puzzle doesn't exist"""
        with patch.object(puzzle_repo, 'get_puzzle_by_id', return_value=None):
            
            with pytest.raises(ItemNotFoundError):
                await puzzle_repo.validate_guess("nonexistent", "Spider-Man")
    
    @pytest.mark.asyncio
    async def test_get_puzzles_by_universe(self, puzzle_repo, sample_puzzle_data):
        """Test getting puzzles by universe"""
        with patch.object(puzzle_repo, 'query', return_value=[sample_puzzle_data]):
            
            result = await puzzle_repo.get_puzzles_by_universe("marvel")
            
            assert len(result) == 1
            assert isinstance(result[0], Puzzle)
            assert result[0].universe == "marvel"
    
    @pytest.mark.asyncio
    async def test_delete_puzzle_success(self, puzzle_repo):
        """Test successful puzzle deletion"""
        with patch.object(puzzle_repo, 'delete', return_value=True):
            
            result = await puzzle_repo.delete_puzzle("20240115-marvel")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_puzzle_invalid_id(self, puzzle_repo):
        """Test puzzle deletion with invalid ID"""
        result = await puzzle_repo.delete_puzzle("invalid-id")
        
        assert result is False


class TestGuessRepository:
    """Test cases for GuessRepository"""
    
    @pytest.fixture
    def guess_repo(self):
        return GuessRepository()
    
    @pytest.fixture
    def sample_guess_data(self):
        return {
            "id": "guess-123",
            "user_id": "user-123",
            "puzzle_id": "20240115-marvel",
            "guess": "Spider-Man",
            "is_correct": True,
            "timestamp": datetime.utcnow().isoformat(),
            "attempt_number": 1
        }
    
    @pytest.fixture
    def sample_guess_create(self):
        return GuessCreate(
            user_id="user-123",
            puzzle_id="20240115-marvel",
            guess="Iron Man"
        )
    
    @pytest.mark.asyncio
    async def test_create_guess_success(self, guess_repo, sample_guess_create):
        """Test successful guess creation"""
        with patch.object(guess_repo, 'create') as mock_create:
            
            mock_create.return_value = {
                "id": "new-guess-123",
                "user_id": "user-123",
                "puzzle_id": "20240115-marvel",
                "guess": "Iron Man",
                "is_correct": False,
                "timestamp": datetime.utcnow().isoformat(),
                "attempt_number": 2
            }
            
            result = await guess_repo.create_guess(sample_guess_create, is_correct=False, attempt_number=2)
            
            assert isinstance(result, Guess)
            assert result.guess == "Iron Man"
            assert result.is_correct is False
            assert result.attempt_number == 2
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_guesses_for_puzzle(self, guess_repo, sample_guess_data):
        """Test getting user guesses for a specific puzzle"""
        with patch.object(guess_repo, 'query', return_value=[sample_guess_data]):
            
            result = await guess_repo.get_user_guesses_for_puzzle("user-123", "20240115-marvel")
            
            assert len(result) == 1
            assert isinstance(result[0], Guess)
            assert result[0].user_id == "user-123"
            assert result[0].puzzle_id == "20240115-marvel"
    
    @pytest.mark.asyncio
    async def test_get_user_guess_history(self, guess_repo, sample_guess_data):
        """Test getting user guess history"""
        with patch.object(guess_repo, 'get_user_guesses_for_puzzle', return_value=[Guess(**sample_guess_data)]):
            
            result = await guess_repo.get_user_guess_history("user-123", "20240115-marvel")
            
            assert result.puzzle_id == "20240115-marvel"
            assert result.is_solved is True
            assert result.attempts_used == 1
            assert len(result.guesses) == 1
    
    @pytest.mark.asyncio
    async def test_get_next_attempt_number(self, guess_repo, sample_guess_data):
        """Test getting next attempt number"""
        with patch.object(guess_repo, 'get_user_guesses_for_puzzle', return_value=[Guess(**sample_guess_data)]):
            
            result = await guess_repo.get_next_attempt_number("user-123", "20240115-marvel")
            
            assert result == 2
    
    @pytest.mark.asyncio
    async def test_has_user_solved_puzzle_true(self, guess_repo):
        """Test checking if user has solved puzzle (true case)"""
        with patch.object(guess_repo, 'query', return_value=[1]):
            
            result = await guess_repo.has_user_solved_puzzle("user-123", "20240115-marvel")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_has_user_solved_puzzle_false(self, guess_repo):
        """Test checking if user has solved puzzle (false case)"""
        with patch.object(guess_repo, 'query', return_value=[0]):
            
            result = await guess_repo.has_user_solved_puzzle("user-123", "20240115-marvel")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_user_attempts_count(self, guess_repo):
        """Test getting user attempts count"""
        with patch.object(guess_repo, 'query', return_value=[3]):
            
            result = await guess_repo.get_user_attempts_count("user-123", "20240115-marvel")
            
            assert result == 3
    
    @pytest.mark.asyncio
    async def test_can_user_make_guess_true(self, guess_repo):
        """Test if user can make guess (true case)"""
        with patch.object(guess_repo, 'has_user_solved_puzzle', return_value=False), \
             patch.object(guess_repo, 'get_user_attempts_count', return_value=3):
            
            result = await guess_repo.can_user_make_guess("user-123", "20240115-marvel")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_can_user_make_guess_already_solved(self, guess_repo):
        """Test if user can make guess when already solved"""
        with patch.object(guess_repo, 'has_user_solved_puzzle', return_value=True):
            
            result = await guess_repo.can_user_make_guess("user-123", "20240115-marvel")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_can_user_make_guess_max_attempts(self, guess_repo):
        """Test if user can make guess when at max attempts"""
        with patch.object(guess_repo, 'has_user_solved_puzzle', return_value=False), \
             patch.object(guess_repo, 'get_user_attempts_count', return_value=6):
            
            result = await guess_repo.can_user_make_guess("user-123", "20240115-marvel")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_puzzle_guess_statistics(self, guess_repo):
        """Test getting puzzle guess statistics"""
        with patch.object(guess_repo, 'query') as mock_query:
            # Mock different query results
            mock_query.side_effect = [
                [10],  # total attempts
                [3],   # successful solves
                [5],   # unique users
                [{"avg_attempts": 2.5}]  # average attempts
            ]
            
            result = await guess_repo.get_puzzle_guess_statistics("20240115-marvel")
            
            assert result["puzzle_id"] == "20240115-marvel"
            assert result["total_attempts"] == 10
            assert result["successful_solves"] == 3
            assert result["unique_users"] == 5
            assert result["success_rate"] == 0.6
            assert result["average_attempts_to_solve"] == 2.5
    
    @pytest.mark.asyncio
    async def test_get_user_guess_statistics(self, guess_repo):
        """Test getting user guess statistics"""
        with patch.object(guess_repo, 'query') as mock_query:
            # Mock different query results
            mock_query.side_effect = [
                [15],  # total guesses
                [12],  # correct guesses
                [8]    # unique puzzles
            ]
            
            result = await guess_repo.get_user_guess_statistics("user-123")
            
            assert result["user_id"] == "user-123"
            assert result["total_guesses"] == 15
            assert result["correct_guesses"] == 12
            assert result["unique_puzzles_attempted"] == 8
            assert result["accuracy_rate"] == 0.8