"""Rate limiting middleware for API endpoints"""

import time
import logging
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import asyncio
from threading import Lock

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Rate limiter using sliding window algorithm
    Supports both IP-based and user-based rate limiting
    """
    
    def __init__(self):
        self.ip_windows: Dict[str, deque] = defaultdict(deque)
        self.user_windows: Dict[str, deque] = defaultdict(deque)
        self.lock = Lock()
        
        # Rate limiting configuration
        self.limits = {
            "guess": {
                "ip": {"requests": 30, "window": 60},  # 30 requests per minute per IP
                "user": {"requests": 10, "window": 60}  # 10 requests per minute per user
            },
            "default": {
                "ip": {"requests": 100, "window": 60},  # 100 requests per minute per IP
                "user": {"requests": 60, "window": 60}  # 60 requests per minute per user
            }
        }
    
    def _clean_old_requests(self, window: deque, time_window: int) -> None:
        """Remove requests older than the time window"""
        current_time = time.time()
        while window and window[0] < current_time - time_window:
            window.popleft()
    
    def _is_rate_limited(self, key: str, windows: Dict[str, deque], limit_config: dict) -> Tuple[bool, int]:
        """
        Check if a key is rate limited
        Returns (is_limited, remaining_requests)
        """
        window = windows[key]
        current_time = time.time()
        time_window = limit_config["window"]
        max_requests = limit_config["requests"]
        
        # Clean old requests
        self._clean_old_requests(window, time_window)
        
        # Check if limit exceeded
        current_count = len(window)
        if current_count >= max_requests:
            return True, 0
        
        # Add current request
        window.append(current_time)
        remaining = max_requests - (current_count + 1)
        
        return False, remaining
    
    async def check_rate_limit(self, request: Request, endpoint_type: str = "default") -> Optional[JSONResponse]:
        """
        Check rate limits for IP and user
        Returns JSONResponse if rate limited, None if allowed
        """
        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)
        
        # Get rate limit configuration for endpoint
        config = self.limits.get(endpoint_type, self.limits["default"])
        
        with self.lock:
            # Check IP-based rate limiting
            ip_limited, ip_remaining = self._is_rate_limited(
                client_ip, self.ip_windows, config["ip"]
            )
            
            if ip_limited:
                logger.warning(f"IP rate limit exceeded for {client_ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": "Too many requests from this IP address",
                        "retry_after": config["ip"]["window"],
                        "limit_type": "ip"
                    },
                    headers={
                        "Retry-After": str(config["ip"]["window"]),
                        "X-RateLimit-Limit": str(config["ip"]["requests"]),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time() + config["ip"]["window"]))
                    }
                )
            
            # Check user-based rate limiting if user is identified
            if user_id:
                user_limited, user_remaining = self._is_rate_limited(
                    user_id, self.user_windows, config["user"]
                )
                
                if user_limited:
                    logger.warning(f"User rate limit exceeded for user {user_id}")
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "Rate limit exceeded",
                            "detail": "Too many requests for this user",
                            "retry_after": config["user"]["window"],
                            "limit_type": "user"
                        },
                        headers={
                            "Retry-After": str(config["user"]["window"]),
                            "X-RateLimit-Limit": str(config["user"]["requests"]),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(int(time.time() + config["user"]["window"]))
                        }
                    )
        
        # Add rate limit headers to successful requests
        return None
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request if available"""
        # Try to get from JWT token in Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from app.auth.jwt_handler import verify_token
                token = auth_header.split(" ")[1]
                payload = verify_token(token)
                return payload.get("sub")  # JWT standard uses 'sub' for user ID
            except Exception:
                # If token is invalid, continue without user ID
                pass
        
        # Try to get from query parameters (for some endpoints)
        return request.query_params.get("user_id")
    
    def get_rate_limit_info(self, request: Request, endpoint_type: str = "default") -> dict:
        """Get current rate limit status for debugging/monitoring"""
        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)
        config = self.limits.get(endpoint_type, self.limits["default"])
        
        with self.lock:
            # Clean and count IP requests
            ip_window = self.ip_windows[client_ip]
            self._clean_old_requests(ip_window, config["ip"]["window"])
            ip_count = len(ip_window)
            
            # Clean and count user requests
            user_count = 0
            if user_id:
                user_window = self.user_windows[user_id]
                self._clean_old_requests(user_window, config["user"]["window"])
                user_count = len(user_window)
        
        return {
            "ip": {
                "current": ip_count,
                "limit": config["ip"]["requests"],
                "remaining": max(0, config["ip"]["requests"] - ip_count),
                "window": config["ip"]["window"]
            },
            "user": {
                "current": user_count,
                "limit": config["user"]["requests"],
                "remaining": max(0, config["user"]["requests"] - user_count),
                "window": config["user"]["window"]
            } if user_id else None
        }

# Global rate limiter instance
rate_limiter = RateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    """
    FastAPI middleware for rate limiting
    """
    # Determine endpoint type based on path
    endpoint_type = "default"
    if "/guess" in request.url.path:
        endpoint_type = "guess"
    
    # Check rate limits
    rate_limit_response = await rate_limiter.check_rate_limit(request, endpoint_type)
    if rate_limit_response:
        return rate_limit_response
    
    # Process request normally
    response = await call_next(request)
    
    # Add rate limit headers to response
    try:
        rate_info = rate_limiter.get_rate_limit_info(request, endpoint_type)
        ip_info = rate_info["ip"]
        
        response.headers["X-RateLimit-Limit"] = str(ip_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(ip_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + ip_info["window"]))
        
        # Add user rate limit headers if user is identified
        if rate_info["user"]:
            user_info = rate_info["user"]
            response.headers["X-RateLimit-User-Limit"] = str(user_info["limit"])
            response.headers["X-RateLimit-User-Remaining"] = str(user_info["remaining"])
    
    except Exception as e:
        logger.error(f"Error adding rate limit headers: {e}")
    
    return response

class RateLimitException(HTTPException):
    """Custom exception for rate limit violations"""
    
    def __init__(self, detail: str, retry_after: int, limit_type: str = "general"):
        super().__init__(
            status_code=429,
            detail=detail,
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Type": limit_type
            }
        )

def rate_limit_dependency(endpoint_type: str = "default"):
    """
    Dependency function for applying rate limits to specific endpoints
    """
    async def check_rate_limit(request: Request):
        rate_limit_response = await rate_limiter.check_rate_limit(request, endpoint_type)
        if rate_limit_response:
            # Convert JSONResponse to HTTPException
            content = rate_limit_response.body.decode()
            import json
            error_data = json.loads(content)
            raise RateLimitException(
                detail=error_data["detail"],
                retry_after=error_data["retry_after"],
                limit_type=error_data["limit_type"]
            )
        return True
    
    return check_rate_limit

# Convenience dependencies for common endpoints
guess_rate_limit = rate_limit_dependency("guess")
default_rate_limit = rate_limit_dependency("default")