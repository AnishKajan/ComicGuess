"""
Tests for comprehensive threat protection system
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from fastapi.testclient import TestClient

from app.security.threat_protection import (
    ThreatDetector, ThreatEvent, ThreatLevel, ProgressivePenalty,
    CaptchaProvider, ThreatProtectionMiddleware
)
from app.security.security_assessment import OWASPASVSAssessment, PenetrationTester


class TestThreatDetector:
    """Test threat detection functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.detector = ThreatDetector()
    
    def test_progressive_penalty_calculation(self):
        """Test progressive penalty calculation"""
        penalty = ProgressivePenalty()
        
        # First violation: 1 minute
        penalty.add_violation()
        assert penalty.penalty_duration == 60
        
        # Second violation: 5 minutes
        penalty.add_violation()
        assert penalty.penalty_duration == 300
        
        # Third violation: 15 minutes
        penalty.add_violation()
        assert penalty.penalty_duration == 900
        
        # Fourth violation: 1 hour
        penalty.add_violation()
        assert penalty.penalty_duration == 3600
        
        # Fifth+ violation: 24 hours
        penalty.add_violation()
        assert penalty.penalty_duration == 86400
    
    def test_rapid_request_detection(self):
        """Test rapid request pattern detection"""
        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}
        
        # Simulate rapid requests
        threats = []
        for i in range(25):  # Exceed threshold of 20
            detected_threats = self.detector.detect_threats(mock_request)
            threats.extend(detected_threats)
        
        # Should detect rapid request threat
        rapid_threats = [t for t in threats if t.threat_type == "rapid_requests"]
        assert len(rapid_threats) > 0
        assert rapid_threats[0].threat_level == ThreatLevel.MEDIUM
    
    def test_suspicious_pattern_detection(self):
        """Test suspicious pattern detection in user input"""
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}
        
        # Test various suspicious patterns
        suspicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "javascript:alert(1)",
            "UNION SELECT * FROM users",
            "admin'--"
        ]
        
        for suspicious_input in suspicious_inputs:
            threats = self.detector.detect_threats(
                mock_request, 
                user_id="test_user",
                guess=suspicious_input
            )
            
            pattern_threats = [t for t in threats if t.threat_type == "suspicious_pattern"]
            assert len(pattern_threats) > 0
            assert pattern_threats[0].threat_level == ThreatLevel.MEDIUM
    
    def test_user_agent_anomaly_detection(self):
        """Test user agent anomaly detection"""
        # Test missing user agent
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}
        
        threats = self.detector.detect_threats(mock_request)
        ua_threats = [t for t in threats if t.threat_type == "suspicious_user_agent"]
        assert len(ua_threats) > 0
        
        # Test bot user agent
        mock_request.headers = {"User-Agent": "GoogleBot/2.1"}
        threats = self.detector.detect_threats(mock_request)
        bot_threats = [t for t in threats if t.threat_type == "bot_user_agent"]
        assert len(bot_threats) > 0
    
    def test_progressive_penalties_application(self):
        """Test application of progressive penalties"""
        # Create threat events
        threats = [
            ThreatEvent(
                timestamp=datetime.utcnow(),
                ip_address="192.168.1.100",
                user_id="test_user",
                threat_type="rapid_requests",
                threat_level=ThreatLevel.MEDIUM,
                details={}
            ),
            ThreatEvent(
                timestamp=datetime.utcnow(),
                ip_address="192.168.1.100",
                user_id="test_user",
                threat_type="suspicious_pattern",
                threat_level=ThreatLevel.HIGH,
                details={}
            )
        ]
        
        penalties = self.detector.apply_progressive_penalties(threats)
        
        # Should have penalties for both IP and user
        assert "ip:192.168.1.100" in penalties
        assert "user:test_user" in penalties
        assert penalties["ip:192.168.1.100"] > 0
        assert penalties["user:test_user"] > 0
    
    def test_blocking_functionality(self):
        """Test IP and user blocking"""
        ip_address = "192.168.1.100"
        user_id = "test_user"
        
        # Initially not blocked
        is_blocked, reason = self.detector.is_blocked(ip_address, user_id)
        assert not is_blocked
        
        # Add to blocked IPs
        self.detector.blocked_ips.add(ip_address)
        is_blocked, reason = self.detector.is_blocked(ip_address, user_id)
        assert is_blocked
        assert "permanently blocked" in reason
        
        # Test user blocking
        self.detector.blocked_ips.remove(ip_address)
        self.detector.blocked_users.add(user_id)
        is_blocked, reason = self.detector.is_blocked(ip_address, user_id)
        assert is_blocked
        assert "User account permanently blocked" in reason
    
    def test_threat_summary_generation(self):
        """Test threat summary generation"""
        # Add some test threat events
        self.detector.threat_events = [
            ThreatEvent(
                timestamp=datetime.utcnow(),
                ip_address="192.168.1.100",
                user_id="user1",
                threat_type="rapid_requests",
                threat_level=ThreatLevel.MEDIUM,
                details={}
            ),
            ThreatEvent(
                timestamp=datetime.utcnow(),
                ip_address="192.168.1.101",
                user_id="user2",
                threat_type="suspicious_pattern",
                threat_level=ThreatLevel.HIGH,
                details={}
            )
        ]
        
        summary = self.detector.get_threat_summary()
        
        assert summary["total_threats"] == 2
        assert summary["threats_by_type"]["rapid_requests"] == 1
        assert summary["threats_by_type"]["suspicious_pattern"] == 1
        assert summary["threats_by_level"]["medium"] == 1
        assert summary["threats_by_level"]["high"] == 1


class TestCaptchaProvider:
    """Test CAPTCHA integration"""
    
    def setup_method(self):
        """Setup test environment"""
        self.captcha = CaptchaProvider("test_secret", "test_site_key")
    
    @pytest.mark.asyncio
    async def test_captcha_verification_success(self):
        """Test successful CAPTCHA verification"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.json.return_value = {"success": True, "score": 0.8}
            mock_post.return_value = mock_response
            
            result = await self.captcha.verify_captcha("valid_token", "192.168.1.100")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_captcha_verification_failure(self):
        """Test failed CAPTCHA verification"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock failed response
            mock_response = Mock()
            mock_response.json.return_value = {"success": False, "error-codes": ["invalid-input-response"]}
            mock_post.return_value = mock_response
            
            result = await self.captcha.verify_captcha("invalid_token", "192.168.1.100")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_captcha_verification_low_score(self):
        """Test CAPTCHA verification with low score"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock low score response
            mock_response = Mock()
            mock_response.json.return_value = {"success": True, "score": 0.3}
            mock_post.return_value = mock_response
            
            result = await self.captcha.verify_captcha("low_score_token", "192.168.1.100")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_captcha_verification_network_error(self):
        """Test CAPTCHA verification with network error"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock network error
            mock_post.side_effect = Exception("Network error")
            
            result = await self.captcha.verify_captcha("token", "192.168.1.100")
            assert result is False


class TestThreatProtectionMiddleware:
    """Test threat protection middleware"""
    
    def setup_method(self):
        """Setup test environment"""
        self.captcha = CaptchaProvider("test_secret", "test_site_key")
        self.middleware = ThreatProtectionMiddleware(self.captcha)
    
    @pytest.mark.asyncio
    async def test_blocked_ip_handling(self):
        """Test handling of blocked IPs"""
        # Block an IP
        self.middleware.detector.blocked_ips.add("192.168.1.100")
        
        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}
        mock_request.url.path = "/guess"
        mock_request.method = "POST"
        
        # Mock call_next
        async def mock_call_next(request):
            return Mock(status_code=200)
        
        response = await self.middleware(mock_request, mock_call_next)
        
        # Should return 429 status
        assert response.status_code == 429
        assert "blocked" in response.body.decode().lower()
    
    @pytest.mark.asyncio
    async def test_captcha_requirement(self):
        """Test CAPTCHA requirement logic"""
        # Add threat history to trigger CAPTCHA requirement
        current_time = datetime.utcnow()
        self.middleware.detector.threat_events = [
            ThreatEvent(
                timestamp=current_time - timedelta(minutes=10),
                ip_address="192.168.1.100",
                user_id="test_user",
                threat_type="rapid_requests",
                threat_level=ThreatLevel.MEDIUM,
                details={}
            ),
            ThreatEvent(
                timestamp=current_time - timedelta(minutes=5),
                ip_address="192.168.1.100",
                user_id="test_user",
                threat_type="suspicious_pattern",
                threat_level=ThreatLevel.MEDIUM,
                details={}
            )
        ]
        
        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {"Authorization": "Bearer test_token"}
        mock_request.url.path = "/guess"
        mock_request.method = "POST"
        mock_request.body = AsyncMock(return_value=b'{"guess": "test"}')
        
        # Mock JWT verification
        with patch('app.auth.jwt_handler.verify_token') as mock_verify:
            mock_verify.return_value = {"sub": "test_user"}
            
            async def mock_call_next(request):
                return Mock(status_code=200)
            
            response = await self.middleware(mock_request, mock_call_next)
            
            # Should require CAPTCHA
            assert response.status_code == 400
            response_data = response.body.decode()
            assert "captcha" in response_data.lower()


class TestOWASPASVSAssessment:
    """Test OWASP ASVS security assessment"""
    
    def setup_method(self):
        """Setup test environment"""
        self.mock_client = Mock(spec=TestClient)
        self.assessment = OWASPASVSAssessment(self.mock_client)
    
    @pytest.mark.asyncio
    async def test_password_policy_assessment(self):
        """Test password policy assessment"""
        # Mock weak password acceptance
        self.mock_client.post.return_value = Mock(status_code=200)
        
        await self.assessment._test_password_policy()
        
        # Should detect weak password acceptance
        auth_findings = [f for f in self.assessment.findings if f.category == "Authentication"]
        assert len(auth_findings) > 0
        assert any("weak password" in f.title.lower() for f in auth_findings)
    
    @pytest.mark.asyncio
    async def test_anti_automation_assessment(self):
        """Test anti-automation controls assessment"""
        # Mock insufficient rate limiting
        self.mock_client.post.return_value = Mock(status_code=200)  # Should be 429
        
        await self.assessment._test_anti_automation()
        
        # Should detect insufficient anti-automation
        findings = [f for f in self.assessment.findings if "automation" in f.title.lower()]
        assert len(findings) > 0
    
    @pytest.mark.asyncio
    async def test_session_exposure_assessment(self):
        """Test session token exposure assessment"""
        # Mock session token in URL acceptance
        self.mock_client.get.return_value = Mock(status_code=200)
        
        await self.assessment._test_session_exposure()
        
        # Should detect session exposure
        session_findings = [f for f in self.assessment.findings if f.category == "Session Management"]
        assert len(session_findings) > 0
    
    @pytest.mark.asyncio
    async def test_idor_assessment(self):
        """Test Insecure Direct Object Reference assessment"""
        # Mock unauthorized data access
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"email": "test@example.com", "password": "hashed"}
        self.mock_client.get.return_value = mock_response
        
        await self.assessment._test_idor_protection()
        
        # Should detect IDOR vulnerability
        idor_findings = [f for f in self.assessment.findings if "direct object" in f.title.lower()]
        assert len(idor_findings) > 0
    
    @pytest.mark.asyncio
    async def test_error_disclosure_assessment(self):
        """Test error information disclosure assessment"""
        # Mock error with sensitive information
        mock_response = Mock(status_code=500)
        mock_response.text = "Database connection failed: mysql://user:pass@localhost/db"
        self.mock_client.post.return_value = mock_response
        self.mock_client.get.return_value = mock_response
        
        await self.assessment._test_error_information_disclosure()
        
        # Should detect information disclosure
        error_findings = [f for f in self.assessment.findings if f.category == "Error Handling"]
        assert len(error_findings) > 0
    
    @pytest.mark.asyncio
    async def test_security_headers_assessment(self):
        """Test security headers assessment"""
        # Mock missing security headers
        mock_response = Mock()
        mock_response.headers = {}  # No security headers
        self.mock_client.get.return_value = mock_response
        
        await self.assessment._test_tls_usage()
        
        # Should detect missing security headers
        tls_findings = [f for f in self.assessment.findings if f.category == "Communication Security"]
        assert len(tls_findings) > 0
    
    def test_report_generation(self):
        """Test security assessment report generation"""
        # Add some test findings
        self.assessment.findings = [
            Mock(
                id="TEST-001",
                title="Test Finding",
                description="Test description",
                severity=Mock(value="high"),
                category="Test Category",
                affected_component="Test Component",
                recommendation="Test recommendation",
                cwe_id="CWE-123",
                owasp_category="V1.1.1",
                evidence={},
                timestamp=datetime.utcnow()
            )
        ]
        
        report = self.assessment.generate_report()
        
        assert "assessment_date" in report
        assert "total_findings" in report
        assert report["total_findings"] == 1
        assert "findings_by_severity" in report
        assert "findings_by_category" in report
        assert "findings" in report
        assert len(report["findings"]) == 1


class TestPenetrationTester:
    """Test penetration testing functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.pen_tester = PenetrationTester("http://localhost:8000")
    
    @pytest.mark.asyncio
    async def test_sql_injection_detection(self):
        """Test SQL injection vulnerability detection"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock SQL error response
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "MySQL error: You have an error in your SQL syntax"
            mock_post.return_value = mock_response
            
            await self.pen_tester._test_sql_injection()
            
            # Should detect SQL injection vulnerability
            sqli_findings = [f for f in self.pen_tester.findings if f.id.startswith("SQLI")]
            assert len(sqli_findings) > 0
            assert sqli_findings[0].severity == VulnerabilityLevel.CRITICAL
    
    @pytest.mark.asyncio
    async def test_xss_detection(self):
        """Test XSS vulnerability detection"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock reflected XSS
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "Hello <script>alert('XSS')</script>"
            mock_post.return_value = mock_response
            
            await self.pen_tester._test_xss_vulnerabilities()
            
            # Should detect XSS vulnerability
            xss_findings = [f for f in self.pen_tester.findings if f.id.startswith("XSS")]
            assert len(xss_findings) > 0
            assert xss_findings[0].severity == VulnerabilityLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_path_traversal_detection(self):
        """Test path traversal vulnerability detection"""
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock successful path traversal
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "root:x:0:0:root:/root:/bin/bash"
            mock_get.return_value = mock_response
            
            await self.pen_tester._test_path_traversal()
            
            # Should detect path traversal vulnerability
            path_findings = [f for f in self.pen_tester.findings if f.id.startswith("PATH")]
            assert len(path_findings) > 0
            assert path_findings[0].severity == VulnerabilityLevel.HIGH
    
    @pytest.mark.asyncio
    async def test_authentication_bypass_detection(self):
        """Test authentication bypass detection"""
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock successful bypass
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "Admin panel access granted"
            mock_get.return_value = mock_response
            
            await self.pen_tester._test_authentication_bypass()
            
            # Should detect authentication bypass
            bypass_findings = [f for f in self.pen_tester.findings if "bypass" in f.id.lower()]
            assert len(bypass_findings) > 0
            assert bypass_findings[0].severity == VulnerabilityLevel.CRITICAL


@pytest.mark.integration
class TestThreatProtectionIntegration:
    """Integration tests for threat protection system"""
    
    @pytest.mark.asyncio
    async def test_full_threat_detection_workflow(self):
        """Test complete threat detection and mitigation workflow"""
        detector = ThreatDetector()
        
        # Simulate attack sequence
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {"User-Agent": "AttackBot/1.0"}
        
        # 1. Initial suspicious activity
        threats1 = detector.detect_threats(
            mock_request, 
            user_id="attacker",
            guess="'; DROP TABLE users; --"
        )
        
        # 2. Apply penalties
        penalties1 = detector.apply_progressive_penalties(threats1)
        
        # 3. More suspicious activity
        threats2 = detector.detect_threats(
            mock_request,
            user_id="attacker", 
            guess="<script>alert('xss')</script>"
        )
        
        # 4. Apply more penalties
        penalties2 = detector.apply_progressive_penalties(threats2)
        
        # 5. Check if blocked
        is_blocked, reason = detector.is_blocked("192.168.1.100", "attacker")
        
        # Should have detected threats and applied penalties
        assert len(threats1) > 0
        assert len(threats2) > 0
        assert len(penalties1) > 0
        assert len(penalties2) > 0
        
        # Should eventually block the attacker
        # (May not be blocked immediately depending on threat levels)
        summary = detector.get_threat_summary()
        assert summary["total_threats"] > 0
    
    @pytest.mark.asyncio
    async def test_captcha_integration_workflow(self):
        """Test CAPTCHA integration in threat protection workflow"""
        captcha = CaptchaProvider("test_secret", "test_site_key")
        middleware = ThreatProtectionMiddleware(captcha)
        
        # Add threat history to trigger CAPTCHA
        current_time = datetime.utcnow()
        middleware.detector.threat_events = [
            ThreatEvent(
                timestamp=current_time - timedelta(minutes=10),
                ip_address="192.168.1.100",
                user_id="test_user",
                threat_type="rapid_requests",
                threat_level=ThreatLevel.MEDIUM,
                details={}
            ),
            ThreatEvent(
                timestamp=current_time - timedelta(minutes=5),
                ip_address="192.168.1.100", 
                user_id="test_user",
                threat_type="suspicious_pattern",
                threat_level=ThreatLevel.MEDIUM,
                details={}
            )
        ]
        
        # Test CAPTCHA requirement
        should_require = await middleware._should_require_captcha("192.168.1.100", "test_user")
        assert should_require is True
        
        # Test CAPTCHA verification
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"success": True, "score": 0.8}
            mock_post.return_value = mock_response
            
            result = await captcha.verify_captcha("valid_token", "192.168.1.100")
            assert result is True