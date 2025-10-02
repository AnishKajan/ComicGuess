"""Retry logic for database operations"""

import asyncio
import logging
from typing import Callable, Any, Optional, Type, Tuple
from functools import wraps
from azure.cosmos.exceptions import CosmosHttpResponseError

from .exceptions import handle_cosmos_error, RateLimitError, ConnectionError

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (
            RateLimitError,
            ConnectionError,
            CosmosHttpResponseError
        )
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for retry attempt"""
    import random
    
    # Exponential backoff
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    
    # Cap at max delay
    delay = min(delay, config.max_delay)
    
    # Add jitter to prevent thundering herd
    if config.jitter:
        delay = delay * (0.5 + random.random() * 0.5)
    
    return delay


async def retry_async(
    func: Callable,
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> Any:
    """Retry an async function with exponential backoff"""
    
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func(*args, **kwargs)
            
        except Exception as e:
            last_exception = e
            
            # Convert Cosmos errors to application errors
            if isinstance(e, CosmosHttpResponseError):
                app_error = handle_cosmos_error(e)
                last_exception = app_error
                e = app_error
            
            # Check if exception is retryable
            if not isinstance(e, config.retryable_exceptions):
                logger.warning(f"Non-retryable error in {func.__name__}: {e}")
                raise e
            
            # Don't retry on last attempt
            if attempt == config.max_attempts:
                logger.error(f"Max retry attempts ({config.max_attempts}) exceeded for {func.__name__}")
                break
            
            # Calculate delay and wait
            delay = calculate_delay(attempt, config)
            logger.warning(
                f"Attempt {attempt}/{config.max_attempts} failed for {func.__name__}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
    
    # All attempts failed
    raise last_exception


def with_retry(config: Optional[RetryConfig] = None):
    """Decorator to add retry logic to async functions"""
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, config, *args, **kwargs)
        return wrapper
    
    return decorator


# Pre-configured retry decorators for common scenarios
def with_standard_retry(func: Callable):
    """Standard retry configuration for most database operations"""
    return with_retry(RetryConfig(max_attempts=3, base_delay=1.0))(func)


def with_aggressive_retry(func: Callable):
    """Aggressive retry configuration for critical operations"""
    return with_retry(RetryConfig(max_attempts=5, base_delay=0.5, max_delay=30.0))(func)


def with_gentle_retry(func: Callable):
    """Gentle retry configuration for non-critical operations"""
    return with_retry(RetryConfig(max_attempts=2, base_delay=2.0))(func)