"""
Centralized logging configuration for the ComicGuess application.
Provides structured logging with correlation IDs and performance metrics.
"""

import logging
import logging.config
import json
import time
import uuid
from typing import Dict, Any, Optional
from contextvars import ContextVar
from functools import wraps
import traceback

# Context variable for request correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

class CorrelationFilter(logging.Filter):
    """Add correlation ID to log records."""
    
    def filter(self, record):
        record.correlation_id = correlation_id.get() or 'no-correlation-id'
        return True

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', 'no-correlation-id'),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info', 'correlation_id']:
                log_entry[key] = value
        
        return json.dumps(log_entry)

def setup_logging(log_level: str = "INFO", enable_json: bool = True) -> None:
    """
    Configure application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_json: Whether to use JSON formatting
    """
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': JSONFormatter,
            },
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s (%(correlation_id)s)',
            },
        },
        'filters': {
            'correlation': {
                '()': CorrelationFilter,
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'json' if enable_json else 'standard',
                'filters': ['correlation'],
                'stream': 'ext://sys.stdout',
            },
        },
        'loggers': {
            'app': {
                'level': log_level,
                'handlers': ['console'],
                'propagate': False,
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'azure': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False,
            },
        },
        'root': {
            'level': log_level,
            'handlers': ['console'],
        },
    }
    
    logging.config.dictConfig(config)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(f"app.{name}")

def set_correlation_id(request_id: Optional[str] = None) -> str:
    """Set correlation ID for the current context."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    correlation_id.set(request_id)
    return request_id

def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id.get()

def log_performance(func):
    """Decorator to log function performance metrics."""
    
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger = get_logger(f"performance.{func.__module__}.{func.__name__}")
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(
                f"Function completed successfully",
                extra={
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'success'
                }
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Function failed",
                extra={
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'error',
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            )
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger = get_logger(f"performance.{func.__module__}.{func.__name__}")
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(
                f"Function completed successfully",
                extra={
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'success'
                }
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Function failed",
                extra={
                    'function': func.__name__,
                    'duration_ms': round(duration * 1000, 2),
                    'status': 'error',
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            )
            raise
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

class MetricsCollector:
    """Collect application metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.logger = get_logger("metrics")
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        self.logger.info(
            f"Counter incremented",
            extra={
                'metric_type': 'counter',
                'metric_name': name,
                'value': value,
                'tags': tags or {}
            }
        )
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a histogram metric."""
        self.logger.info(
            f"Histogram recorded",
            extra={
                'metric_type': 'histogram',
                'metric_name': name,
                'value': value,
                'tags': tags or {}
            }
        )
    
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a gauge metric."""
        self.logger.info(
            f"Gauge recorded",
            extra={
                'metric_type': 'gauge',
                'metric_name': name,
                'value': value,
                'tags': tags or {}
            }
        )

# Global metrics collector instance
metrics = MetricsCollector()