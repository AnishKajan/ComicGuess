"""FastAPI authentication middleware and dependencies"""

import logging
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.jwt_handler import JWTError
from app.auth.session import session_manager, UserSession
from app.repositories.user_repository import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)

class AuthenticationError(HTTPException):
    """Custom authentication error"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class AuthorizationError(HTTPException):
    """Custom authorization error"""
    def __init__(self, detail: str = "Access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )

async def get_current_user_session(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> UserSession:
    """
    Dependency to get the current authenticated user session.
    Raises HTTPException if authentication fails.
    """
    if not credentials:
        raise AuthenticationError("Missing authentication token")
    
    try:
        # Get session by token
        session = session_manager.get_session_by_token(credentials.credentials)
        
        if not session:
            raise AuthenticationError("Invalid or expired token")
        
        return session
        
    except JWTError as e:
        logger.warning(f"JWT authentication failed: {e}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise AuthenticationError("Authentication failed")

async def get_current_user(
    session: Annotated[UserSession, Depends(get_current_user_session)]
) -> User:
    """
    Dependency to get the current authenticated user.
    Requires a valid session.
    """
    try:
        # Get user from repository
        user_repo = UserRepository()
        user = await user_repo.get_user_by_id(session.user_id)
        
        if not user:
            # User was deleted but session still exists
            session_manager.invalidate_session(session.user_id)
            raise AuthenticationError("User not found")
        
        return user
        
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise AuthenticationError("Failed to get user information")

async def get_optional_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> Optional[User]:
    """
    Dependency to optionally get the current authenticated user.
    Returns None if no valid authentication is provided.
    """
    if not credentials:
        return None
    
    try:
        session = session_manager.get_session_by_token(credentials.credentials)
        
        if not session:
            return None
        
        # Get user from repository
        user_repo = UserRepository()
        user = await user_repo.get_user_by_id(session.user_id)
        
        return user
        
    except Exception as e:
        logger.debug(f"Optional authentication failed: {e}")
        return None

async def require_user_access(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Dependency to ensure the current user can access a specific user's data.
    Checks if the authenticated user matches the target user.
    """
    if current_user.id != user_id:
        raise AuthorizationError("Access denied: Cannot access other user's data")
    return current_user

class AuthMiddleware:
    """Authentication middleware for FastAPI"""
    
    def __init__(self):
        self.user_repo = UserRepository()
    
    async def authenticate_request(self, request: Request) -> Optional[User]:
        """
        Authenticate a request and return the user if valid.
        This can be used in middleware to add user context to requests.
        """
        try:
            # Get authorization header
            auth_header = request.headers.get("Authorization")
            
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
            
            # Extract token
            token = auth_header.split(" ")[1]
            
            # Get session
            session = session_manager.get_session_by_token(token)
            
            if not session:
                return None
            
            # Get user
            user = await self.user_repo.get_user_by_id(session.user_id)
            
            return user
            
        except Exception as e:
            logger.debug(f"Request authentication failed: {e}")
            return None
    
    async def require_authentication(self, request: Request) -> User:
        """
        Require authentication for a request.
        Raises HTTPException if authentication fails.
        """
        user = await self.authenticate_request(request)
        
        if not user:
            raise AuthenticationError("Authentication required")
        
        return user

# Global middleware instance
auth_middleware = AuthMiddleware()

# Rate limiting helpers (can be expanded later)
class RateLimitConfig:
    """Configuration for rate limiting"""
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute

def create_rate_limiter(config: RateLimitConfig):
    """
    Create a rate limiter dependency.
    This is a placeholder for future rate limiting implementation.
    """
    async def rate_limit_check(request: Request):
        # TODO: Implement actual rate limiting logic
        # For now, this is a no-op
        pass
    
    return rate_limit_check

# Common rate limit configurations
standard_rate_limit = create_rate_limiter(RateLimitConfig(requests_per_minute=60))
strict_rate_limit = create_rate_limiter(RateLimitConfig(requests_per_minute=10))

# Security headers middleware
async def add_security_headers(request: Request, call_next):
    """
    Middleware to add security headers to responses.
    This should be added to the FastAPI app.
    """
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response