"""JWT token generation and validation utilities with advanced security features"""

import jwt
import logging
import secrets
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Set, Tuple
from collections import defaultdict
from jose import JWTError, jwt as jose_jwt
import redis
import json

from app.config import settings

logger = logging.getLogger(__name__)

class TokenRevocationStore:
    """Manages revoked tokens using Redis or in-memory storage"""
    
    def __init__(self):
        self.redis_client = None
        self.in_memory_store: Set[str] = set()
        
        # Try to connect to Redis for distributed token revocation
        try:
            import redis
            redis_url = getattr(settings, 'redis_url', None)
            if redis_url:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()  # Test connection
                logger.info("Connected to Redis for token revocation")
        except Exception as e:
            logger.warning(f"Redis not available, using in-memory token revocation: {e}")
    
    def revoke_token(self, token_jti: str, expiration: datetime):
        """Revoke a token by its JTI (JWT ID)"""
        try:
            if self.redis_client:
                # Store in Redis with expiration
                ttl = int((expiration - datetime.now(timezone.utc)).total_seconds())
                if ttl > 0:
                    self.redis_client.setex(f"revoked:{token_jti}", ttl, "1")
            else:
                # Store in memory
                self.in_memory_store.add(token_jti)
        except Exception as e:
            logger.error(f"Error revoking token {token_jti}: {e}")
    
    def is_token_revoked(self, token_jti: str) -> bool:
        """Check if a token is revoked"""
        try:
            if self.redis_client:
                return bool(self.redis_client.exists(f"revoked:{token_jti}"))
            else:
                return token_jti in self.in_memory_store
        except Exception as e:
            logger.error(f"Error checking token revocation {token_jti}: {e}")
            return False
    
    def revoke_all_user_tokens(self, user_id: str):
        """Revoke all tokens for a specific user"""
        try:
            if self.redis_client:
                # Set a user revocation timestamp
                self.redis_client.set(f"user_revoked:{user_id}", int(time.time()))
            else:
                # For in-memory, we'll need to track this differently
                # This is a limitation of in-memory storage
                pass
        except Exception as e:
            logger.error(f"Error revoking all tokens for user {user_id}: {e}")
    
    def is_user_tokens_revoked(self, user_id: str, token_issued_at: datetime) -> bool:
        """Check if all user tokens issued before a certain time are revoked"""
        try:
            if self.redis_client:
                revoked_timestamp = self.redis_client.get(f"user_revoked:{user_id}")
                if revoked_timestamp:
                    revoked_time = int(revoked_timestamp)
                    token_time = int(token_issued_at.timestamp())
                    return token_time < revoked_time
            return False
        except Exception as e:
            logger.error(f"Error checking user token revocation {user_id}: {e}")
            return False

class JWTHandler:
    """Handles JWT token operations for authentication with advanced security features"""
    
    def __init__(self):
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expiration = timedelta(hours=getattr(settings, 'jwt_expiration_hours', 1))
        self.refresh_token_expiration = timedelta(days=getattr(settings, 'jwt_refresh_expiration_days', 7))
        self.clock_skew_tolerance = timedelta(seconds=getattr(settings, 'jwt_clock_skew_seconds', 30))
        
        # Token rotation and revocation
        self.revocation_store = TokenRevocationStore()
        self.rotation_threshold = timedelta(minutes=getattr(settings, 'jwt_rotation_threshold_minutes', 15))
        
        # Track token families for refresh token rotation
        self.token_families: Dict[str, Dict] = defaultdict(dict)
    
    def create_access_token(self, user_id: str, additional_claims: Optional[Dict[str, Any]] = None, 
                           token_family: Optional[str] = None) -> Tuple[str, str]:
        """Create a JWT access token for a user with enhanced security"""
        try:
            now = datetime.now(timezone.utc)
            expire = now + self.access_token_expiration
            
            # Generate unique token ID (JTI) for revocation tracking
            jti = secrets.token_urlsafe(32)
            
            # Create token payload with security enhancements
            payload = {
                "sub": user_id,  # Subject (user ID)
                "iat": int(now.timestamp()),  # Issued at (Unix timestamp)
                "exp": int(expire.timestamp()),  # Expiration time (Unix timestamp)
                "nbf": int(now.timestamp()),  # Not before (Unix timestamp)
                "jti": jti,  # JWT ID for revocation
                "type": "access",  # Token type
                "iss": getattr(settings, 'jwt_issuer', 'comicguess-api'),  # Issuer
                "aud": getattr(settings, 'jwt_audience', 'comicguess-app'),  # Audience
            }
            
            # Add token family for refresh token rotation
            if token_family:
                payload["fam"] = token_family
            
            # Add any additional claims
            if additional_claims:
                payload.update(additional_claims)
            
            # Generate token
            token = jose_jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Created access token for user: {user_id}, JTI: {jti}")
            return token, jti
            
        except Exception as e:
            logger.error(f"Error creating access token for user {user_id}: {e}")
            raise JWTError(f"Failed to create access token: {str(e)}")
    
    def create_refresh_token(self, user_id: str, token_family: Optional[str] = None) -> Tuple[str, str, str]:
        """Create a JWT refresh token for a user with token family tracking"""
        try:
            now = datetime.now(timezone.utc)
            expire = now + self.refresh_token_expiration
            
            # Generate unique token ID and family ID
            jti = secrets.token_urlsafe(32)
            if not token_family:
                token_family = secrets.token_urlsafe(16)
            
            payload = {
                "sub": user_id,
                "iat": int(now.timestamp()),
                "exp": int(expire.timestamp()),
                "nbf": int(now.timestamp()),
                "jti": jti,
                "type": "refresh",
                "fam": token_family,  # Token family for rotation tracking
                "iss": getattr(settings, 'jwt_issuer', 'comicguess-api'),
                "aud": getattr(settings, 'jwt_audience', 'comicguess-app'),
            }
            
            token = jose_jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            # Track token family
            self.token_families[token_family] = {
                "user_id": user_id,
                "created_at": now,
                "last_used": now,
                "rotation_count": 0
            }
            
            logger.info(f"Created refresh token for user: {user_id}, JTI: {jti}, Family: {token_family}")
            return token, jti, token_family
            
        except Exception as e:
            logger.error(f"Error creating refresh token for user {user_id}: {e}")
            raise JWTError(f"Failed to create refresh token: {str(e)}")
    
    def verify_token(self, token: str, expected_type: Optional[str] = None, 
                    allow_clock_skew: bool = True) -> Dict[str, Any]:
        """Verify and decode a JWT token with enhanced security checks"""
        try:
            # Decode token without verification first to check basic structure
            unverified_payload = jose_jwt.get_unverified_claims(token)
            
            # Check token type if specified
            if expected_type and unverified_payload.get("type") != expected_type:
                raise JWTError(f"Invalid token type. Expected: {expected_type}")
            
            # Check if token is revoked by JTI
            jti = unverified_payload.get("jti")
            if jti and self.revocation_store.is_token_revoked(jti):
                raise JWTError("Token has been revoked")
            
            # Check if all user tokens are revoked
            user_id = unverified_payload.get("sub")
            iat = unverified_payload.get("iat")
            if user_id and iat:
                iat_datetime = datetime.fromtimestamp(iat, tz=timezone.utc)
                if self.revocation_store.is_user_tokens_revoked(user_id, iat_datetime):
                    raise JWTError("All user tokens have been revoked")
            
            # Verify token signature and claims
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            }
            
            # Handle clock skew
            current_time = datetime.now(timezone.utc)
            if allow_clock_skew:
                # Allow some clock skew tolerance
                leeway = self.clock_skew_tolerance.total_seconds()
            else:
                leeway = 0
            
            payload = jose_jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options=options,
                audience=getattr(settings, 'jwt_audience', 'comicguess-app'),
                issuer=getattr(settings, 'jwt_issuer', 'comicguess-api'),
                leeway=leeway
            )
            
            # Additional security checks
            self._perform_additional_security_checks(payload, current_time)
            
            return payload
            
        except jose_jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: Token has expired")
            raise JWTError("Token has expired")
        except jose_jwt.JWTClaimsError as e:
            logger.warning(f"Token verification failed: Invalid claims - {e}")
            raise JWTError(f"Invalid token claims: {str(e)}")
        except jose_jwt.JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            raise JWTError(f"Invalid token: {str(e)}")
        except JWTError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}")
            raise JWTError(f"Token verification failed: {str(e)}")
    
    def _perform_additional_security_checks(self, payload: Dict[str, Any], current_time: datetime):
        """Perform additional security checks on token payload"""
        # Check not-before claim with clock skew tolerance
        nbf = payload.get("nbf")
        if nbf:
            nbf_datetime = datetime.fromtimestamp(nbf, tz=timezone.utc)
            if current_time < (nbf_datetime - self.clock_skew_tolerance):
                raise JWTError("Token not yet valid")
        
        # Check issued-at claim for reasonable time
        iat = payload.get("iat")
        if iat:
            iat_datetime = datetime.fromtimestamp(iat, tz=timezone.utc)
            # Token shouldn't be issued too far in the future
            if iat_datetime > (current_time + self.clock_skew_tolerance):
                raise JWTError("Token issued in the future")
            
            # Token shouldn't be too old (prevent replay attacks)
            max_age = timedelta(days=30)  # Maximum token age
            if current_time > (iat_datetime + max_age):
                raise JWTError("Token is too old")
        
        # Validate token family for refresh tokens
        if payload.get("type") == "refresh":
            token_family = payload.get("fam")
            if token_family and token_family in self.token_families:
                family_info = self.token_families[token_family]
                # Update last used time
                family_info["last_used"] = current_time
    
    def get_user_id_from_token(self, token: str) -> str:
        """Extract user ID from a valid token"""
        try:
            payload = self.verify_token(token)
            user_id = payload.get("sub")
            
            if not user_id:
                raise JWTError("Token does not contain user ID")
            
            return user_id
            
        except JWTError:
            raise
        except Exception as e:
            logger.error(f"Error extracting user ID from token: {e}")
            raise JWTError(f"Failed to extract user ID: {str(e)}")
    
    def is_token_expired(self, token: str) -> bool:
        """Check if a token is expired without raising an exception"""
        try:
            self.verify_token(token)
            return False
        except JWTError as e:
            if "expired" in str(e).lower():
                return True
            return False
        except Exception:
            return True
    
    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """Get the expiration time of a token"""
        try:
            payload = self.verify_token(token)
            exp = payload.get("exp")
            
            if exp:
                return datetime.fromtimestamp(exp, tz=timezone.utc)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting token expiration: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str, rotate_refresh: bool = True) -> Dict[str, str]:
        """Create a new access token using a valid refresh token with rotation"""
        try:
            # Verify refresh token
            payload = self.verify_token(refresh_token, expected_type="refresh")
            
            # Extract user ID and token info
            user_id = payload.get("sub")
            if not user_id:
                raise JWTError("Refresh token does not contain user ID")
            
            old_jti = payload.get("jti")
            token_family = payload.get("fam")
            
            # Check if refresh token should be rotated
            iat = payload.get("iat")
            if iat and rotate_refresh:
                iat_datetime = datetime.fromtimestamp(iat, tz=timezone.utc)
                time_since_issued = datetime.now(timezone.utc) - iat_datetime
                
                if time_since_issued > self.rotation_threshold:
                    # Rotate refresh token
                    old_exp = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
                    
                    # Revoke old refresh token
                    if old_jti:
                        self.revocation_store.revoke_token(old_jti, old_exp)
                    
                    # Create new token pair
                    new_access_token, access_jti = self.create_access_token(user_id, token_family=token_family)
                    new_refresh_token, refresh_jti, new_family = self.create_refresh_token(user_id, token_family)
                    
                    # Update token family rotation count
                    if token_family in self.token_families:
                        self.token_families[token_family]["rotation_count"] += 1
                    
                    logger.info(f"Rotated refresh token for user: {user_id}")
                    
                    return {
                        "access_token": new_access_token,
                        "refresh_token": new_refresh_token,
                        "token_type": "bearer",
                        "rotated": True
                    }
            
            # Just create new access token without rotation
            new_access_token, access_jti = self.create_access_token(user_id, token_family=token_family)
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer",
                "rotated": False
            }
            
        except JWTError:
            raise
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            raise JWTError(f"Failed to refresh token: {str(e)}")
    
    def revoke_token(self, token: str):
        """Revoke a specific token"""
        try:
            # Get token info without full verification (in case it's expired)
            unverified_payload = jose_jwt.get_unverified_claims(token)
            jti = unverified_payload.get("jti")
            exp = unverified_payload.get("exp")
            
            if jti and exp:
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                self.revocation_store.revoke_token(jti, exp_datetime)
                logger.info(f"Revoked token with JTI: {jti}")
            
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            raise JWTError(f"Failed to revoke token: {str(e)}")
    
    def revoke_all_user_tokens(self, user_id: str):
        """Revoke all tokens for a specific user"""
        try:
            self.revocation_store.revoke_all_user_tokens(user_id)
            
            # Also revoke all token families for this user
            families_to_remove = []
            for family_id, family_info in self.token_families.items():
                if family_info.get("user_id") == user_id:
                    families_to_remove.append(family_id)
            
            for family_id in families_to_remove:
                del self.token_families[family_id]
            
            logger.info(f"Revoked all tokens for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Error revoking all user tokens: {e}")
            raise JWTError(f"Failed to revoke user tokens: {str(e)}")
    
    def logout_user(self, access_token: str, refresh_token: Optional[str] = None):
        """Securely logout user by revoking tokens"""
        try:
            # Revoke access token
            self.revoke_token(access_token)
            
            # Revoke refresh token if provided
            if refresh_token:
                self.revoke_token(refresh_token)
                
                # Also revoke the entire token family
                try:
                    payload = jose_jwt.get_unverified_claims(refresh_token)
                    token_family = payload.get("fam")
                    if token_family and token_family in self.token_families:
                        del self.token_families[token_family]
                except Exception:
                    pass  # Continue even if family cleanup fails
            
            logger.info("User logged out successfully")
            
        except Exception as e:
            logger.error(f"Error during logout: {e}")
            raise JWTError(f"Failed to logout: {str(e)}")
    
    def validate_token_security(self, token: str) -> Dict[str, Any]:
        """Validate token security and return security metrics"""
        try:
            payload = self.verify_token(token)
            
            iat = payload.get("iat")
            exp = payload.get("exp")
            current_time = datetime.now(timezone.utc)
            
            security_info = {
                "valid": True,
                "token_type": payload.get("type"),
                "user_id": payload.get("sub"),
                "jti": payload.get("jti"),
                "issued_at": datetime.fromtimestamp(iat, tz=timezone.utc) if iat else None,
                "expires_at": datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None,
                "time_to_expiry": None,
                "age": None,
                "is_near_expiry": False,
                "should_refresh": False
            }
            
            if iat:
                security_info["age"] = current_time - datetime.fromtimestamp(iat, tz=timezone.utc)
            
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                security_info["time_to_expiry"] = exp_datetime - current_time
                
                # Check if token is near expiry (within 15 minutes)
                if security_info["time_to_expiry"] < timedelta(minutes=15):
                    security_info["is_near_expiry"] = True
                    security_info["should_refresh"] = True
            
            return security_info
            
        except JWTError as e:
            return {
                "valid": False,
                "error": str(e),
                "should_refresh": True
            }
        except Exception as e:
            logger.error(f"Error validating token security: {e}")
            return {
                "valid": False,
                "error": "Token validation failed",
                "should_refresh": True
            }
    
    def create_token_pair(self, user_id: str, additional_claims: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Create both access and refresh tokens for a user with enhanced security"""
        try:
            # Create refresh token first to get token family
            refresh_token, refresh_jti, token_family = self.create_refresh_token(user_id)
            
            # Create access token with same token family
            access_token, access_jti = self.create_access_token(user_id, additional_claims, token_family)
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": int(self.access_token_expiration.total_seconds()),
                "refresh_expires_in": int(self.refresh_token_expiration.total_seconds()),
                "token_family": token_family
            }
            
        except Exception as e:
            logger.error(f"Error creating token pair for user {user_id}: {e}")
            raise JWTError(f"Failed to create token pair: {str(e)}")

# Global JWT handler instance
jwt_handler = JWTHandler()

# Convenience functions
def create_access_token(user_id: str, additional_claims: Optional[Dict[str, Any]] = None, 
                       token_family: Optional[str] = None) -> Tuple[str, str]:
    """Create an access token for a user"""
    return jwt_handler.create_access_token(user_id, additional_claims, token_family)

def create_refresh_token(user_id: str, token_family: Optional[str] = None) -> Tuple[str, str, str]:
    """Create a refresh token for a user"""
    return jwt_handler.create_refresh_token(user_id, token_family)

def verify_token(token: str, expected_type: Optional[str] = None, 
                allow_clock_skew: bool = True) -> Dict[str, Any]:
    """Verify and decode a JWT token"""
    return jwt_handler.verify_token(token, expected_type, allow_clock_skew)

def get_user_id_from_token(token: str) -> str:
    """Extract user ID from a valid token"""
    return jwt_handler.get_user_id_from_token(token)

def create_token_pair(user_id: str, additional_claims: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Create both access and refresh tokens for a user"""
    return jwt_handler.create_token_pair(user_id, additional_claims)

def refresh_access_token(refresh_token: str, rotate_refresh: bool = True) -> Dict[str, str]:
    """Create a new access token using a valid refresh token"""
    return jwt_handler.refresh_access_token(refresh_token, rotate_refresh)

def revoke_token(token: str):
    """Revoke a specific token"""
    return jwt_handler.revoke_token(token)

def revoke_all_user_tokens(user_id: str):
    """Revoke all tokens for a specific user"""
    return jwt_handler.revoke_all_user_tokens(user_id)

def logout_user(access_token: str, refresh_token: Optional[str] = None):
    """Securely logout user by revoking tokens"""
    return jwt_handler.logout_user(access_token, refresh_token)

def validate_token_security(token: str) -> Dict[str, Any]:
    """Validate token security and return security metrics"""
    return jwt_handler.validate_token_security(token)