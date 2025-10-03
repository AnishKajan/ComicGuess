"""Tests for guess validation service"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.services.guess_service import GuessValidationService
from app.models.guess import Guess, GuessResponse, GuessHistory
from app.models.user import User
from app.models.puzzle import Puzzle
from app.database.exceptions import ItemNotFoundError

class TestGuessValidationService:
    """Test cases for GuessValidationService"""
    
    @pytest.fixture
    def guess_service(self):
        """Create guess validation service instance"""
        return GuessValidationService()
    
    @pytest.fixture
    def sample_user(self):
        """Sample user for testing"""
        return User(
            id="user123",
            username="testuser",
            email="test@example.com",
            streaks={"marvel": 5, "dc": 2, "image": 0},
            last_played={"marvel": "2024-01-14", "dc": "2024-01-13"},
            total_games=10,
            total_wins=7
        )
    
    @pytest.fixture
    def sample_puzzle(self):
        """Sample puzzle for testing"""
        return Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spidey", "Web-Slinger", "Peter Parker"],
            image_key="marvel/spiderman.jpg",
            active_date="2024-01-15"
        )
    
    @pytest.fixture
    def sample_guess(self):
        """Sample guess for testing"""
        return Guess(
            id="guess123",
            user_id="user123",
            puzzle_id="20240115-marvel",
            guess="Spider-Man",
            is_correct=True,
            attempt_number=1
        )
    
    def test_normalize_guess(self, guess_service):
        """Test guess normalization"""
        # Basic normalization
        assert guess_service.normalize_guess("Spider-Man") == "spider man"
        assert guess_service.normalize_guess("  IRON  MAN  ") == "iron man"
        
        # Punctuation removal
        assert guess_service.normalize_guess("Spider-Man!") == "spider man"
        assert guess_service.normalize_guess("Dr. Strange") == "dr strange"
        
        # Hyphen handling
        assert guess_service.normalize_guess("Spider-Man") == "spider man"
        assert guess_service.normalize_guess("X-Men") == "x men"
    
    def test_character_name_matches_exact(self, guess_service):
        """Test exact character name matching"""
        character = "Spider-Man"
        aliases = ["Spidey", "Web-Slinger"]
        
        # Exact match
        assert guess_service.character_name_matches("Spider-Man", character, aliases) is True
        
        # Case insensitive
        assert guess_service.character_name_matches("spider-man", character, aliases) is True
        assert guess_service.character_name_matches("SPIDER-MAN", character, aliases) is True
        
        # With extra spaces
        assert guess_service.character_name_matches("  Spider-Man  ", character, aliases) is True
    
    def test_character_name_matches_aliases(self, guess_service):
        """Test character alias matching"""
        character = "Spider-Man"
        aliases = ["Spidey", "Web-Slinger", "Peter Parker"]
        
        # Alias matches
        assert guess_service.character_name_matches("Spidey", character, aliases) is True
        assert guess_service.character_name_matches("Web-Slinger", character, aliases) is True
        assert guess_service.character_name_matches("Peter Parker", character, aliases) is True
        
        # Case insensitive aliases
        assert guess_service.character_name_matches("spidey", character, aliases) is True
        assert guess_service.character_name_matches("WEB-SLINGER", character, aliases) is True
    
    def test_character_name_matches_partial(self, guess_service):
        """Test partial character name matching"""
        character = "Spider-Man"
        aliases = ["Web Slinger"]
        
        # Space vs hyphen variations
        assert guess_service.character_name_matches("Spider Man", character, aliases) is True
        assert guess_service.character_name_matches("WebSlinger", character, aliases) is True
        assert guess_service.character_name_matches("Web-Slinger", character, aliases) is True
    
    def test_character_name_matches_negative(self, guess_service):
        """Test character name matching negative cases"""
        character = "Spider-Man"
        aliases = ["Spidey", "Web-Slinger"]
        
        # Wrong character
        assert guess_service.character_name_matches("Iron Man", character, aliases) is False
        assert guess_service.character_name_matches("Batman", character, aliases) is False
        
        # Partial wrong matches
        assert guess_service.character_name_matches("Spider", character, aliases) is False
        assert guess_service.character_name_matches("Man", character, aliases) is False
    
    @pytest.mark.asyncio
    async def test_validate_guess_correct(self, guess_service, sample_user, sample_puzzle):
        """Test validating a correct guess"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.guess_repository, 'can_user_make_guess', new_callable=AsyncMock) as mock_can_guess:
                with patch.object(guess_service.guess_repository, 'get_next_attempt_number', new_callable=AsyncMock) as mock_attempt:
                    with patch.object(guess_service.puzzle_service, 'validate_puzzle_guess', new_callable=AsyncMock) as mock_validate:
                        with patch.object(guess_service.guess_repository, 'create_guess', new_callable=AsyncMock) as mock_create:
                            with patch.object(guess_service, '_update_user_streak', new_callable=AsyncMock) as mock_streak:
                                with patch.object(guess_service, '_build_image_url', return_value="https://example.com/image.jpg"):
                                    
                                    mock_get_user.return_value = sample_user
                                    mock_can_guess.return_value = True
                                    mock_attempt.return_value = 1
                                    mock_validate.return_value = (True, "Spider-Man", "marvel/spiderman.jpg")
                                    mock_streak.return_value = 6
                                    
                                    result = await guess_service.validate_guess("user123", "20240115-marvel", "Spider-Man")
                                    
                                    assert isinstance(result, GuessResponse)
                                    assert result.correct is True
                                    assert result.character == "Spider-Man"
                                    assert result.image_url == "https://example.com/image.jpg"
                                    assert result.streak == 6
                                    assert result.attempt_number == 1
                                    assert result.game_over is True
    
    @pytest.mark.asyncio
    async def test_validate_guess_incorrect(self, guess_service, sample_user):
        """Test validating an incorrect guess"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.guess_repository, 'can_user_make_guess', new_callable=AsyncMock) as mock_can_guess:
                with patch.object(guess_service.guess_repository, 'get_next_attempt_number', new_callable=AsyncMock) as mock_attempt:
                    with patch.object(guess_service.puzzle_service, 'validate_puzzle_guess', new_callable=AsyncMock) as mock_validate:
                        with patch.object(guess_service.guess_repository, 'create_guess', new_callable=AsyncMock) as mock_create:
                            with patch.object(guess_service, '_update_user_streak', new_callable=AsyncMock) as mock_streak:
                                
                                mock_get_user.return_value = sample_user
                                mock_can_guess.return_value = True
                                mock_attempt.return_value = 2
                                mock_validate.return_value = (False, None, None)
                                mock_streak.return_value = 5
                                
                                result = await guess_service.validate_guess("user123", "20240115-marvel", "Iron Man")
                                
                                assert isinstance(result, GuessResponse)
                                assert result.correct is False
                                assert result.character is None
                                assert result.image_url is None
                                assert result.streak == 5
                                assert result.attempt_number == 2
                                assert result.game_over is False
    
    @pytest.mark.asyncio
    async def test_validate_guess_max_attempts(self, guess_service, sample_user):
        """Test validating guess at max attempts"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.guess_repository, 'can_user_make_guess', new_callable=AsyncMock) as mock_can_guess:
                with patch.object(guess_service.guess_repository, 'get_next_attempt_number', new_callable=AsyncMock) as mock_attempt:
                    with patch.object(guess_service.puzzle_service, 'validate_puzzle_guess', new_callable=AsyncMock) as mock_validate:
                        with patch.object(guess_service.guess_repository, 'create_guess', new_callable=AsyncMock) as mock_create:
                            with patch.object(guess_service, '_update_user_streak', new_callable=AsyncMock) as mock_streak:
                                
                                mock_get_user.return_value = sample_user
                                mock_can_guess.return_value = True
                                mock_attempt.return_value = 6  # Max attempts
                                mock_validate.return_value = (False, None, None)
                                mock_streak.return_value = 0  # Streak reset
                                
                                result = await guess_service.validate_guess("user123", "20240115-marvel", "Wrong Answer")
                                
                                assert result.correct is False
                                assert result.attempt_number == 6
                                assert result.game_over is True  # Game over due to max attempts
                                assert result.streak == 0  # Streak should be reset
    
    @pytest.mark.asyncio
    async def test_validate_guess_already_solved(self, guess_service, sample_user):
        """Test validating guess when puzzle already solved"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.guess_repository, 'can_user_make_guess', new_callable=AsyncMock) as mock_can_guess:
                with patch.object(guess_service.guess_repository, 'has_user_solved_puzzle', new_callable=AsyncMock) as mock_solved:
                    
                    mock_get_user.return_value = sample_user
                    mock_can_guess.return_value = False
                    mock_solved.return_value = True
                    
                    with pytest.raises(ValueError, match="Puzzle already solved"):
                        await guess_service.validate_guess("user123", "20240115-marvel", "Spider-Man")
    
    @pytest.mark.asyncio
    async def test_validate_guess_max_attempts_reached(self, guess_service, sample_user):
        """Test validating guess when max attempts reached"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.guess_repository, 'can_user_make_guess', new_callable=AsyncMock) as mock_can_guess:
                with patch.object(guess_service.guess_repository, 'has_user_solved_puzzle', new_callable=AsyncMock) as mock_solved:
                    
                    mock_get_user.return_value = sample_user
                    mock_can_guess.return_value = False
                    mock_solved.return_value = False
                    
                    with pytest.raises(ValueError, match="Maximum attempts \\(6\\) reached"):
                        await guess_service.validate_guess("user123", "20240115-marvel", "Spider-Man")
    
    @pytest.mark.asyncio
    async def test_validate_guess_user_not_found(self, guess_service):
        """Test validating guess for non-existent user"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None
            
            with pytest.raises(ItemNotFoundError, match="User user123 not found"):
                await guess_service.validate_guess("user123", "20240115-marvel", "Spider-Man")
    
    @pytest.mark.asyncio
    async def test_validate_guess_invalid_puzzle_id(self, guess_service, sample_user):
        """Test validating guess with invalid puzzle ID"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = sample_user
            
            with pytest.raises(ValueError, match="Invalid puzzle ID format"):
                await guess_service.validate_guess("user123", "invalid-puzzle-id", "Spider-Man")
    
    @pytest.mark.asyncio
    async def test_update_user_streak_correct_guess(self, guess_service, sample_user):
        """Test updating user streak for correct guess"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.user_repository, 'update_user', new_callable=AsyncMock) as mock_update:
                
                mock_get_user.return_value = sample_user
                
                result = await guess_service._update_user_streak("user123", "marvel", True)
                
                assert result == 6  # 5 + 1
                mock_update.assert_called_once()
                
                # Check that streaks were updated correctly
                call_args = mock_update.call_args[0]
                updated_streaks = call_args[1]["streaks"]
                assert updated_streaks["marvel"] == 6
                assert updated_streaks["dc"] == 2  # Unchanged
    
    @pytest.mark.asyncio
    async def test_update_user_streak_incorrect_final_attempt(self, guess_service, sample_user):
        """Test updating user streak for incorrect guess on final attempt"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.user_repository, 'update_user', new_callable=AsyncMock) as mock_update:
                with patch.object(guess_service.guess_repository, 'get_user_attempts_count', new_callable=AsyncMock) as mock_attempts:
                    
                    mock_get_user.return_value = sample_user
                    mock_attempts.return_value = 6  # Max attempts reached
                    
                    result = await guess_service._update_user_streak("user123", "marvel", False)
                    
                    assert result == 0  # Streak reset
                    
                    # Check that streaks were updated correctly
                    call_args = mock_update.call_args[0]
                    updated_streaks = call_args[1]["streaks"]
                    assert updated_streaks["marvel"] == 0
    
    @pytest.mark.asyncio
    async def test_can_user_guess(self, guess_service):
        """Test checking if user can make a guess"""
        with patch.object(guess_service.guess_repository, 'has_user_solved_puzzle', new_callable=AsyncMock) as mock_solved:
            with patch.object(guess_service.guess_repository, 'get_user_attempts_count', new_callable=AsyncMock) as mock_attempts:
                with patch.object(guess_service.guess_repository, 'can_user_make_guess', new_callable=AsyncMock) as mock_can_guess:
                    
                    mock_solved.return_value = False
                    mock_attempts.return_value = 3
                    mock_can_guess.return_value = True
                    
                    result = await guess_service.can_user_guess("user123", "20240115-marvel")
                    
                    assert result["can_guess"] is True
                    assert result["is_solved"] is False
                    assert result["attempts_used"] == 3
                    assert result["attempts_remaining"] == 3
                    assert result["max_attempts"] == 6
    
    @pytest.mark.asyncio
    async def test_get_daily_progress(self, guess_service, sample_user):
        """Test getting daily progress for all universes"""
        with patch.object(guess_service.puzzle_service, 'generate_puzzle_id') as mock_gen_id:
            with patch.object(guess_service.puzzle_service, 'get_daily_puzzle', new_callable=AsyncMock) as mock_get_puzzle:
                with patch.object(guess_service, 'can_user_guess', new_callable=AsyncMock) as mock_can_guess:
                    with patch.object(guess_service, 'get_user_guess_history', new_callable=AsyncMock) as mock_history:
                        
                        mock_gen_id.side_effect = lambda date, universe: f"20240115-{universe}"
                        mock_get_puzzle.return_value = True  # Puzzle exists
                        mock_can_guess.return_value = {
                            "is_solved": False,
                            "attempts_used": 2,
                            "attempts_remaining": 4,
                            "can_guess": True
                        }
                        mock_history.return_value = GuessHistory(
                            puzzle_id="20240115-marvel",
                            guesses=["Iron Man", "Captain America"],
                            is_solved=False,
                            attempts_used=2
                        )
                        
                        result = await guess_service.get_daily_progress("user123", "2024-01-15")
                        
                        assert len(result) == 3  # marvel, dc, image
                        assert all(universe in result for universe in ["marvel", "dc", "image"])
                        
                        for universe_data in result.values():
                            assert universe_data["puzzle_available"] is True
                            assert universe_data["is_solved"] is False
                            assert universe_data["attempts_used"] == 2
                            assert len(universe_data["guesses"]) == 2
    
    @pytest.mark.asyncio
    async def test_calculate_streak_statistics(self, guess_service, sample_user):
        """Test calculating streak statistics"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = sample_user
            
            result = await guess_service.calculate_streak_statistics("user123")
            
            assert result["current_streaks"] == {"marvel": 5, "dc": 2, "image": 0}
            assert result["total_current_streak"] == 7
            assert result["best_universe"] == "marvel"
            assert result["best_streak_value"] == 5
            assert result["max_streaks"] == {"marvel": 5, "dc": 2, "image": 0}
    
    @pytest.mark.asyncio
    async def test_reset_streak(self, guess_service, sample_user):
        """Test resetting streak for a universe"""
        with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
            with patch.object(guess_service.user_repository, 'update_user', new_callable=AsyncMock) as mock_update:
                
                mock_get_user.return_value = sample_user
                
                result = await guess_service.reset_streak("user123", "marvel")
                
                assert result == 0
                
                # Check that only marvel streak was reset
                call_args = mock_update.call_args[0]
                updated_streaks = call_args[1]["streaks"]
                assert updated_streaks["marvel"] == 0
                assert updated_streaks["dc"] == 2  # Unchanged
                assert updated_streaks["image"] == 0  # Unchanged
    
    @pytest.mark.asyncio
    async def test_simulate_guess_outcome(self, guess_service, sample_user):
        """Test simulating guess outcome without recording"""
        with patch.object(guess_service.puzzle_service, 'validate_puzzle_guess', new_callable=AsyncMock) as mock_validate:
            with patch.object(guess_service.guess_repository, 'get_next_attempt_number', new_callable=AsyncMock) as mock_attempt:
                with patch.object(guess_service.user_repository, 'get_user_by_id', new_callable=AsyncMock) as mock_get_user:
                    
                    mock_validate.return_value = (True, "Spider-Man", "marvel/spiderman.jpg")
                    mock_attempt.return_value = 3
                    mock_get_user.return_value = sample_user
                    
                    result = await guess_service.simulate_guess_outcome("user123", "20240115-marvel", "Spider-Man")
                    
                    assert result["would_be_correct"] is True
                    assert result["character_name"] == "Spider-Man"
                    assert result["current_streak"] == 5
                    assert result["new_streak"] == 6  # Would increment
                    assert result["attempt_number"] == 3
                    assert result["game_would_end"] is True
    
    @pytest.mark.asyncio
    async def test_check_streak_maintenance(self, guess_service):
        """Test checking streak maintenance status"""
        progress_data = {
            "marvel": {
                "puzzle_available": True,
                "is_solved": True,
                "can_guess": False,
                "attempts_remaining": 0
            },
            "dc": {
                "puzzle_available": True,
                "is_solved": False,
                "can_guess": True,
                "attempts_remaining": 4
            },
            "image": {
                "puzzle_available": False
            }
        }
        
        with patch.object(guess_service, 'get_daily_progress', new_callable=AsyncMock) as mock_progress:
            mock_progress.return_value = progress_data
            
            result = await guess_service.check_streak_maintenance("user123")
            
            assert result["marvel"]["status"] == "completed"
            assert result["dc"]["status"] == "pending"
            assert result["image"]["status"] == "no_puzzle"
    
    def test_build_image_url(self, guess_service):
        """Test building image URL from image key"""
        image_key = "marvel/spiderman.jpg"
        result = guess_service._build_image_url(image_key)
        
        assert result == "https://your-cdn-domain.com/marvel/spiderman.jpg"
    
    def test_get_today_puzzle_id(self, guess_service):
        """Test getting today's puzzle ID"""
        with patch('app.services.guess_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.strftime.return_value = "20240115"
            
            result = guess_service._get_today_puzzle_id("marvel")
            
            assert result == "20240115-marvel"