"""User session management utilities with advanced security features"""

import logging
import secrets
import hashlib
from typing import Optional, Dict, Any, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

from app.auth.jwt_handler import jwt_handler, JWTError
from app.models.user import User

logger = logging.getLogger(__name__)

@dataclass
class SessionSecurityInfo:
    """Security information for a session"""
    ip_address: str
    user_agent: str
    device_fingerprint: Optional[str] = None
    location: Optional[str] = None
    is_suspicious: bool = False
    risk_score: float = 0.0
    
@dataclass
class UserSession:
    """Represents an active user session with enhanced security"""
    user_id: str
    username: str
    email: str
    created_at: datetime
    last_activity: datetime
    access_token: str
    refresh_token: Optional[str] = None
    session_id: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    token_family: Optional[str] = None
    security_info: Optional[SessionSecurityInfo] = None
    login_attempts: int = 0
    max_idle_time: timedelta = field(default_factory=lambda: timedelta(hours=24))
    absolute_timeout: timedelta = field(default_factory=lambda: timedelta(days=7))
    
    def is_expired(self) -> bool:
        """Check if the session is expired"""
        try:
            # Check token expiration
            if jwt_handler.is_token_expired(self.access_token):
                return True
            
            # Check idle timeout
            if self.is_idle_timeout():
                return True
            
            # Check absolute timeout
            if self.is_absolute_timeout():
                return True
            
            return False
        except Exception:
            return True
    
    def is_idle_timeout(self) -> bool:
        """Check if session has exceeded idle timeout"""
        idle_time = datetime.now(timezone.utc) - self.last_activity
        return idle_time > self.max_idle_time
    
    def is_absolute_timeout(self) -> bool:
        """Check if session has exceeded absolute timeout"""
        session_age = datetime.now(timezone.utc) - self.created_at
        return session_age > self.absolute_timeout
    
    def update_activity(self, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> None:
        """Update the last activity timestamp and security info"""
        self.last_activity = datetime.now(timezone.utc)
        
        # Update security info if provided
        if ip_address or user_agent:
            if not self.security_info:
                self.security_info = SessionSecurityInfo(
                    ip_address=ip_address or "unknown",
                    user_agent=user_agent or "unknown"
                )
            else:
                # Check for suspicious activity (IP or user agent change)
                if ip_address and ip_address != self.security_info.ip_address:
                    logger.warning(f"IP address change detected for user {self.user_id}: {self.security_info.ip_address} -> {ip_address}")
                    self.security_info.is_suspicious = True
                    self.security_info.risk_score += 0.3
                
                if user_agent and user_agent != self.security_info.user_agent:
                    logger.warning(f"User agent change detected for user {self.user_id}")
                    self.security_info.is_suspicious = True
                    self.security_info.risk_score += 0.2
                
                # Update current values
                if ip_address:
                    self.security_info.ip_address = ip_address
                if user_agent:
                    self.security_info.user_agent = user_agent
    
    def calculate_risk_score(self) -> float:
        """Calculate session risk score based on various factors"""
        risk_score = 0.0
        
        if self.security_info:
            # Base risk from security info
            risk_score += self.security_info.risk_score
            
            # Risk from multiple login attempts
            if self.login_attempts > 3:
                risk_score += 0.2 * (self.login_attempts - 3)
            
            # Risk from session age
            session_age = datetime.now(timezone.utc) - self.created_at
            if session_age > timedelta(days=3):
                risk_score += 0.1
            
            # Risk from idle time
            idle_time = datetime.now(timezone.utc) - self.last_activity
            if idle_time > timedelta(hours=12):
                risk_score += 0.1
        
        return min(risk_score, 1.0)  # Cap at 1.0
    
    def is_high_risk(self) -> bool:
        """Check if session is considered high risk"""
        return self.calculate_risk_score() > 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_family": self.token_family,
            "risk_score": self.calculate_risk_score(),
            "is_high_risk": self.is_high_risk(),
            "security_info": {
                "ip_address": self.security_info.ip_address,
                "user_agent": self.security_info.user_agent,
                "is_suspicious": self.security_info.is_suspicious,
                "risk_score": self.security_info.risk_score
            } if self.security_info else None
        }

class SessionManager:
    """Manages user sessions and authentication state with advanced security"""
    
    def __init__(self):
        # In a production environment, you might want to use Redis or another
        # persistent storage for sessions. For now, we'll use in-memory storage.
        self._active_sessions: Dict[str, UserSession] = {}
        self._session_by_id: Dict[str, UserSession] = {}
        self._failed_login_attempts: Dict[str, Dict] = defaultdict(dict)
        self._concurrent_session_limit = 5  # Max concurrent sessions per user
        self._session_cleanup_interval = timedelta(hours=1)
    
    def create_session(self, user: User, ip_address: Optional[str] = None, 
                      user_agent: Optional[str] = None, device_fingerprint: Optional[str] = None) -> UserSession:
        """Create a new user session with enhanced security"""
        try:
            # Check concurrent session limit
            existing_sessions = self._get_user_sessions(user.id)
            if len(existing_sessions) >= self._concurrent_session_limit:
                # Remove oldest session
                oldest_session = min(existing_sessions, key=lambda s: s.created_at)
                self._remove_session(oldest_session)
                logger.info(f"Removed oldest session for user {user.id} due to concurrent limit")
            
            # Create JWT tokens
            token_pair = jwt_handler.create_token_pair(
                user.id,
                additional_claims={
                    "username": user.username,
                    "email": user.email
                }
            )
            
            # Create security info
            security_info = SessionSecurityInfo(
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                device_fingerprint=device_fingerprint
            )
            
            # Create session object
            session = UserSession(
                user_id=user.id,
                username=user.username,
                email=user.email,
                created_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                access_token=token_pair["access_token"],
                refresh_token=token_pair["refresh_token"],
                token_family=token_pair.get("token_family"),
                security_info=security_info
            )
            
            # Store session
            self._active_sessions[user.id] = session
            self._session_by_id[session.session_id] = session
            
            # Clear failed login attempts
            if user.id in self._failed_login_attempts:
                del self._failed_login_attempts[user.id]
            
            logger.info(f"Created session for user: {user.id}, session_id: {session.session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating session for user {user.id}: {e}")
            raise
    
    def _get_user_sessions(self, user_id: str) -> list[UserSession]:
        """Get all active sessions for a user"""
        return [session for session in self._active_sessions.values() 
                if session.user_id == user_id and not session.is_expired()]
    
    def _remove_session(self, session: UserSession):
        """Remove a session from storage"""
        if session.user_id in self._active_sessions:
            del self._active_sessions[session.user_id]
        if session.session_id in self._session_by_id:
            del self._session_by_id[session.session_id]
    
    def get_session(self, user_id: str) -> Optional[UserSession]:
        """Get an active session by user ID"""
        session = self._active_sessions.get(user_id)
        
        if session and not session.is_expired():
            session.update_activity()
            return session
        elif session:
            # Session is expired, remove it
            self.invalidate_session(user_id)
        
        return None
    
    def get_session_by_token(self, access_token: str) -> Optional[UserSession]:
        """Get a session by access token"""
        try:
            # Verify token and extract user ID
            user_id = jwt_handler.get_user_id_from_token(access_token)
            
            # Get session
            session = self.get_session(user_id)
            
            # Verify the token matches the stored session
            if session and session.access_token == access_token:
                return session
            
            return None
            
        except JWTError:
            return None
        except Exception as e:
            logger.error(f"Error getting session by token: {e}")
            return None
    
    def refresh_session(self, user_id: str, refresh_token: str, 
                       ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> Optional[UserSession]:
        """Refresh a user session using refresh token with enhanced security"""
        try:
            session = self._active_sessions.get(user_id)
            
            if not session or session.refresh_token != refresh_token:
                logger.warning(f"Invalid refresh attempt for user: {user_id}")
                return None
            
            # Check if session is high risk
            if session.is_high_risk():
                logger.warning(f"Blocking refresh for high-risk session: {user_id}")
                self.invalidate_session(user_id)
                return None
            
            # Refresh tokens (may include rotation)
            token_result = jwt_handler.refresh_access_token(refresh_token, rotate_refresh=True)
            
            # Update session with new tokens
            session.access_token = token_result["access_token"]
            if token_result.get("rotated") and "refresh_token" in token_result:
                session.refresh_token = token_result["refresh_token"]
            
            # Update activity and security info
            session.update_activity(ip_address, user_agent)
            
            logger.info(f"Refreshed session for user: {user_id}, rotated: {token_result.get('rotated', False)}")
            return session
            
        except JWTError as e:
            logger.warning(f"Failed to refresh session for user {user_id}: {e}")
            # Invalidate session on JWT errors
            self.invalidate_session(user_id)
            return None
        except Exception as e:
            logger.error(f"Error refreshing session for user {user_id}: {e}")
            return None
    
    def invalidate_session(self, user_id: str) -> bool:
        """Invalidate a user session"""
        try:
            session = self._active_sessions.get(user_id)
            if session:
                # Revoke JWT tokens
                try:
                    jwt_handler.logout_user(session.access_token, session.refresh_token)
                except Exception as e:
                    logger.warning(f"Error revoking tokens during session invalidation: {e}")
                
                # Remove from storage
                self._remove_session(session)
                logger.info(f"Invalidated session for user: {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error invalidating session for user {user_id}: {e}")
            return False
    
    def invalidate_session_by_id(self, session_id: str) -> bool:
        """Invalidate a session by session ID"""
        try:
            session = self._session_by_id.get(session_id)
            if session:
                return self.invalidate_session(session.user_id)
            return False
        except Exception as e:
            logger.error(f"Error invalidating session by ID {session_id}: {e}")
            return False
    
    def invalidate_all_sessions(self, user_id: str) -> bool:
        """Invalidate all sessions for a user (useful for logout from all devices)"""
        try:
            # Revoke all user tokens
            jwt_handler.revoke_all_user_tokens(user_id)
            
            # Remove all user sessions
            sessions_to_remove = [s for s in self._active_sessions.values() if s.user_id == user_id]
            for session in sessions_to_remove:
                self._remove_session(session)
            
            logger.info(f"Invalidated all sessions for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating all sessions for user {user_id}: {e}")
            return False
    
    def record_failed_login(self, user_id: str, ip_address: str):
        """Record a failed login attempt"""
        current_time = datetime.now(timezone.utc)
        
        if user_id not in self._failed_login_attempts:
            self._failed_login_attempts[user_id] = {
                "count": 0,
                "last_attempt": current_time,
                "ip_addresses": set()
            }
        
        attempt_info = self._failed_login_attempts[user_id]
        attempt_info["count"] += 1
        attempt_info["last_attempt"] = current_time
        attempt_info["ip_addresses"].add(ip_address)
        
        logger.warning(f"Failed login attempt for user {user_id} from IP {ip_address}. Total attempts: {attempt_info['count']}")
    
    def is_account_locked(self, user_id: str) -> bool:
        """Check if account is locked due to failed login attempts"""
        if user_id not in self._failed_login_attempts:
            return False
        
        attempt_info = self._failed_login_attempts[user_id]
        
        # Lock account after 5 failed attempts within 15 minutes
        if attempt_info["count"] >= 5:
            time_since_last = datetime.now(timezone.utc) - attempt_info["last_attempt"]
            if time_since_last < timedelta(minutes=15):
                return True
        
        return False
    
    def get_session_security_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get security information for a session"""
        session = self.get_session(user_id)
        if session and session.security_info:
            return {
                "session_id": session.session_id,
                "ip_address": session.security_info.ip_address,
                "user_agent": session.security_info.user_agent,
                "device_fingerprint": session.security_info.device_fingerprint,
                "is_suspicious": session.security_info.is_suspicious,
                "risk_score": session.calculate_risk_score(),
                "is_high_risk": session.is_high_risk(),
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            }
        return None
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count of cleaned sessions"""
        try:
            expired_sessions = []
            
            for user_id, session in self._active_sessions.items():
                if session.is_expired():
                    expired_sessions.append(user_id)
            
            for user_id in expired_sessions:
                del self._active_sessions[user_id]
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
            
            return len(expired_sessions)
            
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    def get_active_session_count(self) -> int:
        """Get the number of active sessions"""
        return len(self._active_sessions)
    
    def is_user_logged_in(self, user_id: str) -> bool:
        """Check if a user has an active session"""
        session = self.get_session(user_id)
        return session is not None
    
    def get_session_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get session information for a user"""
        session = self.get_session(user_id)
        
        if session:
            return {
                "user_id": session.user_id,
                "username": session.username,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "is_expired": session.is_expired()
            }
        
        return None

# Global session manager instance
session_manager = SessionManager()

# Convenience functions
def create_session(user: User) -> UserSession:
    """Create a new user session"""
    return session_manager.create_session(user)

def get_session(user_id: str) -> Optional[UserSession]:
    """Get an active session by user ID"""
    return session_manager.get_session(user_id)

def get_session_by_token(access_token: str) -> Optional[UserSession]:
    """Get a session by access token"""
    return session_manager.get_session_by_token(access_token)

def refresh_session(user_id: str, refresh_token: str) -> Optional[UserSession]:
    """Refresh a user session"""
    return session_manager.refresh_session(user_id, refresh_token)

def invalidate_session(user_id: str) -> bool:
    """Invalidate a user session"""
    return session_manager.invalidate_session(user_id)

def is_user_logged_in(user_id: str) -> bool:
    """Check if a user has an active session"""
    return session_manager.is_user_logged_in(user_id)