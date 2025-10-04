"""
Tests for data rights API endpoints for GDPR/COPPA compliance
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.guess import Guess
from app.models.puzzle import Puzzle

client = TestClient(app)

@pytest.fixture
def mock_user():
    """Mock user for testing"""
    return User(
        id="test-user-123",
        username="testuser",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        streaks={"marvel": 5, "dc": 3, "image": 0},
        last_played={"marvel": "2024-01-15", "dc": "2024-01-14"},
        total_games=10,
        total_wins=8
    )

@pytest.fixture
def mock_guesses():
    """Mock guesses for testing"""
    return [
        Guess(
            id="guess-1",
            user_id="test-user-123",
            puzzle_id="20240115-marvel",
            guess="Spider-Man",
            is_correct=True,
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            attempt_number=1
        ),
        Guess(
            id="guess-2",
            user_id="test-user-123",
            puzzle_id="20240115-dc",
            guess="Batman",
            is_correct=True,
            timestamp=datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
            attempt_number=2
        )
    ]

@pytest.fixture
def mock_puzzles():
    """Mock puzzles for testing"""
    return {
        "20240115-marvel": Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker"],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        ),
        "20240115-dc": Puzzle(
            id="20240115-dc",
            universe="dc",
            character="Batman",
            character_aliases=["Bruce Wayne", "Dark Knight"],
            image_key="dc/batman.jpg",
            active_date="2024-01-15"
        )
    }

@pytest.fixture
def auth_headers():
    """Mock authentication headers"""
    return {"Authorization": "Bearer valid-token"}

class TestDataExportAPI:
    """Test data export functionality"""

    @patch('app.api.data_rights.get_current_user')
    @patch('app.api.data_rights.get_database')
    async def test_export_user_data_success(self, mock_db, mock_auth, mock_user, mock_guesses, mock_puzzles):
        """Test successful data export"""
        # Setup mocks
        mock_auth.return_value = mock_user
        mock_user_repo = AsyncMock()
        mock_guess_repo = AsyncMock()
        mock_puzzle_repo = AsyncMock()
        
        mock_user_repo.get_by_id.return_value = mock_user
        mock_guess_repo.get_by_user_id.return_value = mock_guesses
        mock_puzzle_repo.get_by_id.side_effect = lambda pid: mock_puzzles.get(pid)
        
        with patch('app.api.data_rights.UserRepository', return_value=mock_user_repo), \
             patch('app.api.data_rights.GuessRepository', return_value=mock_guess_repo), \
             patch('app.api.data_rights.PuzzleRepository', return_value=mock_puzzle_repo):
            
            response = client.get(
                "/api/user/test-user-123/export",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers["content-disposition"]
        
        # Parse exported data
        export_data = response.json()
        
        # Verify export structure
        assert "export_info" in export_data
        assert "user_profile" in export_data
        assert "gameplay_history" in export_data
        assert "statistics" in export_data
        
        # Verify user profile data
        user_profile = export_data["user_profile"]
        assert user_profile["id"] == "test-user-123"
        assert user_profile["username"] == "testuser"
        assert user_profile["streaks"] == {"marvel": 5, "dc": 3, "image": 0}
        
        # Verify gameplay history
        gameplay_history = export_data["gameplay_history"]
        assert len(gameplay_history) == 2
        assert gameplay_history[0]["guess"] == "Spider-Man"
        assert gameplay_history[0]["is_correct"] is True
        
        # Verify statistics
        statistics = export_data["statistics"]
        assert statistics["total_guesses"] == 2
        assert statistics["correct_guesses"] == 2
        assert statistics["accuracy_rate"] == 100.0

    @patch('app.api.data_rights.get_current_user')
    async def test_export_unauthorized_user(self, mock_auth, mock_user):
        """Test export attempt by unauthorized user"""
        mock_auth.return_value = mock_user
        
        response = client.get(
            "/api/user/different-user-123/export",
            headers={"Authorization": "Bearer valid-token"}
        )
        
        assert response.status_code == 403
        assert "You can only export your own data" in response.json()["detail"]

    @patch('app.api.data_rights.get_current_user')
    @patch('app.api.data_rights.get_database')
    async def test_export_user_not_found(self, mock_db, mock_auth, mock_user):
        """Test export for non-existent user"""
        mock_auth.return_value = mock_user
        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_id.return_value = None
        
        with patch('app.api.data_rights.UserRepository', return_value=mock_user_repo):
            response = client.get(
                "/api/user/test-user-123/export",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

class TestAccountDeletionAPI:
    """Test account deletion functionality"""

    @patch('app.api.data_rights.get_current_user')
    @patch('app.api.data_rights.get_database')
    async def test_delete_account_success(self, mock_db, mock_auth, mock_user):
        """Test successful account deletion"""
        mock_auth.return_value = mock_user
        mock_user_repo = AsyncMock()
        mock_guess_repo = AsyncMock()
        
        mock_user_repo.get_by_id.return_value = mock_user
        mock_user_repo.delete.return_value = True
        mock_guess_repo.delete_by_user_id.return_value = 5  # 5 guesses deleted
        
        with patch('app.api.data_rights.UserRepository', return_value=mock_user_repo), \
             patch('app.api.data_rights.GuessRepository', return_value=mock_guess_repo):
            
            response = client.delete(
                "/api/user/test-user-123",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] is True
        assert "permanently deleted" in result["message"]
        assert result["user_id"] == "test-user-123"
        assert "deleted_at" in result
        
        # Verify deletion calls were made
        mock_guess_repo.delete_by_user_id.assert_called_once_with("test-user-123")
        mock_user_repo.delete.assert_called_once_with("test-user-123")

    @patch('app.api.data_rights.get_current_user')
    async def test_delete_unauthorized_user(self, mock_auth, mock_user):
        """Test deletion attempt by unauthorized user"""
        mock_auth.return_value = mock_user
        
        response = client.delete(
            "/api/user/different-user-123",
            headers={"Authorization": "Bearer valid-token"}
        )
        
        assert response.status_code == 403
        assert "You can only delete your own account" in response.json()["detail"]

    @patch('app.api.data_rights.get_current_user')
    @patch('app.api.data_rights.get_database')
    async def test_delete_user_not_found(self, mock_db, mock_auth, mock_user):
        """Test deletion for non-existent user"""
        mock_auth.return_value = mock_user
        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_id.return_value = None
        
        with patch('app.api.data_rights.UserRepository', return_value=mock_user_repo):
            response = client.delete(
                "/api/user/test-user-123",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

class TestDataSummaryAPI:
    """Test data summary functionality"""

    @patch('app.api.data_rights.get_current_user')
    @patch('app.api.data_rights.get_database')
    async def test_get_data_summary_success(self, mock_db, mock_auth, mock_user, mock_guesses):
        """Test successful data summary retrieval"""
        mock_auth.return_value = mock_user
        mock_user_repo = AsyncMock()
        mock_guess_repo = AsyncMock()
        
        mock_user_repo.get_by_id.return_value = mock_user
        mock_guess_repo.get_by_user_id.return_value = mock_guesses
        
        with patch('app.api.data_rights.UserRepository', return_value=mock_user_repo), \
             patch('app.api.data_rights.GuessRepository', return_value=mock_guess_repo):
            
            response = client.get(
                "/api/user/test-user-123/data-summary",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 200
        
        summary = response.json()
        assert summary["user_id"] == "test-user-123"
        
        # Verify data categories
        assert "data_categories" in summary
        categories = summary["data_categories"]
        assert "profile_data" in categories
        assert "game_statistics" in categories
        assert "gameplay_history" in categories
        
        # Verify gameplay history count
        assert categories["gameplay_history"]["count"] == 2
        
        # Verify data retention info
        assert "data_retention" in summary
        retention = summary["data_retention"]
        assert "active_retention" in retention
        assert "inactive_deletion" in retention
        assert "manual_deletion" in retention
        
        # Verify user rights
        assert "your_rights" in summary
        rights = summary["your_rights"]
        assert "Access your data" in rights
        assert "Export your data" in rights
        assert "Delete your account" in rights

    @patch('app.api.data_rights.get_current_user')
    async def test_get_data_summary_unauthorized(self, mock_auth, mock_user):
        """Test data summary for unauthorized user"""
        mock_auth.return_value = mock_user
        
        response = client.get(
            "/api/user/different-user-123/data-summary",
            headers={"Authorization": "Bearer valid-token"}
        )
        
        assert response.status_code == 403
        assert "You can only view your own data summary" in response.json()["detail"]

class TestCOPPACompliance:
    """Test COPPA compliance features"""

    def test_coppa_information_in_export(self):
        """Test that exported data includes COPPA-relevant information"""
        # This would be tested in integration with actual export
        # Verify that no PII beyond necessary game data is included
        pass

    def test_minimal_data_collection(self):
        """Test that only minimal necessary data is collected"""
        # Verify data models only include necessary fields
        user = User(
            id="test-user",
            username="testuser",
            streaks={},
            last_played={},
            total_games=0,
            total_wins=0
        )
        
        # Verify no email, phone, address, or other PII fields
        user_dict = user.model_dump()
        coppa_sensitive_fields = [
            'email', 'phone', 'address', 'full_name', 
            'birth_date', 'location', 'ip_address'
        ]
        
        for field in coppa_sensitive_fields:
            assert field not in user_dict, f"COPPA-sensitive field '{field}' found in user model"

    def test_parental_consent_information(self):
        """Test that parental consent information is available"""
        # This would verify that legal pages include proper COPPA language
        # about parental consent and data collection from minors
        pass

class TestDataMinimization:
    """Test data minimization principles"""

    def test_user_model_minimal_fields(self):
        """Test that user model contains only necessary fields"""
        user = User(
            id="test",
            username="test",
            streaks={},
            last_played={},
            total_games=0,
            total_wins=0
        )
        
        required_fields = {'id', 'username', 'streaks', 'last_played', 'total_games', 'total_wins'}
        actual_fields = set(user.model_dump().keys())
        
        # Allow for created_at as it's useful for data lifecycle
        allowed_extra_fields = {'created_at'}
        
        unexpected_fields = actual_fields - required_fields - allowed_extra_fields
        assert not unexpected_fields, f"Unexpected fields in user model: {unexpected_fields}"

    def test_guess_model_minimal_fields(self):
        """Test that guess model contains only necessary fields"""
        guess = Guess(
            id="test",
            user_id="test-user",
            puzzle_id="test-puzzle",
            guess="test-guess",
            is_correct=True,
            attempt_number=1
        )
        
        required_fields = {
            'id', 'user_id', 'puzzle_id', 'guess', 
            'is_correct', 'attempt_number'
        }
        actual_fields = set(guess.model_dump().keys())
        
        # Allow for timestamp as it's useful for analytics
        allowed_extra_fields = {'timestamp'}
        
        unexpected_fields = actual_fields - required_fields - allowed_extra_fields
        assert not unexpected_fields, f"Unexpected fields in guess model: {unexpected_fields}"

class TestErrorHandling:
    """Test error handling for data rights operations"""

    @patch('app.api.data_rights.get_current_user')
    @patch('app.api.data_rights.get_database')
    async def test_export_database_error(self, mock_db, mock_auth, mock_user):
        """Test export handling of database errors"""
        mock_auth.return_value = mock_user
        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_id.side_effect = Exception("Database connection failed")
        
        with patch('app.api.data_rights.UserRepository', return_value=mock_user_repo):
            response = client.get(
                "/api/user/test-user-123/export",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 500
        assert "Failed to export user data" in response.json()["detail"]

    @patch('app.api.data_rights.get_current_user')
    @patch('app.api.data_rights.get_database')
    async def test_delete_database_error(self, mock_db, mock_auth, mock_user):
        """Test deletion handling of database errors"""
        mock_auth.return_value = mock_user
        mock_user_repo = AsyncMock()
        mock_user_repo.get_by_id.return_value = mock_user
        mock_user_repo.delete.side_effect = Exception("Database connection failed")
        
        with patch('app.api.data_rights.UserRepository', return_value=mock_user_repo):
            response = client.delete(
                "/api/user/test-user-123",
                headers={"Authorization": "Bearer valid-token"}
            )
        
        assert response.status_code == 500
        assert "Failed to delete user account" in response.json()["detail"]