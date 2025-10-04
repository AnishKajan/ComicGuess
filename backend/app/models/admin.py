"""Admin-specific models and RBAC definitions"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class AdminRole(str, Enum):
    """Admin role definitions"""
    SUPER_ADMIN = "super_admin"
    CONTENT_ADMIN = "content_admin"
    PUZZLE_ADMIN = "puzzle_admin"
    USER_ADMIN = "user_admin"
    READ_ONLY = "read_only"


class Permission(str, Enum):
    """Permission definitions"""
    # User management
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    
    # Puzzle management
    VIEW_PUZZLES = "view_puzzles"
    CREATE_PUZZLES = "create_puzzles"
    EDIT_PUZZLES = "edit_puzzles"
    DELETE_PUZZLES = "delete_puzzles"
    SCHEDULE_PUZZLES = "schedule_puzzles"
    
    # Content management
    VIEW_CONTENT = "view_content"
    UPLOAD_IMAGES = "upload_images"
    MANAGE_ALIASES = "manage_aliases"
    MODERATE_CONTENT = "moderate_content"
    
    # System management
    VIEW_SYSTEM_STATS = "view_system_stats"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_SYSTEM = "manage_system"
    
    # Emergency actions
    HOTFIX_PUZZLES = "hotfix_puzzles"
    EMERGENCY_ACTIONS = "emergency_actions"


# Role-Permission mapping
ROLE_PERMISSIONS: Dict[AdminRole, List[Permission]] = {
    AdminRole.SUPER_ADMIN: list(Permission),  # All permissions
    
    AdminRole.CONTENT_ADMIN: [
        Permission.VIEW_CONTENT,
        Permission.UPLOAD_IMAGES,
        Permission.MANAGE_ALIASES,
        Permission.MODERATE_CONTENT,
        Permission.VIEW_PUZZLES,
        Permission.CREATE_PUZZLES,
        Permission.EDIT_PUZZLES,
        Permission.VIEW_SYSTEM_STATS,
        Permission.VIEW_AUDIT_LOGS,
    ],
    
    AdminRole.PUZZLE_ADMIN: [
        Permission.VIEW_PUZZLES,
        Permission.CREATE_PUZZLES,
        Permission.EDIT_PUZZLES,
        Permission.SCHEDULE_PUZZLES,
        Permission.HOTFIX_PUZZLES,
        Permission.VIEW_SYSTEM_STATS,
        Permission.VIEW_AUDIT_LOGS,
    ],
    
    AdminRole.USER_ADMIN: [
        Permission.VIEW_USERS,
        Permission.EDIT_USERS,
        Permission.VIEW_SYSTEM_STATS,
        Permission.VIEW_AUDIT_LOGS,
    ],
    
    AdminRole.READ_ONLY: [
        Permission.VIEW_USERS,
        Permission.VIEW_PUZZLES,
        Permission.VIEW_CONTENT,
        Permission.VIEW_SYSTEM_STATS,
        Permission.VIEW_AUDIT_LOGS,
    ],
}


class AdminUser(BaseModel):
    """Extended user model with admin capabilities"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(...)
    roles: List[AdminRole] = Field(default_factory=list)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    created_by: Optional[str] = None  # ID of admin who created this user
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission"""
        if not self.is_active:
            return False
        
        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, []):
                return True
        return False
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(self.has_permission(perm) for perm in permissions)
    
    def get_all_permissions(self) -> List[Permission]:
        """Get all permissions for this user"""
        if not self.is_active:
            return []
        
        permissions = set()
        for role in self.roles:
            permissions.update(ROLE_PERMISSIONS.get(role, []))
        return list(permissions)


class AuditLogEntry(BaseModel):
    """Audit log entry for admin actions"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    admin_id: str = Field(..., description="ID of admin who performed the action")
    admin_username: str = Field(..., description="Username of admin")
    action: str = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[str] = Field(None, description="ID of affected resource")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional action details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = Field(default=True)
    error_message: Optional[str] = None


class SystemStats(BaseModel):
    """System statistics for admin dashboard"""
    total_users: int
    active_users_today: int
    active_users_week: int
    total_puzzles: int
    puzzles_by_universe: Dict[str, int]
    total_guesses_today: int
    total_guesses_week: int
    success_rate_today: float
    success_rate_week: float
    top_characters: List[Dict[str, Any]]
    system_health: Dict[str, Any]
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class PuzzleSchedule(BaseModel):
    """Puzzle scheduling model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    universe: str = Field(..., pattern="^(marvel|dc|image)$")
    character: str = Field(...)
    character_aliases: List[str] = Field(default_factory=list)
    image_key: str = Field(...)
    scheduled_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    created_by: str = Field(..., description="Admin ID who scheduled this")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    notes: Optional[str] = None


class ContentReview(BaseModel):
    """Content review and approval model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_type: str = Field(..., description="Type of content (puzzle, image, alias)")
    content_id: str = Field(..., description="ID of content being reviewed")
    status: str = Field(default="pending", pattern="^(pending|approved|rejected)$")
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    submitted_by: str = Field(..., description="ID of user who submitted content")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    content_data: Dict[str, Any] = Field(default_factory=dict)


class AdminDashboardData(BaseModel):
    """Complete admin dashboard data"""
    stats: SystemStats
    recent_audit_logs: List[AuditLogEntry]
    pending_reviews: List[ContentReview]
    scheduled_puzzles: List[PuzzleSchedule]
    system_alerts: List[Dict[str, Any]] = Field(default_factory=list)