"""
Comprehensive metrics collection and SLO monitoring for ComicGuess application.
Provides detailed metrics for p95/p99 latency, error rates, cache hit rates, and rate-limit blocks.
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import statistics
import json
from datetime import datetime, timedelta

from .logging_config import get_logger

class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"

@dataclass
class MetricPoint:
    """Individual metric data point."""
    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class HistogramBucket:
    """Histogram bucket for latency measurements."""
    upper_bound: float
    count: int = 0

class Histogram:
    """Histogram for tracking latency distributions."""
    
    def __init__(self, buckets: List[float] = None):
        if buckets is None:
            # Default buckets for latency (in milliseconds)
            buckets = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
        
        self.buckets = [HistogramBucket(bound) for bound in sorted(buckets)]
        self.buckets.append(HistogramBucket(float('inf')))  # +Inf bucket
        self.sum = 0.0
        self.count = 0
        self.values = deque(maxlen=10000)  # Keep recent values for percentile calculation
    
    def observe(self, value: float):
        """Record a value in the histogram."""
        self.sum += value
        self.count += 1
        self.values.append(value)
        
        # Update buckets
        for bucket in self.buckets:
            if value <= bucket.upper_bound:
                bucket.count += 1
    
    def get_percentile(self, percentile: float) -> float:
        """Calculate percentile from recent values."""
        if not self.values:
            return 0.0
        
        sorted_values = sorted(self.values)
        index = int((percentile / 100.0) * len(sorted_values))
        if index >= len(sorted_values):
            index = len(sorted_values) - 1
        return sorted_values[index]
    
    def get_bucket_counts(self) -> List[Tuple[float, int]]:
        """Get bucket counts for histogram export."""
        return [(bucket.upper_bound, bucket.count) for bucket in self.buckets]

class Counter:
    """Counter metric for tracking totals."""
    
    def __init__(self):
        self.value = 0.0
        self.last_updated = time.time()
    
    def increment(self, amount: float = 1.0):
        """Increment the counter."""
        self.value += amount
        self.last_updated = time.time()
    
    def get_value(self) -> float:
        """Get current counter value."""
        return self.value

class Gauge:
    """Gauge metric for tracking current values."""
    
    def __init__(self):
        self.value = 0.0
        self.last_updated = time.time()
    
    def set(self, value: float):
        """Set the gauge value."""
        self.value = value
        self.last_updated = time.time()
    
    def increment(self, amount: float = 1.0):
        """Increment the gauge."""
        self.value += amount
        self.last_updated = time.time()
    
    def decrement(self, amount: float = 1.0):
        """Decrement the gauge."""
        self.value -= amount
        self.last_updated = time.time()
    
    def get_value(self) -> float:
        """Get current gauge value."""
        return self.value

class MetricsRegistry:
    """Registry for all application metrics."""
    
    def __init__(self):
        self.counters: Dict[str, Counter] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.logger = get_logger("metrics_registry")
    
    def get_counter(self, name: str) -> Counter:
        """Get or create a counter metric."""
        if name not in self.counters:
            self.counters[name] = Counter()
        return self.counters[name]
    
    def get_histogram(self, name: str, buckets: List[float] = None) -> Histogram:
        """Get or create a histogram metric."""
        if name not in self.histograms:
            self.histograms[name] = Histogram(buckets)
        return self.histograms[name]
    
    def get_gauge(self, name: str) -> Gauge:
        """Get or create a gauge metric."""
        if name not in self.gauges:
            self.gauges[name] = Gauge()
        return self.gauges[name]
    
    def increment_counter(self, name: str, amount: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter with optional tags."""
        metric_name = self._build_metric_name(name, tags)
        counter = self.get_counter(metric_name)
        counter.increment(amount)
    
    def observe_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a value in a histogram with optional tags."""
        metric_name = self._build_metric_name(name, tags)
        histogram = self.get_histogram(metric_name)
        histogram.observe(value)
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge value with optional tags."""
        metric_name = self._build_metric_name(name, tags)
        gauge = self.get_gauge(metric_name)
        gauge.set(value)
    
    def _build_metric_name(self, name: str, tags: Dict[str, str] = None) -> str:
        """Build metric name with tags."""
        if not tags:
            return name
        
        tag_parts = [f"{k}={v}" for k, v in sorted(tags.items())]
        return f"{name}{{{','.join(tag_parts)}}}"
    
    def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics in Prometheus format."""
        metrics = {
            'counters': {},
            'histograms': {},
            'gauges': {},
            'timestamp': time.time()
        }
        
        # Export counters
        for name, counter in self.counters.items():
            metrics['counters'][name] = {
                'value': counter.get_value(),
                'last_updated': counter.last_updated
            }
        
        # Export histograms
        for name, histogram in self.histograms.items():
            metrics['histograms'][name] = {
                'count': histogram.count,
                'sum': histogram.sum,
                'buckets': histogram.get_bucket_counts(),
                'p50': histogram.get_percentile(50),
                'p95': histogram.get_percentile(95),
                'p99': histogram.get_percentile(99),
                'p99_9': histogram.get_percentile(99.9)
            }
        
        # Export gauges
        for name, gauge in self.gauges.items():
            metrics['gauges'][name] = {
                'value': gauge.get_value(),
                'last_updated': gauge.last_updated
            }
        
        return metrics

# Global metrics registry
metrics_registry = MetricsRegistry()

@dataclass
class SLOTarget:
    """Service Level Objective target definition."""
    name: str
    description: str
    target_percentage: float  # e.g., 99.9 for 99.9%
    measurement_window_hours: int  # e.g., 24 for 24 hours
    metric_name: str
    threshold_value: float
    comparison: str  # 'lt' (less than), 'gt' (greater than), 'eq' (equal)

@dataclass
class SLOStatus:
    """Current SLO status."""
    target: SLOTarget
    current_percentage: float
    is_meeting_target: bool
    error_budget_remaining: float  # Percentage of error budget left
    measurement_period_start: datetime
    measurement_period_end: datetime
    total_measurements: int
    successful_measurements: int

class SLOMonitor:
    """Service Level Objective monitoring."""
    
    def __init__(self, metrics_registry: MetricsRegistry):
        self.metrics_registry = metrics_registry
        self.slo_targets: Dict[str, SLOTarget] = {}
        self.measurement_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.logger = get_logger("slo_monitor")
        
        # Define default SLOs
        self._setup_default_slos()
    
    def _setup_default_slos(self):
        """Set up default SLO targets for the application."""
        
        # API Response Time SLO - 95% of requests under 500ms
        self.add_slo_target(SLOTarget(
            name="api_response_time_p95",
            description="95% of API requests complete within 500ms",
            target_percentage=95.0,
            measurement_window_hours=24,
            metric_name="request_duration_ms",
            threshold_value=500.0,
            comparison="lt"
        ))
        
        # API Response Time SLO - 99% of requests under 2000ms
        self.add_slo_target(SLOTarget(
            name="api_response_time_p99",
            description="99% of API requests complete within 2000ms",
            target_percentage=99.0,
            measurement_window_hours=24,
            metric_name="request_duration_ms",
            threshold_value=2000.0,
            comparison="lt"
        ))
        
        # Error Rate SLO - 99.9% of requests succeed
        self.add_slo_target(SLOTarget(
            name="api_success_rate",
            description="99.9% of API requests succeed (non-5xx responses)",
            target_percentage=99.9,
            measurement_window_hours=24,
            metric_name="request_success_rate",
            threshold_value=1.0,
            comparison="eq"
        ))
        
        # Cache Hit Rate SLO - 90% cache hit rate
        self.add_slo_target(SLOTarget(
            name="cache_hit_rate",
            description="90% cache hit rate for puzzle data",
            target_percentage=90.0,
            measurement_window_hours=24,
            metric_name="cache_hit_rate",
            threshold_value=0.9,
            comparison="gt"
        ))
    
    def add_slo_target(self, target: SLOTarget):
        """Add an SLO target to monitor."""
        self.slo_targets[target.name] = target
        self.logger.info(f"Added SLO target: {target.name} - {target.description}")
    
    def record_measurement(self, slo_name: str, value: float, timestamp: float = None):
        """Record a measurement for SLO calculation."""
        if timestamp is None:
            timestamp = time.time()
        
        if slo_name in self.slo_targets:
            self.measurement_history[slo_name].append((timestamp, value))
    
    def calculate_slo_status(self, slo_name: str) -> Optional[SLOStatus]:
        """Calculate current SLO status."""
        if slo_name not in self.slo_targets:
            return None
        
        target = self.slo_targets[slo_name]
        measurements = self.measurement_history[slo_name]
        
        if not measurements:
            return None
        
        # Filter measurements within the window
        window_start = time.time() - (target.measurement_window_hours * 3600)
        recent_measurements = [(ts, val) for ts, val in measurements if ts >= window_start]
        
        if not recent_measurements:
            return None
        
        # Calculate success rate based on comparison
        total_measurements = len(recent_measurements)
        successful_measurements = 0
        
        for _, value in recent_measurements:
            if target.comparison == "lt" and value < target.threshold_value:
                successful_measurements += 1
            elif target.comparison == "gt" and value > target.threshold_value:
                successful_measurements += 1
            elif target.comparison == "eq" and value == target.threshold_value:
                successful_measurements += 1
        
        current_percentage = (successful_measurements / total_measurements) * 100
        is_meeting_target = current_percentage >= target.target_percentage
        
        # Calculate error budget remaining
        error_budget_total = 100 - target.target_percentage
        error_budget_used = max(0, target.target_percentage - current_percentage)
        error_budget_remaining = max(0, error_budget_total - error_budget_used)
        error_budget_remaining_pct = (error_budget_remaining / error_budget_total) * 100 if error_budget_total > 0 else 100
        
        return SLOStatus(
            target=target,
            current_percentage=current_percentage,
            is_meeting_target=is_meeting_target,
            error_budget_remaining=error_budget_remaining_pct,
            measurement_period_start=datetime.fromtimestamp(window_start),
            measurement_period_end=datetime.now(),
            total_measurements=total_measurements,
            successful_measurements=successful_measurements
        )
    
    def get_all_slo_status(self) -> Dict[str, SLOStatus]:
        """Get status for all SLO targets."""
        status_dict = {}
        for slo_name in self.slo_targets:
            status = self.calculate_slo_status(slo_name)
            if status:
                status_dict[slo_name] = status
        return status_dict
    
    def check_slo_violations(self) -> List[SLOStatus]:
        """Check for SLO violations and return list of violated SLOs."""
        violations = []
        for slo_name in self.slo_targets:
            status = self.calculate_slo_status(slo_name)
            if status and not status.is_meeting_target:
                violations.append(status)
        return violations

# Global SLO monitor
slo_monitor = SLOMonitor(metrics_registry)

class AlertManager:
    """Alert management for SLO violations and system issues."""
    
    def __init__(self, slo_monitor: SLOMonitor):
        self.slo_monitor = slo_monitor
        self.alert_history: deque = deque(maxlen=1000)
        self.alert_cooldowns: Dict[str, float] = {}
        self.logger = get_logger("alert_manager")
        
        # Alert thresholds
        self.error_budget_warning_threshold = 25.0  # Warn when 25% error budget remaining
        self.error_budget_critical_threshold = 10.0  # Critical when 10% error budget remaining
        self.cooldown_period = 300  # 5 minutes between same alerts
    
    def check_alerts(self):
        """Check for alert conditions and send notifications."""
        current_time = time.time()
        
        # Check SLO violations
        violations = self.slo_monitor.check_slo_violations()
        for violation in violations:
            self._handle_slo_violation(violation, current_time)
        
        # Check error budget depletion
        all_status = self.slo_monitor.get_all_slo_status()
        for slo_name, status in all_status.items():
            self._check_error_budget_alerts(slo_name, status, current_time)
    
    def _handle_slo_violation(self, violation: SLOStatus, current_time: float):
        """Handle SLO violation alert."""
        alert_key = f"slo_violation_{violation.target.name}"
        
        if self._should_send_alert(alert_key, current_time):
            alert = {
                'type': 'slo_violation',
                'severity': 'critical',
                'slo_name': violation.target.name,
                'description': violation.target.description,
                'current_percentage': violation.current_percentage,
                'target_percentage': violation.target.target_percentage,
                'error_budget_remaining': violation.error_budget_remaining,
                'timestamp': current_time
            }
            
            self._send_alert(alert)
            self.alert_cooldowns[alert_key] = current_time
    
    def _check_error_budget_alerts(self, slo_name: str, status: SLOStatus, current_time: float):
        """Check for error budget depletion alerts."""
        if status.error_budget_remaining <= self.error_budget_critical_threshold:
            alert_key = f"error_budget_critical_{slo_name}"
            if self._should_send_alert(alert_key, current_time):
                alert = {
                    'type': 'error_budget_critical',
                    'severity': 'critical',
                    'slo_name': slo_name,
                    'description': f"Critical: Only {status.error_budget_remaining:.1f}% error budget remaining",
                    'error_budget_remaining': status.error_budget_remaining,
                    'timestamp': current_time
                }
                self._send_alert(alert)
                self.alert_cooldowns[alert_key] = current_time
        
        elif status.error_budget_remaining <= self.error_budget_warning_threshold:
            alert_key = f"error_budget_warning_{slo_name}"
            if self._should_send_alert(alert_key, current_time):
                alert = {
                    'type': 'error_budget_warning',
                    'severity': 'warning',
                    'slo_name': slo_name,
                    'description': f"Warning: Only {status.error_budget_remaining:.1f}% error budget remaining",
                    'error_budget_remaining': status.error_budget_remaining,
                    'timestamp': current_time
                }
                self._send_alert(alert)
                self.alert_cooldowns[alert_key] = current_time
    
    def _should_send_alert(self, alert_key: str, current_time: float) -> bool:
        """Check if alert should be sent based on cooldown."""
        last_sent = self.alert_cooldowns.get(alert_key, 0)
        return current_time - last_sent > self.cooldown_period
    
    def _send_alert(self, alert: Dict[str, Any]):
        """Send alert notification."""
        self.alert_history.append(alert)
        
        # Log the alert
        self.logger.error(
            f"ALERT: {alert['type']} - {alert['description']}",
            extra={
                'alert_type': alert['type'],
                'severity': alert['severity'],
                'slo_name': alert.get('slo_name'),
                'alert_data': alert
            }
        )
        
        # In production, this would integrate with:
        # - PagerDuty for critical alerts
        # - Slack for warnings
        # - Email for notifications
        # - SMS for critical issues
        
        print(f"🚨 ALERT [{alert['severity'].upper()}]: {alert['description']}")

# Global alert manager
alert_manager = AlertManager(slo_monitor)

# Convenience functions for metrics collection
def increment_counter(name: str, amount: float = 1.0, tags: Dict[str, str] = None):
    """Increment a counter metric."""
    metrics_registry.increment_counter(name, amount, tags)

def observe_histogram(name: str, value: float, tags: Dict[str, str] = None):
    """Record a histogram observation."""
    metrics_registry.observe_histogram(name, value, tags)

def set_gauge(name: str, value: float, tags: Dict[str, str] = None):
    """Set a gauge value."""
    metrics_registry.set_gauge(name, value, tags)

def record_slo_measurement(slo_name: str, value: float):
    """Record an SLO measurement."""
    slo_monitor.record_measurement(slo_name, value)

def get_metrics_summary() -> Dict[str, Any]:
    """Get comprehensive metrics summary."""
    return {
        'metrics': metrics_registry.export_metrics(),
        'slo_status': {name: {
            'current_percentage': status.current_percentage,
            'is_meeting_target': status.is_meeting_target,
            'error_budget_remaining': status.error_budget_remaining,
            'target_percentage': status.target.target_percentage
        } for name, status in slo_monitor.get_all_slo_status().items()},
        'timestamp': datetime.now().isoformat()
    }