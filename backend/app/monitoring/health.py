"""
Application health monitoring and resilience patterns
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import uuid
import json

from app.config import settings
from app.database.connection import get_cosmos_db
from app.storage.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    component: str
    status: HealthStatus
    timestamp: datetime
    response_time_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class RetryPolicy:
    """Retry policy configuration"""
    max_attempts: int = 3
    base_delay_ms: int = 100
    max_delay_ms: int = 5000
    exponential_base: float = 2.0
    jitter: bool = True


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    name: str
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None


class HealthMonitor:
    """Application health monitoring and resilience manager"""
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_policies: Dict[str, RetryPolicy] = {}
        self.graceful_shutdown_handlers: List[Callable] = []
        self.startup_checks: List[Callable] = []
        self.readiness_checks: List[Callable] = []
        self.liveness_checks: List[Callable] = []
        
        # Initialize default components
        self._register_default_health_checks()
        self._register_default_circuit_breakers()
        self._register_default_retry_policies()
    
    def _register_default_health_checks(self):
        """Register default health checks for core components"""
        self.register_health_check("database", self._check_database_health)
        self.register_health_check("storage", self._check_storage_health)
        self.register_health_check("memory", self._check_memory_health)
        self.register_health_check("disk", self._check_disk_health)
    
    def _register_default_circuit_breakers(self):
        """Register default circuit breakers"""
        self.register_circuit_breaker("database", CircuitBreaker(
            name="database",
            failure_threshold=3,
            recovery_timeout_seconds=30
        ))
        
        self.register_circuit_breaker("storage", CircuitBreaker(
            name="storage",
            failure_threshold=5,
            recovery_timeout_seconds=60
        ))
    
    def _register_default_retry_policies(self):
        """Register default retry policies"""
        self.register_retry_policy("database", RetryPolicy(
            max_attempts=3,
            base_delay_ms=100,
            max_delay_ms=2000
        ))
        
        self.register_retry_policy("storage", RetryPolicy(
            max_attempts=5,
            base_delay_ms=200,
            max_delay_ms=5000
        ))
        
        self.register_retry_policy("api", RetryPolicy(
            max_attempts=2,
            base_delay_ms=50,
            max_delay_ms=1000
        ))
    
    def register_health_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = check_func
        logger.info(f"Registered health check: {name}")
    
    def register_circuit_breaker(self, name: str, circuit_breaker: CircuitBreaker):
        """Register a circuit breaker"""
        self.circuit_breakers[name] = circuit_breaker
        logger.info(f"Registered circuit breaker: {name}")
    
    def register_retry_policy(self, name: str, retry_policy: RetryPolicy):
        """Register a retry policy"""
        self.retry_policies[name] = retry_policy
        logger.info(f"Registered retry policy: {name}")
    
    def register_graceful_shutdown_handler(self, handler: Callable):
        """Register a graceful shutdown handler"""
        self.graceful_shutdown_handlers.append(handler)
        logger.info(f"Registered graceful shutdown handler: {handler.__name__}")
    
    def register_startup_check(self, check_func: Callable):
        """Register a startup readiness check"""
        self.startup_checks.append(check_func)
        logger.info(f"Registered startup check: {check_func.__name__}")
    
    def register_readiness_check(self, check_func: Callable):
        """Register a readiness check"""
        self.readiness_checks.append(check_func)
        logger.info(f"Registered readiness check: {check_func.__name__}")
    
    def register_liveness_check(self, check_func: Callable):
        """Register a liveness check"""
        self.liveness_checks.append(check_func)
        logger.info(f"Registered liveness check: {check_func.__name__}")
    
    async def perform_health_check(self, component: str) -> HealthCheckResult:
        """Perform a health check for a specific component"""
        if component not in self.health_checks:
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.utcnow(),
                response_time_ms=0,
                error=f"No health check registered for component: {component}"
            )
        
        start_time = time.time()
        
        try:
            check_func = self.health_checks[component]
            result = await check_func()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                component=component,
                status=HealthStatus.HEALTHY if result.get("healthy", False) else HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=response_time_ms,
                details=result
            )
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Health check failed for {component}: {e}")
            
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                response_time_ms=response_time_ms,
                error=str(e)
            )
    
    async def perform_all_health_checks(self) -> Dict[str, HealthCheckResult]:
        """Perform all registered health checks"""
        results = {}
        
        # Run health checks concurrently
        tasks = [
            self.perform_health_check(component)
            for component in self.health_checks.keys()
        ]
        
        health_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(health_results):
            component = list(self.health_checks.keys())[i]
            
            if isinstance(result, Exception):
                results[component] = HealthCheckResult(
                    component=component,
                    status=HealthStatus.UNHEALTHY,
                    timestamp=datetime.utcnow(),
                    response_time_ms=0,
                    error=str(result)
                )
            else:
                results[component] = result
        
        return results
    
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall application health status"""
        health_results = await self.perform_all_health_checks()
        
        # Determine overall status
        statuses = [result.status for result in health_results.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                name: {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "details": result.details,
                    "error": result.error
                }
                for name, result in health_results.items()
            },
            "circuit_breakers": {
                name: {
                    "state": cb.state.value,
                    "failure_count": cb.failure_count,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                }
                for name, cb in self.circuit_breakers.items()
            }
        }
    
    async def check_readiness(self) -> Dict[str, Any]:
        """Check if application is ready to serve traffic"""
        readiness_results = []
        
        for check_func in self.readiness_checks:
            try:
                result = await check_func()
                readiness_results.append({
                    "check": check_func.__name__,
                    "ready": result.get("ready", False),
                    "details": result
                })
            except Exception as e:
                readiness_results.append({
                    "check": check_func.__name__,
                    "ready": False,
                    "error": str(e)
                })
        
        all_ready = all(result["ready"] for result in readiness_results)
        
        return {
            "ready": all_ready,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": readiness_results
        }
    
    async def check_liveness(self) -> Dict[str, Any]:
        """Check if application is alive and should not be restarted"""
        liveness_results = []
        
        for check_func in self.liveness_checks:
            try:
                result = await check_func()
                liveness_results.append({
                    "check": check_func.__name__,
                    "alive": result.get("alive", False),
                    "details": result
                })
            except Exception as e:
                liveness_results.append({
                    "check": check_func.__name__,
                    "alive": False,
                    "error": str(e)
                })
        
        all_alive = all(result["alive"] for result in liveness_results)
        
        return {
            "alive": all_alive,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": liveness_results
        }
    
    @asynccontextmanager
    async def circuit_breaker(self, name: str):
        """Circuit breaker context manager"""
        if name not in self.circuit_breakers:
            # If no circuit breaker registered, just execute normally
            yield
            return
        
        cb = self.circuit_breakers[name]
        
        # Check circuit breaker state
        if cb.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (cb.last_failure_time and 
                datetime.utcnow() - cb.last_failure_time > timedelta(seconds=cb.recovery_timeout_seconds)):
                cb.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"Circuit breaker {name} moved to HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker {name} is OPEN")
        
        try:
            yield
            
            # Success - reset failure count and update state
            cb.failure_count = 0
            cb.last_success_time = datetime.utcnow()
            
            if cb.state == CircuitBreakerState.HALF_OPEN:
                cb.state = CircuitBreakerState.CLOSED
                logger.info(f"Circuit breaker {name} moved to CLOSED state")
                
        except Exception as e:
            # Failure - increment failure count
            cb.failure_count += 1
            cb.last_failure_time = datetime.utcnow()
            
            # Check if we should open the circuit breaker
            if cb.failure_count >= cb.failure_threshold:
                cb.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker {name} moved to OPEN state after {cb.failure_count} failures")
            
            raise e
    
    async def retry_with_backoff(self, operation: Callable, policy_name: str = "default", *args, **kwargs):
        """Execute operation with retry and exponential backoff"""
        policy = self.retry_policies.get(policy_name, RetryPolicy())
        
        last_exception = None
        
        for attempt in range(policy.max_attempts):
            try:
                if asyncio.iscoroutinefunction(operation):
                    return await operation(*args, **kwargs)
                else:
                    return operation(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                if attempt == policy.max_attempts - 1:
                    # Last attempt, don't wait
                    break
                
                # Calculate delay with exponential backoff
                delay_ms = min(
                    policy.base_delay_ms * (policy.exponential_base ** attempt),
                    policy.max_delay_ms
                )
                
                # Add jitter if enabled
                if policy.jitter:
                    import random
                    delay_ms *= (0.5 + random.random() * 0.5)
                
                logger.warning(f"Attempt {attempt + 1} failed for {operation.__name__}: {e}. Retrying in {delay_ms:.0f}ms")
                await asyncio.sleep(delay_ms / 1000)
        
        # All attempts failed
        logger.error(f"All {policy.max_attempts} attempts failed for {operation.__name__}")
        raise last_exception
    
    async def graceful_shutdown(self):
        """Perform graceful shutdown"""
        logger.info("Starting graceful shutdown...")
        
        # Run all shutdown handlers
        for handler in self.graceful_shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
                logger.info(f"Executed shutdown handler: {handler.__name__}")
            except Exception as e:
                logger.error(f"Error in shutdown handler {handler.__name__}: {e}")
        
        logger.info("Graceful shutdown completed")
    
    # Default health check implementations
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            
            cosmos_db = await get_cosmos_db()
            health_result = await cosmos_db.health_check()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return {
                "healthy": health_result.get("status") == "healthy",
                "response_time_ms": response_time_ms,
                "database": health_result.get("database"),
                "containers": health_result.get("containers", {}),
                "error": health_result.get("error")
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def _check_storage_health(self) -> Dict[str, Any]:
        """Check blob storage connectivity and performance"""
        try:
            start_time = time.time()
            
            storage_service = BlobStorageService()
            
            # Test basic connectivity by checking container properties
            container_properties = storage_service.container_client.get_container_properties()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return {
                "healthy": True,
                "response_time_ms": response_time_ms,
                "container": settings.azure_storage_container_name,
                "storage_account": settings.azure_storage_account_name
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def _check_memory_health(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            
            # Consider unhealthy if memory usage > 90%
            healthy = memory.percent < 90
            
            return {
                "healthy": healthy,
                "memory_percent": memory.percent,
                "memory_available_mb": memory.available / (1024 * 1024),
                "memory_total_mb": memory.total / (1024 * 1024)
            }
            
        except ImportError:
            # psutil not available, assume healthy
            return {
                "healthy": True,
                "note": "Memory monitoring not available (psutil not installed)"
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def _check_disk_health(self) -> Dict[str, Any]:
        """Check disk usage"""
        try:
            import psutil
            
            disk = psutil.disk_usage('/')
            
            # Consider unhealthy if disk usage > 85%
            disk_percent = (disk.used / disk.total) * 100
            healthy = disk_percent < 85
            
            return {
                "healthy": healthy,
                "disk_percent": disk_percent,
                "disk_free_mb": disk.free / (1024 * 1024),
                "disk_total_mb": disk.total / (1024 * 1024)
            }
            
        except ImportError:
            # psutil not available, assume healthy
            return {
                "healthy": True,
                "note": "Disk monitoring not available (psutil not installed)"
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }


class IdempotencyManager:
    """Manages idempotency keys for write operations"""
    
    def __init__(self):
        self.processed_keys: Dict[str, Dict[str, Any]] = {}
        self.key_expiry_hours = 24
    
    def generate_idempotency_key(self, operation: str, params: Dict[str, Any]) -> str:
        """Generate an idempotency key for an operation"""
        import hashlib
        
        # Create a deterministic key based on operation and parameters
        key_data = f"{operation}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def execute_idempotent(
        self, 
        idempotency_key: str, 
        operation: Callable, 
        *args, 
        **kwargs
    ) -> Dict[str, Any]:
        """Execute an operation idempotently"""
        
        # Check if we've already processed this key
        if idempotency_key in self.processed_keys:
            stored_result = self.processed_keys[idempotency_key]
            
            # Check if result is still valid (not expired)
            stored_time = datetime.fromisoformat(stored_result["timestamp"])
            if datetime.utcnow() - stored_time < timedelta(hours=self.key_expiry_hours):
                logger.info(f"Returning cached result for idempotency key: {idempotency_key}")
                return stored_result["result"]
            else:
                # Expired, remove from cache
                del self.processed_keys[idempotency_key]
        
        # Execute the operation
        try:
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)
            
            # Store the result
            self.processed_keys[idempotency_key] = {
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
                "operation": operation.__name__
            }
            
            return result
            
        except Exception as e:
            # Don't cache failures
            logger.error(f"Idempotent operation failed for key {idempotency_key}: {e}")
            raise
    
    def cleanup_expired_keys(self):
        """Clean up expired idempotency keys"""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, data in self.processed_keys.items():
            stored_time = datetime.fromisoformat(data["timestamp"])
            if current_time - stored_time >= timedelta(hours=self.key_expiry_hours):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.processed_keys[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired idempotency keys")


# Global instances
health_monitor = HealthMonitor()
idempotency_manager = IdempotencyManager()