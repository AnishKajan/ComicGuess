"""
OWASP ASVS security assessment and vulnerability testing utilities
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import hashlib
import secrets
from datetime import datetime, timedelta

import httpx
from fastapi import Request
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)

class VulnerabilityLevel(Enum):
    """Vulnerability severity levels based on CVSS"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityFinding:
    """Represents a security assessment finding"""
    id: str
    title: str
    description: str
    severity: VulnerabilityLevel
    category: str
    affected_component: str
    recommendation: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

class OWASPASVSAssessment:
    """
    OWASP Application Security Verification Standard (ASVS) assessment
    Implements key security controls from ASVS v4.0
    """
    
    def __init__(self, app_client: TestClient):
        self.client = app_client
        self.findings: List[SecurityFinding] = []
        
        # ASVS control categories
        self.asvs_categories = {
            "V1": "Architecture, Design and Threat Modeling",
            "V2": "Authentication",
            "V3": "Session Management", 
            "V4": "Access Control",
            "V5": "Validation, Sanitization and Encoding",
            "V7": "Error Handling and Logging",
            "V8": "Data Protection",
            "V9": "Communication",
            "V10": "Malicious Code",
            "V11": "Business Logic",
            "V12": "Files and Resources",
            "V13": "API and Web Service",
            "V14": "Configuration"
        }
    
    async def run_full_assessment(self) -> List[SecurityFinding]:
        """Run complete OWASP ASVS security assessment"""
        logger.info("Starting OWASP ASVS security assessment")
        
        # V2: Authentication Verification
        await self._assess_authentication()
        
        # V3: Session Management Verification  
        await self._assess_session_management()
        
        # V4: Access Control Verification
        await self._assess_access_control()
        
        # V5: Validation, Sanitization and Encoding
        await self._assess_input_validation()
        
        # V7: Error Handling and Logging
        await self._assess_error_handling()
        
        # V8: Data Protection
        await self._assess_data_protection()
        
        # V9: Communication Security
        await self._assess_communication_security()
        
        # V11: Business Logic Verification
        await self._assess_business_logic()
        
        # V13: API and Web Service Verification
        await self._assess_api_security()
        
        logger.info(f"Security assessment completed. Found {len(self.findings)} findings")
        return self.findings
    
    async def _assess_authentication(self):
        """V2: Authentication Verification Requirements"""
        
        # V2.1.1: Verify that user set passwords are at least 12 characters
        await self._test_password_policy()
        
        # V2.2.1: Verify that anti-automation controls are effective
        await self._test_anti_automation()
        
        # V2.3.1: Verify system generated initial passwords are randomly generated
        await self._test_password_generation()
        
        # V2.5.1: Verify that a system generated initial activation or recovery secret is not sent in clear text
        await self._test_credential_transmission()
    
    async def _assess_session_management(self):
        """V3: Session Management Verification Requirements"""
        
        # V3.1.1: Verify that the application never reveals session tokens in URL parameters
        await self._test_session_exposure()
        
        # V3.2.1: Verify that the application generates a new session token on user authentication
        await self._test_session_regeneration()
        
        # V3.3.1: Verify that session tokens are generated using approved cryptographic algorithms
        await self._test_session_token_strength()
        
        # V3.7.1: Verify that the application ensures a valid login session or requires re-authentication
        await self._test_session_timeout()
    
    async def _assess_access_control(self):
        """V4: Access Control Verification Requirements"""
        
        # V4.1.1: Verify that the application enforces access control rules on a trusted service layer
        await self._test_access_control_enforcement()
        
        # V4.2.1: Verify that sensitive data and APIs are protected against Insecure Direct Object References
        await self._test_idor_protection()
        
        # V4.3.1: Verify administrative interfaces use appropriate multi-factor authentication
        await self._test_admin_access_controls()
    
    async def _assess_input_validation(self):
        """V5: Validation, Sanitization and Encoding Verification Requirements"""
        
        # V5.1.1: Verify that the application has defenses against HTTP parameter pollution attacks
        await self._test_parameter_pollution()
        
        # V5.2.1: Verify that all untrusted HTML input is validated using a whitelist
        await self._test_html_validation()
        
        # V5.3.1: Verify that URL redirects and forwards only allow destinations which appear on a whitelist
        await self._test_redirect_validation()
        
        # V5.5.1: Verify that deserialization of untrusted data is avoided or is protected
        await self._test_deserialization_safety()
    
    async def _assess_error_handling(self):
        """V7: Error Handling and Logging Verification Requirements"""
        
        # V7.1.1: Verify that the application does not log credentials or payment details
        await self._test_sensitive_data_logging()
        
        # V7.2.1: Verify that all authentication decisions are logged
        await self._test_authentication_logging()
        
        # V7.4.1: Verify that error messages do not reveal sensitive information
        await self._test_error_information_disclosure()
    
    async def _assess_data_protection(self):
        """V8: Data Protection Verification Requirements"""
        
        # V8.1.1: Verify that the application protects sensitive data from being cached
        await self._test_sensitive_data_caching()
        
        # V8.2.1: Verify that all sensitive data is sent to the server in the HTTP message body
        await self._test_sensitive_data_transmission()
        
        # V8.3.1: Verify that sensitive data is sent with the Secure attribute
        await self._test_secure_cookie_attributes()
    
    async def _assess_communication_security(self):
        """V9: Communication Security Verification Requirements"""
        
        # V9.1.1: Verify that TLS is used for all connectivity
        await self._test_tls_usage()
        
        # V9.2.1: Verify that connections to and from the server use trusted TLS certificates
        await self._test_certificate_validation()
    
    async def _assess_business_logic(self):
        """V11: Business Logic Verification Requirements"""
        
        # V11.1.1: Verify the application will only process business logic flows for the same user
        await self._test_business_logic_integrity()
        
        # V11.2.1: Verify the application will only process business logic flows in sequential step order
        await self._test_workflow_integrity()
    
    async def _assess_api_security(self):
        """V13: API and Web Service Verification Requirements"""
        
        # V13.1.1: Verify that all application components use the same encodings and parsers
        await self._test_encoding_consistency()
        
        # V13.2.1: Verify that enabled RESTful HTTP methods are a valid choice for the user or action
        await self._test_http_method_validation()
        
        # V13.4.1: Verify that authorization decisions are made at both the URI and resource level
        await self._test_api_authorization()
    
    # Individual test implementations
    
    async def _test_password_policy(self):
        """Test password policy enforcement"""
        try:
            # Test weak password rejection
            weak_passwords = ["123", "password", "abc123", "qwerty"]
            
            for weak_password in weak_passwords:
                response = self.client.post("/auth/register", json={
                    "username": f"test_{secrets.token_hex(4)}",
                    "email": f"test_{secrets.token_hex(4)}@example.com",
                    "password": weak_password
                })
                
                if response.status_code == 200:
                    self.findings.append(SecurityFinding(
                        id="AUTH-001",
                        title="Weak Password Policy",
                        description=f"Application accepts weak password: {weak_password}",
                        severity=VulnerabilityLevel.MEDIUM,
                        category="Authentication",
                        affected_component="User Registration",
                        recommendation="Implement strong password policy requiring minimum 12 characters with complexity requirements",
                        evidence={"weak_password": weak_password, "response_code": response.status_code},
                        cwe_id="CWE-521",
                        owasp_category="V2.1.1"
                    ))
        except Exception as e:
            logger.error(f"Password policy test failed: {e}")
    
    async def _test_anti_automation(self):
        """Test anti-automation controls"""
        try:
            # Test rapid login attempts
            start_time = time.time()
            failed_attempts = 0
            
            for i in range(20):  # Try 20 rapid requests
                response = self.client.post("/auth/login", json={
                    "username": "nonexistent_user",
                    "password": "wrong_password"
                })
                
                if response.status_code != 429:  # Should be rate limited
                    failed_attempts += 1
            
            if failed_attempts > 10:  # More than half succeeded
                self.findings.append(SecurityFinding(
                    id="AUTH-002", 
                    title="Insufficient Anti-Automation Controls",
                    description="Application does not properly rate limit authentication attempts",
                    severity=VulnerabilityLevel.HIGH,
                    category="Authentication",
                    affected_component="Login Endpoint",
                    recommendation="Implement progressive delays, CAPTCHA, and account lockout mechanisms",
                    evidence={"failed_attempts": failed_attempts, "total_attempts": 20},
                    cwe_id="CWE-307",
                    owasp_category="V2.2.1"
                ))
        except Exception as e:
            logger.error(f"Anti-automation test failed: {e}")
    
    async def _test_session_exposure(self):
        """Test for session token exposure in URLs"""
        try:
            # Test if session tokens appear in URLs
            response = self.client.get("/user/profile?session_token=test123")
            
            if response.status_code == 200:
                self.findings.append(SecurityFinding(
                    id="SESS-001",
                    title="Session Token in URL",
                    description="Application may accept session tokens in URL parameters",
                    severity=VulnerabilityLevel.MEDIUM,
                    category="Session Management",
                    affected_component="Authentication System",
                    recommendation="Ensure session tokens are only transmitted in HTTP headers or secure cookies",
                    evidence={"test_url": "/user/profile?session_token=test123"},
                    cwe_id="CWE-598",
                    owasp_category="V3.1.1"
                ))
        except Exception as e:
            logger.error(f"Session exposure test failed: {e}")
    
    async def _test_idor_protection(self):
        """Test for Insecure Direct Object References"""
        try:
            # Test accessing other users' data
            user_ids = ["user1", "user2", "admin", "test", "1", "2"]
            
            for user_id in user_ids:
                response = self.client.get(f"/user/{user_id}")
                
                if response.status_code == 200:
                    # Check if response contains sensitive data without proper authorization
                    response_data = response.json()
                    if "email" in response_data or "password" in response_data:
                        self.findings.append(SecurityFinding(
                            id="AUTHZ-001",
                            title="Insecure Direct Object Reference",
                            description=f"Unauthorized access to user data for user_id: {user_id}",
                            severity=VulnerabilityLevel.HIGH,
                            category="Access Control",
                            affected_component="User API",
                            recommendation="Implement proper authorization checks for all user data access",
                            evidence={"user_id": user_id, "exposed_fields": list(response_data.keys())},
                            cwe_id="CWE-639",
                            owasp_category="V4.2.1"
                        ))
        except Exception as e:
            logger.error(f"IDOR test failed: {e}")
    
    async def _test_error_information_disclosure(self):
        """Test for information disclosure in error messages"""
        try:
            # Test various malformed requests
            test_cases = [
                {"endpoint": "/guess", "data": {"invalid": "data"}},
                {"endpoint": "/user/invalid_id", "data": None},
                {"endpoint": "/puzzle/invalid_date", "data": None},
            ]
            
            for test_case in test_cases:
                if test_case["data"]:
                    response = self.client.post(test_case["endpoint"], json=test_case["data"])
                else:
                    response = self.client.get(test_case["endpoint"])
                
                if response.status_code >= 400:
                    error_text = response.text.lower()
                    
                    # Check for sensitive information in error messages
                    sensitive_patterns = [
                        "database", "sql", "connection", "server", "internal",
                        "stack trace", "exception", "debug", "path", "file"
                    ]
                    
                    for pattern in sensitive_patterns:
                        if pattern in error_text:
                            self.findings.append(SecurityFinding(
                                id="ERROR-001",
                                title="Information Disclosure in Error Messages",
                                description=f"Error message contains sensitive information: {pattern}",
                                severity=VulnerabilityLevel.MEDIUM,
                                category="Error Handling",
                                affected_component=test_case["endpoint"],
                                recommendation="Implement generic error messages that don't reveal system internals",
                                evidence={"endpoint": test_case["endpoint"], "pattern": pattern},
                                cwe_id="CWE-209",
                                owasp_category="V7.4.1"
                            ))
                            break
        except Exception as e:
            logger.error(f"Error disclosure test failed: {e}")
    
    async def _test_tls_usage(self):
        """Test TLS configuration and usage"""
        try:
            # This would typically test the actual deployment
            # For now, we'll check if the application is configured for HTTPS
            
            # Check security headers that indicate HTTPS usage
            response = self.client.get("/")
            headers = response.headers
            
            security_headers = {
                "Strict-Transport-Security": "HSTS header missing",
                "X-Content-Type-Options": "Content type options header missing",
                "X-Frame-Options": "Frame options header missing",
                "X-XSS-Protection": "XSS protection header missing"
            }
            
            for header, message in security_headers.items():
                if header not in headers:
                    self.findings.append(SecurityFinding(
                        id="TLS-001",
                        title="Missing Security Header",
                        description=message,
                        severity=VulnerabilityLevel.MEDIUM,
                        category="Communication Security",
                        affected_component="HTTP Headers",
                        recommendation=f"Add {header} header to all responses",
                        evidence={"missing_header": header},
                        cwe_id="CWE-693",
                        owasp_category="V9.1.1"
                    ))
        except Exception as e:
            logger.error(f"TLS test failed: {e}")
    
    # Placeholder implementations for remaining tests
    async def _test_password_generation(self): pass
    async def _test_credential_transmission(self): pass
    async def _test_session_regeneration(self): pass
    async def _test_session_token_strength(self): pass
    async def _test_session_timeout(self): pass
    async def _test_access_control_enforcement(self): pass
    async def _test_admin_access_controls(self): pass
    async def _test_parameter_pollution(self): pass
    async def _test_html_validation(self): pass
    async def _test_redirect_validation(self): pass
    async def _test_deserialization_safety(self): pass
    async def _test_sensitive_data_logging(self): pass
    async def _test_authentication_logging(self): pass
    async def _test_sensitive_data_caching(self): pass
    async def _test_sensitive_data_transmission(self): pass
    async def _test_secure_cookie_attributes(self): pass
    async def _test_certificate_validation(self): pass
    async def _test_business_logic_integrity(self): pass
    async def _test_workflow_integrity(self): pass
    async def _test_encoding_consistency(self): pass
    async def _test_http_method_validation(self): pass
    async def _test_api_authorization(self): pass
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate security assessment report"""
        findings_by_severity = {}
        findings_by_category = {}
        
        for finding in self.findings:
            # Group by severity
            severity = finding.severity.value
            if severity not in findings_by_severity:
                findings_by_severity[severity] = []
            findings_by_severity[severity].append(finding)
            
            # Group by category
            category = finding.category
            if category not in findings_by_category:
                findings_by_category[category] = []
            findings_by_category[category].append(finding)
        
        return {
            "assessment_date": datetime.utcnow().isoformat(),
            "total_findings": len(self.findings),
            "findings_by_severity": {
                severity: len(findings) for severity, findings in findings_by_severity.items()
            },
            "findings_by_category": {
                category: len(findings) for category, findings in findings_by_category.items()
            },
            "findings": [
                {
                    "id": f.id,
                    "title": f.title,
                    "description": f.description,
                    "severity": f.severity.value,
                    "category": f.category,
                    "affected_component": f.affected_component,
                    "recommendation": f.recommendation,
                    "cwe_id": f.cwe_id,
                    "owasp_category": f.owasp_category,
                    "evidence": f.evidence,
                    "timestamp": f.timestamp.isoformat()
                }
                for f in self.findings
            ]
        }

class PenetrationTester:
    """Automated penetration testing utilities"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.findings: List[SecurityFinding] = []
    
    async def run_penetration_tests(self) -> List[SecurityFinding]:
        """Run automated penetration tests"""
        logger.info("Starting penetration testing")
        
        await self._test_sql_injection()
        await self._test_xss_vulnerabilities()
        await self._test_command_injection()
        await self._test_path_traversal()
        await self._test_authentication_bypass()
        
        logger.info(f"Penetration testing completed. Found {len(self.findings)} vulnerabilities")
        return self.findings
    
    async def _test_sql_injection(self):
        """Test for SQL injection vulnerabilities"""
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users --",
            "1' AND 1=1 --",
            "admin'--",
            "' OR 1=1#"
        ]
        
        endpoints = ["/guess", "/user/search", "/puzzle/search"]
        
        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                for payload in payloads:
                    try:
                        response = await client.post(
                            f"{self.base_url}{endpoint}",
                            json={"query": payload},
                            timeout=10.0
                        )
                        
                        # Check for SQL error messages
                        if response.status_code == 500:
                            error_text = response.text.lower()
                            sql_errors = ["sql", "mysql", "postgresql", "sqlite", "database"]
                            
                            if any(error in error_text for error in sql_errors):
                                self.findings.append(SecurityFinding(
                                    id="SQLI-001",
                                    title="Potential SQL Injection",
                                    description=f"SQL injection payload triggered database error in {endpoint}",
                                    severity=VulnerabilityLevel.CRITICAL,
                                    category="Input Validation",
                                    affected_component=endpoint,
                                    recommendation="Use parameterized queries and input validation",
                                    evidence={"payload": payload, "endpoint": endpoint},
                                    cwe_id="CWE-89"
                                ))
                    except Exception as e:
                        logger.debug(f"SQL injection test error: {e}")
    
    async def _test_xss_vulnerabilities(self):
        """Test for Cross-Site Scripting vulnerabilities"""
        payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "';alert('XSS');//",
            "<svg onload=alert('XSS')>"
        ]
        
        endpoints = ["/guess", "/user/profile"]
        
        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                for payload in payloads:
                    try:
                        response = await client.post(
                            f"{self.base_url}{endpoint}",
                            json={"input": payload},
                            timeout=10.0
                        )
                        
                        # Check if payload is reflected without encoding
                        if payload in response.text:
                            self.findings.append(SecurityFinding(
                                id="XSS-001",
                                title="Potential Cross-Site Scripting",
                                description=f"XSS payload reflected without encoding in {endpoint}",
                                severity=VulnerabilityLevel.HIGH,
                                category="Input Validation",
                                affected_component=endpoint,
                                recommendation="Implement proper output encoding and Content Security Policy",
                                evidence={"payload": payload, "endpoint": endpoint},
                                cwe_id="CWE-79"
                            ))
                    except Exception as e:
                        logger.debug(f"XSS test error: {e}")
    
    async def _test_command_injection(self):
        """Test for command injection vulnerabilities"""
        payloads = [
            "; ls -la",
            "| whoami",
            "&& cat /etc/passwd",
            "`id`",
            "$(whoami)"
        ]
        
        # This would test endpoints that might process system commands
        # Implementation depends on specific application functionality
        pass
    
    async def _test_path_traversal(self):
        """Test for path traversal vulnerabilities"""
        payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ]
        
        # Test file access endpoints
        endpoints = ["/images/", "/files/"]
        
        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                for payload in payloads:
                    try:
                        response = await client.get(
                            f"{self.base_url}{endpoint}{payload}",
                            timeout=10.0
                        )
                        
                        # Check for system file content
                        if "root:" in response.text or "localhost" in response.text:
                            self.findings.append(SecurityFinding(
                                id="PATH-001",
                                title="Path Traversal Vulnerability",
                                description=f"Path traversal successful in {endpoint}",
                                severity=VulnerabilityLevel.HIGH,
                                category="Access Control",
                                affected_component=endpoint,
                                recommendation="Implement proper file path validation and sandboxing",
                                evidence={"payload": payload, "endpoint": endpoint},
                                cwe_id="CWE-22"
                            ))
                    except Exception as e:
                        logger.debug(f"Path traversal test error: {e}")
    
    async def _test_authentication_bypass(self):
        """Test for authentication bypass vulnerabilities"""
        # Test common authentication bypass techniques
        bypass_attempts = [
            {"headers": {"X-Forwarded-User": "admin"}},
            {"headers": {"X-Remote-User": "admin"}},
            {"cookies": {"admin": "true"}},
            {"params": {"admin": "1"}}
        ]
        
        protected_endpoint = "/admin/users"
        
        async with httpx.AsyncClient() as client:
            for attempt in bypass_attempts:
                try:
                    response = await client.get(
                        f"{self.base_url}{protected_endpoint}",
                        headers=attempt.get("headers", {}),
                        cookies=attempt.get("cookies", {}),
                        params=attempt.get("params", {}),
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        self.findings.append(SecurityFinding(
                            id="AUTH-BYPASS-001",
                            title="Authentication Bypass",
                            description=f"Authentication bypass successful using {attempt}",
                            severity=VulnerabilityLevel.CRITICAL,
                            category="Authentication",
                            affected_component=protected_endpoint,
                            recommendation="Implement proper authentication validation on server side",
                            evidence={"bypass_method": attempt, "endpoint": protected_endpoint},
                            cwe_id="CWE-287"
                        ))
                except Exception as e:
                    logger.debug(f"Auth bypass test error: {e}")