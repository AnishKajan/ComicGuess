"""Integration tests for user management API endpoints"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status
import json

from main import app
from app.models.user import User, UserUpdate, UserStats
from app.repositories.user_repository import UserRepository
from app.auth.jwt_handler import create_access_token
from app.auth.session import session_manager
from app.database.exceptions import ItemNotFoundError, DuplicateItemError


class TestUserAPI:
    """Integration tests for user management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup_auth_mocks(self, sample_user, other_user):
        """Setup authentication mocks for all tests"""
        with patch('app.auth.middleware.UserRepository') as mock_auth_repo_class:
            mock_auth_repo = AsyncMock(spec=UserRepository)
            mock_auth_repo_class.return_value = mock_auth_repo
            
            # Configure the mock to return the appropriate user based on ID
            def get_user_by_id_side_effect(user_id):
                if user_id == sample_user.id:
                    return sample_user
                elif user_id == other_user.id:
                    return other_user
                return None
            
            mock_auth_repo.get_user_by_id.side_effect = get_user_by_id_side_effect
            yield mock_auth_repo
    
    @pytest.fixture
    def client(self):
        """Test client for FastAPI app"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_user(self):
        """Sample user for testing"""
        return User(
            id="test-user-123",
            username="testuser",
            email="test@example.com",
            total_games=10,
            total_wins=7,
            streaks={"marvel": 3, "DC": 1, "image": 0},
            last_played={"marvel": "2024-01-15", "DC": "2024-01-14", "image": None}
        )
    
    @pytest.fixture
    def other_user(self):
        """Another user for testing access control"""
        return User(
            id="other-user-456",
            username="otheruser",
            email="other@example.com"
        )
    
    @pytest.fixture
    def auth_headers(self, sample_user):
        """Authentication headers for test user"""
        # Clear any existing sessions first
        session_manager.invalidate_session(sample_user.id)
        # Create session for the user
        session = session_manager.create_session(sample_user)
        return {"Authorization": f"Bearer {session.access_token}"}
    
    @pytest.fixture
    def other_auth_headers(self, other_user):
        """Authentication headers for other user"""
        # Clear any existing sessions first
        session_manager.invalidate_session(other_user.id)
        # Create session for the other user
        session = session_manager.create_session(other_user)
        return {"Authorization": f"Bearer {session.access_token}"}
    
    @pytest.fixture
    def mock_user_repo(self):
        """Mock user repository"""
        with patch('app.api.users.UserRepository') as mock_repo_class:
            mock_repo = AsyncMock(spec=UserRepository)
            mock_repo_class.return_value = mock_repo
            yield mock_repo
    



class TestGetUser(TestUserAPI):
    """Tests for GET /user/{user_id} endpoint"""
    
    def test_get_user_success(self, client, sample_user, auth_headers, mock_user_repo):
        """Test successful user retrieval"""
        # Mock repository response
        mock_user_repo.get_user_by_id.return_value = sample_user
        
        # Make request
        response = client.get(f"/user/{sample_user.id}", headers=auth_headers)
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        
        user_data = response.json()
        assert user_data["id"] == sample_user.id
        assert user_data["username"] == sample_user.username
        assert user_data["email"] == sample_user.email
        assert user_data["total_games"] == sample_user.total_games
        assert user_data["total_wins"] == sample_user.total_wins
        assert user_data["streaks"] == sample_user.streaks
        
        # Verify repository was called correctly
        mock_user_repo.get_user_by_id.assert_called_once_with(sample_user.id)
    
    def test_get_user_not_found(self, client, sample_user, auth_headers, mock_user_repo):
        """Test user not found"""
        # Mock repository to return None
        mock_user_repo.get_user_by_id.return_value = None
        
        # Make request
        response = client.get(f"/user/{sample_user.id}", headers=auth_headers)
        
        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    def test_get_user_access_denied(self, client, sample_user, other_user, other_auth_headers, mock_user_repo):
        """Test access denied when trying to access other user's data"""
        # Make request with other user's token
        response = client.get(f"/user/{sample_user.id}", headers=other_auth_headers)
        
        # Verify response
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in response.json()["detail"]
        
        # Repository should not be called
        mock_user_repo.get_user_by_id.assert_not_called()
    
    def test_get_user_no_auth(self, client, sample_user):
        """Test request without authentication"""
        response = client.get(f"/user/{sample_user.id}")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_user_invalid_token(self, client, sample_user):
        """Test request with invalid token"""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get(f"/user/{sample_user.id}", headers=headers)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_user_repository_error(self, client, sample_user, auth_headers, mock_user_repo):
        """Test repository error handling"""
        # Mock repository to raise exception
        mock_user_repo.get_user_by_id.side_effect = Exception("Database error")
        
        response = client.get(f"/user/{sample_user.id}", headers=auth_headers)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Internal server error" in response.json()["detail"]


class TestUpdateUser(TestUserAPI):
    """Tests for POST /user/{user_id} endpoint"""
    
    def test_update_user_success(self, client, sample_user, auth_headers, mock_user_repo):
        """Test successful user update"""
        # Prepare update data
        update_data = {
            "username": "newusername",
            "email": "newemail@example.com"
        }
        
        # Mock repository responses
        mock_user_repo.get_user_by_id.return_value = sample_user
        mock_user_repo.get_user_by_email.return_value = None  # No email conflict
        
        updated_user = User(**{**sample_user.model_dump(), **update_data})
        mock_user_repo.update_user.return_value = updated_user
        
        # Make request
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        
        user_data = response.json()
        assert user_data["username"] == update_data["username"]
        assert user_data["email"] == update_data["email"]
        
        # Verify repository calls
        mock_user_repo.get_user_by_id.assert_called_once_with(sample_user.id)
        mock_user_repo.get_user_by_email.assert_called_once_with(update_data["email"])
        mock_user_repo.update_user.assert_called_once()
    
    def test_update_user_partial(self, client, sample_user, auth_headers, mock_user_repo):
        """Test partial user update (only username)"""
        update_data = {"username": "newusername"}
        
        # Mock repository responses
        mock_user_repo.get_user_by_id.return_value = sample_user
        
        updated_user = User(**{**sample_user.model_dump(), **update_data})
        mock_user_repo.update_user.return_value = updated_user
        
        # Make request
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["username"] == update_data["username"]
        
        # Email check should not be called since email wasn't updated
        mock_user_repo.get_user_by_email.assert_not_called()
    
    def test_update_user_email_conflict(self, client, sample_user, other_user, auth_headers, mock_user_repo):
        """Test email conflict during update"""
        update_data = {"email": "other@example.com"}
        
        # Mock repository responses
        mock_user_repo.get_user_by_id.return_value = sample_user
        mock_user_repo.get_user_by_email.return_value = other_user  # Email already exists
        
        # Make request
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already in use" in response.json()["detail"]
        
        # Update should not be called
        mock_user_repo.update_user.assert_not_called()
    
    def test_update_user_same_email(self, client, sample_user, auth_headers, mock_user_repo):
        """Test updating to same email (should be allowed)"""
        update_data = {"email": sample_user.email}
        
        # Mock repository responses
        mock_user_repo.get_user_by_id.return_value = sample_user
        mock_user_repo.get_user_by_email.return_value = sample_user  # Same user
        
        updated_user = User(**sample_user.model_dump())
        mock_user_repo.update_user.return_value = updated_user
        
        # Make request
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        
        # Update should be called
        mock_user_repo.update_user.assert_called_once()
    
    def test_update_user_not_found(self, client, sample_user, auth_headers, mock_user_repo):
        """Test updating non-existent user"""
        update_data = {"username": "newusername"}
        
        # Mock repository to return None
        mock_user_repo.get_user_by_id.return_value = None
        
        # Make request
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    def test_update_user_access_denied(self, client, sample_user, other_auth_headers):
        """Test access denied when trying to update other user"""
        update_data = {"username": "newusername"}
        
        # Make request with other user's token
        response = client.post(
            f"/user/{sample_user.id}",
            headers=other_auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in response.json()["detail"]
    
    def test_update_user_invalid_data(self, client, sample_user, auth_headers):
        """Test update with invalid data"""
        update_data = {
            "username": "ab",  # Too short
            "email": "invalid-email"  # Invalid format
        }
        
        # Make request
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_update_user_repository_error(self, client, sample_user, auth_headers, mock_user_repo):
        """Test repository error during update"""
        update_data = {"username": "newusername"}
        
        # Mock repository responses
        mock_user_repo.get_user_by_id.return_value = sample_user
        mock_user_repo.update_user.side_effect = Exception("Database error")
        
        # Make request
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Verify response
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Internal server error" in response.json()["detail"]


class TestGetUserStats(TestUserAPI):
    """Tests for GET /user/{user_id}/stats endpoint"""
    
    def test_get_user_stats_success(self, client, sample_user, auth_headers, mock_user_repo):
        """Test successful user stats retrieval"""
        # Create expected stats
        expected_stats = UserStats.from_user(sample_user)
        
        # Mock repository response
        mock_user_repo.get_user_stats.return_value = expected_stats
        
        # Make request
        response = client.get(f"/user/{sample_user.id}/stats", headers=auth_headers)
        
        # Verify response
        assert response.status_code == status.HTTP_200_OK
        
        stats_data = response.json()
        assert stats_data["total_games"] == expected_stats.total_games
        assert stats_data["total_wins"] == expected_stats.total_wins
        assert stats_data["win_rate"] == expected_stats.win_rate
        assert stats_data["streaks"] == expected_stats.streaks
        assert stats_data["last_played"] == expected_stats.last_played
        
        # Verify repository was called correctly
        mock_user_repo.get_user_stats.assert_called_once_with(sample_user.id)
    
    def test_get_user_stats_not_found(self, client, sample_user, auth_headers, mock_user_repo):
        """Test stats for non-existent user"""
        # Mock repository to raise ItemNotFoundError
        mock_user_repo.get_user_stats.side_effect = ItemNotFoundError(f"User with id {sample_user.id} not found")
        
        # Make request
        response = client.get(f"/user/{sample_user.id}/stats", headers=auth_headers)
        
        # Verify response
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    def test_get_user_stats_access_denied(self, client, sample_user, other_auth_headers, mock_user_repo):
        """Test access denied when trying to access other user's stats"""
        # Make request with other user's token
        response = client.get(f"/user/{sample_user.id}/stats", headers=other_auth_headers)
        
        # Verify response
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in response.json()["detail"]
        
        # Repository should not be called
        mock_user_repo.get_user_stats.assert_not_called()
    
    def test_get_user_stats_no_auth(self, client, sample_user):
        """Test request without authentication"""
        response = client.get(f"/user/{sample_user.id}/stats")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_user_stats_repository_error(self, client, sample_user, auth_headers, mock_user_repo):
        """Test repository error handling"""
        # Mock repository to raise exception
        mock_user_repo.get_user_stats.side_effect = Exception("Database error")
        
        response = client.get(f"/user/{sample_user.id}/stats", headers=auth_headers)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Internal server error" in response.json()["detail"]





class TestAuthenticationIntegration(TestUserAPI):
    """Integration tests for authentication with user endpoints"""
    
    @patch('app.auth.middleware.UserRepository')
    def test_full_authentication_flow(self, mock_repo_class, client, sample_user):
        """Test complete authentication flow with user endpoints"""
        # Mock repository for authentication middleware
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_user_by_id.return_value = sample_user
        
        # Create session for user
        session = session_manager.create_session(sample_user)
        headers = {"Authorization": f"Bearer {session.access_token}"}
        
        # Mock repository for user endpoint
        with patch('app.api.users.UserRepository') as mock_user_repo_class:
            mock_user_repo = AsyncMock()
            mock_user_repo_class.return_value = mock_user_repo
            mock_user_repo.get_user_by_id.return_value = sample_user
            
            # Make authenticated request
            response = client.get(f"/user/{sample_user.id}", headers=headers)
            
            # Verify success
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["id"] == sample_user.id
        
        # Clean up session
        session_manager.invalidate_session(sample_user.id)
    
    def test_expired_token_handling(self, client, sample_user):
        """Test handling of expired tokens"""
        # Create an expired token (mock it as expired)
        with patch('app.auth.jwt_handler.jwt_handler.is_token_expired', return_value=True):
            token = create_access_token(sample_user.id)
            headers = {"Authorization": f"Bearer {token}"}
            
            response = client.get(f"/user/{sample_user.id}", headers=headers)
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestErrorHandling(TestUserAPI):
    """Tests for comprehensive error handling"""
    
    def test_malformed_json(self, client, sample_user, auth_headers):
        """Test handling of malformed JSON in request body"""
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            data="invalid json"
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_missing_content_type(self, client, sample_user, auth_headers):
        """Test handling of missing content type"""
        response = client.post(
            f"/user/{sample_user.id}",
            headers={**auth_headers, "Content-Type": "text/plain"},
            data="not json"
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_empty_request_body(self, client, sample_user, auth_headers, mock_user_repo):
        """Test handling of empty request body for update"""
        # Mock repository responses
        mock_user_repo.get_user_by_id.return_value = sample_user
        mock_user_repo.update_user.return_value = sample_user
        
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json={}
        )
        
        # Empty update should still succeed (no changes)
        assert response.status_code == status.HTTP_200_OK


class TestConcurrency(TestUserAPI):
    """Tests for concurrent access scenarios"""
    
    @patch('app.api.users.UserRepository')
    def test_concurrent_user_updates(self, mock_repo_class, client, sample_user, auth_headers):
        """Test handling of concurrent user updates"""
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        
        # Simulate concurrent modification by having the user change between get and update
        original_user = sample_user
        modified_user = User(**{**sample_user.model_dump(), "username": "changed_by_other"})
        
        mock_repo.get_user_by_id.side_effect = [original_user, modified_user]
        mock_repo.update_user.return_value = modified_user
        
        update_data = {"username": "my_update"}
        
        response = client.post(
            f"/user/{sample_user.id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Should still succeed - last write wins
        assert response.status_code == status.HTTP_200_OK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])