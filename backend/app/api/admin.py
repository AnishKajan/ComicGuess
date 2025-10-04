"""Admin API endpoints for ComicGuess application"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
import os

from app.auth.admin_auth import (
    get_current_admin_user,
    require_view_users,
    require_edit_users,
    require_view_puzzles,
    require_create_puzzles,
    require_edit_puzzles,
    require_schedule_puzzles,
    require_hotfix_puzzles,
    require_view_system_stats,
    require_view_audit_logs,
    require_manage_system,
    audit_logger,
    admin_repo
)
from app.models.admin import (
    AdminUser,
    SystemStats,
    PuzzleSchedule,
    ContentReview,
    AdminDashboardData,
    AuditLogEntry
)
from app.models.user import User
from app.models.puzzle import Puzzle
from app.repositories.user_repository import UserRepository
from app.repositories.puzzle_repository import PuzzleRepository
from app.services.puzzle_service import PuzzleService
from app.services.content_governance_service import ContentGovernanceService
from app.services.analytics_service import AnalyticsService
from app.models.content_governance import (
    CanonicalCharacter,
    ContentReviewRequest,
    ContentType,
    ContentStatus
)
from app.models.analytics import (
    AuditEventType,
    AuditSeverity
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard_page():
    """Serve the admin dashboard HTML page"""
    try:
        # Get the path to the template file
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "admin_dashboard.html")
        
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        return HTMLResponse(content=html_content)
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin dashboard template not found"
        )
    except Exception as e:
        logger.error(f"Error serving admin dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load admin dashboard"
        )


@router.get("/dashboard", response_model=AdminDashboardData)
async def get_admin_dashboard(
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None
):
    """Get admin dashboard data with system stats and recent activity"""
    try:
        # Get system statistics
        stats = await get_system_statistics()
        
        # Get recent audit logs
        recent_logs = await admin_repo.get_audit_logs(limit=10)
        
        # Get pending content reviews (placeholder)
        pending_reviews = []  # TODO: Implement content review system
        
        # Get scheduled puzzles (placeholder)
        scheduled_puzzles = []  # TODO: Implement puzzle scheduling
        
        # Get system alerts (placeholder)
        system_alerts = []  # TODO: Implement system health monitoring
        
        dashboard_data = AdminDashboardData(
            stats=stats,
            recent_audit_logs=recent_logs,
            pending_reviews=pending_reviews,
            scheduled_puzzles=scheduled_puzzles,
            system_alerts=system_alerts
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_dashboard",
            resource_type="dashboard",
            request=request
        )
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting admin dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard data"
        )


@router.get("/users", response_model=List[Dict[str, Any]])
async def get_users(
    admin_user: AdminUser = Depends(require_view_users),
    request: Request = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get list of users with pagination"""
    try:
        user_repo = UserRepository()
        users = await user_repo.get_users_paginated(limit=limit, offset=offset)
        
        # Convert to dict format for admin view
        user_data = []
        for user in users:
            user_dict = user.model_dump()
            user_dict['win_rate'] = user.total_wins / user.total_games if user.total_games > 0 else 0.0
            user_data.append(user_dict)
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_users",
            resource_type="users",
            details={"limit": limit, "offset": offset},
            request=request
        )
        
        return user_data
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.get("/users/{user_id}", response_model=Dict[str, Any])
async def get_user_details(
    user_id: str,
    admin_user: AdminUser = Depends(require_view_users),
    request: Request = None
):
    """Get detailed information about a specific user"""
    try:
        user_repo = UserRepository()
        user = await user_repo.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get additional user statistics
        user_dict = user.model_dump()
        user_dict['win_rate'] = user.total_wins / user.total_games if user.total_games > 0 else 0.0
        
        # TODO: Add recent game history, guess patterns, etc.
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_user_details",
            resource_type="user",
            resource_id=user_id,
            request=request
        )
        
        return user_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user details"
        )


@router.get("/puzzles", response_model=List[Dict[str, Any]])
async def get_puzzles(
    admin_user: AdminUser = Depends(require_view_puzzles),
    request: Request = None,
    universe: Optional[str] = Query(None, pattern="^(marvel|dc|image)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get list of puzzles with optional universe filter"""
    try:
        puzzle_repo = PuzzleRepository()
        puzzles = await puzzle_repo.get_puzzles_paginated(
            universe=universe,
            limit=limit,
            offset=offset
        )
        
        puzzle_data = [puzzle.model_dump() for puzzle in puzzles]
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_puzzles",
            resource_type="puzzles",
            details={"universe": universe, "limit": limit, "offset": offset},
            request=request
        )
        
        return puzzle_data
        
    except Exception as e:
        logger.error(f"Error getting puzzles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve puzzles"
        )


@router.post("/puzzles/hotfix")
async def hotfix_puzzle(
    puzzle_id: str,
    replacement_character: str,
    admin_user: AdminUser = Depends(require_hotfix_puzzles),
    request: Request = None
):
    """Emergency hotfix for a puzzle - replace character for today's puzzle"""
    try:
        puzzle_service = PuzzleService()
        
        # Validate that this is today's puzzle
        today = datetime.utcnow().strftime('%Y%m%d')
        if not puzzle_id.startswith(today):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hotfix can only be applied to today's puzzle"
            )
        
        # Apply the hotfix
        updated_puzzle = await puzzle_service.hotfix_puzzle(puzzle_id, replacement_character)
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="hotfix_puzzle",
            resource_type="puzzle",
            resource_id=puzzle_id,
            details={
                "replacement_character": replacement_character,
                "original_puzzle": puzzle_id
            },
            request=request
        )
        
        return {
            "success": True,
            "message": f"Puzzle {puzzle_id} hotfixed with character: {replacement_character}",
            "puzzle": updated_puzzle.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying hotfix: {e}")
        await audit_logger.log_action(
            admin_user=admin_user,
            action="hotfix_puzzle",
            resource_type="puzzle",
            resource_id=puzzle_id,
            success=False,
            error_message=str(e),
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply hotfix"
        )


@router.get("/audit-logs", response_model=List[AuditLogEntry])
async def get_audit_logs(
    admin_user: AdminUser = Depends(require_view_audit_logs),
    request: Request = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action_filter: Optional[str] = Query(None),
    admin_filter: Optional[str] = Query(None)
):
    """Get audit logs with filtering and pagination"""
    try:
        logs = await admin_repo.get_audit_logs(limit=limit, offset=offset)
        
        # Apply filters
        if action_filter:
            logs = [log for log in logs if action_filter.lower() in log.action.lower()]
        
        if admin_filter:
            logs = [log for log in logs if admin_filter.lower() in log.admin_username.lower()]
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_audit_logs",
            resource_type="audit_logs",
            details={
                "limit": limit,
                "offset": offset,
                "action_filter": action_filter,
                "admin_filter": admin_filter
            },
            request=request
        )
        
        return logs
        
    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )


@router.get("/system/health")
async def get_system_health(
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None
):
    """Get system health status"""
    try:
        # TODO: Implement actual health checks
        health_status = {
            "database": "healthy",
            "blob_storage": "healthy",
            "cache": "healthy",
            "api": "healthy",
            "last_check": datetime.utcnow().isoformat(),
            "uptime": "99.9%",
            "response_time_avg": "120ms"
        }
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_system_health",
            resource_type="system",
            request=request
        )
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system health"
        )


async def get_system_statistics() -> SystemStats:
    """Helper function to gather system statistics"""
    try:
        user_repo = UserRepository()
        puzzle_repo = PuzzleRepository()
        
        # Get basic counts
        total_users = await user_repo.get_user_count()
        total_puzzles = await puzzle_repo.get_puzzle_count()
        
        # Get puzzles by universe
        puzzles_by_universe = {
            "marvel": await puzzle_repo.get_puzzle_count_by_universe("marvel"),
            "dc": await puzzle_repo.get_puzzle_count_by_universe("dc"),
            "image": await puzzle_repo.get_puzzle_count_by_universe("image")
        }
        
        # TODO: Implement actual statistics gathering
        # For now, return placeholder data
        return SystemStats(
            total_users=total_users,
            active_users_today=0,  # TODO: Implement
            active_users_week=0,   # TODO: Implement
            total_puzzles=total_puzzles,
            puzzles_by_universe=puzzles_by_universe,
            total_guesses_today=0,  # TODO: Implement
            total_guesses_week=0,   # TODO: Implement
            success_rate_today=0.0, # TODO: Implement
            success_rate_week=0.0,  # TODO: Implement
            top_characters=[],      # TODO: Implement
            system_health={}        # TODO: Implement
        )
        
    except Exception as e:
        logger.error(f"Error gathering system statistics: {e}")
        # Return empty stats on error
        return SystemStats(
            total_users=0,
            active_users_today=0,
            active_users_week=0,
            total_puzzles=0,
            puzzles_by_universe={"marvel": 0, "dc": 0, "image": 0},
            total_guesses_today=0,
            total_guesses_week=0,
            success_rate_today=0.0,
            success_rate_week=0.0,
            top_characters=[],
            system_health={}
        )


# Content Governance Endpoints

@router.get("/content/characters", response_model=List[Dict[str, Any]])
async def get_canonical_characters(
    admin_user: AdminUser = Depends(require_content_management),
    request: Request = None,
    universe: Optional[str] = Query(None, pattern="^(marvel|dc|image)$")
):
    """Get canonical characters, optionally filtered by universe"""
    try:
        governance_service = ContentGovernanceService()
        
        if universe:
            characters = await governance_service.get_canonical_characters_by_universe(universe)
        else:
            # Get all characters from all universes
            all_characters = []
            for univ in ["marvel", "dc", "image"]:
                chars = await governance_service.get_canonical_characters_by_universe(univ)
                all_characters.extend(chars)
            characters = all_characters
        
        character_data = [char.model_dump() for char in characters]
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_canonical_characters",
            resource_type="characters",
            details={"universe": universe, "count": len(characters)},
            request=request
        )
        
        return character_data
        
    except Exception as e:
        logger.error(f"Error getting canonical characters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve canonical characters"
        )


@router.post("/content/characters")
async def create_canonical_character(
    character_data: Dict[str, Any],
    admin_user: AdminUser = Depends(require_content_management),
    request: Request = None
):
    """Create a new canonical character"""
    try:
        governance_service = ContentGovernanceService()
        
        character = await governance_service.create_canonical_character(
            canonical_name=character_data["canonical_name"],
            universe=character_data["universe"],
            approved_aliases=character_data.get("approved_aliases", []),
            created_by=admin_user.id,
            notes=character_data.get("notes")
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="create_canonical_character",
            resource_type="character",
            resource_id=character.id,
            details={"canonical_name": character.canonical_name, "universe": character.universe},
            request=request
        )
        
        return {
            "success": True,
            "message": f"Created canonical character: {character.canonical_name}",
            "character": character.model_dump()
        }
        
    except Exception as e:
        logger.error(f"Error creating canonical character: {e}")
        await audit_logger.log_action(
            admin_user=admin_user,
            action="create_canonical_character",
            resource_type="character",
            success=False,
            error_message=str(e),
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create canonical character"
        )


@router.post("/content/characters/{character_id}/aliases")
async def add_character_alias(
    character_id: str,
    alias_data: Dict[str, str],
    admin_user: AdminUser = Depends(require_content_management),
    request: Request = None
):
    """Add an alias to a canonical character"""
    try:
        governance_service = ContentGovernanceService()
        
        success = await governance_service.add_character_alias(
            character_id=character_id,
            alias=alias_data["alias"],
            admin_id=admin_user.id
        )
        
        if success:
            await audit_logger.log_action(
                admin_user=admin_user,
                action="add_character_alias",
                resource_type="character",
                resource_id=character_id,
                details={"alias": alias_data["alias"]},
                request=request
            )
            
            return {
                "success": True,
                "message": f"Added alias '{alias_data['alias']}' to character"
            }
        else:
            return {
                "success": False,
                "message": "Failed to add alias - may conflict with existing names"
            }
        
    except Exception as e:
        logger.error(f"Error adding character alias: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add character alias"
        )


@router.post("/content/validate-character")
async def validate_character_name(
    validation_data: Dict[str, str],
    admin_user: AdminUser = Depends(require_content_management),
    request: Request = None
):
    """Validate a character name for duplicates and governance rules"""
    try:
        governance_service = ContentGovernanceService()
        
        validation_result = await governance_service.validate_character_name(
            name=validation_data["name"],
            universe=validation_data["universe"]
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="validate_character_name",
            resource_type="validation",
            details={"name": validation_data["name"], "universe": validation_data["universe"]},
            request=request
        )
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Error validating character name: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate character name"
        )


@router.get("/content/reviews", response_model=List[Dict[str, Any]])
async def get_content_reviews(
    admin_user: AdminUser = Depends(require_content_management),
    request: Request = None,
    status_filter: Optional[str] = Query(None, pattern="^(pending|approved|rejected)$"),
    content_type_filter: Optional[str] = Query(None, pattern="^(character|alias|image|puzzle)$"),
    limit: int = Query(50, ge=1, le=100)
):
    """Get content review requests"""
    try:
        governance_service = ContentGovernanceService()
        
        content_status = ContentStatus(status_filter) if status_filter else None
        content_type = ContentType(content_type_filter) if content_type_filter else None
        
        if content_status == ContentStatus.PENDING:
            reviews = await governance_service.get_pending_content_reviews(
                content_type=content_type,
                limit=limit
            )
        else:
            # For now, just get pending reviews - could extend to get all reviews
            reviews = await governance_service.get_pending_content_reviews(
                content_type=content_type,
                limit=limit
            )
        
        review_data = [review.model_dump() for review in reviews]
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_content_reviews",
            resource_type="content_reviews",
            details={"status": status_filter, "content_type": content_type_filter, "count": len(reviews)},
            request=request
        )
        
        return review_data
        
    except Exception as e:
        logger.error(f"Error getting content reviews: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve content reviews"
        )


@router.post("/content/reviews/{review_id}/approve")
async def approve_content_review(
    review_id: str,
    approval_data: Dict[str, Any],
    admin_user: AdminUser = Depends(require_content_management),
    request: Request = None
):
    """Approve a content review request"""
    try:
        governance_service = ContentGovernanceService()
        
        review = await governance_service.approve_content_review(
            review_id=review_id,
            admin_id=admin_user.id,
            notes=approval_data.get("notes")
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="approve_content_review",
            resource_type="content_review",
            resource_id=review_id,
            details={"notes": approval_data.get("notes")},
            request=request
        )
        
        return {
            "success": True,
            "message": "Content review approved",
            "review": review.model_dump()
        }
        
    except Exception as e:
        logger.error(f"Error approving content review: {e}")
        await audit_logger.log_action(
            admin_user=admin_user,
            action="approve_content_review",
            resource_type="content_review",
            resource_id=review_id,
            success=False,
            error_message=str(e),
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve content review"
        )


@router.post("/content/reviews/{review_id}/reject")
async def reject_content_review(
    review_id: str,
    rejection_data: Dict[str, Any],
    admin_user: AdminUser = Depends(require_content_management),
    request: Request = None
):
    """Reject a content review request"""
    try:
        governance_service = ContentGovernanceService()
        
        review = await governance_service.reject_content_review(
            review_id=review_id,
            admin_id=admin_user.id,
            notes=rejection_data.get("notes", "No reason provided")
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="reject_content_review",
            resource_type="content_review",
            resource_id=review_id,
            details={"notes": rejection_data.get("notes")},
            request=request
        )
        
        return {
            "success": True,
            "message": "Content review rejected",
            "review": review.model_dump()
        }
        
    except Exception as e:
        logger.error(f"Error rejecting content review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject content review"
        )


@router.get("/content/governance-report")
async def generate_governance_report(
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None,
    report_type: str = Query("duplicate_analysis", pattern="^(duplicate_analysis|alias_coverage|content_review_status)$"),
    universe: Optional[str] = Query(None, pattern="^(marvel|dc|image)$")
):
    """Generate a content governance report"""
    try:
        governance_service = ContentGovernanceService()
        
        filters = {}
        if universe:
            filters["universe"] = universe
        
        report = await governance_service.generate_governance_report(
            report_type=report_type,
            filters=filters,
            generated_by=admin_user.id
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="generate_governance_report",
            resource_type="governance_report",
            resource_id=report.id,
            details={"report_type": report_type, "filters": filters},
            request=request
        )
        
        return report.model_dump()
        
    except Exception as e:
        logger.error(f"Error generating governance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate governance report"
        )


# Analytics and Audit Endpoints

@router.get("/analytics/audit-events", response_model=List[Dict[str, Any]])
async def get_audit_events(
    admin_user: AdminUser = Depends(require_view_audit_logs),
    request: Request = None,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, pattern="^(debug|info|warning|error|critical)$"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get audit events with advanced filtering"""
    try:
        analytics_service = AnalyticsService()
        
        # Parse dates
        start_datetime = None
        end_datetime = None
        
        if start_date:
            start_datetime = datetime.fromisoformat(start_date + "T00:00:00")
        if end_date:
            end_datetime = datetime.fromisoformat(end_date + "T23:59:59")
        
        # Parse event type
        event_types = None
        if event_type:
            try:
                event_types = [AuditEventType(event_type)]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid event type: {event_type}"
                )
        
        # Parse severity
        severity_enum = None
        if severity:
            severity_enum = AuditSeverity(severity)
        
        events = await analytics_service.get_audit_events(
            start_date=start_datetime,
            end_date=end_datetime,
            event_types=event_types,
            user_id=user_id,
            admin_id=admin_user.id if not user_id else None,
            severity=severity_enum,
            limit=limit,
            offset=offset
        )
        
        event_data = [event.model_dump() for event in events]
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_audit_events",
            resource_type="audit_events",
            details={
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "event_type": event_type,
                    "user_id": user_id,
                    "severity": severity
                },
                "count": len(events)
            },
            request=request
        )
        
        return event_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit events"
        )


@router.get("/analytics/audit-summary")
async def get_audit_summary(
    admin_user: AdminUser = Depends(require_view_audit_logs),
    request: Request = None,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """Get audit event summary for a date range"""
    try:
        analytics_service = AnalyticsService()
        
        # Parse dates
        start_date_obj = datetime.fromisoformat(start_date).date()
        end_date_obj = datetime.fromisoformat(end_date).date()
        
        summary = await analytics_service.get_audit_event_summary(start_date_obj, end_date_obj)
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_audit_summary",
            resource_type="audit_summary",
            details={"start_date": start_date, "end_date": end_date},
            request=request
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting audit summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit summary"
        )


@router.post("/analytics/data-export")
async def create_data_export(
    export_data: Dict[str, Any],
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None
):
    """Create a data export request"""
    try:
        analytics_service = AnalyticsService()
        
        # Parse optional dates
        start_date = None
        end_date = None
        
        if export_data.get("start_date"):
            start_date = datetime.fromisoformat(export_data["start_date"]).date()
        if export_data.get("end_date"):
            end_date = datetime.fromisoformat(export_data["end_date"]).date()
        
        export_request = await analytics_service.create_data_export_request(
            export_type=export_data["export_type"],
            requested_by=admin_user.id,
            date_range_start=start_date,
            date_range_end=end_date,
            filters=export_data.get("filters", {}),
            format=export_data.get("format", "json")
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="create_data_export",
            resource_type="data_export",
            resource_id=export_request.id,
            details={
                "export_type": export_request.export_type,
                "format": export_request.format,
                "date_range": f"{start_date} to {end_date}" if start_date and end_date else "default"
            },
            request=request
        )
        
        return {
            "success": True,
            "message": "Data export request created",
            "export_request": export_request.model_dump()
        }
        
    except Exception as e:
        logger.error(f"Error creating data export: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create data export request"
        )


@router.get("/analytics/data-exports", response_model=List[Dict[str, Any]])
async def get_data_exports(
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None,
    status_filter: Optional[str] = Query(None, pattern="^(pending|processing|completed|failed)$"),
    limit: int = Query(50, ge=1, le=100)
):
    """Get data export requests"""
    try:
        analytics_service = AnalyticsService()
        
        exports = await analytics_service.get_data_export_requests(
            requested_by=admin_user.id,
            status=status_filter,
            limit=limit
        )
        
        export_data = [export.model_dump() for export in exports]
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_data_exports",
            resource_type="data_exports",
            details={"status_filter": status_filter, "count": len(exports)},
            request=request
        )
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error getting data exports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve data exports"
        )


@router.post("/analytics/operational-report")
async def generate_operational_report(
    report_data: Dict[str, Any],
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None
):
    """Generate an operational report"""
    try:
        analytics_service = AnalyticsService()
        
        # Parse dates
        start_date = datetime.fromisoformat(report_data["start_date"]).date()
        end_date = datetime.fromisoformat(report_data["end_date"]).date()
        
        report = await analytics_service.generate_operational_report(
            report_type=report_data["report_type"],
            generated_by=admin_user.id,
            start_date=start_date,
            end_date=end_date,
            filters=report_data.get("filters", {})
        )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="generate_operational_report",
            resource_type="operational_report",
            resource_id=report.id,
            details={
                "report_type": report.report_type,
                "date_range": f"{start_date} to {end_date}",
                "processing_time_ms": report.processing_time_ms
            },
            request=request
        )
        
        return report.model_dump()
        
    except Exception as e:
        logger.error(f"Error generating operational report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate operational report"
        )


@router.get("/analytics/operational-reports", response_model=List[Dict[str, Any]])
async def get_operational_reports(
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None,
    report_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """Get operational reports"""
    try:
        analytics_service = AnalyticsService()
        
        reports = await analytics_service.get_operational_reports(
            generated_by=admin_user.id,
            report_type=report_type,
            limit=limit
        )
        
        report_data = [report.model_dump() for report in reports]
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_operational_reports",
            resource_type="operational_reports",
            details={"report_type": report_type, "count": len(reports)},
            request=request
        )
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error getting operational reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve operational reports"
        )


@router.get("/analytics/system-health")
async def get_system_health_metrics(
    admin_user: AdminUser = Depends(require_view_system_stats),
    request: Request = None
):
    """Get current system health metrics"""
    try:
        analytics_service = AnalyticsService()
        
        current_health = await analytics_service.get_current_system_health()
        
        if current_health:
            health_data = current_health.model_dump()
            health_data["overall_health_score"] = current_health.get_overall_health_score()
        else:
            health_data = {"message": "No recent health data available"}
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="view_system_health_metrics",
            resource_type="system_health",
            request=request
        )
        
        return health_data
        
    except Exception as e:
        logger.error(f"Error getting system health metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system health metrics"
        )


@router.post("/analytics/cleanup")
async def cleanup_analytics_data(
    cleanup_data: Dict[str, Any],
    admin_user: AdminUser = Depends(require_manage_system),
    request: Request = None
):
    """Clean up old analytics data"""
    try:
        analytics_service = AnalyticsService()
        
        cleanup_type = cleanup_data.get("cleanup_type", "audit_events")
        days_to_keep = cleanup_data.get("days_to_keep", 90)
        
        if cleanup_type == "audit_events":
            deleted_count = await analytics_service.cleanup_old_audit_events(days_to_keep)
        elif cleanup_type == "metrics":
            deleted_count = await analytics_service.cleanup_old_metrics(days_to_keep)
        elif cleanup_type == "exports":
            deleted_count = await analytics_service.cleanup_expired_exports()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cleanup type: {cleanup_type}"
            )
        
        await audit_logger.log_action(
            admin_user=admin_user,
            action="cleanup_analytics_data",
            resource_type="analytics_cleanup",
            details={
                "cleanup_type": cleanup_type,
                "days_to_keep": days_to_keep,
                "deleted_count": deleted_count
            },
            request=request
        )
        
        return {
            "success": True,
            "message": f"Cleaned up {deleted_count} {cleanup_type} records",
            "deleted_count": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up analytics data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clean up analytics data"
        )