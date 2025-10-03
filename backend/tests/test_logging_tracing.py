"""
Tests for comprehensive logging and tracing system.
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from fastapi.responses import JSONResponse

from app.monitoring.tracing import (
    TracingContext, SpanKind, SpanStatus, trace_collector,
    get_trace_id, get_span_id, set_trace_context,
    trace_function, trace_database_operation, trace_http_request
)
from app.monitoring.log_aggregation import (
    LogAggregator, LogEntry, LogLevel, LogFilter,
    search_logs, get_log_stats, get_trace_logs
)
from app.monitoring.logging_config import (
    set_correlation_id, get_correlation_id, 
    log_performance, MetricsCollector
)
from app.monitoring.middleware import MonitoringMiddleware

class TestDistributedTracing:
    """Test distributed tracing functionality."""
    
    def test_tracing_context_creation(self):
        """Test creating and managing tracing contexts."""
        with TracingContext("test_operation", SpanKind.INTERNAL) as ctx:
            # Should have trace and span IDs
            trace_id = get_trace_id()
            span_id = get_span_id()
            
            assert trace_id is not None
            assert span_id is not None
            assert len(trace_id) > 0
            assert len(span_id) > 0
            
            # Add tags and logs
            ctx.add_tag("test.key", "test.value")
            ctx.add_log("test_event", detail="test detail")
        
        # Context should be cleaned up
        assert get_trace_id() is None or get_trace_id() != trace_id
    
    def test_nested_tracing_contexts(self):
        """Test nested tracing contexts maintain parent-child relationships."""
        with TracingContext("parent_operation", SpanKind.SERVER) as parent_ctx:
            parent_trace_id = get_trace_id()
            parent_span_id = get_span_id()
            
            with TracingContext("child_operation", SpanKind.INTERNAL) as child_ctx:
                child_trace_id = get_trace_id()
                child_span_id = get_span_id()
                
                # Should share trace ID but have different span IDs
                assert child_trace_id == parent_trace_id
                assert child_span_id != parent_span_id
        
        # Should restore parent context
        assert get_trace_id() == parent_trace_id
        assert get_span_id() == parent_span_id
    
    def test_trace_context_from_headers(self):
        """Test setting trace context from external headers."""
        external_trace_id = "external-trace-123"
        external_span_id = "external-span-456"
        
        set_trace_context(external_trace_id, external_span_id)
        
        assert get_trace_id() == external_trace_id
        assert get_span_id() == external_span_id
    
    def test_trace_function_decorator(self):
        """Test automatic function tracing decorator."""
        
        @trace_function("test.sync_function")
        def sync_function(x, y):
            return x + y
        
        @trace_function("test.async_function")
        async def async_function(x, y):
            await asyncio.sleep(0.01)
            return x * y
        
        # Test sync function
        result = sync_function(2, 3)
        assert result == 5
        
        # Test async function
        async def test_async():
            result = await async_function(4, 5)
            assert result == 20
        
        asyncio.run(test_async())
    
    def test_database_operation_tracing(self):
        """Test database operation tracing decorator."""
        
        @trace_database_operation("select", "users")
        async def get_user(user_id: str):
            # Simulate database operation
            await asyncio.sleep(0.01)
            return {"id": user_id, "name": "Test User"}
        
        async def test_db_trace():
            with TracingContext("test_request", SpanKind.SERVER):
                result = await get_user("user123")
                assert result["id"] == "user123"
        
        asyncio.run(test_db_trace())
    
    def test_http_request_tracing(self):
        """Test HTTP request tracing decorator."""
        
        @trace_http_request("GET", "https://api.example.com/users")
        async def make_api_call():
            # Simulate HTTP request
            await asyncio.sleep(0.01)
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response
        
        async def test_http_trace():
            with TracingContext("test_request", SpanKind.SERVER):
                response = await make_api_call()
                assert response.status_code == 200
        
        asyncio.run(test_http_trace())
    
    def test_trace_collector(self):
        """Test trace collection and export."""
        with TracingContext("test_operation", SpanKind.INTERNAL) as ctx:
            trace_id = get_trace_id()
            ctx.add_tag("test.key", "test.value")
            ctx.add_log("test_event", detail="test detail")
        
        # Get collected trace
        spans = trace_collector.get_trace(trace_id)
        assert len(spans) > 0
        
        span = spans[0]
        assert span.operation_name == "test_operation"
        assert span.kind == SpanKind.INTERNAL
        assert "test.key" in span.tags
        assert span.tags["test.key"] == "test.value"
        
        # Test export
        exported = trace_collector.export_trace(trace_id)
        assert "traceId" in exported
        assert exported["traceId"] == trace_id
        assert len(exported["spans"]) > 0

class TestLogAggregation:
    """Test log aggregation and search functionality."""
    
    def test_log_entry_creation(self):
        """Test creating and serializing log entries."""
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            logger="test.logger",
            message="Test message",
            correlation_id="test-correlation-123",
            trace_id="test-trace-456",
            span_id="test-span-789",
            extra_fields={"custom_field": "custom_value"}
        )
        
        entry_dict = entry.to_dict()
        assert entry_dict["level"] == "INFO"
        assert entry_dict["message"] == "Test message"
        assert entry_dict["trace_id"] == "test-trace-456"
        assert entry_dict["custom_field"] == "custom_value"
        assert "datetime" in entry_dict
    
    def test_log_aggregator_basic_operations(self):
        """Test basic log aggregator operations."""
        aggregator = LogAggregator(max_entries=100)
        
        # Add log entries
        for i in range(10):
            entry = LogEntry(
                timestamp=time.time(),
                level=LogLevel.INFO if i % 2 == 0 else LogLevel.ERROR,
                logger=f"test.logger.{i % 3}",
                message=f"Test message {i}",
                correlation_id=f"correlation-{i % 5}",
                trace_id=f"trace-{i % 3}"
            )
            aggregator.add_entry(entry)
        
        assert len(aggregator.entries) == 10
        
        # Test indices
        assert len(aggregator.indices['level']['INFO']) == 5
        assert len(aggregator.indices['level']['ERROR']) == 5
    
    def test_log_filtering(self):
        """Test log filtering functionality."""
        aggregator = LogAggregator()
        
        # Add test entries
        entries = [
            LogEntry(time.time(), LogLevel.INFO, "app.service", "Info message", "corr-1", "trace-1"),
            LogEntry(time.time(), LogLevel.ERROR, "app.service", "Error message", "corr-1", "trace-1"),
            LogEntry(time.time(), LogLevel.INFO, "app.controller", "Controller message", "corr-2", "trace-2"),
        ]
        
        for entry in entries:
            aggregator.add_entry(entry)
        
        # Test level filter
        filter_obj = LogFilter()
        filter_obj.level = LogLevel.ERROR
        results = aggregator.search(filter_obj)
        assert len(results) == 1
        assert results[0].message == "Error message"
        
        # Test correlation ID filter
        filter_obj = LogFilter()
        filter_obj.correlation_id = "corr-1"
        results = aggregator.search(filter_obj)
        assert len(results) == 2
        
        # Test trace ID filter
        filter_obj = LogFilter()
        filter_obj.trace_id = "trace-2"
        results = aggregator.search(filter_obj)
        assert len(results) == 1
        assert results[0].logger == "app.controller"
        
        # Test message pattern filter
        filter_obj = LogFilter()
        filter_obj.message_pattern = "Controller"
        results = aggregator.search(filter_obj)
        assert len(results) == 1
        assert "Controller" in results[0].message
    
    def test_log_statistics(self):
        """Test log statistics generation."""
        aggregator = LogAggregator()
        
        # Add test entries with different levels
        current_time = time.time()
        entries = [
            LogEntry(current_time, LogLevel.INFO, "app.service", "Info 1", "corr-1"),
            LogEntry(current_time, LogLevel.INFO, "app.service", "Info 2", "corr-2"),
            LogEntry(current_time, LogLevel.ERROR, "app.service", "Error 1", "corr-3"),
            LogEntry(current_time, LogLevel.ERROR, "app.controller", "Error 2", "corr-4"),
            LogEntry(current_time - 7200, LogLevel.INFO, "app.service", "Old info", "corr-5"),  # 2 hours ago
        ]
        
        for entry in entries:
            aggregator.add_entry(entry)
        
        # Get stats for last hour
        stats = aggregator.get_stats(time_window_hours=1)
        
        assert stats['total_entries'] == 4  # Should exclude old entry
        assert stats['by_level']['INFO'] == 2
        assert stats['by_level']['ERROR'] == 2
        assert stats['error_rate'] == 2 / 60  # 2 errors per minute
        assert len(stats['top_errors']) == 2
    
    def test_search_logs_convenience_function(self):
        """Test the convenience search_logs function."""
        # This would use the global aggregator, so we'll test the interface
        results = search_logs(
            level="INFO",
            logger_pattern="app.*",
            hours_back=1,
            limit=10
        )
        
        # Should return a list of dictionaries
        assert isinstance(results, list)
    
    def test_trace_correlation(self):
        """Test correlation between traces and logs."""
        aggregator = LogAggregator()
        
        trace_id = "test-trace-correlation"
        
        # Add log entries with same trace ID
        entries = [
            LogEntry(time.time(), LogLevel.INFO, "app.service", "Service log", "corr-1", trace_id),
            LogEntry(time.time(), LogLevel.DEBUG, "app.database", "DB query", "corr-1", trace_id),
            LogEntry(time.time(), LogLevel.INFO, "app.controller", "Response sent", "corr-1", trace_id),
        ]
        
        for entry in entries:
            aggregator.add_entry(entry)
        
        # Get all logs for the trace
        trace_logs = aggregator.get_trace_logs(trace_id)
        assert len(trace_logs) == 3
        
        # Verify all logs have the same trace ID
        for log in trace_logs:
            assert log.trace_id == trace_id

class TestMonitoringMiddleware:
    """Test monitoring middleware integration."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"
        request.query_params = {}
        request.headers = {
            "user-agent": "test-agent",
            "X-Correlation-ID": "test-correlation-123"
        }
        request.client.host = "127.0.0.1"
        return request
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = JSONResponse(content={"status": "ok"})
        response.status_code = 200
        response.headers = {}
        return response
    
    @pytest.mark.asyncio
    async def test_monitoring_middleware_success(self, mock_request, mock_response):
        """Test monitoring middleware for successful requests."""
        middleware = MonitoringMiddleware(None)
        
        async def mock_call_next(request):
            return mock_response
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        # Should add tracing headers
        assert "X-Correlation-ID" in response.headers
        assert "X-Trace-ID" in response.headers
        assert "X-Span-ID" in response.headers
    
    @pytest.mark.asyncio
    async def test_monitoring_middleware_error(self, mock_request):
        """Test monitoring middleware for failed requests."""
        middleware = MonitoringMiddleware(None)
        
        async def mock_call_next(request):
            raise ValueError("Test error")
        
        response = await middleware.dispatch(mock_request, mock_call_next)
        
        # Should return error response with tracing info
        assert response.status_code == 500
        assert "X-Correlation-ID" in response.headers
        assert "X-Trace-ID" in response.headers
        
        # Response should contain error details
        content = json.loads(response.body)
        assert "error" in content
        assert "correlation_id" in content
        assert "trace_id" in content

class TestPerformanceLogging:
    """Test performance logging functionality."""
    
    def test_log_performance_decorator_sync(self):
        """Test performance logging decorator for sync functions."""
        
        @log_performance
        def slow_function():
            time.sleep(0.01)
            return "result"
        
        result = slow_function()
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_log_performance_decorator_async(self):
        """Test performance logging decorator for async functions."""
        
        @log_performance
        async def async_slow_function():
            await asyncio.sleep(0.01)
            return "async_result"
        
        result = await async_slow_function()
        assert result == "async_result"
    
    def test_metrics_collector(self):
        """Test metrics collection functionality."""
        collector = MetricsCollector()
        
        # Test counter
        collector.increment_counter("test_counter", 5, {"tag": "value"})
        
        # Test histogram
        collector.record_histogram("test_histogram", 123.45, {"tag": "value"})
        
        # Test gauge
        collector.record_gauge("test_gauge", 67.89, {"tag": "value"})
        
        # These should not raise exceptions and should log appropriately

class TestIntegration:
    """Test integration between tracing, logging, and aggregation."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_tracing_logging(self):
        """Test complete end-to-end tracing and logging flow."""
        
        # Set up correlation ID
        correlation_id = set_correlation_id("integration-test-123")
        
        # Create tracing context
        with TracingContext("integration_test", SpanKind.SERVER) as ctx:
            trace_id = get_trace_id()
            span_id = get_span_id()
            
            # Add some tags and logs to the span
            ctx.add_tag("test.type", "integration")
            ctx.add_tag("test.component", "logging")
            ctx.add_log("test_started", detail="Integration test started")
            
            # Simulate some work with nested spans
            with TracingContext("database_operation", SpanKind.CLIENT) as db_ctx:
                db_ctx.add_tag("db.table", "users")
                db_ctx.add_tag("db.operation", "select")
                await asyncio.sleep(0.01)  # Simulate DB time
            
            with TracingContext("external_api_call", SpanKind.CLIENT) as api_ctx:
                api_ctx.add_tag("http.method", "GET")
                api_ctx.add_tag("http.url", "https://api.example.com/data")
                await asyncio.sleep(0.01)  # Simulate API time
        
        # Verify trace was collected
        spans = trace_collector.get_trace(trace_id)
        assert len(spans) >= 3  # Main span + 2 child spans
        
        # Verify span relationships
        main_span = next(s for s in spans if s.operation_name == "integration_test")
        child_spans = [s for s in spans if s.parent_span_id == main_span.span_id]
        assert len(child_spans) >= 2
        
        # Verify span details
        assert main_span.tags["test.type"] == "integration"
        assert len(main_span.logs) > 0
        
        db_span = next(s for s in child_spans if s.operation_name == "database_operation")
        assert db_span.tags["db.table"] == "users"
        
        api_span = next(s for s in child_spans if s.operation_name == "external_api_call")
        assert api_span.tags["http.method"] == "GET"
    
    def test_correlation_across_components(self):
        """Test that correlation IDs work across different components."""
        correlation_id = set_correlation_id("cross-component-test")
        
        # Verify correlation ID is maintained
        assert get_correlation_id() == correlation_id
        
        # Test with tracing context
        with TracingContext("test_operation", SpanKind.INTERNAL):
            assert get_correlation_id() == correlation_id
            
            # Nested context should maintain correlation
            with TracingContext("nested_operation", SpanKind.INTERNAL):
                assert get_correlation_id() == correlation_id