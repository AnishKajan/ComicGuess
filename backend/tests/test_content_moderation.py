"""
Tests for content moderation and security features
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from app.security.content_moderation import (
    ProfanityFilter, ContentModerationManager, SecurityHeadersManager,
    ModerationAction, ContentCategory, ModerationResult
)
from app.security.csrf_protection import (
    CSRFProtection, CSRFMiddleware, DependencyScanner
)


class TestProfanityFilter:
    """Test profanity filtering functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.filter = ProfanityFilter()
    
    def test_normalize_text(self):
        """Test text normalization"""
        # Test basic normalization
        assert self.filter.normalize_text("HELLO WORLD") == "hello world"
        assert self.filter.normalize_text("  extra   spaces  ") == "extra spaces"
        
        # Test leetspeak conversion
        assert self.filter.normalize_text("h3ll0 w0rld") == "hello world"
        assert self.filter.normalize_text("@dm1n") == "admin"
        
        # Test special character removal
        assert self.filter.normalize_text("hello!@#$%world") == "helloworld"
    
    def test_direct_profanity_detection(self):
        """Test direct profanity word detection"""
        # Test clean content
        result = self.filter.check_profanity("hello world", ContentCategory.GUESS)
        assert result.action == ModerationAction.ALLOW
        
        # Test profanity (using sanitized test words)
        result = self.filter.check_profanity("this is badword1", ContentCategory.GUESS)
        assert result.action in [ModerationAction.WARN, ModerationAction.BLOCK, ModerationAction.REVIEW]
        assert "profanity" in " ".join(result.reasons).lower()
    
    def test_obfuscated_profanity_detection(self):
        """Test detection of obfuscated profanity"""
        # Test leetspeak obfuscation
        result = self.filter.check_profanity("b4dw0rd1", ContentCategory.GUESS)
        assert result.action in [ModerationAction.WARN, ModerationAction.BLOCK, ModerationAction.REVIEW]
        
        # Test character substitution
        result = self.filter.check_profanity("b@dw0rd1", ContentCategory.GUESS)
        assert result.action in [ModerationAction.WARN, ModerationAction.BLOCK, ModerationAction.REVIEW]
    
    def test_spam_pattern_detection(self):
        """Test spam pattern detection"""
        # Test repeated characters
        result = self.filter.check_profanity("hellooooooo", ContentCategory.GUESS)
        assert "repeated characters" in " ".join(result.reasons).lower()
        
        # Test excessive caps
        result = self.filter.check_profanity("THISISALLCAPS", ContentCategory.GUESS)
        assert "capital letters" in " ".join(result.reasons).lower()
        
        # Test mixed case spam
        result = self.filter.check_profanity("aBcDeFgHiJkL", ContentCategory.GUESS)
        assert "mixed case" in " ".join(result.reasons).lower()
    
    def test_category_specific_rules(self):
        """Test category-specific moderation rules"""
        # Test username rules
        result = self.filter.check_profanity("ab", ContentCategory.USERNAME)
        assert "too short" in " ".join(result.reasons).lower()
        
        result = self.filter.check_profanity("admin123", ContentCategory.USERNAME)
        assert "reserved" in " ".join(result.reasons).lower()
        
        result = self.filter.check_profanity("official_user", ContentCategory.USERNAME)
        assert "impersonation" in " ".join(result.reasons).lower()
        
        # Test guess rules
        long_guess = "a" * 60
        result = self.filter.check_profanity(long_guess, ContentCategory.GUESS)
        assert "too long" in " ".join(result.reasons).lower()
        
        result = self.filter.check_profanity("visit www.spam.com", ContentCategory.GUESS)
        assert "url" in " ".join(result.reasons).lower()
    
    def test_whitelist_exceptions(self):
        """Test whitelist exceptions for gaming terms"""
        # Gaming terms should be allowed
        gaming_terms = ["kill", "die", "fight", "battle", "destroy"]
        for term in gaming_terms:
            result = self.filter.check_profanity(term, ContentCategory.GUESS)
            assert result.action == ModerationAction.ALLOW
        
        # Character names should be allowed
        character_names = ["deadpool", "punisher", "destroyer"]
        for name in character_names:
            result = self.filter.check_profanity(name, ContentCategory.GUESS)
            assert result.action == ModerationAction.ALLOW
    
    def test_content_filtering(self):
        """Test content filtering based on moderation action"""
        # Test blocking
        result = ModerationResult(ModerationAction.BLOCK, 0.9, ["test"])
        filtered = self.filter._filter_content("bad content", result.action)
        assert filtered == "[CONTENT BLOCKED]"
        
        # Test review
        result = ModerationResult(ModerationAction.REVIEW, 0.7, ["test"])
        filtered = self.filter._filter_content("questionable content", result.action)
        assert filtered == "[CONTENT UNDER REVIEW]"
        
        # Test warning with profanity replacement
        content_with_profanity = "this contains badword1"
        filtered = self.filter._filter_content(content_with_profanity, ModerationAction.WARN)
        assert "badword1" not in filtered
        assert "*" in filtered


class TestContentModerationManager:
    """Test content moderation manager"""
    
    def setup_method(self):
        """Setup test environment"""
        self.moderator = ContentModerationManager()
    
    def test_moderate_content_basic(self):
        """Test basic content moderation"""
        # Test clean content
        result = self.moderator.moderate_content(
            "Spider-Man", 
            ContentCategory.GUESS, 
            user_id="test_user"
        )
        assert result.action == ModerationAction.ALLOW
        
        # Test problematic content
        result = self.moderator.moderate_content(
            "badword1", 
            ContentCategory.GUESS, 
            user_id="test_user"
        )
        assert result.action in [ModerationAction.WARN, ModerationAction.BLOCK, ModerationAction.REVIEW]
    
    def test_context_based_moderation(self):
        """Test context-based moderation enhancements"""
        context = {
            'recent_submissions': 15,  # High frequency
            'is_duplicate': True,
            'user_reputation': 0.3     # Low reputation
        }
        
        # Even clean content might be flagged with bad context
        result = self.moderator.moderate_content(
            "clean content",
            ContentCategory.GUESS,
            user_id="test_user",
            context=context
        )
        
        # Should have additional reasons from context
        assert len(result.reasons) > 0
        assert any("frequency" in reason.lower() for reason in result.reasons)
        assert any("duplicate" in reason.lower() for reason in result.reasons)
        assert any("reputation" in reason.lower() for reason in result.reasons)
    
    def test_user_violation_tracking(self):
        """Test user violation tracking"""
        user_id = "test_violator"
        
        # Generate some violations
        for i in range(3):
            self.moderator.moderate_content(
                "badword1",
                ContentCategory.GUESS,
                user_id=user_id
            )
        
        # Check user status
        status = self.moderator.get_user_moderation_status(user_id)
        assert status['user_id'] == user_id
        assert status['total_violations'] > 0
        assert 'recent_violations' in status
    
    def test_moderation_logging(self):
        """Test moderation action logging"""
        initial_log_count = len(self.moderator.moderation_log)
        
        # Perform moderation action
        self.moderator.moderate_content(
            "test content",
            ContentCategory.GUESS,
            user_id="test_user"
        )
        
        # Check that action was logged
        assert len(self.moderator.moderation_log) == initial_log_count + 1
        
        log_entry = self.moderator.moderation_log[-1]
        assert 'timestamp' in log_entry
        assert 'content_hash' in log_entry
        assert log_entry['category'] == ContentCategory.GUESS.value
        assert log_entry['user_id'] == "test_user"
    
    def test_moderation_stats(self):
        """Test moderation statistics generation"""
        # Generate some moderation actions
        self.moderator.moderate_content("clean", ContentCategory.GUESS)
        self.moderator.moderate_content("badword1", ContentCategory.GUESS)
        
        stats = self.moderator.get_moderation_stats()
        
        assert 'total_actions' in stats
        assert 'actions_by_type' in stats
        assert 'categories_by_type' in stats
        assert stats['total_actions'] >= 2
    
    def test_error_handling(self):
        """Test error handling in moderation"""
        # Test with None content
        result = self.moderator.moderate_content(None, ContentCategory.GUESS)
        assert result.action == ModerationAction.ALLOW
        
        # Test with empty content
        result = self.moderator.moderate_content("", ContentCategory.GUESS)
        assert result.action == ModerationAction.ALLOW


class TestSecurityHeadersManager:
    """Test security headers management"""
    
    def setup_method(self):
        """Setup test environment"""
        self.headers_manager = SecurityHeadersManager()
    
    def test_default_security_headers(self):
        """Test default security headers"""
        headers = self.headers_manager.get_security_headers()
        
        # Check that all important security headers are present
        expected_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options', 
            'X-XSS-Protection',
            'Strict-Transport-Security',
            'Referrer-Policy',
            'Permissions-Policy',
            'Content-Security-Policy',
            'Cross-Origin-Embedder-Policy',
            'Cross-Origin-Opener-Policy',
            'Cross-Origin-Resource-Policy'
        ]
        
        for header in expected_headers:
            assert header in headers
            assert headers[header]  # Not empty
    
    def test_path_specific_headers(self):
        """Test path-specific header modifications"""
        # Test API endpoints
        api_headers = self.headers_manager.get_security_headers('/api/users')
        assert 'X-Frame-Options' not in api_headers  # Removed for API
        assert api_headers['Content-Security-Policy'] == "default-src 'none'"
        
        # Test image endpoints
        image_headers = self.headers_manager.get_security_headers('/images/character.jpg')
        assert 'Cache-Control' in image_headers
        assert image_headers['Cross-Origin-Resource-Policy'] == 'cross-origin'
    
    def test_additional_headers(self):
        """Test adding additional headers"""
        additional = {'Custom-Header': 'custom-value'}
        headers = self.headers_manager.get_security_headers(
            additional_headers=additional
        )
        
        assert 'Custom-Header' in headers
        assert headers['Custom-Header'] == 'custom-value'
    
    def test_csp_compliance_validation(self):
        """Test CSP compliance validation"""
        # Test content with violations
        content_with_violations = '''
        <script>alert('xss')</script>
        <div style="color: red;">Inline style</div>
        <a href="javascript:void(0)">JS URL</a>
        <script src="data:text/javascript,alert('xss')"></script>
        '''
        
        violations = self.headers_manager.validate_csp_compliance(content_with_violations)
        
        assert len(violations) > 0
        assert any("inline script" in v.lower() for v in violations)
        assert any("inline style" in v.lower() for v in violations)
        assert any("javascript url" in v.lower() for v in violations)
        
        # Test clean content
        clean_content = '''
        <div>Clean content</div>
        <script src="https://example.com/script.js"></script>
        '''
        
        violations = self.headers_manager.validate_csp_compliance(clean_content)
        assert len(violations) == 0


class TestCSRFProtection:
    """Test CSRF protection functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.csrf = CSRFProtection("test-secret-key")
    
    def test_token_generation(self):
        """Test CSRF token generation"""
        token = self.csrf.generate_token("test_user", "test_session")
        
        assert isinstance(token, str)
        assert len(token) > 20  # Should be reasonably long
        assert '.' in token     # Should have signature separator
        
        # Token should be stored
        assert token in self.csrf.active_tokens
        
        # Metadata should be correct
        metadata = self.csrf.active_tokens[token]
        assert metadata.user_id == "test_user"
        assert metadata.session_id == "test_session"
        assert not metadata.used
    
    def test_token_validation(self):
        """Test CSRF token validation"""
        user_id = "test_user"
        session_id = "test_session"
        
        # Generate token
        token = self.csrf.generate_token(user_id, session_id)
        
        # Valid token should pass
        assert self.csrf.validate_token(token, user_id, session_id) is True
        
        # Token should be marked as used
        metadata = self.csrf.active_tokens[token]
        assert metadata.used is True
        
        # Used token should fail on second validation
        assert self.csrf.validate_token(token, user_id, session_id) is False
    
    def test_token_validation_failures(self):
        """Test various token validation failure scenarios"""
        user_id = "test_user"
        session_id = "test_session"
        token = self.csrf.generate_token(user_id, session_id)
        
        # Wrong user ID
        assert self.csrf.validate_token(token, "wrong_user", session_id, mark_used=False) is False
        
        # Wrong session ID
        assert self.csrf.validate_token(token, user_id, "wrong_session", mark_used=False) is False
        
        # Invalid token format
        assert self.csrf.validate_token("invalid_token", user_id, session_id) is False
        
        # Non-existent token
        assert self.csrf.validate_token("nonexistent.token", user_id, session_id) is False
        
        # Empty token
        assert self.csrf.validate_token("", user_id, session_id) is False
        assert self.csrf.validate_token(None, user_id, session_id) is False
    
    def test_token_expiration(self):
        """Test token expiration handling"""
        # Create CSRF protection with very short lifetime
        short_csrf = CSRFProtection("test-key", token_lifetime=timedelta(seconds=1))
        
        token = short_csrf.generate_token("test_user", "test_session")
        
        # Token should be valid initially
        assert short_csrf.validate_token(token, "test_user", "test_session", mark_used=False) is True
        
        # Manually expire the token
        metadata = short_csrf.active_tokens[token]
        metadata.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        # Expired token should fail
        assert short_csrf.validate_token(token, "test_user", "test_session") is False
        
        # Token should be removed from active tokens
        assert token not in short_csrf.active_tokens
    
    def test_token_cleanup(self):
        """Test expired token cleanup"""
        # Create tokens with different expiration times
        csrf = CSRFProtection("test-key", token_lifetime=timedelta(seconds=1))
        
        token1 = csrf.generate_token("user1", "session1")
        token2 = csrf.generate_token("user2", "session2")
        
        # Manually expire one token
        csrf.active_tokens[token1].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        # Trigger cleanup by generating new token
        token3 = csrf.generate_token("user3", "session3")
        
        # Expired token should be removed
        assert token1 not in csrf.active_tokens
        assert token2 in csrf.active_tokens
        assert token3 in csrf.active_tokens
    
    def test_user_token_revocation(self):
        """Test revoking all tokens for a user"""
        user_id = "test_user"
        
        # Generate multiple tokens for the user
        token1 = self.csrf.generate_token(user_id, "session1")
        token2 = self.csrf.generate_token(user_id, "session2")
        token3 = self.csrf.generate_token("other_user", "session3")
        
        # Revoke tokens for specific user
        self.csrf.revoke_user_tokens(user_id)
        
        # User's tokens should be removed
        assert token1 not in self.csrf.active_tokens
        assert token2 not in self.csrf.active_tokens
        
        # Other user's token should remain
        assert token3 in self.csrf.active_tokens
    
    def test_token_info(self):
        """Test getting token information"""
        user_id = "test_user"
        session_id = "test_session"
        token = self.csrf.generate_token(user_id, session_id)
        
        info = self.csrf.get_token_info(token)
        
        assert info is not None
        assert info['user_id'] == user_id
        assert info['session_id'] == session_id
        assert 'created_at' in info
        assert 'expires_at' in info
        assert 'time_remaining' in info
        assert info['used'] is False
        
        # Non-existent token should return None
        assert self.csrf.get_token_info("nonexistent") is None
    
    def test_csrf_stats(self):
        """Test CSRF protection statistics"""
        # Generate some tokens
        token1 = self.csrf.generate_token("user1", "session1")
        token2 = self.csrf.generate_token("user2", "session2")
        
        # Use one token
        self.csrf.validate_token(token1, "user1", "session1")
        
        # Expire one token
        self.csrf.active_tokens[token2].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        stats = self.csrf.get_stats()
        
        assert stats['total_active_tokens'] == 2
        assert stats['used_tokens'] == 1
        assert stats['expired_tokens'] == 1
        assert stats['valid_tokens'] == 0


class TestDependencyScanner:
    """Test dependency vulnerability scanning"""
    
    def setup_method(self):
        """Setup test environment"""
        self.scanner = DependencyScanner()
    
    def test_check_package_security(self):
        """Test checking individual package security"""
        # Test vulnerable package
        result = self.scanner.check_package_security("requests", "2.25.0")
        assert result['package'] == "requests"
        assert result['version'] == "2.25.0"
        assert result['is_vulnerable'] is True
        assert len(result['vulnerabilities']) > 0
        
        # Test non-vulnerable package
        result = self.scanner.check_package_security("unknown_package", "1.0.0")
        assert result['is_vulnerable'] is False
        assert len(result['vulnerabilities']) == 0
    
    def test_scan_requirements_file(self):
        """Test scanning requirements file"""
        # Create temporary requirements content
        requirements_content = """
# Test requirements file
requests==2.25.0
pillow==8.1.0
safe_package==1.0.0
"""
        
        # Mock file reading
        with patch('builtins.open', mock_open(read_data=requirements_content)):
            result = self.scanner.scan_requirements_file("test_requirements.txt")
        
        assert 'scan_date' in result
        assert 'total_vulnerabilities' in result
        assert 'vulnerabilities' in result
        assert 'recommendations' in result
        
        # Should find vulnerabilities in requests and pillow
        vulnerabilities = result['vulnerabilities']
        vulnerable_packages = [v['package'] for v in vulnerabilities]
        assert 'requests' in vulnerable_packages
        assert 'pillow' in vulnerable_packages
        assert 'safe_package' not in vulnerable_packages
    
    def test_scan_nonexistent_file(self):
        """Test scanning non-existent requirements file"""
        result = self.scanner.scan_requirements_file("nonexistent.txt")
        assert 'error' in result
        assert 'not found' in result['error'].lower()
    
    def test_recommendations_generation(self):
        """Test security recommendations generation"""
        vulnerabilities = [
            {"package": "requests", "severity": "high"},
            {"package": "pillow", "severity": "medium"}
        ]
        
        recommendations = self.scanner._generate_recommendations(vulnerabilities)
        
        assert len(recommendations) > 0
        assert any("update" in rec.lower() for rec in recommendations)
        assert any("urgent" in rec.lower() for rec in recommendations)  # High severity


def mock_open(read_data):
    """Mock file open for testing"""
    from unittest.mock import mock_open as original_mock_open
    return original_mock_open(read_data=read_data)


@pytest.mark.integration
class TestContentModerationIntegration:
    """Integration tests for content moderation system"""
    
    def test_complete_moderation_workflow(self):
        """Test complete content moderation workflow"""
        moderator = ContentModerationManager()
        
        # Test various content types
        test_cases = [
            ("Spider-Man", ContentCategory.GUESS, ModerationAction.ALLOW),
            ("badword1", ContentCategory.GUESS, ModerationAction.WARN),
            ("admin123", ContentCategory.USERNAME, ModerationAction.REVIEW),
            ("ab", ContentCategory.USERNAME, ModerationAction.REVIEW),
        ]
        
        for content, category, expected_min_action in test_cases:
            result = moderator.moderate_content(content, category, "test_user")
            
            # Action should be at least as restrictive as expected
            action_severity = {
                ModerationAction.ALLOW: 0,
                ModerationAction.WARN: 1,
                ModerationAction.REVIEW: 2,
                ModerationAction.BLOCK: 3
            }
            
            assert action_severity[result.action] >= action_severity[expected_min_action]
    
    def test_security_headers_integration(self):
        """Test security headers integration"""
        headers_manager = SecurityHeadersManager()
        
        # Test different endpoint types
        endpoints = [
            ("/", "web"),
            ("/api/users", "api"),
            ("/images/character.jpg", "static")
        ]
        
        for path, endpoint_type in endpoints:
            headers = headers_manager.get_security_headers(path)
            
            # All endpoints should have basic security headers
            assert 'X-Content-Type-Options' in headers
            assert 'Strict-Transport-Security' in headers
            
            # API endpoints should have restrictive CSP
            if endpoint_type == "api":
                assert headers['Content-Security-Policy'] == "default-src 'none'"
            
            # Static endpoints should have caching headers
            if endpoint_type == "static":
                assert 'Cache-Control' in headers
    
    def test_csrf_protection_integration(self):
        """Test CSRF protection integration"""
        csrf = CSRFProtection("integration-test-key")
        
        # Simulate user login and token generation
        user_id = "integration_user"
        session_id = "integration_session"
        
        # Generate token
        token = csrf.generate_token(user_id, session_id)
        assert token is not None
        
        # Validate token
        assert csrf.validate_token(token, user_id, session_id) is True
        
        # Token should be consumed
        assert csrf.validate_token(token, user_id, session_id) is False
        
        # Generate new token for logout test
        token2 = csrf.generate_token(user_id, session_id)
        
        # Revoke all user tokens (logout)
        csrf.revoke_user_tokens(user_id)
        
        # Token should no longer be valid
        assert csrf.validate_token(token2, user_id, session_id) is False