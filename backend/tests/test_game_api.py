"""Integration tests for game API endpoints"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from datetime import datetime

from main import app
from app.models.puzzle import Puzzle, PuzzleResponse
from app.models.guess import GuessResponse, GuessHistory
from app.models.user import User
from app.database.exceptions import ItemNotFoundError
from app.api.game import get_current_user

# Override the dependency for testing
def override_get_current_user():
    return User(
        id="user123",
        username="testuser",
        email="test@example.com",
        streaks={"marvel": 5, "dc": 2, "image": 0},
        last_played={"marvel": "2024-01-14", "dc": "2024-01-13"},
        total_games=10,
        total_wins=7
    )

app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)

class TestGameAPI:
    """Test cases for game API endpoints"""
    
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
            character_aliases=["Spidey", "Web-Slinger"],
            image_key="marvel/spiderman.jpg",
            active_date="2024-01-15"
        )
    
    @pytest.fixture
    def sample_puzzle_response(self):
        """Sample puzzle response for testing"""
        return PuzzleResponse(
            id="20240115-marvel",
            universe="marvel",
            active_date="2024-01-15"
        )
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication dependency - now handled by dependency override"""
        return True
    
    def test_submit_guess_correct(self, mock_auth, sample_puzzle):
        """Test submitting a correct guess"""
        guess_response = GuessResponse(
            correct=True,
            character="Spider-Man",
            image_url="https://example.com/spiderman.jpg",
            streak=6,
            attempt_number=1,
            max_attempts=6,
            game_over=True
        )
        
        with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
            with patch("app.api.game.puzzle_service.generate_puzzle_id", return_value="20240115-marvel"):
                with patch("app.api.game.puzzle_service.get_daily_puzzle", new_callable=AsyncMock) as mock_get_puzzle:
                    with patch("app.api.game.guess_service.validate_guess", new_callable=AsyncMock) as mock_validate:
                        
                        mock_get_puzzle.return_value = sample_puzzle
                        mock_validate.return_value = guess_response
                        
                        response = client.post("/api/guess", json={
                            "user_id": "user123",
                            "universe": "marvel",
                            "guess": "Spider-Man"
                        })
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["correct"] is True
                        assert data["character"] == "Spider-Man"
                        assert data["streak"] == 6
                        assert data["game_over"] is True
    
    def test_submit_guess_incorrect(self, mock_auth, sample_puzzle):
        """Test submitting an incorrect guess"""
        guess_response = GuessResponse(
            correct=False,
            character=None,
            image_url=None,
            streak=5,
            attempt_number=2,
            max_attempts=6,
            game_over=False
        )
        
        with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
            with patch("app.api.game.puzzle_service.generate_puzzle_id", return_value="20240115-marvel"):
                with patch("app.api.game.puzzle_service.get_daily_puzzle", new_callable=AsyncMock) as mock_get_puzzle:
                    with patch("app.api.game.guess_service.validate_guess", new_callable=AsyncMock) as mock_validate:
                        
                        mock_get_puzzle.return_value = sample_puzzle
                        mock_validate.return_value = guess_response
                        
                        response = client.post("/api/guess", json={
                            "user_id": "user123",
                            "universe": "marvel",
                            "guess": "Iron Man"
                        })
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["correct"] is False
                        assert data["character"] is None
                        assert data["streak"] == 5
                        assert data["game_over"] is False
    
    def test_submit_guess_invalid_universe(self, mock_auth):
        """Test submitting guess with invalid universe"""
        response = client.post("/api/guess", json={
            "user_id": "user123",
            "universe": "invalid",
            "guess": "Spider-Man"
        })
        
        assert response.status_code == 400
        assert "Universe must be one of" in response.json()["detail"]
    
    def test_submit_guess_no_puzzle(self, mock_auth):
        """Test submitting guess when no puzzle exists"""
        with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
            with patch("app.api.game.puzzle_service.generate_puzzle_id", return_value="20240115-marvel"):
                with patch("app.api.game.puzzle_service.get_daily_puzzle", new_callable=AsyncMock) as mock_get_puzzle:
                    
                    mock_get_puzzle.return_value = None
                    
                    response = client.post("/api/guess", json={
                        "user_id": "user123",
                        "universe": "marvel",
                        "guess": "Spider-Man"
                    })
                    
                    assert response.status_code == 404
                    assert "No puzzle available" in response.json()["detail"]
    
    def test_submit_guess_already_solved(self, mock_auth, sample_puzzle):
        """Test submitting guess when puzzle already solved"""
        with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
            with patch("app.api.game.puzzle_service.generate_puzzle_id", return_value="20240115-marvel"):
                with patch("app.api.game.puzzle_service.get_daily_puzzle", new_callable=AsyncMock) as mock_get_puzzle:
                    with patch("app.api.game.guess_service.validate_guess", new_callable=AsyncMock) as mock_validate:
                        
                        mock_get_puzzle.return_value = sample_puzzle
                        mock_validate.side_effect = ValueError("Puzzle already solved")
                        
                        response = client.post("/api/guess", json={
                            "user_id": "user123",
                            "universe": "marvel",
                            "guess": "Spider-Man"
                        })
                        
                        assert response.status_code == 400
                        assert "Puzzle already solved" in response.json()["detail"]
    
    def test_get_today_puzzle(self, mock_auth, sample_puzzle_response):
        """Test getting today's puzzle"""
        with patch("app.api.game.puzzle_service.get_daily_puzzle_response", new_callable=AsyncMock) as mock_get_puzzle:
            mock_get_puzzle.return_value = sample_puzzle_response
            
            response = client.get("/api/puzzle/today?universe=marvel")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "20240115-marvel"
            assert data["universe"] == "marvel"
            assert data["active_date"] == "2024-01-15"
            # Should not contain character info
            assert "character" not in data
    
    def test_get_today_puzzle_invalid_universe(self, mock_auth):
        """Test getting today's puzzle with invalid universe"""
        response = client.get("/api/puzzle/today?universe=invalid")
        
        assert response.status_code == 400
        assert "Universe must be one of" in response.json()["detail"]
    
    def test_get_today_puzzle_not_found(self, mock_auth):
        """Test getting today's puzzle when none exists"""
        with patch("app.api.game.puzzle_service.get_daily_puzzle_response", new_callable=AsyncMock) as mock_get_puzzle:
            mock_get_puzzle.return_value = None
            
            response = client.get("/api/puzzle/today?universe=marvel")
            
            assert response.status_code == 404
            assert "No puzzle available" in response.json()["detail"]
    
    def test_get_puzzle_status(self, mock_auth, sample_puzzle):
        """Test getting puzzle status"""
        guess_status = {
            "can_guess": True,
            "is_solved": False,
            "attempts_used": 2,
            "attempts_remaining": 4,
            "max_attempts": 6
        }
        
        with patch("app.api.game.puzzle_service.puzzle_repository.get_puzzle_by_id", new_callable=AsyncMock) as mock_get_puzzle:
            with patch("app.api.game.guess_service.can_user_guess", new_callable=AsyncMock) as mock_can_guess:
                
                mock_get_puzzle.return_value = sample_puzzle
                mock_can_guess.return_value = guess_status
                
                response = client.get("/api/puzzle/20240115-marvel/status?user_id=user123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["puzzle_id"] == "20240115-marvel"
                assert data["universe"] == "marvel"
                assert data["can_guess"] is True
                assert data["attempts_used"] == 2
                assert data["attempts_remaining"] == 4
    
    def test_get_puzzle_status_invalid_id(self, mock_auth):
        """Test getting puzzle status with invalid puzzle ID"""
        response = client.get("/api/puzzle/invalid-id/status?user_id=user123")
        
        assert response.status_code == 400
        assert "Invalid puzzle ID format" in response.json()["detail"]
    
    def test_get_puzzle_status_not_found(self, mock_auth):
        """Test getting puzzle status for non-existent puzzle"""
        with patch("app.api.game.puzzle_service.puzzle_repository.get_puzzle_by_id", new_callable=AsyncMock) as mock_get_puzzle:
            mock_get_puzzle.return_value = None
            
            response = client.get("/api/puzzle/20240115-marvel/status?user_id=user123")
            
            assert response.status_code == 404
            assert "Puzzle 20240115-marvel not found" in response.json()["detail"]
    
    def test_get_guess_history(self, mock_auth, sample_puzzle):
        """Test getting guess history"""
        guess_history = GuessHistory(
            puzzle_id="20240115-marvel",
            guesses=["Iron Man", "Captain America"],
            is_solved=False,
            attempts_used=2
        )
        
        with patch("app.api.game.puzzle_service.puzzle_repository.get_puzzle_by_id", new_callable=AsyncMock) as mock_get_puzzle:
            with patch("app.api.game.guess_service.get_user_guess_history", new_callable=AsyncMock) as mock_get_history:
                
                mock_get_puzzle.return_value = sample_puzzle
                mock_get_history.return_value = guess_history
                
                response = client.get("/api/puzzle/20240115-marvel/history?user_id=user123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["puzzle_id"] == "20240115-marvel"
                assert data["guesses"] == ["Iron Man", "Captain America"]
                assert data["is_solved"] is False
                assert data["attempts_used"] == 2
    
    def test_get_daily_progress(self, mock_auth):
        """Test getting daily progress"""
        progress_data = {
            "marvel": {
                "puzzle_available": True,
                "puzzle_id": "20240115-marvel",
                "is_solved": True,
                "attempts_used": 1,
                "attempts_remaining": 5,
                "can_guess": False,
                "guesses": ["Spider-Man"]
            },
            "dc": {
                "puzzle_available": True,
                "puzzle_id": "20240115-dc",
                "is_solved": False,
                "attempts_used": 2,
                "attempts_remaining": 4,
                "can_guess": True,
                "guesses": ["Batman", "Superman"]
            },
            "image": {
                "puzzle_available": False,
                "puzzle_id": "20240115-image"
            }
        }
        
        with patch("app.api.game.guess_service.get_daily_progress", new_callable=AsyncMock) as mock_get_progress:
            with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
                
                mock_get_progress.return_value = progress_data
                
                response = client.get("/api/daily-progress?user_id=user123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["date"] == "2024-01-15"
                assert data["user_id"] == "user123"
                assert "universes" in data
                assert data["universes"]["marvel"]["is_solved"] is True
                assert data["universes"]["dc"]["is_solved"] is False
    
    def test_get_streak_status(self, mock_auth):
        """Test getting streak status"""
        streak_stats = {
            "current_streaks": {"marvel": 5, "dc": 2, "image": 0},
            "total_current_streak": 7,
            "best_universe": "marvel",
            "best_streak_value": 5,
            "max_streaks": {"marvel": 5, "dc": 2, "image": 0}
        }
        
        maintenance_status = {
            "marvel": {"status": "completed", "message": "Puzzle solved - streak maintained"},
            "dc": {"status": "pending", "message": "Puzzle not attempted - streak at risk"},
            "image": {"status": "no_puzzle", "message": "No puzzle available today"}
        }
        
        with patch("app.api.game.guess_service.calculate_streak_statistics", new_callable=AsyncMock) as mock_stats:
            with patch("app.api.game.guess_service.check_streak_maintenance", new_callable=AsyncMock) as mock_maintenance:
                with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
                    
                    mock_stats.return_value = streak_stats
                    mock_maintenance.return_value = maintenance_status
                    
                    response = client.get("/api/streak-status?user_id=user123")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["user_id"] == "user123"
                    assert data["streak_statistics"]["total_current_streak"] == 7
                    assert data["maintenance_status"]["marvel"]["status"] == "completed"
    
    def test_simulate_guess(self, mock_auth, sample_puzzle):
        """Test simulating a guess"""
        simulation_result = {
            "would_be_correct": True,
            "character_name": "Spider-Man",
            "current_streak": 5,
            "new_streak": 6,
            "attempt_number": 1,
            "game_would_end": True
        }
        
        with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
            with patch("app.api.game.puzzle_service.generate_puzzle_id", return_value="20240115-marvel"):
                with patch("app.api.game.puzzle_service.get_daily_puzzle", new_callable=AsyncMock) as mock_get_puzzle:
                    with patch("app.api.game.guess_service.simulate_guess_outcome", new_callable=AsyncMock) as mock_simulate:
                        
                        mock_get_puzzle.return_value = sample_puzzle
                        mock_simulate.return_value = simulation_result
                        
                        response = client.post("/api/simulate-guess", json={
                            "user_id": "user123",
                            "universe": "marvel",
                            "guess": "Spider-Man"
                        })
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["simulation"] is True
                        assert data["puzzle_id"] == "20240115-marvel"
                        assert data["would_be_correct"] is True
                        assert data["character_name"] == "Spider-Man"
    
    def test_health_check(self):
        """Test health check endpoint"""
        with patch("app.api.game.puzzle_service.get_today_date", return_value="2024-01-15"):
            response = client.get("/api/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "game-api"
            assert data["timestamp"] == "2024-01-15"
    
    def test_submit_guess_missing_fields(self, mock_auth):
        """Test submitting guess with missing required fields"""
        response = client.post("/api/guess", json={
            "user_id": "user123",
            "universe": "marvel"
            # Missing 'guess' field
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_submit_guess_empty_guess(self, mock_auth):
        """Test submitting empty guess"""
        response = client.post("/api/guess", json={
            "user_id": "user123",
            "universe": "marvel",
            "guess": ""
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_get_puzzle_status_missing_user_id(self, mock_auth):
        """Test getting puzzle status without user_id parameter"""
        response = client.get("/api/puzzle/20240115-marvel/status")
        
        assert response.status_code == 422  # Missing required query parameter
    
    def test_get_daily_progress_missing_user_id(self, mock_auth):
        """Test getting daily progress without user_id parameter"""
        response = client.get("/api/daily-progress")
        
        assert response.status_code == 422  # Missing required query parameter
    
    def test_error_handling_internal_server_error(self, mock_auth):
        """Test internal server error handling"""
        with patch("app.api.game.puzzle_service.get_daily_puzzle_response", new_callable=AsyncMock) as mock_get_puzzle:
            mock_get_puzzle.side_effect = Exception("Database connection failed")
            
            response = client.get("/api/puzzle/today?universe=marvel")
            
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]