"""Tests for analytics and audit functionality"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, date, timedelta

from app.models.analytics import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    DataExportRequest,
    AnalyticsMetric,
    OperationalReport,
    SystemHealthMetrics,
    AlertRule,
    AlertEvent
)
from app.services.analytics_service import AnalyticsService


class TestAuditEvent:
    """Test audit event model"""
    
    def test_create_audit_event(self):
        """Test creating an audit event"""
        event = AuditEvent(
            event_type=AuditEventType.USER_LOGIN,
            description="User logged in successfully",
            user_id="user-123",
            ip_address="192.168.1.1",
            success=True
        )
        
        assert event.event_type == AuditEventType.USER_LOGIN
        assert event.description == "User logged in successfully"
        assert event.user_id == "user-123"
        assert event.success is True
        assert event.severity == AuditSeverity.INFO  # Default
    
    def test_audit_event_validation(self):
        """Test audit event validation"""
        # Empty description should raise error
        with pytest.raises(ValueError, match="Description cannot be empty"):
            AuditEvent(
                event_type=AuditEventType.USER_LOGIN,
                description="",
                user_id="user-123"
            )
        
        # Whitespace-only description should raise error
        with pytest.raises(ValueError, match="Description cannot be empty"):
            AuditEvent(
                event_type=AuditEventType.USER_LOGIN,
                description="   ",
                user_id="user-123"
            )
    
    def test_audit_event_with_metadata(self):
        """Test audit event with metadata"""
        metadata = {
            "universe": "marvel",
            "puzzle_id": "20240115-marvel",
            "attempts": 3
        }
        
        event = AuditEvent(
            event_type=AuditEventType.PUZZLE_SOLVED,
            description="User solved puzzle",
            user_id="user-123",
            metadata=metadata,
            duration_ms=1500
        )
        
        assert event.metadata == metadata
        assert event.duration_ms == 1500


class TestDataExportRequest:
    """Test data export request model"""
    
    def test_create_export_request(self):
        """Test creating a data export request"""
        export_request = DataExportRequest(
            export_type="audit_events",
            requested_by="admin-123",
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 31),
            format="json"
        )
        
        assert export_request.export_type == "audit_events"
        assert export_request.requested_by == "admin-123"
        assert export_request.status == "pending"
        assert export_request.format == "json"
        assert export_request.progress_percentage == 0
    
    def test_export_expiration(self):
        """Test export expiration logic"""
        # Not expired
        export_request = DataExportRequest(
            export_type="audit_events",
            requested_by="admin-123",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        assert not export_request.is_expired()
        
        # Expired
        export_request.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert export_request.is_expired()
        
        # No expiration set
        export_request.expires_at = None
        assert not export_request.is_expired()
    
    def test_download_permissions(self):
        """Test download permission logic"""
        export_request = DataExportRequest(
            export_type="audit_events",
            requested_by="admin-123",
            status="completed",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            download_count=0,
            max_downloads=5
        )
        
        # Can download when completed, not expired, under limit
        assert export_request.can_download()
        
        # Cannot download when expired
        export_request.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert not export_request.can_download()
        
        # Cannot download when over limit
        export_request.expires_at = datetime.utcnow() + timedelta(hours=1)
        export_request.download_count = 5
        assert not export_request.can_download()
        
        # Cannot download when not completed
        export_request.download_count = 0
        export_request.status = "processing"
        assert not export_request.can_download()


class TestAnalyticsMetric:
    """Test analytics metric model"""
    
    def test_create_metric(self):
        """Test creating an analytics metric"""
        metric = AnalyticsMetric(
            metric_name="api.response_time",
            metric_type="gauge",
            value=125.5,
            unit="ms",
            dimensions={"endpoint": "/api/puzzle", "method": "GET"}
        )
        
        assert metric.metric_name == "api.response_time"
        assert metric.metric_type == "gauge"
        assert metric.value == 125.5
        assert metric.unit == "ms"
        assert metric.dimensions["endpoint"] == "/api/puzzle"
    
    def test_metric_name_validation(self):
        """Test metric name validation"""
        # Valid names
        valid_names = ["api_response_time", "user.count", "cache_hit_rate"]
        for name in valid_names:
            metric = AnalyticsMetric(
                metric_name=name,
                metric_type="gauge",
                value=100
            )
            assert metric.metric_name == name
        
        # Invalid names
        with pytest.raises(ValueError, match="Metric name cannot be empty"):
            AnalyticsMetric(
                metric_name="",
                metric_type="gauge",
                value=100
            )
        
        with pytest.raises(ValueError, match="can only contain letters, numbers, underscores, and dots"):
            AnalyticsMetric(
                metric_name="api-response-time!",
                metric_type="gauge",
                value=100
            )


class TestSystemHealthMetrics:
    """Test system health metrics model"""
    
    def test_create_health_metrics(self):
        """Test creating system health metrics"""
        metrics = SystemHealthMetrics(
            api_response_time_p95=150.0,
            api_error_rate=0.01,
            cache_hit_rate=0.85,
            memory_usage_percentage=65.0,
            cpu_usage_percentage=45.0
        )
        
        assert metrics.api_response_time_p95 == 150.0
        assert metrics.api_error_rate == 0.01
        assert metrics.cache_hit_rate == 0.85
    
    def test_health_score_calculation(self):
        """Test overall health score calculation"""
        # Good health metrics
        good_metrics = SystemHealthMetrics(
            api_response_time_p95=100.0,  # Good response time
            api_error_rate=0.001,         # Low error rate
            cache_hit_rate=0.95,          # High cache hit rate
            memory_usage_percentage=30.0, # Low memory usage
            cpu_usage_percentage=25.0     # Low CPU usage
        )
        
        health_score = good_metrics.get_overall_health_score()
        assert health_score > 0.8  # Should be high
        
        # Poor health metrics
        poor_metrics = SystemHealthMetrics(
            api_response_time_p95=2000.0,  # Poor response time
            api_error_rate=0.1,            # High error rate
            cache_hit_rate=0.3,            # Low cache hit rate
            memory_usage_percentage=90.0,  # High memory usage
            cpu_usage_percentage=95.0      # High CPU usage
        )
        
        health_score = poor_metrics.get_overall_health_score()
        assert health_score < 0.5  # Should be low


class TestAlertRule:
    """Test alert rule model"""
    
    def test_create_alert_rule(self):
        """Test creating an alert rule"""
        rule = AlertRule(
            name="High Error Rate",
            description="Alert when API error rate exceeds 5%",
            metric_name="api.error_rate",
            condition="gt",
            threshold=0.05,
            severity=AuditSeverity.ERROR,
            created_by="admin-123"
        )
        
        assert rule.name == "High Error Rate"
        assert rule.condition == "gt"
        assert rule.threshold == 0.05
        assert rule.is_active is True
    
    def test_alert_triggering(self):
        """Test alert rule triggering logic"""
        rule = AlertRule(
            name="High Response Time",
            description="Alert when response time exceeds 1000ms",
            metric_name="api.response_time",
            condition="gt",
            threshold=1000.0,
            created_by="admin-123"
        )
        
        # Should trigger
        assert rule.should_trigger(1500.0) is True
        assert rule.should_trigger(1000.1) is True
        
        # Should not trigger
        assert rule.should_trigger(999.0) is False
        assert rule.should_trigger(1000.0) is False
        
        # Test different conditions
        rule.condition = "lt"
        assert rule.should_trigger(500.0) is True
        assert rule.should_trigger(1500.0) is False
        
        rule.condition = "eq"
        assert rule.should_trigger(1000.0) is True
        assert rule.should_trigger(999.0) is False
    
    def test_alert_cooldown(self):
        """Test alert cooldown logic"""
        rule = AlertRule(
            name="Test Alert",
            description="Test alert",
            metric_name="test.metric",
            condition="gt",
            threshold=100.0,
            cooldown_minutes=15,
            created_by="admin-123"
        )
        
        # First trigger should work
        assert rule.should_trigger(150.0) is True
        
        # Set last triggered to now
        rule.last_triggered = datetime.utcnow()
        
        # Should not trigger due to cooldown
        assert rule.should_trigger(150.0) is False
        
        # Should trigger after cooldown period
        rule.last_triggered = datetime.utcnow() - timedelta(minutes=16)
        assert rule.should_trigger(150.0) is True
    
    def test_inactive_alert_rule(self):
        """Test inactive alert rule"""
        rule = AlertRule(
            name="Inactive Alert",
            description="This alert is inactive",
            metric_name="test.metric",
            condition="gt",
            threshold=100.0,
            is_active=False,
            created_by="admin-123"
        )
        
        # Should not trigger when inactive
        assert rule.should_trigger(150.0) is False


class TestAlertEvent:
    """Test alert event model"""
    
    def test_create_alert_event(self):
        """Test creating an alert event"""
        event = AlertEvent(
            alert_rule_id="rule-123",
            metric_name="api.error_rate",
            metric_value=0.08,
            threshold=0.05,
            condition="gt",
            severity=AuditSeverity.ERROR,
            message="API error rate exceeded threshold"
        )
        
        assert event.alert_rule_id == "rule-123"
        assert event.metric_value == 0.08
        assert event.threshold == 0.05
        assert event.resolved is False
    
    def test_resolve_alert(self):
        """Test resolving an alert event"""
        event = AlertEvent(
            alert_rule_id="rule-123",
            metric_name="api.error_rate",
            metric_value=0.08,
            threshold=0.05,
            condition="gt",
            severity=AuditSeverity.ERROR,
            message="API error rate exceeded threshold"
        )
        
        # Resolve the alert
        event.resolve("admin-456", "Error rate returned to normal")
        
        assert event.resolved is True
        assert event.resolved_by == "admin-456"
        assert event.resolution_notes == "Error rate returned to normal"
        assert event.resolved_at is not None


class TestAnalyticsService:
    """Test analytics service"""
    
    @pytest.fixture
    def mock_analytics_repo(self):
        """Mock analytics repository"""
        return Mock()
    
    @pytest.fixture
    def analytics_service(self, mock_analytics_repo):
        """Create analytics service with mocked dependencies"""
        service = AnalyticsService()
        service.analytics_repo = mock_analytics_repo
        return service
    
    @pytest.mark.asyncio
    async def test_log_audit_event(self, analytics_service, mock_analytics_repo):
        """Test logging an audit event"""
        mock_event = AuditEvent(
            event_type=AuditEventType.USER_LOGIN,
            description="User logged in",
            user_id="user-123"
        )
        mock_analytics_repo.create_audit_event.return_value = mock_event
        
        event = await analytics_service.log_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            description="User logged in",
            user_id="user-123",
            ip_address="192.168.1.1"
        )
        
        assert event.event_type == AuditEventType.USER_LOGIN
        assert event.description == "User logged in"
        mock_analytics_repo.create_audit_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_audit_events(self, analytics_service, mock_analytics_repo):
        """Test getting audit events"""
        mock_events = [
            AuditEvent(
                event_type=AuditEventType.USER_LOGIN,
                description="User logged in",
                user_id="user-123"
            ),
            AuditEvent(
                event_type=AuditEventType.PUZZLE_SOLVED,
                description="User solved puzzle",
                user_id="user-123"
            )
        ]
        mock_analytics_repo.get_audit_events.return_value = mock_events
        
        events = await analytics_service.get_audit_events(
            user_id="user-123",
            limit=10
        )
        
        assert len(events) == 2
        assert events[0].event_type == AuditEventType.USER_LOGIN
        mock_analytics_repo.get_audit_events.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_audit_event_summary(self, analytics_service, mock_analytics_repo):
        """Test getting audit event summary"""
        mock_events = [
            AuditEvent(
                event_type=AuditEventType.USER_LOGIN,
                description="User logged in",
                user_id="user-123",
                success=True
            ),
            AuditEvent(
                event_type=AuditEventType.USER_LOGIN,
                description="Failed login",
                user_id="user-456",
                success=False,
                error_message="Invalid credentials"
            ),
            AuditEvent(
                event_type=AuditEventType.PUZZLE_SOLVED,
                description="User solved puzzle",
                user_id="user-123",
                success=True
            )
        ]
        mock_analytics_repo.get_audit_events.return_value = mock_events
        
        summary = await analytics_service.get_audit_event_summary(
            date(2024, 1, 1),
            date(2024, 1, 31)
        )
        
        assert summary["total_events"] == 3
        assert summary["by_type"]["user_login"] == 2
        assert summary["by_type"]["puzzle_solved"] == 1
        assert summary["by_success"]["success"] == 2
        assert summary["by_success"]["failure"] == 1
        assert len(summary["error_events"]) == 1
        assert summary["error_events"][0]["error_message"] == "Invalid credentials"
    
    @pytest.mark.asyncio
    async def test_create_data_export_request(self, analytics_service, mock_analytics_repo):
        """Test creating data export request"""
        mock_export = DataExportRequest(
            export_type="audit_events",
            requested_by="admin-123"
        )
        mock_analytics_repo.create_data_export_request.return_value = mock_export
        
        with patch.object(analytics_service, '_process_export_request', new_callable=AsyncMock):
            export_request = await analytics_service.create_data_export_request(
                export_type="audit_events",
                requested_by="admin-123",
                format="json"
            )
        
        assert export_request.export_type == "audit_events"
        assert export_request.requested_by == "admin-123"
        mock_analytics_repo.create_data_export_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_record_metric(self, analytics_service, mock_analytics_repo):
        """Test recording an analytics metric"""
        mock_metric = AnalyticsMetric(
            metric_name="api.response_time",
            metric_type="gauge",
            value=125.5
        )
        mock_analytics_repo.create_analytics_metric.return_value = mock_metric
        
        metric = await analytics_service.record_metric(
            metric_name="api.response_time",
            value=125.5,
            unit="ms"
        )
        
        assert metric.metric_name == "api.response_time"
        assert metric.value == 125.5
        mock_analytics_repo.create_analytics_metric.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_operational_report(self, analytics_service, mock_analytics_repo):
        """Test generating operational report"""
        mock_report = OperationalReport(
            report_name="User Activity Report",
            report_type="user_activity",
            generated_by="admin-123",
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 31)
        )
        mock_analytics_repo.create_operational_report.return_value = mock_report
        mock_analytics_repo.get_audit_events.return_value = []
        
        with patch.object(analytics_service, 'get_audit_event_summary', return_value={"total_events": 0}):
            report = await analytics_service.generate_operational_report(
                report_type="user_activity",
                generated_by="admin-123",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
        
        assert report.report_type == "user_activity"
        assert report.generated_by == "admin-123"
        mock_analytics_repo.create_operational_report.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_audit_events(self, analytics_service, mock_analytics_repo):
        """Test cleaning up old audit events"""
        mock_analytics_repo.delete_audit_events_before.return_value = 150
        mock_analytics_repo.create_audit_event.return_value = Mock()
        
        deleted_count = await analytics_service.cleanup_old_audit_events(days_to_keep=90)
        
        assert deleted_count == 150
        mock_analytics_repo.delete_audit_events_before.assert_called_once()
        mock_analytics_repo.create_audit_event.assert_called_once()  # Cleanup log event


class TestOperationalReport:
    """Test operational report model"""
    
    def test_create_operational_report(self):
        """Test creating an operational report"""
        report = OperationalReport(
            report_name="User Activity Report",
            report_type="user_activity",
            generated_by="admin-123",
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 31)
        )
        
        assert report.report_name == "User Activity Report"
        assert report.report_type == "user_activity"
        assert report.generated_by == "admin-123"
        assert len(report.sections) == 0
        assert len(report.charts) == 0
    
    def test_add_section(self):
        """Test adding sections to report"""
        report = OperationalReport(
            report_name="Test Report",
            report_type="test",
            generated_by="admin-123",
            date_range_start=date(2024, 1, 1),
            date_range_end=date(2024, 1, 31)
        )
        
        # Add section without chart
        report.add_section("Summary", {"total": 100, "active": 75})
        
        assert len(report.sections) == 1
        assert report.sections[0]["title"] == "Summary"
        assert report.sections[0]["data"]["total"] == 100
        assert len(report.charts) == 0
        
        # Add section with chart
        report.add_section("Trends", {"daily": [10, 15, 20]}, "line")
        
        assert len(report.sections) == 2
        assert len(report.charts) == 1
        assert report.charts[0]["type"] == "line"
        assert report.charts[0]["title"] == "Trends"


if __name__ == "__main__":
    pytest.main([__file__])