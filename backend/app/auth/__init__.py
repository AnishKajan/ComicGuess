# Authentication utilities

from .jwt_handler import (
    JWTHandler,
    jwt_handler,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_user_id_from_token,
    create_token_pair,
    refresh_access_token
)

from .session import (
    SessionManager,
    UserSession,
    session_manager,
    create_session,
    get_session,
    get_session_by_token,
    refresh_session,
    invalidate_session,
    is_user_logged_in
)

from .middleware import (
    AuthenticationError,
    AuthorizationError,
    get_current_user_session,
    get_current_user,
    get_optional_current_user,
    require_user_access,
    AuthMiddleware,
    auth_middleware,
    add_security_headers
)

__all__ = [
    # JWT Handler
    "JWTHandler",
    "jwt_handler", 
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "get_user_id_from_token",
    "create_token_pair",
    "refresh_access_token",
    
    # Session Management
    "SessionManager",
    "UserSession",
    "session_manager",
    "create_session",
    "get_session",
    "get_session_by_token", 
    "refresh_session",
    "invalidate_session",
    "is_user_logged_in",
    
    # Middleware
    "AuthenticationError",
    "AuthorizationError",
    "get_current_user_session",
    "get_current_user",
    "get_optional_current_user",
    "require_user_access",
    "AuthMiddleware",
    "auth_middleware",
    "add_security_headers"
]