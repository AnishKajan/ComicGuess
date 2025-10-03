"""
Error tracking and alerting system for ComicGuess application.
Provides structured error handling, alerting, and recovery mechanisms.
"""

import logging
import traceback
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from functools import wraps

from .logging_config import get_logger, get_correlation_id, metrics

# Configure error tracking logger with appropriate levels
error_logger = logging.getLogger(__name__)
error_logger.setLevel(logging.ERROR)  # Set minimum level for error tracking

class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for classification."""
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    NETWORK = "network"
    STORAGE = "storage"

@dataclass
class ErrorContext:
    """Context information for errors."""
    user_id: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

@dataclass
class ErrorEvent:
    """Structured error event."""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception_type: str
    stack_trace: List[str]
    correlation_id: Optional[str]
    context: Optional[ErrorContext]
    resolved: bool = False
    resolution_notes: Optional[str] = None

class ErrorTracker:
    """Central error tracking and alerting system."""
    
    def __init__(self):
        self.logger = get_logger("error_tracker")
        self.error_counts: Dict[str, int] = {}
        self.recent_errors: List[ErrorEvent] = []
        self.max_recent_errors = 1000
    
    def track_error(
        self,
        exception: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        context: Optional[ErrorContext] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track an error event.
        
        Args:
            exception: The exception that occurred
            severity: Error severity level
            category: Error category
            context: Request/user context
            additional_info: Additional error information
            
        Returns:
            Error ID for tracking
        """
        import uuid
        
        error_id = str(uuid.uuid4())
        correlation_id = get_correlation_id()
        
        # Create error event
        error_event = ErrorEvent(
            error_id=error_id,
            timestamp=datetime.utcnow(),
            severity=severity,
            category=category,
            message=str(exception),
            exception_type=type(exception).__name__,
            stack_trace=traceback.format_exception(type(exception), exception, exception.__traceback__),
            correlation_id=correlation_id,
            context=context
        )
        
        # Add to recent errors
        self.recent_errors.append(error_event)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
        
        # Update error counts
        error_key = f"{category.value}:{type(exception).__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Log structured error
        self.logger.error(
            f"Error tracked: {exception}",
            extra={
                'error_id': error_id,
                'severity': severity.value,
                'category': category.value,
                'exception_type': type(exception).__name__,
                'correlation_id': correlation_id,
                'context': asdict(context) if context else None,
                'additional_info': additional_info,
                'stack_trace': error_event.stack_trace
            }
        )
        
        # Record metrics
        metrics.increment_counter(
            'errors_total',
            tags={
                'severity': severity.value,
                'category': category.value,
                'exception_type': type(exception).__name__
            }
        )
        
        # Check for alerting conditions
        self._check_alerting_conditions(error_event)
        
        return error_id
    
    def _check_alerting_conditions(self, error_event: ErrorEvent):
        """Check if error conditions warrant alerting."""
        
        # Critical errors always trigger alerts
        if error_event.severity == ErrorSeverity.CRITICAL:
            self._send_alert(error_event, "Critical error occurred")
        
        # Check for error rate spikes
        recent_errors_count = len([
            e for e in self.recent_errors 
            if e.timestamp > datetime.utcnow() - timedelta(minutes=5)
        ])
        
        if recent_errors_count > 10:  # More than 10 errors in 5 minutes
            self._send_alert(error_event, f"High error rate: {recent_errors_count} errors in 5 minutes")
        
        # Check for repeated errors
        error_key = f"{error_event.category.value}:{error_event.exception_type}"
        if self.error_counts.get(error_key, 0) > 5:  # Same error type more than 5 times
            self._send_alert(error_event, f"Repeated error: {error_key} occurred {self.error_counts[error_key]} times")
    
    def _send_alert(self, error_event: ErrorEvent, alert_message: str):
        """Send alert for error condition."""
        self.logger.critical(
            f"ALERT: {alert_message}",
            extra={
                'alert_type': 'error_condition',
                'error_id': error_event.error_id,
                'severity': error_event.severity.value,
                'category': error_event.category.value,
                'message': alert_message
            }
        )
        
        # In production, this would integrate with alerting systems like:
        # - PagerDuty
        # - Slack webhooks
        # - Email notifications
        # - SMS alerts
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_errors = [e for e in self.recent_errors if e.timestamp > cutoff_time]
        
        # Group by category and severity
        by_category = {}
        by_severity = {}
        
        for error in recent_errors:
            category = error.category.value
            severity = error.severity.value
            
            by_category[category] = by_category.get(category, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            'total_errors': len(recent_errors),
            'by_category': by_category,
            'by_severity': by_severity,
            'error_rate': len(recent_errors) / hours,  # errors per hour
            'most_common_errors': dict(sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }

# Global error tracker instance
error_tracker = ErrorTracker()

def track_errors(
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.SYSTEM,
    reraise: bool = True
):
    """
    Decorator to automatically track errors in functions.
    
    Args:
        severity: Default error severity
        category: Error category
        reraise: Whether to reraise the exception after tracking
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_tracker.track_error(e, severity, category)
                if reraise:
                    raise
                return None
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_tracker.track_error(e, severity, category)
                if reraise:
                    raise
                return None
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class HealthChecker:
    """Application health monitoring."""
    
    def __init__(self):
        self.logger = get_logger("health_checker")
        self.checks: Dict[str, callable] = {}
    
    def register_check(self, name: str, check_func: callable):
        """Register a health check function."""
        self.checks[name] = check_func
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                results[name] = {
                    'status': 'healthy' if result else 'unhealthy',
                    'details': result if isinstance(result, dict) else {}
                }
                
                if not result:
                    overall_healthy = False
                    
            except Exception as e:
                results[name] = {
                    'status': 'error',
                    'error': str(e)
                }
                overall_healthy = False
                
                error_tracker.track_error(
                    e,
                    ErrorSeverity.HIGH,
                    ErrorCategory.SYSTEM,
                    additional_info={'health_check': name}
                )
        
        return {
            'overall_status': 'healthy' if overall_healthy else 'unhealthy',
            'checks': results,
            'timestamp': datetime.utcnow().isoformat()
        }

# Global health checker instance
health_checker = HealthChecker()