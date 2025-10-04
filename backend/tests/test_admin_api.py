"""Tests for admin API endpoints and functionality"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from app.models.admin import AdminUser, AdminRole, Permission, SystemStats, AuditLogEntry
from app.auth.admin_auth import admin_repo, audit_logger
from app.api.admin import router
from app.main import app

# Add admin router to test app
app.include_router(router)

client = TestClient(app)


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user for testing"""
    return AdminUser(
        id="admin-123",
        username="test_admin",
        email="admin@test.com",
        roles=[AdminRole.SUPER_ADMIN],
        is_active=True
    )


@pytest.fixture
def mock_system_stats():
    """Create mock system statistics"""
    return SystemStats(
        total_users=100,
        active_users_today=25,
        active_users_week=75,
        total_puzzles=300,
        puzzles_by_universe={"marvel": 100, "dc": 100, "image": 100},
        total_guesses_today=150,
        total_guesses_week=800,
        success_rate_today=0.65,
        success_rate_week=0.68,
        top_characters=[],
        system_health={}
    )


@pytest.fixture
def mock_audit_logs():
    """Create mock audit log entries"""
    return [
        AuditLogEntry(
            admin_id="admin-123",
            admin_username="test_admin",
            action="view_dashboard",
            resource_type="dashboard",
            timestamp=datetime.utcnow()
        ),
        AuditLogEntry(
            admin_id="admin-123",
            admin_username="test_admin",
            action="view_users",
            resource_type="users",
            timestamp=datetime.utcnow()
        )
    ]


class TestAdminAuthentication:
    """Test admin authentication and authorization"""
    
    def test_admin_user_permissions(self, mock_admin_user):
        """Test admin user permission checking"""
        # Super admin should have all permissions
        assert mock_admin_user.has_permission(Permission.VIEW_USERS)
        assert mock_admin_user.has_permission(Permission.EDIT_USERS)
        assert mock_admin_user.has_permission(Permission.HOTFIX_PUZZLES)
        assert mock_admin_user.has_permission(Permission.MANAGE_SYSTEM)
        
        # Test inactive user
        inactive_admin = AdminUser(
            id="inactive-admin",
            username="inactive",
            email="inactive@test.com",
            roles=[AdminRole.SUPER_ADMIN],
            is_active=False
        )
        assert not inactive_admin.has_permission(Permission.VIEW_USERS)
    
    def test_role_based_permissions(self):
        """Test role-based permission system"""
        # Content admin
        content_admin = AdminUser(
            id="content-admin",
            username="content_admin",
            email="content@test.com",
            roles=[AdminRole.CONTENT_ADMIN],
            is_active=True
        )
        
        assert content_admin.has_permission(Permission.VIEW_CONTENT)
        assert content_admin.has_permission(Permission.UPLOAD_IMAGES)
        assert not content_admin.has_permission(Permission.DELETE_USERS)
        assert not content_admin.has_permission(Permission.MANAGE_SYSTEM)
        
        # Read-only admin
        readonly_admin = AdminUser(
            id="readonly-admin",
            username="readonly",
            email="readonly@test.com",
            roles=[AdminRole.READ_ONLY],
            is_active=True
        )
        
        assert readonly_admin.has_permission(Permission.VIEW_USERS)
        assert readonly_admin.has_permission(Permission.VIEW_PUZZLES)
        assert not readonly_admin.has_permission(Permission.EDIT_USERS)
        assert not readonly_admin.has_permission(Permission.CREATE_PUZZLES)
    
    def test_multiple_roles(self):
        """Test user with multiple roles"""
        multi_role_admin = AdminUser(
            id="multi-admin",
            username="multi_admin",
            email="multi@test.com",
            roles=[AdminRole.USER_ADMIN, AdminRole.PUZZLE_ADMIN],
            is_active=True
        )
        
        # Should have permissions from both roles
        assert multi_role_admin.has_permission(Permission.VIEW_USERS)
        assert multi_role_admin.has_permission(Permission.EDIT_USERS)
        assert multi_role_admin.has_permission(Permission.VIEW_PUZZLES)
        assert multi_role_admin.has_permission(Permission.CREATE_PUZZLES)
        
        # Should not have permissions not in either role
        assert not multi_role_admin.has_permission(Permission.UPLOAD_IMAGES)
        assert not multi_role_admin.has_permission(Permission.MANAGE_SYSTEM)


class TestAdminAPI:
    """Test admin API endpoints"""
    
    @patch('app.auth.admin_auth.get_current_admin_user')
    @patch('app.api.admin.get_system_statistics')
    @patch('app.auth.admin_auth.admin_repo.get_audit_logs')
    def test_get_admin_dashboard(self, mock_get_logs, mock_get_stats, mock_get_admin, 
                               mock_admin_user, mock_system_stats, mock_audit_logs):
        """Test admin dashboard endpoint"""
        mock_get_admin.return_value = mock_admin_user
        mock_get_stats.return_value = mock_system_stats
        mock_get_logs.return_value = mock_audit_logs
        
        response = client.get("/admin/dashboard", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        data = response.json()
        
        assert "stats" in data
        assert "recent_audit_logs" in data
        assert data["stats"]["total_users"] == 100
        assert len(data["recent_audit_logs"]) == 2
    
    @patch('app.auth.admin_auth.get_current_admin_user')
    @patch('app.repositories.user_repository.UserRepository.get_users_paginated')
    def test_get_users(self, mock_get_users, mock_get_admin, mock_admin_user):
        """Test get users endpoint"""
        mock_get_admin.return_value = mock_admin_user
        mock_get_users.return_value = []
        
        response = client.get("/admin/users", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @patch('app.auth.admin_auth.get_current_admin_user')
    @patch('app.repositories.puzzle_repository.PuzzleRepository.get_puzzles_paginated')
    def test_get_puzzles(self, mock_get_puzzles, mock_get_admin, mock_admin_user):
        """Test get puzzles endpoint"""
        mock_get_admin.return_value = mock_admin_user
        mock_get_puzzles.return_value = []
        
        response = client.get("/admin/puzzles", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @patch('app.auth.admin_auth.get_current_admin_user')
    @patch('app.services.puzzle_service.PuzzleService.hotfix_puzzle')
    def test_hotfix_puzzle(self, mock_hotfix, mock_get_admin, mock_admin_user):
        """Test puzzle hotfix endpoint"""
        mock_get_admin.return_value = mock_admin_user
        
        # Mock puzzle with today's date
        today = datetime.utcnow().strftime('%Y%m%d')
        puzzle_id = f"{today}-marvel"
        
        from app.models.puzzle import Puzzle
        mock_puzzle = Puzzle(
            id=puzzle_id,
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spidey"],
            image_key="marvel/spiderman.jpg",
            active_date=datetime.utcnow().strftime('%Y-%m-%d')
        )
        mock_hotfix.return_value = mock_puzzle
        
        response = client.post(
            "/admin/puzzles/hotfix",
            json={
                "puzzle_id": puzzle_id,
                "replacement_character": "Iron Man"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
    
    @patch('app.auth.admin_auth.get_current_admin_user')
    def test_hotfix_puzzle_invalid_date(self, mock_get_admin, mock_admin_user):
        """Test hotfix with invalid date (not today)"""
        mock_get_admin.return_value = mock_admin_user
        
        # Use yesterday's date
        yesterday = (datetime.utcnow().replace(day=datetime.utcnow().day-1)).strftime('%Y%m%d')
        puzzle_id = f"{yesterday}-marvel"
        
        response = client.post(
            "/admin/puzzles/hotfix",
            json={
                "puzzle_id": puzzle_id,
                "replacement_character": "Iron Man"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "today's puzzle" in response.json()["detail"]
    
    @patch('app.auth.admin_auth.get_current_admin_user')
    @patch('app.auth.admin_auth.admin_repo.get_audit_logs')
    def test_get_audit_logs(self, mock_get_logs, mock_get_admin, mock_admin_user, mock_audit_logs):
        """Test get audit logs endpoint"""
        mock_get_admin.return_value = mock_admin_user
        mock_get_logs.return_value = mock_audit_logs
        
        response = client.get("/admin/audit-logs", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["action"] == "view_dashboard"
    
    @patch('app.auth.admin_auth.get_current_admin_user')
    def test_get_system_health(self, mock_get_admin, mock_admin_user):
        """Test system health endpoint"""
        mock_get_admin.return_value = mock_admin_user
        
        response = client.get("/admin/system/health", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert "api" in data
        assert "last_check" in data
    
    def test_admin_dashboard_html(self):
        """Test admin dashboard HTML page"""
        response = client.get("/admin/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "ComicGuess Admin Dashboard" in response.text


class TestAuditLogging:
    """Test audit logging functionality"""
    
    @pytest.mark.asyncio
    async def test_audit_logger(self, mock_admin_user):
        """Test audit logging functionality"""
        # Mock the repository
        with patch.object(audit_logger.repo, 'log_admin_action', new_callable=AsyncMock) as mock_log:
            await audit_logger.log_action(
                admin_user=mock_admin_user,
                action="test_action",
                resource_type="test_resource",
                resource_id="test-123",
                details={"test": "data"}
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0][0]  # First argument (AuditLogEntry)
            
            assert call_args.admin_id == mock_admin_user.id
            assert call_args.admin_username == mock_admin_user.username
            assert call_args.action == "test_action"
            assert call_args.resource_type == "test_resource"
            assert call_args.resource_id == "test-123"
            assert call_args.details == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_audit_logger_with_request(self, mock_admin_user):
        """Test audit logging with request information"""
        # Mock request object
        mock_request = Mock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "test-user-agent"
        
        with patch.object(audit_logger.repo, 'log_admin_action', new_callable=AsyncMock) as mock_log:
            await audit_logger.log_action(
                admin_user=mock_admin_user,
                action="test_action",
                resource_type="test_resource",
                request=mock_request
            )
            
            call_args = mock_log.call_args[0][0]
            assert call_args.ip_address == "127.0.0.1"
            assert call_args.user_agent == "test-user-agent"


class TestAdminRepository:
    """Test admin repository functionality"""
    
    @pytest.mark.asyncio
    async def test_create_admin_user(self, mock_admin_user):
        """Test creating admin user"""
        created_user = await admin_repo.create_admin_user(mock_admin_user)
        
        assert created_user.id == mock_admin_user.id
        assert created_user.username == mock_admin_user.username
        assert created_user.roles == mock_admin_user.roles
    
    @pytest.mark.asyncio
    async def test_get_admin_by_user_id(self, mock_admin_user):
        """Test getting admin by user ID"""
        # First create the admin user
        await admin_repo.create_admin_user(mock_admin_user)
        
        # Then retrieve it
        retrieved_user = await admin_repo.get_admin_by_user_id(mock_admin_user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == mock_admin_user.id
        assert retrieved_user.username == mock_admin_user.username
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_admin(self):
        """Test getting non-existent admin user"""
        retrieved_user = await admin_repo.get_admin_by_user_id("nonexistent-id")
        assert retrieved_user is None
    
    @pytest.mark.asyncio
    async def test_log_admin_action(self):
        """Test logging admin actions"""
        audit_entry = AuditLogEntry(
            admin_id="admin-123",
            admin_username="test_admin",
            action="test_action",
            resource_type="test_resource"
        )
        
        await admin_repo.log_admin_action(audit_entry)
        
        # Verify the log was stored
        logs = await admin_repo.get_audit_logs(limit=10)
        assert len(logs) > 0
        assert logs[-1].action == "test_action"
    
    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination(self):
        """Test audit logs pagination"""
        # Create multiple audit entries
        for i in range(15):
            audit_entry = AuditLogEntry(
                admin_id="admin-123",
                admin_username="test_admin",
                action=f"test_action_{i}",
                resource_type="test_resource"
            )
            await admin_repo.log_admin_action(audit_entry)
        
        # Test pagination
        first_page = await admin_repo.get_audit_logs(limit=10, offset=0)
        second_page = await admin_repo.get_audit_logs(limit=10, offset=10)
        
        assert len(first_page) == 10
        assert len(second_page) >= 5  # At least 5 from our test data
        
        # Ensure no overlap
        first_page_actions = {log.action for log in first_page}
        second_page_actions = {log.action for log in second_page}
        assert len(first_page_actions.intersection(second_page_actions)) == 0


class TestPermissionSystem:
    """Test the permission system"""
    
    def test_permission_inheritance(self):
        """Test that roles have correct permissions"""
        from app.models.admin import ROLE_PERMISSIONS
        
        # Super admin should have all permissions
        super_admin_perms = ROLE_PERMISSIONS[AdminRole.SUPER_ADMIN]
        assert len(super_admin_perms) == len(list(Permission))
        
        # Content admin should have content-related permissions
        content_admin_perms = ROLE_PERMISSIONS[AdminRole.CONTENT_ADMIN]
        assert Permission.VIEW_CONTENT in content_admin_perms
        assert Permission.UPLOAD_IMAGES in content_admin_perms
        assert Permission.DELETE_USERS not in content_admin_perms
        
        # Read-only should only have view permissions
        readonly_perms = ROLE_PERMISSIONS[AdminRole.READ_ONLY]
        view_permissions = [p for p in Permission if p.value.startswith('view_')]
        for perm in view_permissions:
            assert perm in readonly_perms
        
        # Should not have any edit/create/delete permissions
        assert Permission.EDIT_USERS not in readonly_perms
        assert Permission.CREATE_PUZZLES not in readonly_perms
        assert Permission.DELETE_USERS not in readonly_perms
    
    def test_get_all_permissions(self):
        """Test getting all permissions for a user"""
        admin_user = AdminUser(
            id="test-admin",
            username="test",
            email="test@test.com",
            roles=[AdminRole.USER_ADMIN, AdminRole.PUZZLE_ADMIN],
            is_active=True
        )
        
        all_perms = admin_user.get_all_permissions()
        
        # Should have permissions from both roles
        assert Permission.VIEW_USERS in all_perms
        assert Permission.EDIT_USERS in all_perms
        assert Permission.VIEW_PUZZLES in all_perms
        assert Permission.CREATE_PUZZLES in all_perms
        
        # Should not have permissions not in either role
        assert Permission.UPLOAD_IMAGES not in all_perms
        assert Permission.MANAGE_SYSTEM not in all_perms
    
    def test_inactive_user_permissions(self):
        """Test that inactive users have no permissions"""
        inactive_admin = AdminUser(
            id="inactive",
            username="inactive",
            email="inactive@test.com",
            roles=[AdminRole.SUPER_ADMIN],
            is_active=False
        )
        
        assert not inactive_admin.has_permission(Permission.VIEW_USERS)
        assert not inactive_admin.has_permission(Permission.MANAGE_SYSTEM)
        assert len(inactive_admin.get_all_permissions()) == 0


if __name__ == "__main__":
    pytest.main([__file__])