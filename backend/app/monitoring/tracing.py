"""
Distributed tracing implementation for ComicGuess application.
Provides trace and span correlation across frontend-backend boundaries.
"""

import uuid
import time
import json
from typing import Dict, Any, Optional, List
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from functools import wraps

from .logging_config import get_logger

# Context variables for distributed tracing
trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
span_id: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
parent_span_id: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)

class SpanKind(Enum):
    """Types of spans for categorization."""
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"

class SpanStatus(Enum):
    """Span completion status."""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

@dataclass
class SpanEvent:
    """Event within a span."""
    timestamp: float
    name: str
    attributes: Dict[str, Any]

@dataclass
class Span:
    """Distributed tracing span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: SpanStatus = SpanStatus.OK
    kind: SpanKind = SpanKind.INTERNAL
    tags: Dict[str, Any] = None
    logs: List[SpanEvent] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.logs is None:
            self.logs = []
    
    def add_tag(self, key: str, value: Any):
        """Add a tag to the span."""
        self.tags[key] = value
    
    def add_log(self, name: str, **attributes):
        """Add a log event to the span."""
        event = SpanEvent(
            timestamp=time.time(),
            name=name,
            attributes=attributes
        )
        self.logs.append(event)
    
    def set_error(self, error: Exception):
        """Mark span as error and record error details."""
        self.status = SpanStatus.ERROR
        self.error = str(error)
        self.add_tag("error", True)
        self.add_tag("error.type", type(error).__name__)
        self.add_tag("error.message", str(error))
    
    def finish(self):
        """Complete the span."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)

class TraceCollector:
    """Collects and manages distributed traces."""
    
    def __init__(self):
        self.spans: Dict[str, List[Span]] = {}
        self.logger = get_logger("tracing")
        self.max_spans_per_trace = 1000
    
    def add_span(self, span: Span):
        """Add a span to the trace collection."""
        if span.trace_id not in self.spans:
            self.spans[span.trace_id] = []
        
        self.spans[span.trace_id].append(span)
        
        # Prevent memory leaks by limiting spans per trace
        if len(self.spans[span.trace_id]) > self.max_spans_per_trace:
            self.spans[span.trace_id].pop(0)
        
        # Log span completion
        self.logger.info(
            f"Span completed: {span.operation_name}",
            extra={
                'trace_id': span.trace_id,
                'span_id': span.span_id,
                'parent_span_id': span.parent_span_id,
                'operation_name': span.operation_name,
                'duration_ms': span.duration_ms,
                'status': span.status.value,
                'kind': span.kind.value,
                'tags': span.tags,
                'error': span.error
            }
        )
    
    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace."""
        return self.spans.get(trace_id, [])
    
    def export_trace(self, trace_id: str) -> Dict[str, Any]:
        """Export trace in OpenTelemetry-compatible format."""
        spans = self.get_trace(trace_id)
        if not spans:
            return {}
        
        return {
            'traceId': trace_id,
            'spans': [
                {
                    'traceId': span.trace_id,
                    'spanId': span.span_id,
                    'parentSpanId': span.parent_span_id,
                    'operationName': span.operation_name,
                    'startTime': span.start_time,
                    'endTime': span.end_time,
                    'duration': span.duration_ms,
                    'status': span.status.value,
                    'kind': span.kind.value,
                    'tags': span.tags,
                    'logs': [asdict(log) for log in span.logs],
                    'error': span.error
                }
                for span in spans
            ]
        }
    
    def cleanup_old_traces(self, max_age_hours: int = 24):
        """Remove traces older than specified hours."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        traces_to_remove = []
        
        for trace_id, spans in self.spans.items():
            if spans and spans[-1].end_time and spans[-1].end_time < cutoff_time:
                traces_to_remove.append(trace_id)
        
        for trace_id in traces_to_remove:
            del self.spans[trace_id]
        
        if traces_to_remove:
            self.logger.info(f"Cleaned up {len(traces_to_remove)} old traces")

# Global trace collector
trace_collector = TraceCollector()

class TracingContext:
    """Context manager for distributed tracing."""
    
    def __init__(self, operation_name: str, kind: SpanKind = SpanKind.INTERNAL, 
                 parent_trace_id: Optional[str] = None, parent_span_id: Optional[str] = None):
        self.operation_name = operation_name
        self.kind = kind
        self.span: Optional[Span] = None
        self.parent_trace_id = parent_trace_id
        self.parent_span_id = parent_span_id
        
        # Store previous context values
        self.prev_trace_id = None
        self.prev_span_id = None
        self.prev_parent_span_id = None
    
    def __enter__(self) -> 'TracingContext':
        # Store previous context
        self.prev_trace_id = trace_id.get()
        self.prev_span_id = span_id.get()
        self.prev_parent_span_id = parent_span_id.get()
        
        # Create new span
        current_trace_id = self.parent_trace_id or self.prev_trace_id or str(uuid.uuid4())
        current_span_id = str(uuid.uuid4())
        current_parent_span_id = self.parent_span_id or self.prev_span_id
        
        self.span = Span(
            trace_id=current_trace_id,
            span_id=current_span_id,
            parent_span_id=current_parent_span_id,
            operation_name=self.operation_name,
            start_time=time.time(),
            kind=self.kind
        )
        
        # Set context variables
        trace_id.set(current_trace_id)
        span_id.set(current_span_id)
        parent_span_id.set(current_parent_span_id)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                self.span.set_error(exc_val)
            
            self.span.finish()
            trace_collector.add_span(self.span)
        
        # Restore previous context
        trace_id.set(self.prev_trace_id)
        span_id.set(self.prev_span_id)
        parent_span_id.set(self.prev_parent_span_id)
    
    def add_tag(self, key: str, value: Any):
        """Add tag to current span."""
        if self.span:
            self.span.add_tag(key, value)
    
    def add_log(self, name: str, **attributes):
        """Add log to current span."""
        if self.span:
            self.span.add_log(name, **attributes)

def get_trace_id() -> Optional[str]:
    """Get current trace ID."""
    return trace_id.get()

def get_span_id() -> Optional[str]:
    """Get current span ID."""
    return span_id.get()

def get_parent_span_id() -> Optional[str]:
    """Get current parent span ID."""
    return parent_span_id.get()

def set_trace_context(trace_id_val: str, span_id_val: str, parent_span_id_val: Optional[str] = None):
    """Set trace context from external source (e.g., HTTP headers)."""
    trace_id.set(trace_id_val)
    span_id.set(span_id_val)
    parent_span_id.set(parent_span_id_val)

def create_child_span(operation_name: str, kind: SpanKind = SpanKind.INTERNAL) -> TracingContext:
    """Create a child span of the current span."""
    return TracingContext(operation_name, kind)

def trace_function(operation_name: Optional[str] = None, kind: SpanKind = SpanKind.INTERNAL):
    """Decorator to automatically trace function execution."""
    
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with create_child_span(operation_name, kind) as span_ctx:
                span_ctx.add_tag("function.name", func.__name__)
                span_ctx.add_tag("function.module", func.__module__)
                
                try:
                    result = await func(*args, **kwargs)
                    span_ctx.add_tag("function.result", "success")
                    return result
                except Exception as e:
                    span_ctx.add_tag("function.result", "error")
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with create_child_span(operation_name, kind) as span_ctx:
                span_ctx.add_tag("function.name", func.__name__)
                span_ctx.add_tag("function.module", func.__module__)
                
                try:
                    result = func(*args, **kwargs)
                    span_ctx.add_tag("function.result", "success")
                    return result
                except Exception as e:
                    span_ctx.add_tag("function.result", "error")
                    raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def trace_database_operation(operation: str, table: str):
    """Decorator specifically for database operations."""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with create_child_span(f"db.{operation}", SpanKind.CLIENT) as span_ctx:
                span_ctx.add_tag("db.operation", operation)
                span_ctx.add_tag("db.table", table)
                span_ctx.add_tag("db.type", "cosmosdb")
                
                try:
                    result = await func(*args, **kwargs)
                    span_ctx.add_tag("db.result", "success")
                    return result
                except Exception as e:
                    span_ctx.add_tag("db.result", "error")
                    span_ctx.add_tag("db.error", str(e))
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with create_child_span(f"db.{operation}", SpanKind.CLIENT) as span_ctx:
                span_ctx.add_tag("db.operation", operation)
                span_ctx.add_tag("db.table", table)
                span_ctx.add_tag("db.type", "cosmosdb")
                
                try:
                    result = func(*args, **kwargs)
                    span_ctx.add_tag("db.result", "success")
                    return result
                except Exception as e:
                    span_ctx.add_tag("db.result", "error")
                    span_ctx.add_tag("db.error", str(e))
                    raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def trace_http_request(method: str, url: str):
    """Decorator for HTTP client requests."""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with create_child_span(f"http.{method.lower()}", SpanKind.CLIENT) as span_ctx:
                span_ctx.add_tag("http.method", method)
                span_ctx.add_tag("http.url", url)
                
                try:
                    result = await func(*args, **kwargs)
                    if hasattr(result, 'status_code'):
                        span_ctx.add_tag("http.status_code", result.status_code)
                    span_ctx.add_tag("http.result", "success")
                    return result
                except Exception as e:
                    span_ctx.add_tag("http.result", "error")
                    span_ctx.add_tag("http.error", str(e))
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with create_child_span(f"http.{method.lower()}", SpanKind.CLIENT) as span_ctx:
                span_ctx.add_tag("http.method", method)
                span_ctx.add_tag("http.url", url)
                
                try:
                    result = func(*args, **kwargs)
                    if hasattr(result, 'status_code'):
                        span_ctx.add_tag("http.status_code", result.status_code)
                    span_ctx.add_tag("http.result", "success")
                    return result
                except Exception as e:
                    span_ctx.add_tag("http.result", "error")
                    span_ctx.add_tag("http.error", str(e))
                    raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator