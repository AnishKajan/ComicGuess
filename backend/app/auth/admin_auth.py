"""Admin authentication and authorization middleware"""

import logging
from typing import List, Annotated, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer

from app.auth.middleware import get_current_user_session
from app.auth.session import UserSession
from app.models.admin import AdminUser, Permission, AuditLogEntry
# AdminRepository is defined below in this file

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AdminAuthError(HTTPException):
    """Admin authentication/authorization error"""
    def __init__(self, detail: str = "Admin access required"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class AdminRepository:
    """Repository for admin user management"""
    
    def __init__(self):
        # This would typically connect to your database
        # For now, we'll use a simple in-memory store for demo
        self._admin_users = {}
        self._audit_logs = []
    
    async def get_admin_by_user_id(self, user_id: str) -> Optional[AdminUser]:
        """Get admin user by regular user ID"""
        return self._admin_users.get(user_id)
    
    async def create_admin_user(self, admin_user: AdminUser) -> AdminUser:
        """Create a new admin user"""
        self._admin_users[admin_user.id] = admin_user
        return admin_user
    
    async def update_admin_user(self, admin_user: AdminUser) -> AdminUser:
        """Update an admin user"""
        self._admin_users[admin_user.id] = admin_user
        return admin_user
    
    async def log_admin_action(self, audit_entry: AuditLogEntry) -> None:
        """Log an admin action"""
        self._audit_logs.append(audit_entry)
        logger.info(f"Admin action logged: {audit_entry.action} by {audit_entry.admin_username}")
    
    async def get_audit_logs(self, limit: int = 100, offset: int = 0) -> List[AuditLogEntry]:
        """Get audit logs with pagination"""
        return self._audit_logs[offset:offset + limit]


# Global admin repository instance
admin_repo = AdminRepository()


async def get_current_admin_user(
    session: Annotated[UserSession, Depends(get_current_user_session)]
) -> AdminUser:
    """
    Dependency to get the current authenticated admin user.
    Raises HTTPException if user is not an admin.
    """
    try:
        # Get admin user data
        admin_user = await admin_repo.get_admin_by_user_id(session.user_id)
        
        if not admin_user:
            raise AdminAuthError("Admin access required")
        
        if not admin_user.is_active:
            raise AdminAuthError("Admin account is inactive")
        
        return admin_user
        
    except AdminAuthError:
        raise
    except Exception as e:
        logger.error(f"Error getting admin user: {e}")
        raise AdminAuthError("Failed to verify admin access")


def require_permission(permission: Permission):
    """
    Dependency factory to require a specific permission.
    Returns a dependency that checks if the current admin has the required permission.
    """
    async def permission_check(
        admin_user: Annotated[AdminUser, Depends(get_current_admin_user)]
    ) -> AdminUser:
        if not admin_user.has_permission(permission):
            raise AdminAuthError(f"Permission required: {permission.value}")
        return admin_user
    
    return permission_check


def require_any_permission(permissions: List[Permission]):
    """
    Dependency factory to require any of the specified permissions.
    """
    async def permission_check(
        admin_user: Annotated[AdminUser, Depends(get_current_admin_user)]
    ) -> AdminUser:
        if not admin_user.has_any_permission(permissions):
            perm_names = [p.value for p in permissions]
            raise AdminAuthError(f"One of these permissions required: {', '.join(perm_names)}")
        return admin_user
    
    return permission_check


class AdminAuditLogger:
    """Helper class for logging admin actions"""
    
    def __init__(self):
        self.repo = admin_repo
    
    async def log_action(
        self,
        admin_user: AdminUser,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        request: Optional[Request] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Log an admin action"""
        audit_entry = AuditLogEntry(
            admin_id=admin_user.id,
            admin_username=admin_user.username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            success=success,
            error_message=error_message
        )
        
        await self.repo.log_admin_action(audit_entry)


# Global audit logger instance
audit_logger = AdminAuditLogger()


def audit_action(action: str, resource_type: str):
    """
    Decorator to automatically audit admin actions.
    Usage: @audit_action("create_puzzle", "puzzle")
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract admin_user and request from kwargs if present
            admin_user = kwargs.get('admin_user')
            request = kwargs.get('request')
            
            try:
                result = await func(*args, **kwargs)
                
                # Log successful action
                if admin_user:
                    await audit_logger.log_action(
                        admin_user=admin_user,
                        action=action,
                        resource_type=resource_type,
                        request=request,
                        success=True
                    )
                
                return result
                
            except Exception as e:
                # Log failed action
                if admin_user:
                    await audit_logger.log_action(
                        admin_user=admin_user,
                        action=action,
                        resource_type=resource_type,
                        request=request,
                        success=False,
                        error_message=str(e)
                    )
                raise
        
        return wrapper
    return decorator


# Common permission dependencies
require_view_users = require_permission(Permission.VIEW_USERS)
require_edit_users = require_permission(Permission.EDIT_USERS)
require_view_puzzles = require_permission(Permission.VIEW_PUZZLES)
require_create_puzzles = require_permission(Permission.CREATE_PUZZLES)
require_edit_puzzles = require_permission(Permission.EDIT_PUZZLES)
require_schedule_puzzles = require_permission(Permission.SCHEDULE_PUZZLES)
require_hotfix_puzzles = require_permission(Permission.HOTFIX_PUZZLES)
require_view_system_stats = require_permission(Permission.VIEW_SYSTEM_STATS)
require_view_audit_logs = require_permission(Permission.VIEW_AUDIT_LOGS)
require_manage_system = require_permission(Permission.MANAGE_SYSTEM)

# Combined permission dependencies
require_puzzle_management = require_any_permission([
    Permission.CREATE_PUZZLES,
    Permission.EDIT_PUZZLES,
    Permission.SCHEDULE_PUZZLES
])

require_content_management = require_any_permission([
    Permission.UPLOAD_IMAGES,
    Permission.MANAGE_ALIASES,
    Permission.MODERATE_CONTENT
])