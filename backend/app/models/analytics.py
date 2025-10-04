"""Analytics and operational audit models"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
from enum import Enum
import uuid


class AuditEventType(str, Enum):
    """Types of audit events"""
    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    
    # Game actions
    PUZZLE_GUESS = "puzzle_guess"
    PUZZLE_SOLVED = "puzzle_solved"
    PUZZLE_FAILED = "puzzle_failed"
    
    # Admin actions
    ADMIN_LOGIN = "admin_login"
    ADMIN_ACTION = "admin_action"
    PUZZLE_HOTFIX = "puzzle_hotfix"
    CONTENT_APPROVED = "content_approved"
    CONTENT_REJECTED = "content_rejected"
    
    # System events
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    RATE_LIMIT_HIT = "rate_limit_hit"
    CACHE_MISS = "cache_miss"
    
    # Data operations
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    DATA_BACKUP = "data_backup"
    DATA_RESTORE = "data_restore"


class AuditSeverity(str, Enum):
    """Audit event severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """Comprehensive audit event model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: AuditEventType = Field(...)
    severity: AuditSeverity = Field(default=AuditSeverity.INFO)
    
    # Actor information
    user_id: Optional[str] = None
    admin_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    
    # Event details
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    description: str = Field(...)
    
    # Additional data
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Outcome
    success: bool = Field(default=True)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Performance metrics
    duration_ms: Optional[int] = None
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Ensure description is not empty"""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()


class DataExportRequest(BaseModel):
    """Data export request model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requested_by: str = Field(..., description="Admin ID who requested export")
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Export parameters
    export_type: str = Field(..., description="Type of data to export")
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    format: str = Field(default="json", pattern="^(json|csv|xlsx)$")
    
    # Status
    status: str = Field(default="pending", pattern="^(pending|processing|completed|failed)$")
    progress_percentage: int = Field(default=0, ge=0, le=100)
    
    # Results
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    record_count: Optional[int] = None
    
    # Completion info
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Security
    expires_at: Optional[datetime] = None
    download_count: int = Field(default=0)
    max_downloads: int = Field(default=5)
    
    def is_expired(self) -> bool:
        """Check if export has expired"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    def can_download(self) -> bool:
        """Check if export can still be downloaded"""
        return (
            self.status == "completed" and
            not self.is_expired() and
            self.download_count < self.max_downloads
        )


class AnalyticsMetric(BaseModel):
    """Analytics metric model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = Field(...)
    metric_type: str = Field(..., description="counter, gauge, histogram, etc.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Metric value
    value: Union[int, float] = Field(...)
    unit: Optional[str] = None
    
    # Dimensions/tags
    dimensions: Dict[str, str] = Field(default_factory=dict)
    
    # Aggregation period
    period: Optional[str] = None  # "1m", "5m", "1h", "1d", etc.
    
    @field_validator('metric_name')
    @classmethod
    def validate_metric_name(cls, v):
        """Validate metric name format"""
        if not v or not v.strip():
            raise ValueError("Metric name cannot be empty")
        
        # Basic validation for metric naming convention
        if not v.replace("_", "").replace(".", "").isalnum():
            raise ValueError("Metric name can only contain letters, numbers, underscores, and dots")
        
        return v.strip()


class OperationalReport(BaseModel):
    """Operational report model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_name: str = Field(...)
    report_type: str = Field(..., description="Type of operational report")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = Field(..., description="Admin ID who generated report")
    
    # Report parameters
    date_range_start: date = Field(...)
    date_range_end: date = Field(...)
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # Report data
    summary: Dict[str, Any] = Field(default_factory=dict)
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Metadata
    total_records: int = Field(default=0)
    processing_time_ms: Optional[int] = None
    
    def add_section(self, title: str, data: Dict[str, Any], chart_type: Optional[str] = None):
        """Add a section to the report"""
        section = {
            "title": title,
            "data": data,
            "order": len(self.sections)
        }
        self.sections.append(section)
        
        if chart_type:
            chart = {
                "title": title,
                "type": chart_type,
                "data": data,
                "section_index": len(self.sections) - 1
            }
            self.charts.append(chart)


class UserActivitySummary(BaseModel):
    """User activity summary for analytics"""
    date: date = Field(...)
    universe: str = Field(..., pattern="^(marvel|dc|image|all)$")
    
    # User metrics
    total_users: int = Field(default=0)
    active_users: int = Field(default=0)
    new_users: int = Field(default=0)
    returning_users: int = Field(default=0)
    
    # Game metrics
    total_games: int = Field(default=0)
    successful_games: int = Field(default=0)
    failed_games: int = Field(default=0)
    average_attempts: float = Field(default=0.0)
    
    # Engagement metrics
    average_session_duration_minutes: float = Field(default=0.0)
    bounce_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Performance metrics
    average_response_time_ms: float = Field(default=0.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class SystemHealthMetrics(BaseModel):
    """System health metrics"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # API metrics
    api_response_time_p50: float = Field(default=0.0)
    api_response_time_p95: float = Field(default=0.0)
    api_response_time_p99: float = Field(default=0.0)
    api_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    api_requests_per_minute: int = Field(default=0)
    
    # Database metrics
    db_connection_pool_usage: float = Field(default=0.0, ge=0.0, le=1.0)
    db_query_time_avg_ms: float = Field(default=0.0)
    db_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Storage metrics
    blob_storage_requests_per_minute: int = Field(default=0)
    blob_storage_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    blob_storage_avg_response_time_ms: float = Field(default=0.0)
    
    # Cache metrics
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    cache_miss_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Resource utilization
    memory_usage_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    cpu_usage_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Rate limiting
    rate_limit_hits_per_minute: int = Field(default=0)
    
    def get_overall_health_score(self) -> float:
        """Calculate overall health score (0-1)"""
        # Simple health scoring based on key metrics
        scores = []
        
        # API health (lower response time and error rate is better)
        api_score = max(0, 1 - (self.api_response_time_p95 / 1000))  # Normalize to 1 second
        api_score *= (1 - self.api_error_rate)
        scores.append(api_score)
        
        # Database health
        db_score = max(0, 1 - (self.db_query_time_avg_ms / 500))  # Normalize to 500ms
        db_score *= (1 - self.db_error_rate)
        scores.append(db_score)
        
        # Cache health
        cache_score = self.cache_hit_rate
        scores.append(cache_score)
        
        # Resource health
        resource_score = 1 - max(self.memory_usage_percentage, self.cpu_usage_percentage) / 100
        scores.append(resource_score)
        
        return sum(scores) / len(scores) if scores else 0.0


class AlertRule(BaseModel):
    """Alert rule definition"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(...)
    description: str = Field(...)
    
    # Rule configuration
    metric_name: str = Field(...)
    condition: str = Field(..., pattern="^(gt|gte|lt|lte|eq|ne)$")  # greater than, less than, etc.
    threshold: Union[int, float] = Field(...)
    
    # Alert settings
    severity: AuditSeverity = Field(default=AuditSeverity.WARNING)
    is_active: bool = Field(default=True)
    
    # Notification settings
    notification_channels: List[str] = Field(default_factory=list)
    cooldown_minutes: int = Field(default=15, ge=1)
    
    # Metadata
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    trigger_count: int = Field(default=0)
    
    def should_trigger(self, metric_value: Union[int, float]) -> bool:
        """Check if alert should trigger based on metric value"""
        if not self.is_active:
            return False
        
        # Check cooldown
        if self.last_triggered:
            cooldown_delta = datetime.utcnow() - self.last_triggered
            if cooldown_delta.total_seconds() < (self.cooldown_minutes * 60):
                return False
        
        # Check condition
        if self.condition == "gt":
            return metric_value > self.threshold
        elif self.condition == "gte":
            return metric_value >= self.threshold
        elif self.condition == "lt":
            return metric_value < self.threshold
        elif self.condition == "lte":
            return metric_value <= self.threshold
        elif self.condition == "eq":
            return metric_value == self.threshold
        elif self.condition == "ne":
            return metric_value != self.threshold
        
        return False


class AlertEvent(BaseModel):
    """Alert event when rule is triggered"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_rule_id: str = Field(...)
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Alert details
    metric_name: str = Field(...)
    metric_value: Union[int, float] = Field(...)
    threshold: Union[int, float] = Field(...)
    condition: str = Field(...)
    severity: AuditSeverity = Field(...)
    
    # Context
    message: str = Field(...)
    additional_context: Dict[str, Any] = Field(default_factory=dict)
    
    # Resolution
    resolved: bool = Field(default=False)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    
    def resolve(self, resolved_by: str, notes: Optional[str] = None):
        """Mark alert as resolved"""
        self.resolved = True
        self.resolved_at = datetime.utcnow()
        self.resolved_by = resolved_by
        self.resolution_notes = notes