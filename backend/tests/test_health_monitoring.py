"""
Tests for health monitoring and resilience patterns
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.monitoring.health import (
    HealthMonitor, HealthStatus, HealthCheckResult, RetryPolicy, 
    CircuitBreaker, CircuitBreakerState, IdempotencyManager,
    health_monitor, idempotency_manager
)


class TestHealthMonitor:
    """Test cases for HealthMonitor"""
    
    @pytest.fixture
    def health_mgr(self):
        """Create a health monitor instance for testing"""
        return HealthMonitor()
    
    def test_health_monitor_initialization(self, health_mgr):
        """Test health monitor initialization"""
        assert len(health_mgr.health_checks) > 0
        assert len(health_mgr.circuit_breakers) > 0
        assert len(health_mgr.retry_policies) > 0
        
        # Check default components are registered
        assert "database" in health_mgr.health_checks
        assert "storage" in health_mgr.health_checks
        assert "memory" in health_mgr.health_checks
        assert "disk" in health_mgr.health_checks
    
    def test_register_health_check(self, health_mgr):
        """Test registering custom health checks"""
        async def custom_check():
            return {"healthy": True}
        
        health_mgr.register_health_check("custom", custom_check)
        assert "custom" in health_mgr.health_checks
        assert health_mgr.health_checks["custom"] == custom_check
    
    def test_register_circuit_breaker(self, health_mgr):
        """Test registering circuit breakers"""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        health_mgr.register_circuit_breaker("test", cb)
        
        assert "test" in health_mgr.circuit_breakers
        assert health_mgr.circuit_breakers["test"] == cb
    
    def test_register_retry_policy(self, health_mgr):
        """Test registering retry policies"""
        policy = RetryPolicy(max_attempts=5, base_delay_ms=200)
        health_mgr.register_retry_policy("test", policy)
        
        assert "test" in health_mgr.retry_policies
        assert health_mgr.retry_policies["test"] == policy
    
    @pytest.mark.asyncio
    async def test_perform_health_check_success(self, health_mgr):
        """Test successful health check"""
        async def healthy_check():
            return {"healthy": True, "details": "All good"}
        
        health_mgr.register_health_check("test", healthy_check)
        result = await health_mgr.perform_health_check("test")
        
        assert result.component == "test"
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms > 0
        assert result.details["healthy"] is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_perform_health_check_failure(self, health_mgr):
        """Test failed health check"""
        async def unhealthy_check():
            return {"healthy": False, "error": "Something wrong"}
        
        health_mgr.register_health_check("test", unhealthy_check)
        result = await health_mgr.perform_health_check("test")
        
        assert result.component == "test"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.response_time_ms > 0
        assert result.details["healthy"] is False
    
    @pytest.mark.asyncio
    async def test_perform_health_check_exception(self, health_mgr):
        """Test health check that raises exception"""
        async def exception_check():
            raise Exception("Check failed")
        
        health_mgr.register_health_check("test", exception_check)
        result = await health_mgr.perform_health_check("test")
        
        assert result.component == "test"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Check failed"
    
    @pytest.mark.asyncio
    async def test_perform_health_check_unknown_component(self, health_mgr):
        """Test health check for unknown component"""
        result = await health_mgr.perform_health_check("nonexistent")
        
        assert result.component == "nonexistent"
        assert result.status == HealthStatus.UNKNOWN
        assert "No health check registered" in result.error
    
    @pytest.mark.asyncio
    async def test_perform_all_health_checks(self, health_mgr):
        """Test performing all health checks"""
        async def check1():
            return {"healthy": True}
        
        async def check2():
            return {"healthy": False}
        
        health_mgr.register_health_check("test1", check1)
        health_mgr.register_health_check("test2", check2)
        
        results = await health_mgr.perform_all_health_checks()
        
        assert "test1" in results
        assert "test2" in results
        assert results["test1"].status == HealthStatus.HEALTHY
        assert results["test2"].status == HealthStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_get_overall_health_all_healthy(self, health_mgr):
        """Test overall health when all components are healthy"""
        async def healthy_check():
            return {"healthy": True}
        
        health_mgr.register_health_check("test1", healthy_check)
        health_mgr.register_health_check("test2", healthy_check)
        
        overall_health = await health_mgr.get_overall_health()
        
        assert overall_health["status"] == "healthy"
        assert "components" in overall_health
        assert "circuit_breakers" in overall_health
        assert "timestamp" in overall_health
    
    @pytest.mark.asyncio
    async def test_get_overall_health_some_unhealthy(self, health_mgr):
        """Test overall health when some components are unhealthy"""
        async def healthy_check():
            return {"healthy": True}
        
        async def unhealthy_check():
            return {"healthy": False}
        
        health_mgr.register_health_check("test1", healthy_check)
        health_mgr.register_health_check("test2", unhealthy_check)
        
        overall_health = await health_mgr.get_overall_health()
        
        assert overall_health["status"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_check_readiness(self, health_mgr):
        """Test readiness checks"""
        async def ready_check():
            return {"ready": True}
        
        async def not_ready_check():
            return {"ready": False}
        
        health_mgr.register_readiness_check(ready_check)
        health_mgr.register_readiness_check(not_ready_check)
        
        readiness = await health_mgr.check_readiness()
        
        assert readiness["ready"] is False  # One check failed
        assert len(readiness["checks"]) == 2
    
    @pytest.mark.asyncio
    async def test_check_liveness(self, health_mgr):
        """Test liveness checks"""
        async def alive_check():
            return {"alive": True}
        
        health_mgr.register_liveness_check(alive_check)
        
        liveness = await health_mgr.check_liveness()
        
        assert liveness["alive"] is True
        assert len(liveness["checks"]) == 1


class TestCircuitBreaker:
    """Test cases for circuit breaker functionality"""
    
    @pytest.fixture
    def health_mgr(self):
        """Create a health monitor with circuit breaker"""
        mgr = HealthMonitor()
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_seconds=1)
        mgr.register_circuit_breaker("test", cb)
        return mgr
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_success(self, health_mgr):
        """Test circuit breaker in closed state with successful operation"""
        async with health_mgr.circuit_breaker("test"):
            # Simulate successful operation
            pass
        
        cb = health_mgr.circuit_breakers["test"]
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_success_time is not None
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_tracking(self, health_mgr):
        """Test circuit breaker failure tracking"""
        cb = health_mgr.circuit_breakers["test"]
        
        # First failure
        with pytest.raises(Exception):
            async with health_mgr.circuit_breaker("test"):
                raise Exception("Test failure")
        
        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED  # Still closed
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            async with health_mgr.circuit_breaker("test"):
                raise Exception("Test failure")
        
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state(self, health_mgr):
        """Test circuit breaker in open state"""
        cb = health_mgr.circuit_breakers["test"]
        
        # Force circuit breaker to open state
        cb.state = CircuitBreakerState.OPEN
        cb.failure_count = 2
        cb.last_failure_time = datetime.utcnow()
        
        # Should raise exception immediately
        with pytest.raises(Exception, match="Circuit breaker test is OPEN"):
            async with health_mgr.circuit_breaker("test"):
                pass
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, health_mgr):
        """Test circuit breaker recovery from half-open state"""
        cb = health_mgr.circuit_breakers["test"]
        
        # Set to half-open state
        cb.state = CircuitBreakerState.HALF_OPEN
        cb.failure_count = 2
        
        # Successful operation should close the circuit
        async with health_mgr.circuit_breaker("test"):
            pass
        
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout_recovery(self, health_mgr):
        """Test circuit breaker timeout-based recovery"""
        cb = health_mgr.circuit_breakers["test"]
        
        # Set to open state with old failure time
        cb.state = CircuitBreakerState.OPEN
        cb.failure_count = 2
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=2)  # Past recovery timeout
        
        # Should move to half-open and allow operation
        async with health_mgr.circuit_breaker("test"):
            pass
        
        assert cb.state == CircuitBreakerState.CLOSED


class TestRetryMechanism:
    """Test cases for retry with backoff"""
    
    @pytest.fixture
    def health_mgr(self):
        """Create a health monitor with retry policy"""
        mgr = HealthMonitor()
        policy = RetryPolicy(max_attempts=3, base_delay_ms=10, max_delay_ms=100)
        mgr.register_retry_policy("test", policy)
        return mgr
    
    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self, health_mgr):
        """Test successful operation on first attempt"""
        call_count = 0
        
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await health_mgr.retry_with_backoff(successful_operation, "test")
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, health_mgr):
        """Test successful operation after some failures"""
        call_count = 0
        
        async def eventually_successful_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await health_mgr.retry_with_backoff(eventually_successful_operation, "test")
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self, health_mgr):
        """Test when all retry attempts fail"""
        call_count = 0
        
        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise Exception("Persistent failure")
        
        with pytest.raises(Exception, match="Persistent failure"):
            await health_mgr.retry_with_backoff(always_failing_operation, "test")
        
        assert call_count == 3  # Should have tried 3 times
    
    @pytest.mark.asyncio
    async def test_retry_with_sync_function(self, health_mgr):
        """Test retry with synchronous function"""
        call_count = 0
        
        def sync_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Failure")
            return "success"
        
        result = await health_mgr.retry_with_backoff(sync_operation, "test")
        
        assert result == "success"
        assert call_count == 2


class TestIdempotencyManager:
    """Test cases for IdempotencyManager"""
    
    @pytest.fixture
    def idempotency_mgr(self):
        """Create an idempotency manager for testing"""
        return IdempotencyManager()
    
    def test_generate_idempotency_key(self, idempotency_mgr):
        """Test idempotency key generation"""
        key1 = idempotency_mgr.generate_idempotency_key("test_op", {"param1": "value1"})
        key2 = idempotency_mgr.generate_idempotency_key("test_op", {"param1": "value1"})
        key3 = idempotency_mgr.generate_idempotency_key("test_op", {"param1": "value2"})
        
        assert key1 == key2  # Same operation and params should generate same key
        assert key1 != key3  # Different params should generate different key
        assert len(key1) == 64  # SHA256 hex string length
    
    @pytest.mark.asyncio
    async def test_execute_idempotent_first_time(self, idempotency_mgr):
        """Test idempotent execution for the first time"""
        call_count = 0
        
        async def test_operation():
            nonlocal call_count
            call_count += 1
            return {"result": "success", "count": call_count}
        
        key = "test_key_1"
        result = await idempotency_mgr.execute_idempotent(key, test_operation)
        
        assert result["result"] == "success"
        assert result["count"] == 1
        assert call_count == 1
        assert key in idempotency_mgr.processed_keys
    
    @pytest.mark.asyncio
    async def test_execute_idempotent_cached_result(self, idempotency_mgr):
        """Test idempotent execution returns cached result"""
        call_count = 0
        
        async def test_operation():
            nonlocal call_count
            call_count += 1
            return {"result": "success", "count": call_count}
        
        key = "test_key_2"
        
        # First execution
        result1 = await idempotency_mgr.execute_idempotent(key, test_operation)
        
        # Second execution should return cached result
        result2 = await idempotency_mgr.execute_idempotent(key, test_operation)
        
        assert result1 == result2
        assert call_count == 1  # Operation should only be called once
    
    @pytest.mark.asyncio
    async def test_execute_idempotent_with_sync_function(self, idempotency_mgr):
        """Test idempotent execution with synchronous function"""
        def sync_operation():
            return {"result": "sync_success"}
        
        key = "test_key_3"
        result = await idempotency_mgr.execute_idempotent(key, sync_operation)
        
        assert result["result"] == "sync_success"
        assert key in idempotency_mgr.processed_keys
    
    @pytest.mark.asyncio
    async def test_execute_idempotent_failure_not_cached(self, idempotency_mgr):
        """Test that failures are not cached"""
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Temporary failure")
            return {"result": "success"}
        
        key = "test_key_4"
        
        # First attempt should fail
        with pytest.raises(Exception, match="Temporary failure"):
            await idempotency_mgr.execute_idempotent(key, failing_operation)
        
        # Key should not be cached
        assert key not in idempotency_mgr.processed_keys
        
        # Second attempt should also fail
        with pytest.raises(Exception, match="Temporary failure"):
            await idempotency_mgr.execute_idempotent(key, failing_operation)
        
        # Third attempt should succeed
        result = await idempotency_mgr.execute_idempotent(key, failing_operation)
        assert result["result"] == "success"
        assert key in idempotency_mgr.processed_keys
    
    def test_cleanup_expired_keys(self, idempotency_mgr):
        """Test cleanup of expired idempotency keys"""
        # Add some keys with different timestamps
        current_time = datetime.utcnow()
        
        idempotency_mgr.processed_keys["fresh_key"] = {
            "result": {"data": "fresh"},
            "timestamp": current_time.isoformat(),
            "operation": "test"
        }
        
        idempotency_mgr.processed_keys["expired_key"] = {
            "result": {"data": "expired"},
            "timestamp": (current_time - timedelta(hours=25)).isoformat(),  # Expired
            "operation": "test"
        }
        
        # Run cleanup
        idempotency_mgr.cleanup_expired_keys()
        
        # Fresh key should remain, expired key should be removed
        assert "fresh_key" in idempotency_mgr.processed_keys
        assert "expired_key" not in idempotency_mgr.processed_keys


class TestGracefulShutdown:
    """Test cases for graceful shutdown"""
    
    @pytest.fixture
    def health_mgr(self):
        """Create a health monitor for testing"""
        return HealthMonitor()
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_handlers(self, health_mgr):
        """Test graceful shutdown handler execution"""
        shutdown_calls = []
        
        async def async_handler():
            shutdown_calls.append("async_handler")
        
        def sync_handler():
            shutdown_calls.append("sync_handler")
        
        health_mgr.register_graceful_shutdown_handler(async_handler)
        health_mgr.register_graceful_shutdown_handler(sync_handler)
        
        await health_mgr.graceful_shutdown()
        
        assert "async_handler" in shutdown_calls
        assert "sync_handler" in shutdown_calls
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_handler_exception(self, health_mgr):
        """Test graceful shutdown continues even if handler fails"""
        shutdown_calls = []
        
        async def failing_handler():
            raise Exception("Handler failed")
        
        def working_handler():
            shutdown_calls.append("working_handler")
        
        health_mgr.register_graceful_shutdown_handler(failing_handler)
        health_mgr.register_graceful_shutdown_handler(working_handler)
        
        # Should not raise exception
        await health_mgr.graceful_shutdown()
        
        # Working handler should still be called
        assert "working_handler" in shutdown_calls


class TestHealthMonitoringIntegration:
    """Integration tests for health monitoring system"""
    
    @pytest.mark.asyncio
    async def test_complete_health_monitoring_workflow(self):
        """Test complete health monitoring workflow"""
        mgr = HealthMonitor()
        
        # Register components
        async def db_check():
            return {"healthy": True, "connections": 5}
        
        async def storage_check():
            return {"healthy": True, "containers": 3}
        
        mgr.register_health_check("database", db_check)
        mgr.register_health_check("storage", storage_check)
        
        # Test overall health
        overall_health = await mgr.get_overall_health()
        assert overall_health["status"] == "healthy"
        assert "database" in overall_health["components"]
        assert "storage" in overall_health["components"]
    
    @pytest.mark.asyncio
    async def test_resilience_patterns_integration(self):
        """Test integration of circuit breaker and retry patterns"""
        mgr = HealthMonitor()
        
        # Register circuit breaker and retry policy
        cb = CircuitBreaker(name="test_service", failure_threshold=2)
        mgr.register_circuit_breaker("test_service", cb)
        
        policy = RetryPolicy(max_attempts=3, base_delay_ms=1)
        mgr.register_retry_policy("test_service", policy)
        
        call_count = 0
        
        async def unreliable_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 4:  # Fail first 4 attempts
                raise Exception("Service unavailable")
            return "success"
        
        # First attempt with circuit breaker and retry
        with pytest.raises(Exception):
            async with mgr.circuit_breaker("test_service"):
                await mgr.retry_with_backoff(unreliable_service, "test_service")
        
        # Circuit breaker should be open after failures
        assert cb.state == CircuitBreakerState.OPEN
        
        # Subsequent calls should fail fast due to open circuit breaker
        with pytest.raises(Exception, match="Circuit breaker test_service is OPEN"):
            async with mgr.circuit_breaker("test_service"):
                await mgr.retry_with_backoff(unreliable_service, "test_service")


if __name__ == "__main__":
    pytest.main([__file__])