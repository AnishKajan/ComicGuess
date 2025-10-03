"""Unit tests for authentication utilities"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from jose import JWTError

from app.auth.jwt_handler import JWTHandler, jwt_handler
from app.auth.session import SessionManager, UserSession, session_manager
from app.auth.middleware import AuthenticationError, get_current_user_session
from app.models.user import User
from app.config import settings


class TestJWTHandler:
    """Test cases for JWT token handling"""
    
    @pytest.fixture
    def jwt_handler_instance(self):
        return JWTHandler()
    
    @pytest.fixture
    def sample_user_id(self):
        return "test-user-123"
    
    def test_create_access_token(self, jwt_handler_instance, sample_user_id):
        """Test access token creation"""
        token = jwt_handler_instance.create_access_token(sample_user_id)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = jwt_handler_instance.verify_token(token)
        assert payload["sub"] == sample_user_id
        assert payload["type"] == "access"
    
    def test_create_access_token_with_claims(self, jwt_handler_instance, sample_user_id):
        """Test access token creation with additional claims"""
        additional_claims = {"username": "testuser", "role": "user"}
        token = jwt_handler_instance.create_access_token(sample_user_id, additional_claims)
        
        payload = jwt_handler_instance.verify_token(token)
        assert payload["sub"] == sample_user_id
        assert payload["username"] == "testuser"
        assert payload["role"] == "user"
    
    def test_create_refresh_token(self, jwt_handler_instance, sample_user_id):
        """Test refresh token creation"""
        token = jwt_handler_instance.create_refresh_token(sample_user_id)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = jwt_handler_instance.verify_token(token)
        assert payload["sub"] == sample_user_id
        assert payload["type"] == "refresh"
    
    def test_verify_valid_token(self, jwt_handler_instance, sample_user_id):
        """Test verification of valid token"""
        token = jwt_handler_instance.create_access_token(sample_user_id)
        payload = jwt_handler_instance.verify_token(token)
        
        assert payload["sub"] == sample_user_id
        assert "exp" in payload
        assert "iat" in payload
    
    def test_verify_invalid_token(self, jwt_handler_instance):
        """Test verification of invalid token"""
        with pytest.raises(JWTError):
            jwt_handler_instance.verify_token("invalid.token.here")
    
    def test_verify_expired_token(self, jwt_handler_instance, sample_user_id):
        """Test verification of expired token"""
        # Create token with past expiration
        with patch('app.auth.jwt_handler.datetime') as mock_datetime:
            past_time = datetime.now(timezone.utc) - timedelta(hours=2)
            mock_datetime.now.return_value = past_time
            mock_datetime.fromtimestamp = datetime.fromtimestamp
            
            token = jwt_handler_instance.create_access_token(sample_user_id)
        
        # Verify it's now expired
        with pytest.raises(JWTError, match="expired"):
            jwt_handler_instance.verify_token(token)
    
    def test_get_user_id_from_token(self, jwt_handler_instance, sample_user_id):
        """Test extracting user ID from token"""
        token = jwt_handler_instance.create_access_token(sample_user_id)
        extracted_user_id = jwt_handler_instance.get_user_id_from_token(token)
        
        assert extracted_user_id == sample_user_id
    
    def test_get_user_id_from_invalid_token(self, jwt_handler_instance):
        """Test extracting user ID from invalid token"""
        with pytest.raises(JWTError):
            jwt_handler_instance.get_user_id_from_token("invalid.token")
    
    def test_is_token_expired_false(self, jwt_handler_instance, sample_user_id):
        """Test checking if valid token is expired"""
        token = jwt_handler_instance.create_access_token(sample_user_id)
        assert jwt_handler_instance.is_token_expired(token) is False
    
    def test_is_token_expired_true(self, jwt_handler_instance):
        """Test checking if invalid token is expired"""
        assert jwt_handler_instance.is_token_expired("invalid.token") is True
    
    def test_get_token_expiration(self, jwt_handler_instance, sample_user_id):
        """Test getting token expiration time"""
        token = jwt_handler_instance.create_access_token(sample_user_id)
        expiration = jwt_handler_instance.get_token_expiration(token)
        
        assert isinstance(expiration, datetime)
        assert expiration > datetime.now(timezone.utc)
    
    def test_refresh_access_token(self, jwt_handler_instance, sample_user_id):
        """Test refreshing access token with refresh token"""
        refresh_token = jwt_handler_instance.create_refresh_token(sample_user_id)
        new_access_token = jwt_handler_instance.refresh_access_token(refresh_token)
        
        assert isinstance(new_access_token, str)
        
        # Verify new token is valid
        payload = jwt_handler_instance.verify_token(new_access_token)
        assert payload["sub"] == sample_user_id
        assert payload["type"] == "access"
    
    def test_refresh_with_access_token_fails(self, jwt_handler_instance, sample_user_id):
        """Test that refreshing with access token fails"""
        access_token = jwt_handler_instance.create_access_token(sample_user_id)
        
        with pytest.raises(JWTError, match="Invalid token type"):
            jwt_handler_instance.refresh_access_token(access_token)
    
    def test_create_token_pair(self, jwt_handler_instance, sample_user_id):
        """Test creating access and refresh token pair"""
        token_pair = jwt_handler_instance.create_token_pair(sample_user_id)
        
        assert "access_token" in token_pair
        assert "refresh_token" in token_pair
        assert "token_type" in token_pair
        assert token_pair["token_type"] == "bearer"
        
        # Verify both tokens are valid
        access_payload = jwt_handler_instance.verify_token(token_pair["access_token"])
        refresh_payload = jwt_handler_instance.verify_token(token_pair["refresh_token"])
        
        assert access_payload["sub"] == sample_user_id
        assert refresh_payload["sub"] == sample_user_id
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"


class TestSessionManager:
    """Test cases for session management"""
    
    @pytest.fixture
    def session_manager_instance(self):
        return SessionManager()
    
    @pytest.fixture
    def sample_user(self):
        return User(
            id="test-user-123",
            username="testuser",
            email="test@example.com"
        )
    
    def test_create_session(self, session_manager_instance, sample_user):
        """Test session creation"""
        session = session_manager_instance.create_session(sample_user)
        
        assert isinstance(session, UserSession)
        assert session.user_id == sample_user.id
        assert session.username == sample_user.username
        assert session.email == sample_user.email
        assert session.access_token is not None
        assert session.refresh_token is not None
    
    def test_get_session(self, session_manager_instance, sample_user):
        """Test getting session by user ID"""
        # Create session
        created_session = session_manager_instance.create_session(sample_user)
        
        # Get session
        retrieved_session = session_manager_instance.get_session(sample_user.id)
        
        assert retrieved_session is not None
        assert retrieved_session.user_id == sample_user.id
        assert retrieved_session.access_token == created_session.access_token
    
    def test_get_nonexistent_session(self, session_manager_instance):
        """Test getting session that doesn't exist"""
        session = session_manager_instance.get_session("nonexistent-user")
        assert session is None
    
    def test_get_session_by_token(self, session_manager_instance, sample_user):
        """Test getting session by access token"""
        # Create session
        created_session = session_manager_instance.create_session(sample_user)
        
        # Get session by token
        retrieved_session = session_manager_instance.get_session_by_token(
            created_session.access_token
        )
        
        assert retrieved_session is not None
        assert retrieved_session.user_id == sample_user.id
    
    def test_get_session_by_invalid_token(self, session_manager_instance):
        """Test getting session with invalid token"""
        session = session_manager_instance.get_session_by_token("invalid.token")
        assert session is None
    
    def test_refresh_session(self, session_manager_instance, sample_user):
        """Test refreshing a session"""
        # Create session
        original_session = session_manager_instance.create_session(sample_user)
        original_access_token = original_session.access_token
        
        # Refresh session
        refreshed_session = session_manager_instance.refresh_session(
            sample_user.id, 
            original_session.refresh_token
        )
        
        assert refreshed_session is not None
        assert refreshed_session.user_id == sample_user.id
        assert refreshed_session.access_token != original_access_token
    
    def test_refresh_session_invalid_token(self, session_manager_instance, sample_user):
        """Test refreshing session with invalid refresh token"""
        # Create session
        session_manager_instance.create_session(sample_user)
        
        # Try to refresh with invalid token
        refreshed_session = session_manager_instance.refresh_session(
            sample_user.id, 
            "invalid.refresh.token"
        )
        
        assert refreshed_session is None
    
    def test_invalidate_session(self, session_manager_instance, sample_user):
        """Test invalidating a session"""
        # Create session
        session_manager_instance.create_session(sample_user)
        
        # Verify session exists
        assert session_manager_instance.get_session(sample_user.id) is not None
        
        # Invalidate session
        result = session_manager_instance.invalidate_session(sample_user.id)
        
        assert result is True
        assert session_manager_instance.get_session(sample_user.id) is None
    
    def test_invalidate_nonexistent_session(self, session_manager_instance):
        """Test invalidating session that doesn't exist"""
        result = session_manager_instance.invalidate_session("nonexistent-user")
        assert result is False
    
    def test_cleanup_expired_sessions(self, session_manager_instance, sample_user):
        """Test cleaning up expired sessions"""
        # Create session
        session = session_manager_instance.create_session(sample_user)
        
        # Mock the session as expired
        with patch.object(session, 'is_expired', return_value=True):
            cleaned_count = session_manager_instance.cleanup_expired_sessions()
        
        assert cleaned_count == 1
        assert session_manager_instance.get_session(sample_user.id) is None
    
    def test_get_active_session_count(self, session_manager_instance, sample_user):
        """Test getting active session count"""
        assert session_manager_instance.get_active_session_count() == 0
        
        session_manager_instance.create_session(sample_user)
        assert session_manager_instance.get_active_session_count() == 1
    
    def test_is_user_logged_in(self, session_manager_instance, sample_user):
        """Test checking if user is logged in"""
        assert session_manager_instance.is_user_logged_in(sample_user.id) is False
        
        session_manager_instance.create_session(sample_user)
        assert session_manager_instance.is_user_logged_in(sample_user.id) is True
    
    def test_get_session_info(self, session_manager_instance, sample_user):
        """Test getting session information"""
        # No session initially
        info = session_manager_instance.get_session_info(sample_user.id)
        assert info is None
        
        # Create session
        session_manager_instance.create_session(sample_user)
        
        # Get session info
        info = session_manager_instance.get_session_info(sample_user.id)
        assert info is not None
        assert info["user_id"] == sample_user.id
        assert info["username"] == sample_user.username
        assert "created_at" in info
        assert "last_activity" in info
        assert "is_expired" in info


class TestUserSession:
    """Test cases for UserSession dataclass"""
    
    @pytest.fixture
    def sample_session(self):
        return UserSession(
            user_id="test-user-123",
            username="testuser",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            access_token="sample.access.token",
            refresh_token="sample.refresh.token"
        )
    
    def test_update_activity(self, sample_session):
        """Test updating session activity"""
        original_activity = sample_session.last_activity
        
        # Wait a small amount to ensure time difference
        import time
        time.sleep(0.01)
        
        sample_session.update_activity()
        
        assert sample_session.last_activity > original_activity
    
    def test_to_dict(self, sample_session):
        """Test converting session to dictionary"""
        session_dict = sample_session.to_dict()
        
        assert session_dict["user_id"] == sample_session.user_id
        assert session_dict["username"] == sample_session.username
        assert session_dict["email"] == sample_session.email
        assert session_dict["access_token"] == sample_session.access_token
        assert session_dict["refresh_token"] == sample_session.refresh_token
        assert "created_at" in session_dict
        assert "last_activity" in session_dict
    
    def test_is_expired_with_valid_token(self, sample_session):
        """Test checking expiration with valid token"""
        # Mock JWT handler to return False for is_token_expired
        with patch('app.auth.session.jwt_handler.is_token_expired', return_value=False):
            assert sample_session.is_expired() is False
    
    def test_is_expired_with_invalid_token(self, sample_session):
        """Test checking expiration with invalid token"""
        # Mock JWT handler to return True for is_token_expired
        with patch('app.auth.session.jwt_handler.is_token_expired', return_value=True):
            assert sample_session.is_expired() is True


class TestConvenienceFunctions:
    """Test cases for module-level convenience functions"""
    
    def test_global_jwt_handler_functions(self):
        """Test that global convenience functions work"""
        from app.auth.jwt_handler import (
            create_access_token, 
            create_refresh_token, 
            verify_token, 
            get_user_id_from_token,
            create_token_pair
        )
        
        user_id = "test-user-123"
        
        # Test access token
        access_token = create_access_token(user_id)
        assert isinstance(access_token, str)
        
        # Test refresh token
        refresh_token = create_refresh_token(user_id)
        assert isinstance(refresh_token, str)
        
        # Test verification
        payload = verify_token(access_token)
        assert payload["sub"] == user_id
        
        # Test user ID extraction
        extracted_id = get_user_id_from_token(access_token)
        assert extracted_id == user_id
        
        # Test token pair
        token_pair = create_token_pair(user_id)
        assert "access_token" in token_pair
        assert "refresh_token" in token_pair
    
    def test_global_session_functions(self):
        """Test that global session convenience functions work"""
        from app.auth.session import (
            create_session,
            get_session,
            get_session_by_token,
            invalidate_session,
            is_user_logged_in
        )
        from app.models.user import User
        
        user = User(
            id="test-user-456",
            username="testuser2",
            email="test2@example.com"
        )
        
        # Test session creation
        session = create_session(user)
        assert isinstance(session, UserSession)
        
        # Test getting session
        retrieved_session = get_session(user.id)
        assert retrieved_session is not None
        
        # Test getting by token
        token_session = get_session_by_token(session.access_token)
        assert token_session is not None
        
        # Test login check
        assert is_user_logged_in(user.id) is True
        
        # Test invalidation
        assert invalidate_session(user.id) is True
        assert is_user_logged_in(user.id) is False