"""
CSRF (Cross-Site Request Forgery) protection utilities
"""

import secrets
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from fastapi import Request, HTTPException, status
from fastapi.responses import Response

logger = logging.getLogger(__name__)

@dataclass
class CSRFToken:
    """CSRF token with metadata"""
    token: str
    user_id: Optional[str]
    session_id: Optional[str]
    created_at: datetime
    expires_at: datetime
    used: bool = False

class CSRFProtection:
    """CSRF protection implementation"""
    
    def __init__(self, secret_key: str, token_lifetime: timedelta = timedelta(hours=1)):
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
        self.token_lifetime = token_lifetime
        self.active_tokens: Dict[str, CSRFToken] = {}
        
        # Configuration
        self.cookie_name = "csrf_token"
        self.header_name = "X-CSRF-Token"
        self.form_field_name = "csrf_token"
        
        # Cookie settings
        self.cookie_secure = True  # Set to False for development over HTTP
        self.cookie_httponly = True
        self.cookie_samesite = "strict"
    
    def generate_token(self, user_id: Optional[str] = None, 
                      session_id: Optional[str] = None) -> str:
        """Generate a new CSRF token"""
        try:
            # Generate random token
            random_token = secrets.token_urlsafe(32)
            
            # Create token payload
            payload = f"{random_token}:{user_id or 'anonymous'}:{session_id or 'no_session'}"
            
            # Create HMAC signature
            signature = hmac.new(
                self.secret_key,
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Combine token and signature
            csrf_token = f"{random_token}.{signature}"
            
            # Store token metadata
            now = datetime.now(timezone.utc)
            token_metadata = CSRFToken(
                token=csrf_token,
                user_id=user_id,
                session_id=session_id,
                created_at=now,
                expires_at=now + self.token_lifetime
            )
            
            self.active_tokens[csrf_token] = token_metadata
            
            # Clean up expired tokens
            self._cleanup_expired_tokens()
            
            logger.debug(f"Generated CSRF token for user: {user_id}")
            return csrf_token
            
        except Exception as e:
            logger.error(f"Error generating CSRF token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate CSRF token"
            )
    
    def validate_token(self, token: str, user_id: Optional[str] = None,
                      session_id: Optional[str] = None, mark_used: bool = True) -> bool:
        """Validate a CSRF token"""
        try:
            if not token:
                logger.warning("CSRF validation failed: No token provided")
                return False
            
            # Check if token exists and is not expired
            token_metadata = self.active_tokens.get(token)
            if not token_metadata:
                logger.warning(f"CSRF validation failed: Token not found")
                return False
            
            # Check expiration
            if datetime.now(timezone.utc) > token_metadata.expires_at:
                logger.warning("CSRF validation failed: Token expired")
                self._remove_token(token)
                return False
            
            # Check if already used (prevent replay attacks)
            if token_metadata.used:
                logger.warning("CSRF validation failed: Token already used")
                return False
            
            # Validate token structure
            if '.' not in token:
                logger.warning("CSRF validation failed: Invalid token format")
                return False
            
            random_part, signature = token.rsplit('.', 1)
            
            # Recreate payload and verify signature
            payload = f"{random_part}:{user_id or 'anonymous'}:{session_id or 'no_session'}"
            expected_signature = hmac.new(
                self.secret_key,
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("CSRF validation failed: Invalid signature")
                return False
            
            # Validate user/session binding
            if token_metadata.user_id != user_id or token_metadata.session_id != session_id:
                logger.warning("CSRF validation failed: User/session mismatch")
                return False
            
            # Mark token as used if requested
            if mark_used:
                token_metadata.used = True
            
            logger.debug(f"CSRF token validated successfully for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating CSRF token: {e}")
            return False
    
    def _remove_token(self, token: str):
        """Remove a token from active tokens"""
        if token in self.active_tokens:
            del self.active_tokens[token]
    
    def _cleanup_expired_tokens(self):
        """Clean up expired tokens"""
        current_time = datetime.now(timezone.utc)
        expired_tokens = [
            token for token, metadata in self.active_tokens.items()
            if current_time > metadata.expires_at
        ]
        
        for token in expired_tokens:
            del self.active_tokens[token]
        
        if expired_tokens:
            logger.debug(f"Cleaned up {len(expired_tokens)} expired CSRF tokens")
    
    def set_csrf_cookie(self, response: Response, token: str):
        """Set CSRF token as HTTP-only cookie"""
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            max_age=int(self.token_lifetime.total_seconds()),
            httponly=self.cookie_httponly,
            secure=self.cookie_secure,
            samesite=self.cookie_samesite
        )
    
    def get_csrf_token_from_request(self, request: Request) -> Optional[str]:
        """Extract CSRF token from request (header or form data)"""
        # Try header first
        token = request.headers.get(self.header_name)
        if token:
            return token
        
        # Try cookie
        token = request.cookies.get(self.cookie_name)
        if token:
            return token
        
        # For form submissions, token might be in form data
        # This would need to be handled at the endpoint level
        return None
    
    def get_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Get information about a token (for debugging/monitoring)"""
        token_metadata = self.active_tokens.get(token)
        if not token_metadata:
            return None
        
        return {
            "user_id": token_metadata.user_id,
            "session_id": token_metadata.session_id,
            "created_at": token_metadata.created_at.isoformat(),
            "expires_at": token_metadata.expires_at.isoformat(),
            "used": token_metadata.used,
            "time_remaining": (token_metadata.expires_at - datetime.now(timezone.utc)).total_seconds()
        }
    
    def revoke_user_tokens(self, user_id: str):
        """Revoke all CSRF tokens for a specific user"""
        tokens_to_remove = [
            token for token, metadata in self.active_tokens.items()
            if metadata.user_id == user_id
        ]
        
        for token in tokens_to_remove:
            del self.active_tokens[token]
        
        logger.info(f"Revoked {len(tokens_to_remove)} CSRF tokens for user: {user_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get CSRF protection statistics"""
        current_time = datetime.now(timezone.utc)
        
        total_tokens = len(self.active_tokens)
        expired_tokens = sum(
            1 for metadata in self.active_tokens.values()
            if current_time > metadata.expires_at
        )
        used_tokens = sum(
            1 for metadata in self.active_tokens.values()
            if metadata.used
        )
        
        return {
            "total_active_tokens": total_tokens,
            "expired_tokens": expired_tokens,
            "used_tokens": used_tokens,
            "valid_tokens": total_tokens - expired_tokens - used_tokens
        }

class CSRFMiddleware:
    """FastAPI middleware for CSRF protection"""
    
    def __init__(self, csrf_protection: CSRFProtection, 
                 protected_methods: set = None, exempt_paths: set = None):
        self.csrf_protection = csrf_protection
        self.protected_methods = protected_methods or {"POST", "PUT", "PATCH", "DELETE"}
        self.exempt_paths = exempt_paths or {"/health", "/api/auth/login"}
    
    async def __call__(self, request: Request, call_next):
        """Process request through CSRF protection"""
        try:
            # Skip CSRF protection for exempt paths
            if request.url.path in self.exempt_paths:
                return await call_next(request)
            
            # Skip CSRF protection for non-protected methods
            if request.method not in self.protected_methods:
                return await call_next(request)
            
            # Extract user and session info
            user_id = self._get_user_id(request)
            session_id = self._get_session_id(request)
            
            # Get CSRF token from request
            csrf_token = self.csrf_protection.get_csrf_token_from_request(request)
            
            if not csrf_token:
                logger.warning(f"CSRF protection: No token provided for {request.method} {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token required"
                )
            
            # Validate CSRF token
            if not self.csrf_protection.validate_token(csrf_token, user_id, session_id):
                logger.warning(f"CSRF protection: Invalid token for {request.method} {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid CSRF token"
                )
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"CSRF middleware error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CSRF protection error"
            )
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        # Try to get from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from app.auth.jwt_handler import verify_token
                token = auth_header.split(" ")[1]
                payload = verify_token(token)
                return payload.get("sub")
            except Exception:
                pass
        
        return None
    
    def _get_session_id(self, request: Request) -> Optional[str]:
        """Extract session ID from request"""
        # This could be from a session cookie or header
        return request.cookies.get("session_id")

# Dependency scanning utilities
class DependencyScanner:
    """Utilities for scanning dependencies for vulnerabilities"""
    
    def __init__(self):
        self.known_vulnerabilities = {
            # Example vulnerability database (in production, use real vulnerability feeds)
            "requests": {
                "2.25.0": ["CVE-2021-33503"],
                "2.24.0": ["CVE-2021-33503"]
            },
            "pillow": {
                "8.1.0": ["CVE-2021-25287", "CVE-2021-25288"],
                "8.0.0": ["CVE-2021-25287", "CVE-2021-25288"]
            }
        }
    
    def scan_requirements_file(self, requirements_path: str) -> Dict[str, Any]:
        """Scan requirements.txt file for known vulnerabilities"""
        vulnerabilities = []
        
        try:
            with open(requirements_path, 'r') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Parse package and version
                if '==' in line:
                    package, version = line.split('==', 1)
                    package = package.strip()
                    version = version.strip()
                    
                    # Check for known vulnerabilities
                    if package in self.known_vulnerabilities:
                        package_vulns = self.known_vulnerabilities[package]
                        if version in package_vulns:
                            vulnerabilities.append({
                                "package": package,
                                "version": version,
                                "line": line_num,
                                "vulnerabilities": package_vulns[version],
                                "severity": "high"  # Would be determined by CVE data
                            })
            
            return {
                "scan_date": datetime.now(timezone.utc).isoformat(),
                "file_path": requirements_path,
                "total_vulnerabilities": len(vulnerabilities),
                "vulnerabilities": vulnerabilities,
                "recommendations": self._generate_recommendations(vulnerabilities)
            }
            
        except FileNotFoundError:
            return {"error": f"Requirements file not found: {requirements_path}"}
        except Exception as e:
            return {"error": f"Error scanning requirements: {str(e)}"}
    
    def _generate_recommendations(self, vulnerabilities: list) -> list:
        """Generate recommendations based on found vulnerabilities"""
        recommendations = []
        
        if vulnerabilities:
            recommendations.append("Update vulnerable packages to latest secure versions")
            recommendations.append("Review security advisories for affected packages")
            recommendations.append("Consider using dependency scanning tools in CI/CD pipeline")
        
        high_severity = [v for v in vulnerabilities if v.get("severity") == "high"]
        if high_severity:
            recommendations.append("URGENT: Address high-severity vulnerabilities immediately")
        
        return recommendations
    
    def check_package_security(self, package_name: str, version: str) -> Dict[str, Any]:
        """Check a specific package version for security issues"""
        vulnerabilities = []
        
        if package_name in self.known_vulnerabilities:
            package_vulns = self.known_vulnerabilities[package_name]
            if version in package_vulns:
                vulnerabilities = package_vulns[version]
        
        return {
            "package": package_name,
            "version": version,
            "vulnerabilities": vulnerabilities,
            "is_vulnerable": len(vulnerabilities) > 0,
            "check_date": datetime.now(timezone.utc).isoformat()
        }

# Global instances
csrf_protection = CSRFProtection(
    secret_key="your-csrf-secret-key",  # Should be loaded from secure config
    token_lifetime=timedelta(hours=1)
)

dependency_scanner = DependencyScanner()

# Convenience functions
def generate_csrf_token(user_id: str = None, session_id: str = None) -> str:
    """Generate a CSRF token"""
    return csrf_protection.generate_token(user_id, session_id)

def validate_csrf_token(token: str, user_id: str = None, session_id: str = None) -> bool:
    """Validate a CSRF token"""
    return csrf_protection.validate_token(token, user_id, session_id)

def scan_dependencies(requirements_path: str = "requirements.txt") -> Dict[str, Any]:
    """Scan dependencies for vulnerabilities"""
    return dependency_scanner.scan_requirements_file(requirements_path)