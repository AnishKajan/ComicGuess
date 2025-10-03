"""
Tests for metrics collection and SLO monitoring system.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch

from app.monitoring.metrics import (
    MetricsRegistry, Histogram, Counter, Gauge,
    SLOTarget, SLOMonitor, SLOStatus, AlertManager,
    metrics_registry, slo_monitor, alert_manager,
    increment_counter, observe_histogram, set_gauge
)
from app.monitoring.runbooks import (
    IncidentRunbook, RunbookStep, HighLatencyRunbook,
    HighErrorRateRunbook, RunbookManager, runbook_manager
)

class TestMetricsRegistry:
    """Test metrics registry functionality."""
    
    def test_counter_operations(self):
        """Test counter metric operations."""
        registry = MetricsRegistry()
        
        # Test counter creation and increment
        counter = registry.get_counter("test_counter")
        assert counter.get_value() == 0.0
        
        counter.increment(5.0)
        assert counter.get_value() == 5.0
        
        counter.increment()  # Default increment of 1
        assert counter.get_value() == 6.0
    
    def test_histogram_operations(self):
        """Test histogram metric operations."""
        registry = MetricsRegistry()
        
        # Test histogram creation and observations
        histogram = registry.get_histogram("test_histogram")
        assert histogram.count == 0
        assert histogram.sum == 0.0
        
        # Add some values
        values = [10, 20, 30, 40, 50, 100, 200, 500, 1000]
        for value in values:
            histogram.observe(value)
        
        assert histogram.count == len(values)
        assert histogram.sum == sum(values)
        
        # Test percentiles
        p50 = histogram.get_percentile(50)
        p95 = histogram.get_percentile(95)
        p99 = histogram.get_percentile(99)
        
        assert p50 > 0
        assert p95 > p50
        assert p99 >= p95
    
    def test_gauge_operations(self):
        """Test gauge metric operations."""
        registry = MetricsRegistry()
        
        # Test gauge creation and operations
        gauge = registry.get_gauge("test_gauge")
        assert gauge.get_value() == 0.0
        
        gauge.set(42.5)
        assert gauge.get_value() == 42.5
        
        gauge.increment(7.5)
        assert gauge.get_value() == 50.0
        
        gauge.decrement(10.0)
        assert gauge.get_value() == 40.0
    
    def test_metrics_with_tags(self):
        """Test metrics with tags."""
        registry = MetricsRegistry()
        
        # Test counter with tags
        registry.increment_counter("requests_total", 1, {"method": "GET", "status": "200"})
        registry.increment_counter("requests_total", 1, {"method": "POST", "status": "201"})
        registry.increment_counter("requests_total", 1, {"method": "GET", "status": "200"})
        
        # Should create separate counters for different tag combinations
        get_counter = registry.get_counter("requests_total{method=GET,status=200}")
        post_counter = registry.get_counter("requests_total{method=POST,status=201}")
        
        assert get_counter.get_value() == 2.0
        assert post_counter.get_value() == 1.0
    
    def test_metrics_export(self):
        """Test metrics export functionality."""
        registry = MetricsRegistry()
        
        # Add some metrics
        registry.increment_counter("test_counter", 10)
        registry.observe_histogram("test_histogram", 123.45)
        registry.set_gauge("test_gauge", 67.89)
        
        # Export metrics
        exported = registry.export_metrics()
        
        assert "counters" in exported
        assert "histograms" in exported
        assert "gauges" in exported
        assert "timestamp" in exported
        
        # Check counter export
        assert "test_counter" in exported["counters"]
        assert exported["counters"]["test_counter"]["value"] == 10.0
        
        # Check histogram export
        assert "test_histogram" in exported["histograms"]
        histogram_data = exported["histograms"]["test_histogram"]
        assert histogram_data["count"] == 1
        assert histogram_data["sum"] == 123.45
        assert "p95" in histogram_data
        assert "p99" in histogram_data
        
        # Check gauge export
        assert "test_gauge" in exported["gauges"]
        assert exported["gauges"]["test_gauge"]["value"] == 67.89

class TestSLOMonitoring:
    """Test SLO monitoring functionality."""
    
    def test_slo_target_creation(self):
        """Test SLO target creation."""
        target = SLOTarget(
            name="test_slo",
            description="Test SLO for latency",
            target_percentage=95.0,
            measurement_window_hours=24,
            metric_name="request_duration_ms",
            threshold_value=500.0,
            comparison="lt"
        )
        
        assert target.name == "test_slo"
        assert target.target_percentage == 95.0
        assert target.comparison == "lt"
    
    def test_slo_monitor_basic_operations(self):
        """Test basic SLO monitor operations."""
        monitor = SLOMonitor(MetricsRegistry())
        
        # Add a test SLO
        target = SLOTarget(
            name="test_latency_slo",
            description="Test latency SLO",
            target_percentage=95.0,
            measurement_window_hours=1,
            metric_name="request_duration_ms",
            threshold_value=500.0,
            comparison="lt"
        )
        
        monitor.add_slo_target(target)
        assert "test_latency_slo" in monitor.slo_targets
    
    def test_slo_measurement_and_calculation(self):
        """Test SLO measurement recording and status calculation."""
        monitor = SLOMonitor(MetricsRegistry())
        
        # Add a test SLO
        target = SLOTarget(
            name="test_slo",
            description="Test SLO",
            target_percentage=80.0,  # 80% target
            measurement_window_hours=1,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison="lt"
        )
        
        monitor.add_slo_target(target)
        
        # Record measurements (80% should be under 100, 20% over)
        current_time = time.time()
        measurements = [50, 75, 80, 90, 95] + [150, 200]  # 5 good, 2 bad = 71.4%
        
        for i, value in enumerate(measurements):
            monitor.record_measurement("test_slo", value, current_time - i)
        
        # Calculate status
        status = monitor.calculate_slo_status("test_slo")
        
        assert status is not None
        assert status.total_measurements == len(measurements)
        assert status.successful_measurements == 5  # Values under 100
        assert status.current_percentage == (5/7) * 100  # ~71.4%
        assert not status.is_meeting_target  # 71.4% < 80%
        assert status.error_budget_remaining < 100  # Some error budget used
    
    def test_slo_violation_detection(self):
        """Test SLO violation detection."""
        monitor = SLOMonitor(MetricsRegistry())
        
        # Add a strict SLO
        target = SLOTarget(
            name="strict_slo",
            description="Strict SLO",
            target_percentage=99.0,
            measurement_window_hours=1,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison="lt"
        )
        
        monitor.add_slo_target(target)
        
        # Record mostly bad measurements
        current_time = time.time()
        for i in range(10):
            # 9 bad measurements, 1 good = 10% success rate
            value = 50 if i == 0 else 150
            monitor.record_measurement("strict_slo", value, current_time - i)
        
        # Check for violations
        violations = monitor.check_slo_violations()
        
        assert len(violations) == 1
        assert violations[0].target.name == "strict_slo"
        assert not violations[0].is_meeting_target

class TestAlertManager:
    """Test alert management functionality."""
    
    def test_alert_manager_creation(self):
        """Test alert manager creation."""
        monitor = SLOMonitor(MetricsRegistry())
        alert_mgr = AlertManager(monitor)
        
        assert alert_mgr.slo_monitor == monitor
        assert len(alert_mgr.alert_history) == 0
    
    def test_slo_violation_alert(self):
        """Test SLO violation alert generation."""
        monitor = SLOMonitor(MetricsRegistry())
        alert_mgr = AlertManager(monitor)
        
        # Create a failing SLO
        target = SLOTarget(
            name="failing_slo",
            description="Failing SLO",
            target_percentage=95.0,
            measurement_window_hours=1,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison="lt"
        )
        
        monitor.add_slo_target(target)
        
        # Record failing measurements
        current_time = time.time()
        for i in range(10):
            monitor.record_measurement("failing_slo", 150, current_time - i)  # All fail
        
        # Check alerts
        alert_mgr.check_alerts()
        
        # Should have generated an alert
        assert len(alert_mgr.alert_history) > 0
        alert = alert_mgr.alert_history[0]
        assert alert['type'] == 'slo_violation'
        assert alert['slo_name'] == 'failing_slo'
        assert alert['severity'] == 'critical'
    
    def test_error_budget_alerts(self):
        """Test error budget depletion alerts."""
        monitor = SLOMonitor(MetricsRegistry())
        alert_mgr = AlertManager(monitor)
        
        # Create SLO with low error budget
        target = SLOTarget(
            name="low_budget_slo",
            description="Low budget SLO",
            target_percentage=99.0,  # High target = low error budget
            measurement_window_hours=1,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison="lt"
        )
        
        monitor.add_slo_target(target)
        
        # Record measurements that consume most error budget
        current_time = time.time()
        # 95% success rate with 99% target = 4% error budget remaining
        for i in range(100):
            value = 50 if i < 95 else 150
            monitor.record_measurement("low_budget_slo", value, current_time - i)
        
        # Check alerts
        alert_mgr.check_alerts()
        
        # Should have generated error budget alert
        budget_alerts = [a for a in alert_mgr.alert_history if 'error_budget' in a['type']]
        assert len(budget_alerts) > 0
    
    def test_alert_cooldown(self):
        """Test alert cooldown functionality."""
        monitor = SLOMonitor(MetricsRegistry())
        alert_mgr = AlertManager(monitor)
        alert_mgr.cooldown_period = 1  # 1 second cooldown for testing
        
        # Create failing SLO
        target = SLOTarget(
            name="cooldown_test_slo",
            description="Cooldown test SLO",
            target_percentage=95.0,
            measurement_window_hours=1,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison="lt"
        )
        
        monitor.add_slo_target(target)
        
        # Record failing measurements
        current_time = time.time()
        for i in range(10):
            monitor.record_measurement("cooldown_test_slo", 150, current_time - i)
        
        # Check alerts twice quickly
        alert_mgr.check_alerts()
        initial_alert_count = len(alert_mgr.alert_history)
        
        alert_mgr.check_alerts()  # Should be suppressed by cooldown
        assert len(alert_mgr.alert_history) == initial_alert_count
        
        # Wait for cooldown and check again
        time.sleep(1.1)
        alert_mgr.check_alerts()
        assert len(alert_mgr.alert_history) > initial_alert_count

class TestRunbooks:
    """Test incident response runbooks."""
    
    def test_runbook_step_creation(self):
        """Test runbook step creation."""
        async def test_action():
            return {"result": "success"}
        
        step = RunbookStep(
            name="test_step",
            description="Test step",
            action=test_action,
            timeout_seconds=60
        )
        
        assert step.name == "test_step"
        assert step.timeout_seconds == 60
        assert step.required is True
    
    @pytest.mark.asyncio
    async def test_runbook_execution(self):
        """Test runbook execution."""
        async def step1_action():
            return {"step1": "completed"}
        
        async def step2_action():
            await asyncio.sleep(0.01)  # Simulate work
            return {"step2": "completed"}
        
        runbook = IncidentRunbook(
            name="test_runbook",
            description="Test runbook",
            severity="medium"
        )
        
        runbook.add_step(RunbookStep("step1", "First step", step1_action))
        runbook.add_step(RunbookStep("step2", "Second step", step2_action))
        
        result = await runbook.execute()
        
        assert result.success is True
        assert result.steps_completed == 2
        assert result.total_steps == 2
        assert "step1" in result.results
        assert "step2" in result.results
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_runbook_with_failure(self):
        """Test runbook execution with step failure."""
        async def failing_action():
            raise ValueError("Test failure")
        
        async def success_action():
            return {"success": True}
        
        runbook = IncidentRunbook(
            name="failing_runbook",
            description="Runbook with failure",
            severity="high"
        )
        
        runbook.add_step(RunbookStep("success_step", "Success step", success_action))
        runbook.add_step(RunbookStep("failing_step", "Failing step", failing_action, required=True))
        runbook.add_step(RunbookStep("unreached_step", "Unreached step", success_action))
        
        result = await runbook.execute()
        
        assert result.success is False
        assert result.steps_completed == 1  # Only first step completed
        assert len(result.errors) == 1
        assert "Test failure" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_runbook_timeout(self):
        """Test runbook step timeout."""
        async def slow_action():
            await asyncio.sleep(2)  # Longer than timeout
            return {"slow": "completed"}
        
        runbook = IncidentRunbook(
            name="timeout_runbook",
            description="Runbook with timeout",
            severity="low"
        )
        
        runbook.add_step(RunbookStep(
            "slow_step", 
            "Slow step", 
            slow_action, 
            timeout_seconds=1,  # 1 second timeout
            required=True
        ))
        
        result = await runbook.execute()
        
        assert result.success is False
        assert result.steps_completed == 0
        assert len(result.errors) == 1
        assert "timed out" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_high_latency_runbook(self):
        """Test high latency runbook execution."""
        runbook = HighLatencyRunbook()
        
        # Mock the log search to avoid dependencies
        with patch('app.monitoring.runbooks.search_logs') as mock_search:
            mock_search.return_value = [
                {
                    'extra_fields': {
                        'path': '/api/test',
                        'duration_ms': 1500
                    }
                }
            ]
            
            result = await runbook.execute()
            
            # Should complete successfully even with mocked data
            assert result.runbook_name == "high_latency_response"
            assert result.steps_completed > 0
    
    def test_runbook_manager(self):
        """Test runbook manager functionality."""
        manager = RunbookManager()
        
        # Should have default runbooks registered
        available = manager.get_available_runbooks()
        assert len(available) > 0
        
        # Check that default runbooks are present
        runbook_names = [rb['name'] for rb in available]
        assert 'high_latency_response' in runbook_names
        assert 'high_error_rate_response' in runbook_names
    
    @pytest.mark.asyncio
    async def test_runbook_manager_execution(self):
        """Test runbook execution through manager."""
        manager = RunbookManager()
        
        # Create a simple test runbook
        async def simple_action():
            return {"test": "success"}
        
        test_runbook = IncidentRunbook("test_runbook", "Test", "low")
        test_runbook.add_step(RunbookStep("test_step", "Test step", simple_action))
        
        manager.register_runbook(test_runbook)
        
        # Execute the runbook
        result = await manager.execute_runbook("test_runbook")
        
        assert result is not None
        assert result.success is True
        assert result.runbook_name == "test_runbook"
        
        # Check execution history
        history = manager.get_execution_history()
        assert len(history) == 1
        assert history[0].runbook_name == "test_runbook"

class TestConvenienceFunctions:
    """Test convenience functions for metrics."""
    
    def test_convenience_functions(self):
        """Test convenience functions for metrics collection."""
        # Test counter increment
        increment_counter("test_convenience_counter", 5.0, {"tag": "value"})
        
        # Test histogram observation
        observe_histogram("test_convenience_histogram", 123.45, {"tag": "value"})
        
        # Test gauge setting
        set_gauge("test_convenience_gauge", 67.89, {"tag": "value"})
        
        # These should not raise exceptions
        # In a real test, we'd verify the metrics were recorded correctly

class TestIntegration:
    """Test integration between metrics, SLOs, and alerts."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_monitoring_flow(self):
        """Test complete monitoring flow from metrics to alerts."""
        # Create fresh instances for this test
        registry = MetricsRegistry()
        monitor = SLOMonitor(registry)
        alert_mgr = AlertManager(monitor)
        
        # Add a test SLO
        target = SLOTarget(
            name="integration_test_slo",
            description="Integration test SLO",
            target_percentage=90.0,
            measurement_window_hours=1,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison="lt"
        )
        
        monitor.add_slo_target(target)
        
        # Simulate application metrics
        current_time = time.time()
        
        # Record metrics that will violate SLO (only 70% success)
        for i in range(10):
            value = 50 if i < 7 else 150  # 7 successes, 3 failures
            monitor.record_measurement("integration_test_slo", value, current_time - i)
            
            # Also record in histogram
            registry.observe_histogram("test_metric", value)
        
        # Check SLO status
        status = monitor.calculate_slo_status("integration_test_slo")
        assert status is not None
        assert status.current_percentage == 70.0  # 7/10 = 70%
        assert not status.is_meeting_target  # 70% < 90%
        
        # Check for violations
        violations = monitor.check_slo_violations()
        assert len(violations) == 1
        assert violations[0].target.name == "integration_test_slo"
        
        # Trigger alert check
        alert_mgr.check_alerts()
        
        # Should have generated alerts
        assert len(alert_mgr.alert_history) > 0
        
        # Verify alert content
        slo_alerts = [a for a in alert_mgr.alert_history if a['type'] == 'slo_violation']
        assert len(slo_alerts) > 0
        assert slo_alerts[0]['slo_name'] == 'integration_test_slo'
        
        # Export metrics for verification
        exported = registry.export_metrics()
        assert 'histograms' in exported
        assert 'test_metric' in exported['histograms']
        
        histogram_data = exported['histograms']['test_metric']
        assert histogram_data['count'] == 10
        assert histogram_data['p95'] > 0
        assert histogram_data['p99'] > 0