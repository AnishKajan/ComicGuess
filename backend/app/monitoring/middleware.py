"""
Monitoring middleware for FastAPI application.
Provides request/response logging, performance monitoring, and error tracking.
"""

import time
import json
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .logging_config import get_logger, set_correlation_id, get_correlation_id, metrics
from .error_tracking import error_tracker, ErrorSeverity, ErrorCategory, ErrorContext
from .tracing import TracingContext, SpanKind, set_trace_context, get_trace_id, get_span_id

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request monitoring."""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.logger = get_logger("middleware.monitoring")
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip monitoring for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Set correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or set_correlation_id()
        
        # Set up distributed tracing
        trace_id_header = request.headers.get("X-Trace-ID")
        span_id_header = request.headers.get("X-Span-ID")
        parent_span_id_header = request.headers.get("X-Parent-Span-ID")
        
        # Create tracing context for the request
        with TracingContext(
            f"{request.method} {request.url.path}",
            SpanKind.SERVER,
            parent_trace_id=trace_id_header,
            parent_span_id=parent_span_id_header
        ) as trace_ctx:
            # Add request tags to span
            trace_ctx.add_tag("http.method", request.method)
            trace_ctx.add_tag("http.path", request.url.path)
            trace_ctx.add_tag("http.query", str(request.query_params))
            trace_ctx.add_tag("http.user_agent", request.headers.get('user-agent', ''))
            trace_ctx.add_tag("http.client_ip", self._get_client_ip(request))
            trace_ctx.add_tag("correlation_id", correlation_id)
            
            # Start timing
            start_time = time.time()
        
            # Log request with tracing context
            self.logger.info(
                f"Request started",
                extra={
                    'method': request.method,
                    'path': request.url.path,
                    'query_params': str(request.query_params),
                    'user_agent': request.headers.get('user-agent'),
                    'client_ip': self._get_client_ip(request),
                    'content_length': request.headers.get('content-length', 0),
                    'trace_id': get_trace_id(),
                    'span_id': get_span_id()
                }
            )
        
            # Record request metrics
            metrics.increment_counter(
                'requests_total',
                tags={
                    'method': request.method,
                    'path': request.url.path
                }
            )
            
            try:
                # Process request
                response = await call_next(request)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Add response tags to span
                trace_ctx.add_tag("http.status_code", response.status_code)
                trace_ctx.add_tag("http.response_size", response.headers.get('content-length', 0))
                
                # Log response with tracing context
                self.logger.info(
                    f"Request completed",
                    extra={
                        'method': request.method,
                        'path': request.url.path,
                        'status_code': response.status_code,
                        'duration_ms': round(duration * 1000, 2),
                        'response_size': response.headers.get('content-length', 0),
                        'trace_id': get_trace_id(),
                        'span_id': get_span_id()
                    }
                )
                
                # Record response metrics
                metrics.record_histogram(
                    'request_duration_ms',
                    duration * 1000,
                    tags={
                        'method': request.method,
                        'path': request.url.path,
                        'status_code': str(response.status_code)
                    }
                )
                
                metrics.increment_counter(
                    'responses_total',
                    tags={
                        'method': request.method,
                        'path': request.url.path,
                        'status_code': str(response.status_code)
                    }
                )
                
                # Add tracing headers to response
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Trace-ID"] = get_trace_id() or ""
                response.headers["X-Span-ID"] = get_span_id() or ""
                
                return response
                
            except Exception as e:
                # Calculate duration for failed requests
                duration = time.time() - start_time
                
                # Add error tags to span
                trace_ctx.add_tag("error", True)
                trace_ctx.add_tag("error.type", type(e).__name__)
                trace_ctx.add_tag("error.message", str(e))
                
                # Create error context
                error_context = ErrorContext(
                    request_path=request.url.path,
                    request_method=request.method,
                    user_agent=request.headers.get('user-agent'),
                    ip_address=self._get_client_ip(request)
                )
                
                # Track error
                error_id = error_tracker.track_error(
                    e,
                    ErrorSeverity.HIGH,
                    ErrorCategory.SYSTEM,
                    error_context
                )
                
                # Log error with tracing context
                self.logger.error(
                    f"Request failed",
                    extra={
                        'method': request.method,
                        'path': request.url.path,
                        'duration_ms': round(duration * 1000, 2),
                        'error_id': error_id,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'trace_id': get_trace_id(),
                        'span_id': get_span_id()
                    }
                )
                
                # Record error metrics
                metrics.increment_counter(
                    'request_errors_total',
                    tags={
                        'method': request.method,
                        'path': request.url.path,
                        'error_type': type(e).__name__
                    }
                )
                
                # Return error response with tracing headers
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Internal server error",
                        "error_id": error_id,
                        "correlation_id": correlation_id,
                        "trace_id": get_trace_id()
                    },
                    headers={
                        "X-Correlation-ID": correlation_id,
                        "X-Trace-ID": get_trace_id() or "",
                        "X-Span-ID": get_span_id() or ""
                    }
                )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else 'unknown'

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for detailed performance monitoring."""
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.logger = get_logger("middleware.performance")
        self.slow_request_threshold = slow_request_threshold  # seconds
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Add performance markers
        request.state.start_time = start_time
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        # Log slow requests
        if duration > self.slow_request_threshold:
            self.logger.warning(
                f"Slow request detected",
                extra={
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': round(duration * 1000, 2),
                    'threshold_ms': self.slow_request_threshold * 1000,
                    'query_params': str(request.query_params)
                }
            )
            
            # Record slow request metric
            metrics.increment_counter(
                'slow_requests_total',
                tags={
                    'method': request.method,
                    'path': request.url.path
                }
            )
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{round(duration * 1000, 2)}ms"
        
        return response

class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for security monitoring and logging."""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger("middleware.security")
        self.suspicious_patterns = [
            'script', 'javascript:', 'vbscript:', 'onload', 'onerror',
            '../', '..\\', '/etc/passwd', 'cmd.exe', 'powershell'
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check for suspicious patterns in URL and headers
        suspicious_activity = False
        
        # Check URL path
        path_lower = request.url.path.lower()
        for pattern in self.suspicious_patterns:
            if pattern in path_lower:
                suspicious_activity = True
                break
        
        # Check query parameters
        if not suspicious_activity:
            query_string = str(request.query_params).lower()
            for pattern in self.suspicious_patterns:
                if pattern in query_string:
                    suspicious_activity = True
                    break
        
        # Check User-Agent for known bad patterns
        user_agent = request.headers.get('user-agent', '').lower()
        bad_user_agents = ['sqlmap', 'nikto', 'nmap', 'masscan', 'nessus']
        if any(bad_agent in user_agent for bad_agent in bad_user_agents):
            suspicious_activity = True
        
        # Log suspicious activity
        if suspicious_activity:
            self.logger.warning(
                f"Suspicious request detected",
                extra={
                    'method': request.method,
                    'path': request.url.path,
                    'query_params': str(request.query_params),
                    'user_agent': request.headers.get('user-agent'),
                    'client_ip': request.client.host if request.client else 'unknown',
                    'referer': request.headers.get('referer')
                }
            )
            
            metrics.increment_counter(
                'suspicious_requests_total',
                tags={
                    'method': request.method,
                    'client_ip': request.client.host if request.client else 'unknown'
                }
            )
        
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response