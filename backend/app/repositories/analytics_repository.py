"""Repository for analytics and audit data operations"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from app.repositories.base import BaseRepository
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
from app.config import settings
from app.database.exceptions import ItemNotFoundError

logger = logging.getLogger(__name__)


class AnalyticsRepository(BaseRepository):
    """Repository for analytics and audit operations"""
    
    def __init__(self):
        # Use the governance container for analytics data
        super().__init__(settings.cosmos_container_governance)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key"""
        return 'id' in item and item['id'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item"""
        item['id'] = partition_key
        return item
    
    # Audit Event operations
    
    async def create_audit_event(self, event: AuditEvent) -> AuditEvent:
        """Create an audit event"""
        event_dict = event.model_dump()
        event_dict['document_type'] = 'audit_event'
        
        result = await self.create(event_dict, event.id)
        return AuditEvent(**result)
    
    async def get_audit_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get audit event by ID"""
        result = await self.get_by_id(event_id, event_id)
        if result and result.get('document_type') == 'audit_event':
            return AuditEvent(**result)
        return None
    
    async def get_audit_events(self, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None,
                             event_types: Optional[List[AuditEventType]] = None,
                             user_id: Optional[str] = None,
                             admin_id: Optional[str] = None,
                             severity: Optional[AuditSeverity] = None,
                             limit: int = 100, offset: int = 0) -> List[AuditEvent]:
        """Get audit events with filtering"""
        conditions = ["c.document_type = 'audit_event'"]
        parameters = []
        
        if start_date:
            conditions.append("c.timestamp >= @start_date")
            parameters.append({"name": "@start_date", "value": start_date.isoformat()})
        
        if end_date:
            conditions.append("c.timestamp <= @end_date")
            parameters.append({"name": "@end_date", "value": end_date.isoformat()})
        
        if event_types:
            event_type_values = [et.value for et in event_types]
            conditions.append("c.event_type IN (@event_types)")
            parameters.append({"name": "@event_types", "value": event_type_values})
        
        if user_id:
            conditions.append("c.user_id = @user_id")
            parameters.append({"name": "@user_id", "value": user_id})
        
        if admin_id:
            conditions.append("c.admin_id = @admin_id")
            parameters.append({"name": "@admin_id", "value": admin_id})
        
        if severity:
            conditions.append("c.severity = @severity")
            parameters.append({"name": "@severity", "value": severity.value})
        
        parameters.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit}
        ])
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.timestamp DESC
        OFFSET @offset LIMIT @limit
        """
        
        results = await self.query(query, parameters)
        return [AuditEvent(**result) for result in results]
    
    async def delete_audit_events_before(self, cutoff_date: datetime) -> int:
        """Delete audit events before a certain date"""
        query = """
        SELECT c.id FROM c 
        WHERE c.document_type = 'audit_event'
        AND c.timestamp < @cutoff_date
        """
        parameters = [{"name": "@cutoff_date", "value": cutoff_date.isoformat()}]
        
        old_events = await self.query(query, parameters)
        
        deleted_count = 0
        for event in old_events:
            if await self.delete(event['id'], event['id']):
                deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} old audit events")
        return deleted_count
    
    # Data Export Request operations
    
    async def create_data_export_request(self, export_request: DataExportRequest) -> DataExportRequest:
        """Create a data export request"""
        export_dict = export_request.model_dump()
        export_dict['document_type'] = 'data_export_request'
        
        result = await self.create(export_dict, export_request.id)
        return DataExportRequest(**result)
    
    async def get_data_export_request(self, request_id: str) -> Optional[DataExportRequest]:
        """Get data export request by ID"""
        result = await self.get_by_id(request_id, request_id)
        if result and result.get('document_type') == 'data_export_request':
            return DataExportRequest(**result)
        return None
    
    async def update_data_export_request(self, export_request: DataExportRequest) -> DataExportRequest:
        """Update data export request"""
        export_dict = export_request.model_dump()
        export_dict['document_type'] = 'data_export_request'
        
        result = await self.update(export_dict, export_request.id)
        return DataExportRequest(**result)
    
    async def get_data_export_requests(self, requested_by: Optional[str] = None,
                                     status: Optional[str] = None,
                                     limit: int = 50) -> List[DataExportRequest]:
        """Get data export requests with filtering"""
        conditions = ["c.document_type = 'data_export_request'"]
        parameters = []
        
        if requested_by:
            conditions.append("c.requested_by = @requested_by")
            parameters.append({"name": "@requested_by", "value": requested_by})
        
        if status:
            conditions.append("c.status = @status")
            parameters.append({"name": "@status", "value": status})
        
        parameters.append({"name": "@limit", "value": limit})
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.requested_at DESC
        OFFSET 0 LIMIT @limit
        """
        
        results = await self.query(query, parameters)
        return [DataExportRequest(**result) for result in results]
    
    async def get_expired_data_exports(self) -> List[DataExportRequest]:
        """Get expired data export requests"""
        query = """
        SELECT * FROM c 
        WHERE c.document_type = 'data_export_request'
        AND c.expires_at < @now
        """
        parameters = [{"name": "@now", "value": datetime.utcnow().isoformat()}]
        
        results = await self.query(query, parameters)
        return [DataExportRequest(**result) for result in results]
    
    async def delete_data_export_request(self, request_id: str) -> bool:
        """Delete data export request"""
        return await self.delete(request_id, request_id)
    
    # Analytics Metric operations
    
    async def create_analytics_metric(self, metric: AnalyticsMetric) -> AnalyticsMetric:
        """Create an analytics metric"""
        metric_dict = metric.model_dump()
        metric_dict['document_type'] = 'analytics_metric'
        
        result = await self.create(metric_dict, metric.id)
        return AnalyticsMetric(**result)
    
    async def get_analytics_metrics(self, metric_name: Optional[str] = None,
                                  start_time: Optional[datetime] = None,
                                  end_time: Optional[datetime] = None,
                                  dimensions: Optional[Dict[str, str]] = None,
                                  limit: int = 1000) -> List[AnalyticsMetric]:
        """Get analytics metrics with filtering"""
        conditions = ["c.document_type = 'analytics_metric'"]
        parameters = []
        
        if metric_name:
            conditions.append("c.metric_name = @metric_name")
            parameters.append({"name": "@metric_name", "value": metric_name})
        
        if start_time:
            conditions.append("c.timestamp >= @start_time")
            parameters.append({"name": "@start_time", "value": start_time.isoformat()})
        
        if end_time:
            conditions.append("c.timestamp <= @end_time")
            parameters.append({"name": "@end_time", "value": end_time.isoformat()})
        
        # Note: Cosmos DB doesn't have great support for nested object queries
        # In production, you might want to flatten dimensions or use a different approach
        if dimensions:
            for key, value in dimensions.items():
                conditions.append(f"c.dimensions.{key} = @dim_{key}")
                parameters.append({"name": f"@dim_{key}", "value": value})
        
        parameters.append({"name": "@limit", "value": limit})
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.timestamp DESC
        OFFSET 0 LIMIT @limit
        """
        
        results = await self.query(query, parameters)
        return [AnalyticsMetric(**result) for result in results]
    
    async def delete_analytics_metrics_before(self, cutoff_date: datetime) -> int:
        """Delete analytics metrics before a certain date"""
        query = """
        SELECT c.id FROM c 
        WHERE c.document_type = 'analytics_metric'
        AND c.timestamp < @cutoff_date
        """
        parameters = [{"name": "@cutoff_date", "value": cutoff_date.isoformat()}]
        
        old_metrics = await self.query(query, parameters)
        
        deleted_count = 0
        for metric in old_metrics:
            if await self.delete(metric['id'], metric['id']):
                deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} old analytics metrics")
        return deleted_count
    
    # Operational Report operations
    
    async def create_operational_report(self, report: OperationalReport) -> OperationalReport:
        """Create an operational report"""
        report_dict = report.model_dump()
        report_dict['document_type'] = 'operational_report'
        
        result = await self.create(report_dict, report.id)
        return OperationalReport(**result)
    
    async def get_operational_report(self, report_id: str) -> Optional[OperationalReport]:
        """Get operational report by ID"""
        result = await self.get_by_id(report_id, report_id)
        if result and result.get('document_type') == 'operational_report':
            return OperationalReport(**result)
        return None
    
    async def get_operational_reports(self, generated_by: Optional[str] = None,
                                    report_type: Optional[str] = None,
                                    limit: int = 50) -> List[OperationalReport]:
        """Get operational reports with filtering"""
        conditions = ["c.document_type = 'operational_report'"]
        parameters = []
        
        if generated_by:
            conditions.append("c.generated_by = @generated_by")
            parameters.append({"name": "@generated_by", "value": generated_by})
        
        if report_type:
            conditions.append("c.report_type = @report_type")
            parameters.append({"name": "@report_type", "value": report_type})
        
        parameters.append({"name": "@limit", "value": limit})
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.generated_at DESC
        OFFSET 0 LIMIT @limit
        """
        
        results = await self.query(query, parameters)
        return [OperationalReport(**result) for result in results]
    
    async def delete_operational_report(self, report_id: str) -> bool:
        """Delete operational report"""
        return await self.delete(report_id, report_id)
    
    # User Activity Summary operations
    
    async def create_user_activity_summary(self, summary: UserActivitySummary) -> UserActivitySummary:
        """Create a user activity summary"""
        summary_dict = summary.model_dump()
        summary_dict['document_type'] = 'user_activity_summary'
        summary_dict['id'] = f"{summary.date.isoformat()}_{summary.universe}"
        
        result = await self.create(summary_dict, summary_dict['id'])
        return UserActivitySummary(**result)
    
    async def get_user_activity_summaries(self, start_date: date, end_date: date,
                                        universe: Optional[str] = None) -> List[UserActivitySummary]:
        """Get user activity summaries for a date range"""
        conditions = ["c.document_type = 'user_activity_summary'"]
        parameters = []
        
        conditions.append("c.date >= @start_date")
        parameters.append({"name": "@start_date", "value": start_date.isoformat()})
        
        conditions.append("c.date <= @end_date")
        parameters.append({"name": "@end_date", "value": end_date.isoformat()})
        
        if universe:
            conditions.append("c.universe = @universe")
            parameters.append({"name": "@universe", "value": universe})
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.date DESC, c.universe
        """
        
        results = await self.query(query, parameters)
        return [UserActivitySummary(**result) for result in results]
    
    # System Health Metrics operations
    
    async def create_system_health_metrics(self, metrics: SystemHealthMetrics) -> SystemHealthMetrics:
        """Create system health metrics"""
        metrics_dict = metrics.model_dump()
        metrics_dict['document_type'] = 'system_health_metrics'
        metrics_dict['id'] = f"health_{metrics.timestamp.isoformat()}"
        
        result = await self.create(metrics_dict, metrics_dict['id'])
        return SystemHealthMetrics(**result)
    
    async def get_system_health_metrics(self, start_date: date, end_date: date,
                                      limit: int = 1000) -> List[SystemHealthMetrics]:
        """Get system health metrics for a date range"""
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        query = """
        SELECT * FROM c 
        WHERE c.document_type = 'system_health_metrics'
        AND c.timestamp >= @start_date
        AND c.timestamp <= @end_date
        ORDER BY c.timestamp DESC
        OFFSET 0 LIMIT @limit
        """
        
        parameters = [
            {"name": "@start_date", "value": start_datetime.isoformat()},
            {"name": "@end_date", "value": end_datetime.isoformat()},
            {"name": "@limit", "value": limit}
        ]
        
        results = await self.query(query, parameters)
        return [SystemHealthMetrics(**result) for result in results]
    
    # Alert Rule operations
    
    async def create_alert_rule(self, rule: AlertRule) -> AlertRule:
        """Create an alert rule"""
        rule_dict = rule.model_dump()
        rule_dict['document_type'] = 'alert_rule'
        
        result = await self.create(rule_dict, rule.id)
        return AlertRule(**result)
    
    async def get_alert_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get alert rule by ID"""
        result = await self.get_by_id(rule_id, rule_id)
        if result and result.get('document_type') == 'alert_rule':
            return AlertRule(**result)
        return None
    
    async def get_active_alert_rules(self) -> List[AlertRule]:
        """Get all active alert rules"""
        query = """
        SELECT * FROM c 
        WHERE c.document_type = 'alert_rule'
        AND c.is_active = true
        ORDER BY c.name
        """
        
        results = await self.query(query)
        return [AlertRule(**result) for result in results]
    
    async def update_alert_rule(self, rule: AlertRule) -> AlertRule:
        """Update alert rule"""
        rule_dict = rule.model_dump()
        rule_dict['document_type'] = 'alert_rule'
        
        result = await self.update(rule_dict, rule.id)
        return AlertRule(**result)
    
    # Alert Event operations
    
    async def create_alert_event(self, event: AlertEvent) -> AlertEvent:
        """Create an alert event"""
        event_dict = event.model_dump()
        event_dict['document_type'] = 'alert_event'
        
        result = await self.create(event_dict, event.id)
        return AlertEvent(**result)
    
    async def get_alert_events(self, alert_rule_id: Optional[str] = None,
                             resolved: Optional[bool] = None,
                             limit: int = 100) -> List[AlertEvent]:
        """Get alert events with filtering"""
        conditions = ["c.document_type = 'alert_event'"]
        parameters = []
        
        if alert_rule_id:
            conditions.append("c.alert_rule_id = @alert_rule_id")
            parameters.append({"name": "@alert_rule_id", "value": alert_rule_id})
        
        if resolved is not None:
            conditions.append("c.resolved = @resolved")
            parameters.append({"name": "@resolved", "value": resolved})
        
        parameters.append({"name": "@limit", "value": limit})
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.triggered_at DESC
        OFFSET 0 LIMIT @limit
        """
        
        results = await self.query(query, parameters)
        return [AlertEvent(**result) for result in results]
    
    async def update_alert_event(self, event: AlertEvent) -> AlertEvent:
        """Update alert event"""
        event_dict = event.model_dump()
        event_dict['document_type'] = 'alert_event'
        
        result = await self.update(event_dict, event.id)
        return AlertEvent(**result)
    
    # Statistics and cleanup
    
    async def get_analytics_statistics(self) -> Dict[str, Any]:
        """Get analytics statistics"""
        stats = {}
        
        # Count audit events by type
        query = """
        SELECT c.event_type, COUNT(1) as count
        FROM c 
        WHERE c.document_type = 'audit_event'
        GROUP BY c.event_type
        """
        results = await self.query(query)
        stats['audit_events_by_type'] = {r['event_type']: r['count'] for r in results}
        
        # Count data export requests by status
        query = """
        SELECT c.status, COUNT(1) as count
        FROM c 
        WHERE c.document_type = 'data_export_request'
        GROUP BY c.status
        """
        results = await self.query(query)
        stats['export_requests_by_status'] = {r['status']: r['count'] for r in results}
        
        # Count operational reports by type
        query = """
        SELECT c.report_type, COUNT(1) as count
        FROM c 
        WHERE c.document_type = 'operational_report'
        GROUP BY c.report_type
        """
        results = await self.query(query)
        stats['reports_by_type'] = {r['report_type']: r['count'] for r in results}
        
        return stats