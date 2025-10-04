"""Analytics and operational audit service"""

import logging
import json
import csv
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date, timedelta
from io import StringIO
import asyncio

from app.models.analytics import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    DataExportRequest,
    AnalyticsMetric,
    OperationalReport,
    UserActivitySummary,
    SystemHealthMetrics,
    AlertRule,
    AlertEvent
)
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.user_repository import UserRepository
from app.repositories.puzzle_repository import PuzzleRepository
from app.repositories.guess_repository import GuessRepository

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics and operational audit operations"""
    
    def __init__(self):
        self.analytics_repo = AnalyticsRepository()
        self.user_repo = UserRepository()
        self.puzzle_repo = PuzzleRepository()
        self.guess_repo = GuessRepository()
    
    # Audit Event Management
    
    async def log_audit_event(self, event_type: AuditEventType, description: str,
                            user_id: Optional[str] = None, admin_id: Optional[str] = None,
                            resource_type: Optional[str] = None, resource_id: Optional[str] = None,
                            severity: AuditSeverity = AuditSeverity.INFO,
                            metadata: Optional[Dict[str, Any]] = None,
                            success: bool = True, error_message: Optional[str] = None,
                            ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                            duration_ms: Optional[int] = None) -> AuditEvent:
        """Log an audit event"""
        event = AuditEvent(
            event_type=event_type,
            description=description,
            user_id=user_id,
            admin_id=admin_id,
            resource_type=resource_type,
            resource_id=resource_id,
            severity=severity,
            metadata=metadata or {},
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
            duration_ms=duration_ms
        )
        
        return await self.analytics_repo.create_audit_event(event)
    
    async def get_audit_events(self, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None,
                             event_types: Optional[List[AuditEventType]] = None,
                             user_id: Optional[str] = None,
                             admin_id: Optional[str] = None,
                             severity: Optional[AuditSeverity] = None,
                             limit: int = 100, offset: int = 0) -> List[AuditEvent]:
        """Get audit events with filtering"""
        return await self.analytics_repo.get_audit_events(
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
            user_id=user_id,
            admin_id=admin_id,
            severity=severity,
            limit=limit,
            offset=offset
        )
    
    async def get_audit_event_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get summary of audit events for a date range"""
        events = await self.get_audit_events(
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            limit=10000  # Large limit to get all events for analysis
        )
        
        summary = {
            "total_events": len(events),
            "by_type": {},
            "by_severity": {},
            "by_success": {"success": 0, "failure": 0},
            "by_date": {},
            "top_users": {},
            "top_admins": {},
            "error_events": []
        }
        
        for event in events:
            # Count by type
            event_type = event.event_type.value
            summary["by_type"][event_type] = summary["by_type"].get(event_type, 0) + 1
            
            # Count by severity
            severity = event.severity.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            
            # Count by success/failure
            if event.success:
                summary["by_success"]["success"] += 1
            else:
                summary["by_success"]["failure"] += 1
                # Collect error events
                if len(summary["error_events"]) < 10:  # Limit to top 10 errors
                    summary["error_events"].append({
                        "timestamp": event.timestamp.isoformat(),
                        "type": event_type,
                        "description": event.description,
                        "error_message": event.error_message
                    })
            
            # Count by date
            event_date = event.timestamp.date().isoformat()
            summary["by_date"][event_date] = summary["by_date"].get(event_date, 0) + 1
            
            # Count by user
            if event.user_id:
                summary["top_users"][event.user_id] = summary["top_users"].get(event.user_id, 0) + 1
            
            # Count by admin
            if event.admin_id:
                summary["top_admins"][event.admin_id] = summary["top_admins"].get(event.admin_id, 0) + 1
        
        # Sort top users and admins
        summary["top_users"] = dict(sorted(summary["top_users"].items(), key=lambda x: x[1], reverse=True)[:10])
        summary["top_admins"] = dict(sorted(summary["top_admins"].items(), key=lambda x: x[1], reverse=True)[:10])
        
        return summary
    
    # Data Export Management
    
    async def create_data_export_request(self, export_type: str, requested_by: str,
                                       date_range_start: Optional[date] = None,
                                       date_range_end: Optional[date] = None,
                                       filters: Optional[Dict[str, Any]] = None,
                                       format: str = "json") -> DataExportRequest:
        """Create a data export request"""
        # Set default date range if not provided
        if not date_range_end:
            date_range_end = date.today()
        if not date_range_start:
            date_range_start = date_range_end - timedelta(days=30)
        
        # Set expiration to 7 days from now
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        export_request = DataExportRequest(
            export_type=export_type,
            requested_by=requested_by,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            filters=filters or {},
            format=format,
            expires_at=expires_at
        )
        
        # Start async processing
        asyncio.create_task(self._process_export_request(export_request))
        
        return await self.analytics_repo.create_data_export_request(export_request)
    
    async def _process_export_request(self, export_request: DataExportRequest):
        """Process data export request asynchronously"""
        try:
            # Update status to processing
            export_request.status = "processing"
            await self.analytics_repo.update_data_export_request(export_request)
            
            # Generate export data based on type
            if export_request.export_type == "audit_events":
                data = await self._export_audit_events(export_request)
            elif export_request.export_type == "user_activity":
                data = await self._export_user_activity(export_request)
            elif export_request.export_type == "game_statistics":
                data = await self._export_game_statistics(export_request)
            elif export_request.export_type == "system_metrics":
                data = await self._export_system_metrics(export_request)
            else:
                raise ValueError(f"Unknown export type: {export_request.export_type}")
            
            # Save data to file
            file_path = await self._save_export_data(export_request, data)
            
            # Update export request with results
            export_request.status = "completed"
            export_request.file_path = file_path
            export_request.record_count = len(data) if isinstance(data, list) else 1
            export_request.completed_at = datetime.utcnow()
            export_request.progress_percentage = 100
            
            await self.analytics_repo.update_data_export_request(export_request)
            
            # Log successful export
            await self.log_audit_event(
                event_type=AuditEventType.DATA_EXPORT,
                description=f"Data export completed: {export_request.export_type}",
                admin_id=export_request.requested_by,
                resource_type="data_export",
                resource_id=export_request.id,
                metadata={
                    "export_type": export_request.export_type,
                    "record_count": export_request.record_count,
                    "format": export_request.format
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing export request {export_request.id}: {e}")
            
            # Update export request with error
            export_request.status = "failed"
            export_request.error_message = str(e)
            export_request.completed_at = datetime.utcnow()
            
            await self.analytics_repo.update_data_export_request(export_request)
            
            # Log failed export
            await self.log_audit_event(
                event_type=AuditEventType.DATA_EXPORT,
                description=f"Data export failed: {export_request.export_type}",
                admin_id=export_request.requested_by,
                resource_type="data_export",
                resource_id=export_request.id,
                severity=AuditSeverity.ERROR,
                success=False,
                error_message=str(e)
            )
    
    async def _export_audit_events(self, export_request: DataExportRequest) -> List[Dict[str, Any]]:
        """Export audit events"""
        events = await self.get_audit_events(
            start_date=datetime.combine(export_request.date_range_start, datetime.min.time()),
            end_date=datetime.combine(export_request.date_range_end, datetime.max.time()),
            limit=50000  # Large limit for export
        )
        
        return [event.model_dump() for event in events]
    
    async def _export_user_activity(self, export_request: DataExportRequest) -> List[Dict[str, Any]]:
        """Export user activity data"""
        # Get user activity summaries for the date range
        summaries = await self.analytics_repo.get_user_activity_summaries(
            start_date=export_request.date_range_start,
            end_date=export_request.date_range_end
        )
        
        return [summary.model_dump() for summary in summaries]
    
    async def _export_game_statistics(self, export_request: DataExportRequest) -> List[Dict[str, Any]]:
        """Export game statistics"""
        # This would typically aggregate game data from guesses and puzzles
        # For now, return a placeholder structure
        stats = []
        
        current_date = export_request.date_range_start
        while current_date <= export_request.date_range_end:
            for universe in ["marvel", "DC", "image"]:
                # Get puzzle for this date and universe
                puzzle = await self.puzzle_repo.get_daily_puzzle(universe, current_date.isoformat())
                
                if puzzle:
                    # Get guesses for this puzzle (would need to implement this query)
                    stat = {
                        "date": current_date.isoformat(),
                        "universe": universe,
                        "puzzle_id": puzzle.id,
                        "character": puzzle.character,
                        "total_attempts": 0,  # Would calculate from guesses
                        "successful_attempts": 0,  # Would calculate from guesses
                        "success_rate": 0.0,  # Would calculate
                        "average_attempts": 0.0  # Would calculate
                    }
                    stats.append(stat)
            
            current_date += timedelta(days=1)
        
        return stats
    
    async def _export_system_metrics(self, export_request: DataExportRequest) -> List[Dict[str, Any]]:
        """Export system metrics"""
        metrics = await self.analytics_repo.get_system_health_metrics(
            start_date=export_request.date_range_start,
            end_date=export_request.date_range_end
        )
        
        return [metric.model_dump() for metric in metrics]
    
    async def _save_export_data(self, export_request: DataExportRequest, data: List[Dict[str, Any]]) -> str:
        """Save export data to file"""
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{export_request.export_type}_{timestamp}.{export_request.format}"
        file_path = f"/tmp/exports/{filename}"  # In production, use proper storage
        
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save data based on format
        if export_request.format == "json":
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        elif export_request.format == "csv":
            if data:
                with open(file_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
        
        # Calculate file size
        file_size = os.path.getsize(file_path)
        export_request.file_size_bytes = file_size
        
        return file_path
    
    async def get_data_export_requests(self, requested_by: Optional[str] = None,
                                     status: Optional[str] = None,
                                     limit: int = 50) -> List[DataExportRequest]:
        """Get data export requests"""
        return await self.analytics_repo.get_data_export_requests(
            requested_by=requested_by,
            status=status,
            limit=limit
        )
    
    # Analytics Metrics
    
    async def record_metric(self, metric_name: str, value: Union[int, float],
                          metric_type: str = "gauge", unit: Optional[str] = None,
                          dimensions: Optional[Dict[str, str]] = None) -> AnalyticsMetric:
        """Record an analytics metric"""
        metric = AnalyticsMetric(
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            unit=unit,
            dimensions=dimensions or {}
        )
        
        return await self.analytics_repo.create_analytics_metric(metric)
    
    async def get_metrics(self, metric_name: Optional[str] = None,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        dimensions: Optional[Dict[str, str]] = None,
                        limit: int = 1000) -> List[AnalyticsMetric]:
        """Get analytics metrics"""
        return await self.analytics_repo.get_analytics_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            dimensions=dimensions,
            limit=limit
        )
    
    # Operational Reports
    
    async def generate_operational_report(self, report_type: str, generated_by: str,
                                        start_date: date, end_date: date,
                                        filters: Optional[Dict[str, Any]] = None) -> OperationalReport:
        """Generate an operational report"""
        start_time = datetime.utcnow()
        
        report = OperationalReport(
            report_name=f"{report_type.replace('_', ' ').title()} Report",
            report_type=report_type,
            generated_by=generated_by,
            date_range_start=start_date,
            date_range_end=end_date,
            filters=filters or {}
        )
        
        # Generate report based on type
        if report_type == "user_activity":
            await self._generate_user_activity_report(report)
        elif report_type == "system_performance":
            await self._generate_system_performance_report(report)
        elif report_type == "security_audit":
            await self._generate_security_audit_report(report)
        elif report_type == "game_analytics":
            await self._generate_game_analytics_report(report)
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        report.processing_time_ms = int(processing_time)
        
        # Save report
        saved_report = await self.analytics_repo.create_operational_report(report)
        
        # Log report generation
        await self.log_audit_event(
            event_type=AuditEventType.ADMIN_ACTION,
            description=f"Generated operational report: {report_type}",
            admin_id=generated_by,
            resource_type="operational_report",
            resource_id=saved_report.id,
            metadata={
                "report_type": report_type,
                "date_range": f"{start_date} to {end_date}",
                "processing_time_ms": processing_time
            }
        )
        
        return saved_report
    
    async def _generate_user_activity_report(self, report: OperationalReport):
        """Generate user activity report"""
        # Get user activity data
        audit_summary = await self.get_audit_event_summary(
            report.date_range_start,
            report.date_range_end
        )
        
        # Add summary data
        report.summary = {
            "total_events": audit_summary["total_events"],
            "unique_users": len(audit_summary["top_users"]),
            "unique_admins": len(audit_summary["top_admins"]),
            "success_rate": audit_summary["by_success"]["success"] / max(audit_summary["total_events"], 1)
        }
        
        # Add sections
        report.add_section("Event Summary", audit_summary["by_type"], "bar")
        report.add_section("Daily Activity", audit_summary["by_date"], "line")
        report.add_section("Top Users", audit_summary["top_users"], "bar")
        report.add_section("Error Events", {"errors": audit_summary["error_events"]})
        
        report.total_records = audit_summary["total_events"]
    
    async def _generate_system_performance_report(self, report: OperationalReport):
        """Generate system performance report"""
        # Get system metrics
        metrics = await self.analytics_repo.get_system_health_metrics(
            start_date=report.date_range_start,
            end_date=report.date_range_end
        )
        
        if metrics:
            # Calculate averages
            avg_response_time = sum(m.api_response_time_p95 for m in metrics) / len(metrics)
            avg_error_rate = sum(m.api_error_rate for m in metrics) / len(metrics)
            avg_cache_hit_rate = sum(m.cache_hit_rate for m in metrics) / len(metrics)
            
            report.summary = {
                "average_response_time_ms": round(avg_response_time, 2),
                "average_error_rate": round(avg_error_rate, 4),
                "average_cache_hit_rate": round(avg_cache_hit_rate, 4),
                "total_data_points": len(metrics)
            }
            
            # Add performance trends
            performance_data = {
                "timestamps": [m.timestamp.isoformat() for m in metrics],
                "response_times": [m.api_response_time_p95 for m in metrics],
                "error_rates": [m.api_error_rate for m in metrics],
                "cache_hit_rates": [m.cache_hit_rate for m in metrics]
            }
            
            report.add_section("Performance Trends", performance_data, "line")
            report.total_records = len(metrics)
        else:
            report.summary = {"message": "No performance data available for the selected period"}
    
    async def _generate_security_audit_report(self, report: OperationalReport):
        """Generate security audit report"""
        # Get security-related audit events
        security_events = await self.get_audit_events(
            start_date=datetime.combine(report.date_range_start, datetime.min.time()),
            end_date=datetime.combine(report.date_range_end, datetime.max.time()),
            event_types=[
                AuditEventType.USER_LOGIN,
                AuditEventType.ADMIN_LOGIN,
                AuditEventType.RATE_LIMIT_HIT,
                AuditEventType.SYSTEM_ERROR
            ],
            limit=10000
        )
        
        # Analyze security events
        failed_logins = [e for e in security_events if not e.success and "login" in e.event_type.value]
        rate_limit_hits = [e for e in security_events if e.event_type == AuditEventType.RATE_LIMIT_HIT]
        
        report.summary = {
            "total_security_events": len(security_events),
            "failed_login_attempts": len(failed_logins),
            "rate_limit_violations": len(rate_limit_hits),
            "unique_ip_addresses": len(set(e.ip_address for e in security_events if e.ip_address))
        }
        
        # Add security sections
        if failed_logins:
            failed_login_ips = {}
            for event in failed_logins:
                if event.ip_address:
                    failed_login_ips[event.ip_address] = failed_login_ips.get(event.ip_address, 0) + 1
            
            report.add_section("Failed Login Attempts by IP", failed_login_ips, "bar")
        
        if rate_limit_hits:
            rate_limit_ips = {}
            for event in rate_limit_hits:
                if event.ip_address:
                    rate_limit_ips[event.ip_address] = rate_limit_ips.get(event.ip_address, 0) + 1
            
            report.add_section("Rate Limit Violations by IP", rate_limit_ips, "bar")
        
        report.total_records = len(security_events)
    
    async def _generate_game_analytics_report(self, report: OperationalReport):
        """Generate game analytics report"""
        # Get game-related audit events
        game_events = await self.get_audit_events(
            start_date=datetime.combine(report.date_range_start, datetime.min.time()),
            end_date=datetime.combine(report.date_range_end, datetime.max.time()),
            event_types=[
                AuditEventType.PUZZLE_GUESS,
                AuditEventType.PUZZLE_SOLVED,
                AuditEventType.PUZZLE_FAILED
            ],
            limit=10000
        )
        
        # Analyze game events
        total_guesses = len([e for e in game_events if e.event_type == AuditEventType.PUZZLE_GUESS])
        solved_puzzles = len([e for e in game_events if e.event_type == AuditEventType.PUZZLE_SOLVED])
        failed_puzzles = len([e for e in game_events if e.event_type == AuditEventType.PUZZLE_FAILED])
        
        success_rate = solved_puzzles / max(solved_puzzles + failed_puzzles, 1)
        
        report.summary = {
            "total_game_events": len(game_events),
            "total_guesses": total_guesses,
            "solved_puzzles": solved_puzzles,
            "failed_puzzles": failed_puzzles,
            "success_rate": round(success_rate, 4)
        }
        
        # Add game analytics sections
        universe_stats = {}
        for event in game_events:
            if event.metadata and "universe" in event.metadata:
                universe = event.metadata["universe"]
                if universe not in universe_stats:
                    universe_stats[universe] = {"guesses": 0, "solved": 0, "failed": 0}
                
                if event.event_type == AuditEventType.PUZZLE_GUESS:
                    universe_stats[universe]["guesses"] += 1
                elif event.event_type == AuditEventType.PUZZLE_SOLVED:
                    universe_stats[universe]["solved"] += 1
                elif event.event_type == AuditEventType.PUZZLE_FAILED:
                    universe_stats[universe]["failed"] += 1
        
        if universe_stats:
            report.add_section("Game Activity by Universe", universe_stats, "bar")
        
        report.total_records = len(game_events)
    
    async def get_operational_reports(self, generated_by: Optional[str] = None,
                                    report_type: Optional[str] = None,
                                    limit: int = 50) -> List[OperationalReport]:
        """Get operational reports"""
        return await self.analytics_repo.get_operational_reports(
            generated_by=generated_by,
            report_type=report_type,
            limit=limit
        )
    
    # System Health Monitoring
    
    async def record_system_health_metrics(self, metrics: SystemHealthMetrics) -> SystemHealthMetrics:
        """Record system health metrics"""
        return await self.analytics_repo.create_system_health_metrics(metrics)
    
    async def get_current_system_health(self) -> Optional[SystemHealthMetrics]:
        """Get the most recent system health metrics"""
        metrics_list = await self.analytics_repo.get_system_health_metrics(
            start_date=date.today() - timedelta(days=1),
            end_date=date.today(),
            limit=1
        )
        
        return metrics_list[0] if metrics_list else None
    
    # Cleanup Operations
    
    async def cleanup_old_audit_events(self, days_to_keep: int = 90) -> int:
        """Clean up old audit events"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = await self.analytics_repo.delete_audit_events_before(cutoff_date)
        
        # Log cleanup operation
        await self.log_audit_event(
            event_type=AuditEventType.ADMIN_ACTION,
            description=f"Cleaned up {deleted_count} old audit events",
            severity=AuditSeverity.INFO,
            metadata={"days_to_keep": days_to_keep, "deleted_count": deleted_count}
        )
        
        return deleted_count
    
    async def cleanup_old_metrics(self, days_to_keep: int = 30) -> int:
        """Clean up old analytics metrics"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = await self.analytics_repo.delete_analytics_metrics_before(cutoff_date)
        
        logger.info(f"Cleaned up {deleted_count} old analytics metrics")
        return deleted_count
    
    async def cleanup_expired_exports(self) -> int:
        """Clean up expired data exports"""
        expired_exports = await self.analytics_repo.get_expired_data_exports()
        
        deleted_count = 0
        for export in expired_exports:
            # Delete file if it exists
            if export.file_path:
                try:
                    import os
                    if os.path.exists(export.file_path):
                        os.remove(export.file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete export file {export.file_path}: {e}")
            
            # Delete export record
            if await self.analytics_repo.delete_data_export_request(export.id):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} expired data exports")
        return deleted_count