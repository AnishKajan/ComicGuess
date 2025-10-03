"""
Tests for advanced authentication security features
"""

import pytest
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

from app.auth.jwt_handler import (
    JWTHandler, TokenRevocationStore, JWTError,
    create_token_pair, refresh_access_token, revoke_token,
    revoke_all_user_tokens, logout_user, validate_token_security
)
from app.auth.session import (
    SessionManager, UserSession, SessionSecurityInfo
)
from app.models.user import User


class TestTokenRevocationStore:
    """Test token revocation functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.revocation_store = TokenRevocationStore()
    
    def test_revoke_and_check_token(self):
        """Test token revocation and checking"""
        token_jti = "test_jti_123"
        expiration = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Initially not revoked
        assert not self.revocation_store.is_token_revoked(token_jti)
        
        # Revoke token
        self.revocation_store.revoke_token(token_jti, expiration)
        
        # Should now be revoked
        assert self.revocation_store.is_token_revoked(token_jti)
    
    def test_revoke_all_user_tokens(self):
        """Test revoking all tokens for a user"""
        user_id = "test_user_123"
        token_issued_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        # Initially not revoked
        assert not self.revocation_store.is_user_tokens_revoked(user_id, token_issued_at)
        
        # Revoke all user tokens
        self.revocation_store.revoke_all_user_tokens(user_id)
        
        # Should now be revoked
        assert self.revocation_store.is_user_tokens_revoked(user_id, token_issued_at)
        
        # Future tokens should not be revoked
        future_token = datetime.now(timezone.utc) + timedelta(minutes=30)
        assert not self.revocation_store.is_user_tokens_revoked(user_id, future_token)


class TestJWTHandler:
    """Test enhanced JWT handler functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.jwt_handler = JWTHandler()
        self.test_user_id = "test_user_123"
    
    def test_create_access_token_with_security_features(self):
        """Test access token creation with security enhancements"""
        token, jti = self.jwt_handler.create_access_token(self.test_user_id)
        
        # Verify token structure
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert len(jti) > 20  # Should be a secure random string
        
        # Verify token payload
        payload = self.jwt_handler.verify_token(token)
        assert payload["sub"] == self.test_user_id
        assert payload["type"] == "access"
        assert payload["jti"] == jti
        assert "iat" in payload
        assert "exp" in payload
        assert "nbf" in payload
        assert "iss" in payload
        assert "aud" in payload
    
    def test_create_refresh_token_with_family(self):
        """Test refresh token creation with token family"""
        token, jti, family = self.jwt_handler.create_refresh_token(self.test_user_id)
        
        # Verify token structure
        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert isinstance(family, str)
        
        # Verify token payload
        payload = self.jwt_handler.verify_token(token, expected_type="refresh")
        assert payload["sub"] == self.test_user_id
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti
        assert payload["fam"] == family
    
    def test_token_verification_with_revocation(self):
        """Test token verification with revocation checking"""
        token, jti = self.jwt_handler.create_access_token(self.test_user_id)
        
        # Initially valid
        payload = self.jwt_handler.verify_token(token)
        assert payload["sub"] == self.test_user_id
        
        # Revoke token
        expiration = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        self.jwt_handler.revocation_store.revoke_token(jti, expiration)
        
        # Should now be invalid
        with pytest.raises(JWTError, match="revoked"):
            self.jwt_handler.verify_token(token)
    
    def test_clock_skew_handling(self):
        """Test clock skew tolerance in token verification"""
        # Create token with future timestamp (simulating clock skew)
        with patch('app.auth.jwt_handler.datetime') as mock_datetime:
            future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
            mock_datetime.now.return_value = future_time
            mock_datetime.fromtimestamp = datetime.fromtimestamp
            
            token, jti = self.jwt_handler.create_access_token(self.test_user_id)
        
        # Should still be valid with clock skew tolerance
        payload = self.jwt_handler.verify_token(token, allow_clock_skew=True)
        assert payload["sub"] == self.test_user_id
        
        # Should fail without clock skew tolerance
        with pytest.raises(JWTError):
            self.jwt_handler.verify_token(token, allow_clock_skew=False)
    
    def test_token_refresh_with_rotation(self):
        """Test token refresh with rotation"""
        # Create initial token pair
        token_pair = self.jwt_handler.create_token_pair(self.test_user_id)
        refresh_token = token_pair["refresh_token"]
        
        # Wait to trigger rotation threshold
        with patch.object(self.jwt_handler, 'rotation_threshold', timedelta(seconds=0)):
            # Refresh tokens
            result = self.jwt_handler.refresh_access_token(refresh_token, rotate_refresh=True)
            
            assert "access_token" in result
            assert result["token_type"] == "bearer"
            
            # Should have rotated
            if result.get("rotated"):
                assert "refresh_token" in result
                assert result["refresh_token"] != refresh_token
    
    def test_token_family_tracking(self):
        """Test token family tracking for refresh tokens"""
        # Create token pair
        token_pair = self.jwt_handler.create_token_pair(self.test_user_id)
        token_family = token_pair["token_family"]
        
        # Verify family is tracked
        assert token_family in self.jwt_handler.token_families
        family_info = self.jwt_handler.token_families[token_family]
        assert family_info["user_id"] == self.test_user_id
        assert family_info["rotation_count"] == 0
    
    def test_logout_user_functionality(self):
        """Test secure user logout"""
        # Create token pair
        token_pair = self.jwt_handler.create_token_pair(self.test_user_id)
        access_token = token_pair["access_token"]
        refresh_token = token_pair["refresh_token"]
        
        # Logout user
        self.jwt_handler.logout_user(access_token, refresh_token)
        
        # Tokens should now be revoked
        with pytest.raises(JWTError, match="revoked"):
            self.jwt_handler.verify_token(access_token)
        
        with pytest.raises(JWTError, match="revoked"):
            self.jwt_handler.verify_token(refresh_token)
    
    def test_revoke_all_user_tokens(self):
        """Test revoking all tokens for a user"""
        # Create multiple token pairs
        token_pair1 = self.jwt_handler.create_token_pair(self.test_user_id)
        token_pair2 = self.jwt_handler.create_token_pair(self.test_user_id)
        
        # Revoke all user tokens
        self.jwt_handler.revoke_all_user_tokens(self.test_user_id)
        
        # All tokens should be revoked
        with pytest.raises(JWTError, match="revoked"):
            self.jwt_handler.verify_token(token_pair1["access_token"])
        
        with pytest.raises(JWTError, match="revoked"):
            self.jwt_handler.verify_token(token_pair2["access_token"])
    
    def test_validate_token_security(self):
        """Test token security validation"""
        # Create token
        token, jti = self.jwt_handler.create_access_token(self.test_user_id)
        
        # Validate security
        security_info = self.jwt_handler.validate_token_security(token)
        
        assert security_info["valid"] is True
        assert security_info["token_type"] == "access"
        assert security_info["user_id"] == self.test_user_id
        assert security_info["jti"] == jti
        assert "issued_at" in security_info
        assert "expires_at" in security_info
        assert "time_to_expiry" in security_info
        assert "age" in security_info
        
        # Test with expired token
        with patch.object(self.jwt_handler, 'access_token_expiration', timedelta(seconds=-1)):
            expired_token, _ = self.jwt_handler.create_access_token(self.test_user_id)
        
        security_info = self.jwt_handler.validate_token_security(expired_token)
        assert security_info["valid"] is False
        assert security_info["should_refresh"] is True


class TestSessionSecurityInfo:
    """Test session security information"""
    
    def test_session_security_info_creation(self):
        """Test creation of session security info"""
        security_info = SessionSecurityInfo(
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)",
            device_fingerprint="test_fingerprint_123"
        )
        
        assert security_info.ip_address == "192.168.1.100"
        assert security_info.user_agent == "Mozilla/5.0 (Test Browser)"
        assert security_info.device_fingerprint == "test_fingerprint_123"
        assert security_info.is_suspicious is False
        assert security_info.risk_score == 0.0


class TestUserSession:
    """Test enhanced user session functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_user_id = "test_user_123"
        self.test_username = "testuser"
        self.test_email = "test@example.com"
        
        # Create mock tokens
        with patch('app.auth.jwt_handler.jwt_handler') as mock_jwt:
            mock_jwt.is_token_expired.return_value = False
            
            self.session = UserSession(
                user_id=self.test_user_id,
                username=self.test_username,
                email=self.test_email,
                created_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                access_token="test_access_token",
                refresh_token="test_refresh_token"
            )
    
    def test_session_expiration_checks(self):
        """Test various session expiration checks"""
        # Test idle timeout
        self.session.last_activity = datetime.now(timezone.utc) - timedelta(hours=25)
        assert self.session.is_idle_timeout() is True
        
        # Test absolute timeout
        self.session.created_at = datetime.now(timezone.utc) - timedelta(days=8)
        assert self.session.is_absolute_timeout() is True
        
        # Reset for valid session
        self.session.last_activity = datetime.now(timezone.utc)
        self.session.created_at = datetime.now(timezone.utc)
        assert self.session.is_idle_timeout() is False
        assert self.session.is_absolute_timeout() is False
    
    def test_activity_update_with_security_monitoring(self):
        """Test activity update with security monitoring"""
        # Initial security info
        self.session.security_info = SessionSecurityInfo(
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Original Browser)"
        )
        
        # Update with same info (should not be suspicious)
        self.session.update_activity("192.168.1.100", "Mozilla/5.0 (Original Browser)")
        assert self.session.security_info.is_suspicious is False
        
        # Update with different IP (should be suspicious)
        self.session.update_activity("10.0.0.1", "Mozilla/5.0 (Original Browser)")
        assert self.session.security_info.is_suspicious is True
        assert self.session.security_info.risk_score > 0
        
        # Update with different user agent (should increase risk)
        original_risk = self.session.security_info.risk_score
        self.session.update_activity("10.0.0.1", "Mozilla/5.0 (Different Browser)")
        assert self.session.security_info.risk_score > original_risk
    
    def test_risk_score_calculation(self):
        """Test session risk score calculation"""
        # Setup security info
        self.session.security_info = SessionSecurityInfo(
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)"
        )
        
        # Base risk should be low
        base_risk = self.session.calculate_risk_score()
        assert base_risk >= 0.0
        
        # Increase login attempts
        self.session.login_attempts = 5
        risk_with_attempts = self.session.calculate_risk_score()
        assert risk_with_attempts > base_risk
        
        # Make session older
        self.session.created_at = datetime.now(timezone.utc) - timedelta(days=4)
        risk_with_age = self.session.calculate_risk_score()
        assert risk_with_age > risk_with_attempts
        
        # Test high risk detection
        self.session.security_info.risk_score = 0.8
        assert self.session.is_high_risk() is True
    
    def test_session_to_dict(self):
        """Test session serialization to dictionary"""
        self.session.security_info = SessionSecurityInfo(
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)"
        )
        
        session_dict = self.session.to_dict()
        
        assert session_dict["user_id"] == self.test_user_id
        assert session_dict["username"] == self.test_username
        assert session_dict["email"] == self.test_email
        assert "session_id" in session_dict
        assert "created_at" in session_dict
        assert "last_activity" in session_dict
        assert "risk_score" in session_dict
        assert "is_high_risk" in session_dict
        assert "security_info" in session_dict
        
        security_info = session_dict["security_info"]
        assert security_info["ip_address"] == "192.168.1.100"
        assert security_info["user_agent"] == "Mozilla/5.0 (Test Browser)"


class TestSessionManager:
    """Test enhanced session manager functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.session_manager = SessionManager()
        self.test_user = Mock(spec=User)
        self.test_user.id = "test_user_123"
        self.test_user.username = "testuser"
        self.test_user.email = "test@example.com"
    
    @patch('app.auth.jwt_handler.jwt_handler')
    def test_create_session_with_security_info(self, mock_jwt):
        """Test session creation with security information"""
        # Mock JWT handler
        mock_jwt.create_token_pair.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_family": "test_family"
        }
        
        # Create session with security info
        session = self.session_manager.create_session(
            self.test_user,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)",
            device_fingerprint="test_fingerprint"
        )
        
        assert session.user_id == self.test_user.id
        assert session.security_info is not None
        assert session.security_info.ip_address == "192.168.1.100"
        assert session.security_info.user_agent == "Mozilla/5.0 (Test Browser)"
        assert session.security_info.device_fingerprint == "test_fingerprint"
    
    @patch('app.auth.jwt_handler.jwt_handler')
    def test_concurrent_session_limit(self, mock_jwt):
        """Test concurrent session limit enforcement"""
        # Mock JWT handler
        mock_jwt.create_token_pair.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_family": "test_family"
        }
        
        # Set low concurrent limit for testing
        self.session_manager._concurrent_session_limit = 2
        
        # Create multiple sessions
        session1 = self.session_manager.create_session(self.test_user)
        session2 = self.session_manager.create_session(self.test_user)
        
        # Third session should remove the first one
        session3 = self.session_manager.create_session(self.test_user)
        
        # Should only have 2 sessions
        user_sessions = self.session_manager._get_user_sessions(self.test_user.id)
        assert len(user_sessions) <= 2
    
    def test_failed_login_tracking(self):
        """Test failed login attempt tracking"""
        user_id = "test_user_123"
        ip_address = "192.168.1.100"
        
        # Record failed attempts
        for i in range(3):
            self.session_manager.record_failed_login(user_id, ip_address)
        
        # Should not be locked yet
        assert not self.session_manager.is_account_locked(user_id)
        
        # Record more failed attempts
        for i in range(3):
            self.session_manager.record_failed_login(user_id, ip_address)
        
        # Should now be locked
        assert self.session_manager.is_account_locked(user_id)
    
    @patch('app.auth.jwt_handler.jwt_handler')
    def test_session_refresh_with_security_checks(self, mock_jwt):
        """Test session refresh with security checks"""
        # Setup initial session
        mock_jwt.create_token_pair.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_family": "test_family"
        }
        
        session = self.session_manager.create_session(
            self.test_user,
            ip_address="192.168.1.100"
        )
        
        # Mock refresh response
        mock_jwt.refresh_access_token.return_value = {
            "access_token": "new_access_token",
            "token_type": "bearer",
            "rotated": False
        }
        
        # Refresh session
        refreshed_session = self.session_manager.refresh_session(
            self.test_user.id,
            "test_refresh_token",
            ip_address="192.168.1.100"
        )
        
        assert refreshed_session is not None
        assert refreshed_session.access_token == "new_access_token"
    
    @patch('app.auth.jwt_handler.jwt_handler')
    def test_high_risk_session_blocking(self, mock_jwt):
        """Test blocking of high-risk sessions"""
        # Setup session
        mock_jwt.create_token_pair.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_family": "test_family"
        }
        
        session = self.session_manager.create_session(self.test_user)
        
        # Make session high risk
        session.security_info = SessionSecurityInfo(
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)",
            risk_score=0.9  # High risk
        )
        
        # Attempt to refresh should fail
        refreshed_session = self.session_manager.refresh_session(
            self.test_user.id,
            "test_refresh_token"
        )
        
        assert refreshed_session is None
        # Session should be invalidated
        assert self.test_user.id not in self.session_manager._active_sessions
    
    def test_session_security_info_retrieval(self):
        """Test retrieval of session security information"""
        # Create mock session with security info
        session = UserSession(
            user_id=self.test_user.id,
            username=self.test_user.username,
            email=self.test_user.email,
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            access_token="test_token",
            security_info=SessionSecurityInfo(
                ip_address="192.168.1.100",
                user_agent="Mozilla/5.0 (Test Browser)"
            )
        )
        
        self.session_manager._active_sessions[self.test_user.id] = session
        
        # Get security info
        security_info = self.session_manager.get_session_security_info(self.test_user.id)
        
        assert security_info is not None
        assert security_info["ip_address"] == "192.168.1.100"
        assert security_info["user_agent"] == "Mozilla/5.0 (Test Browser)"
        assert "risk_score" in security_info
        assert "is_high_risk" in security_info


@pytest.mark.integration
class TestAdvancedAuthIntegration:
    """Integration tests for advanced authentication security"""
    
    def setup_method(self):
        """Setup test environment"""
        self.jwt_handler = JWTHandler()
        self.session_manager = SessionManager()
        self.test_user = Mock(spec=User)
        self.test_user.id = "integration_test_user"
        self.test_user.username = "integrationuser"
        self.test_user.email = "integration@example.com"
    
    @patch('app.auth.jwt_handler.jwt_handler')
    def test_complete_authentication_flow(self, mock_jwt_global):
        """Test complete authentication flow with security features"""
        # Use real JWT handler for this test
        mock_jwt_global.create_token_pair = self.jwt_handler.create_token_pair
        mock_jwt_global.refresh_access_token = self.jwt_handler.refresh_access_token
        mock_jwt_global.logout_user = self.jwt_handler.logout_user
        
        # 1. Create session (login)
        session = self.session_manager.create_session(
            self.test_user,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)"
        )
        
        assert session is not None
        assert session.user_id == self.test_user.id
        
        # 2. Refresh session
        refreshed_session = self.session_manager.refresh_session(
            self.test_user.id,
            session.refresh_token,
            ip_address="192.168.1.100"
        )
        
        assert refreshed_session is not None
        
        # 3. Logout
        logout_success = self.session_manager.invalidate_session(self.test_user.id)
        assert logout_success is True
        
        # 4. Verify session is gone
        final_session = self.session_manager.get_session(self.test_user.id)
        assert final_session is None
    
    def test_security_threat_response(self):
        """Test response to security threats"""
        # Create session
        with patch('app.auth.jwt_handler.jwt_handler') as mock_jwt:
            mock_jwt.create_token_pair.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "token_family": "test_family"
            }
            
            session = self.session_manager.create_session(
                self.test_user,
                ip_address="192.168.1.100"
            )
        
        # Simulate suspicious activity (IP change)
        session.update_activity("10.0.0.1")
        
        # Should be marked as suspicious
        assert session.security_info.is_suspicious is True
        
        # Multiple suspicious activities should increase risk
        session.update_activity("172.16.0.1")
        session.login_attempts = 10
        
        # Should be high risk
        assert session.is_high_risk() is True
        
        # High risk session should be blocked on refresh
        with patch('app.auth.jwt_handler.jwt_handler') as mock_jwt:
            refreshed_session = self.session_manager.refresh_session(
                self.test_user.id,
                "test_refresh_token"
            )
            
            assert refreshed_session is None