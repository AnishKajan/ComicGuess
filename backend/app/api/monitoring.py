"""
Monitoring and health check API endpoints.
Provides health checks, metrics, and system information.
"""

import os
from datetime import datetime
from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Dict, Any

from ..monitoring.error_tracking import health_checker, error_tracker
from ..monitoring.logging_config import get_logger

router = APIRouter()
logger = get_logger("api.monitoring")

class HealthResponse(BaseModel):
    status: str
    timestamp: str = None

class VersionResponse(BaseModel):
    version: str
    build_time: str = None
    commit_hash: str = None

class PingResponse(BaseModel):
    pong: bool

@router.get("/health/liveness", response_model=HealthResponse)
async def liveness_check():
    """
    Liveness probe - indicates if the application is running.
    Used by orchestrators to determine if the container should be restarted.
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat()
    )

@router.get("/health/readiness", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness probe - indicates if the application is ready to serve traffic.
    Used by load balancers to determine if traffic should be routed to this instance.
    """
    try:
        # Run health checks
        health_results = await health_checker.run_health_checks()
        
        if health_results["overall_status"] == "healthy":
            return HealthResponse(
                status="ready",
                timestamp=datetime.utcnow().isoformat()
            )
        else:
            logger.warning("Readiness check failed", extra={"health_results": health_results})
            return HealthResponse(
                status="not_ready",
                timestamp=datetime.utcnow().isoformat()
            )
    except Exception as e:
        logger.error(f"Readiness check error: {e}")
        return HealthResponse(
            status="not_ready",
            timestamp=datetime.utcnow().isoformat()
        )

@router.get("/metrics")
async def metrics():
    """
    Prometheus-style metrics endpoint.
    Returns metrics in text/plain format for monitoring systems.
    """
    # Basic application metrics
    metrics_data = [
        "# HELP app_up Application is running",
        "# TYPE app_up gauge",
        "app_up 1",
        "",
        "# HELP app_start_time_seconds Time when the application started",
        "# TYPE app_start_time_seconds gauge",
        f"app_start_time_seconds {datetime.utcnow().timestamp()}",
        "",
        "# HELP app_errors_total Total number of application errors",
        "# TYPE app_errors_total counter",
    ]
    
    # Add error metrics
    error_summary = error_tracker.get_error_summary(hours=1)
    metrics_data.append(f"app_errors_total {error_summary['total_errors']}")
    
    # Add error rate
    metrics_data.extend([
        "",
        "# HELP app_error_rate_per_hour Error rate per hour",
        "# TYPE app_error_rate_per_hour gauge",
        f"app_error_rate_per_hour {error_summary['error_rate']}"
    ])
    
    metrics_text = "\n".join(metrics_data)
    
    return Response(
        content=metrics_text,
        media_type="text/plain"
    )

@router.get("/version", response_model=VersionResponse)
async def version_info():
    """
    Application version and build information.
    """
    version = os.getenv("APP_VERSION", "dev")
    build_time = os.getenv("BUILD_TIME", datetime.utcnow().isoformat())
    commit_hash = os.getenv("COMMIT_HASH", "unknown")
    
    return VersionResponse(
        version=version,
        build_time=build_time,
        commit_hash=commit_hash
    )

@router.get("/ping", response_model=PingResponse)
async def ping():
    """
    Simple ping endpoint for basic connectivity testing.
    """
    return PingResponse(pong=True)

@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with component status.
    """
    try:
        health_results = await health_checker.run_health_checks()
        error_summary = error_tracker.get_error_summary(hours=1)
        
        return {
            "status": health_results["overall_status"],
            "timestamp": datetime.utcnow().isoformat(),
            "components": health_results["checks"],
            "error_summary": error_summary,
            "uptime_seconds": (datetime.utcnow() - datetime.utcnow()).total_seconds()  # Placeholder
        }
    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }