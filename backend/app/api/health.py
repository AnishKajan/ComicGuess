"""
Health monitoring API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
import asyncio
import logging

from app.monitoring.health import health_monitor, idempotency_manager
from app.auth.middleware import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    Returns overall application health status
    """
    try:
        health_status = await health_monitor.get_overall_health()
        
        # Return appropriate HTTP status based on health
        if health_status["status"] == "unhealthy":
            raise HTTPException(status_code=503, detail=health_status)
        elif health_status["status"] == "degraded":
            # Still return 200 for degraded state, but include warning
            health_status["warning"] = "Some components are degraded"
        
        return health_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": "Health check system failure",
                "details": str(e)
            }
        )


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint
    Returns whether the application is ready to serve traffic
    """
    try:
        readiness_status = await health_monitor.check_readiness()
        
        if not readiness_status["ready"]:
            raise HTTPException(status_code=503, detail=readiness_status)
        
        return readiness_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "error": "Readiness check system failure",
                "details": str(e)
            }
        )


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check endpoint
    Returns whether the application is alive and should not be restarted
    """
    try:
        liveness_status = await health_monitor.check_liveness()
        
        if not liveness_status["alive"]:
            raise HTTPException(status_code=503, detail=liveness_status)
        
        return liveness_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "alive": False,
                "error": "Liveness check system failure",
                "details": str(e)
            }
        )


@router.get("/components/{component}")
async def component_health_check(component: str) -> Dict[str, Any]:
    """
    Check health of a specific component
    """
    try:
        health_result = await health_monitor.perform_health_check(component)
        
        response = {
            "component": health_result.component,
            "status": health_result.status.value,
            "timestamp": health_result.timestamp.isoformat(),
            "response_time_ms": health_result.response_time_ms,
            "details": health_result.details
        }
        
        if health_result.error:
            response["error"] = health_result.error
        
        # Return appropriate HTTP status
        if health_result.status.value == "unhealthy":
            raise HTTPException(status_code=503, detail=response)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component health check failed for {component}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "component": component,
                "status": "unknown",
                "error": str(e)
            }
        )


@router.get("/detailed")
async def detailed_health_check(
    current_user: Optional[Dict] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Detailed health check with component breakdown
    Requires authentication for detailed information
    """
    try:
        # Get basic health status
        health_status = await health_monitor.get_overall_health()
        
        # Add additional details if user is authenticated
        if current_user:
            # Add circuit breaker states
            health_status["circuit_breakers"] = {
                name: {
                    "state": cb.state.value,
                    "failure_count": cb.failure_count,
                    "failure_threshold": cb.failure_threshold,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None,
                    "last_success": cb.last_success_time.isoformat() if cb.last_success_time else None
                }
                for name, cb in health_monitor.circuit_breakers.items()
            }
            
            # Add retry policy information
            health_status["retry_policies"] = {
                name: {
                    "max_attempts": policy.max_attempts,
                    "base_delay_ms": policy.base_delay_ms,
                    "max_delay_ms": policy.max_delay_ms
                }
                for name, policy in health_monitor.retry_policies.items()
            }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unknown",
                "error": str(e)
            }
        )


@router.post("/circuit-breaker/{name}/reset")
async def reset_circuit_breaker(
    name: str,
    current_user: Dict = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Reset a circuit breaker (requires authentication)
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if name not in health_monitor.circuit_breakers:
        raise HTTPException(status_code=404, detail=f"Circuit breaker '{name}' not found")
    
    try:
        cb = health_monitor.circuit_breakers[name]
        cb.state = health_monitor.CircuitBreakerState.CLOSED
        cb.failure_count = 0
        cb.last_failure_time = None
        
        logger.info(f"Circuit breaker '{name}' reset by user {current_user.get('id', 'unknown')}")
        
        return {
            "circuit_breaker": name,
            "status": "reset",
            "new_state": cb.state.value,
            "timestamp": health_monitor.datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker '{name}': {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "circuit_breaker": name,
                "status": "failed",
                "error": str(e)
            }
        )


@router.get("/metrics")
async def health_metrics() -> Dict[str, Any]:
    """
    Get health monitoring metrics
    """
    try:
        # Perform all health checks to get current metrics
        health_results = await health_monitor.perform_all_health_checks()
        
        # Calculate metrics
        total_components = len(health_results)
        healthy_components = sum(1 for result in health_results.values() 
                               if result.status.value == "healthy")
        unhealthy_components = sum(1 for result in health_results.values() 
                                 if result.status.value == "unhealthy")
        
        avg_response_time = sum(result.response_time_ms for result in health_results.values()) / total_components if total_components > 0 else 0
        
        # Circuit breaker metrics
        open_circuit_breakers = sum(1 for cb in health_monitor.circuit_breakers.values() 
                                  if cb.state.value == "open")
        
        return {
            "timestamp": health_monitor.datetime.utcnow().isoformat(),
            "components": {
                "total": total_components,
                "healthy": healthy_components,
                "unhealthy": unhealthy_components,
                "health_percentage": (healthy_components / total_components * 100) if total_components > 0 else 0
            },
            "performance": {
                "average_response_time_ms": avg_response_time,
                "slowest_component": max(health_results.items(), 
                                       key=lambda x: x[1].response_time_ms)[0] if health_results else None
            },
            "circuit_breakers": {
                "total": len(health_monitor.circuit_breakers),
                "open": open_circuit_breakers,
                "closed": len(health_monitor.circuit_breakers) - open_circuit_breakers
            },
            "idempotency": {
                "cached_operations": len(idempotency_manager.processed_keys)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get health metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to collect health metrics",
                "details": str(e)
            }
        )


@router.post("/maintenance")
async def trigger_maintenance_tasks(
    background_tasks: BackgroundTasks,
    current_user: Optional[Dict] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Trigger maintenance tasks (cleanup, etc.)
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Schedule maintenance tasks in background
        background_tasks.add_task(idempotency_manager.cleanup_expired_keys)
        
        return {
            "status": "scheduled",
            "tasks": ["cleanup_expired_idempotency_keys"],
            "timestamp": health_monitor.datetime.utcnow().isoformat(),
            "triggered_by": current_user.get("id", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger maintenance tasks: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "failed",
                "error": str(e)
            }
        )


# Startup event handlers for health monitoring
async def startup_health_checks():
    """Run startup health checks"""
    logger.info("Running startup health checks...")
    
    try:
        # Register default startup checks
        health_monitor.register_startup_check(_check_database_startup)
        health_monitor.register_startup_check(_check_storage_startup)
        
        # Register default readiness checks
        health_monitor.register_readiness_check(_check_database_readiness)
        health_monitor.register_readiness_check(_check_storage_readiness)
        
        # Register default liveness checks
        health_monitor.register_liveness_check(_check_basic_liveness)
        
        # Register graceful shutdown handlers
        health_monitor.register_graceful_shutdown_handler(_graceful_database_shutdown)
        health_monitor.register_graceful_shutdown_handler(_graceful_storage_shutdown)
        
        logger.info("Health monitoring system initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize health monitoring: {e}")
        raise


# Default check implementations
async def _check_database_startup() -> Dict[str, Any]:
    """Check if database is ready for startup"""
    try:
        from app.database.connection import get_cosmos_db
        cosmos_db = await get_cosmos_db()
        health_result = await cosmos_db.health_check()
        
        return {
            "ready": health_result.get("status") == "healthy",
            "component": "database"
        }
    except Exception as e:
        return {
            "ready": False,
            "component": "database",
            "error": str(e)
        }


async def _check_storage_startup() -> Dict[str, Any]:
    """Check if storage is ready for startup"""
    try:
        from app.storage.blob_storage import BlobStorageService
        storage = BlobStorageService()
        container_properties = storage.container_client.get_container_properties()
        
        return {
            "ready": container_properties is not None,
            "component": "storage"
        }
    except Exception as e:
        return {
            "ready": False,
            "component": "storage",
            "error": str(e)
        }


async def _check_database_readiness() -> Dict[str, Any]:
    """Check if database is ready to serve requests"""
    return await _check_database_startup()


async def _check_storage_readiness() -> Dict[str, Any]:
    """Check if storage is ready to serve requests"""
    return await _check_storage_startup()


async def _check_basic_liveness() -> Dict[str, Any]:
    """Basic liveness check"""
    return {
        "alive": True,
        "component": "application"
    }


async def _graceful_database_shutdown():
    """Gracefully shutdown database connections"""
    try:
        from app.database.connection import close_cosmos_db
        await close_cosmos_db()
        logger.info("Database connections closed gracefully")
    except Exception as e:
        logger.error(f"Error during database shutdown: {e}")


async def _graceful_storage_shutdown():
    """Gracefully shutdown storage connections"""
    try:
        # Storage connections are typically closed automatically
        logger.info("Storage connections closed gracefully")
    except Exception as e:
        logger.error(f"Error during storage shutdown: {e}")