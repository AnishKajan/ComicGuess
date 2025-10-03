"""Tests for rate limiting middleware and functionality"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient

from app.middleware.rate_limiting import (
    RateLimiter, 
    rate_limit_middleware, 
    RateLimitException,
    rate_limit_dependency
)

class TestRateLimiter:
    """Test the RateLimiter class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.rate_limiter = RateLimiter()
        # Override limits for faster testing
        self.rate_limiter.limits = {
            "guess": {
                "ip": {"requests": 3, "window": 5},  # 3 requests per 5 seconds
                "user": {"requests": 2, "window": 5}  # 2 requests per 5 seconds
            },
            "default": {
                "ip": {"requests": 5, "window": 5},  # 5 requests per 5 seconds
                "user": {"requests": 3, "window": 5}  # 3 requests per 5 seconds
            }
        }
    
    def test_clean_old_requests(self):
        """Test cleaning old requests from sliding window"""
        from collections import deque
        
        window = deque()
        current_time = time.time()
        
        # Add some old and new requests
        window.append(current_time - 10)  # Old request
        window.append(current_time - 3)   # Recent request
        window.append(current_time - 1)   # Very recent request
        
        self.rate_limiter._clean_old_requests(window, 5)
        
        # Should only have 2 recent requests left
        assert len(window) == 2
        assert window[0] == current_time - 3
        assert window[1] == current_time - 1
    
    def test_is_rate_limited_within_limit(self):
        """Test rate limiting when within limits"""
        from collections import defaultdict, deque
        
        windows = defaultdict(deque)
        config = {"requests": 3, "window": 5}
        
        # First request should not be limited
        limited, remaining = self.rate_limiter._is_rate_limited("test_key", windows, config)
        assert not limited
        assert remaining == 2
        
        # Second request should not be limited
        limited, remaining = self.rate_limiter._is_rate_limited("test_key", windows, config)
        assert not limited
        assert remaining == 1
    
    def test_is_rate_limited_exceeds_limit(self):
        """Test rate limiting when exceeding limits"""
        from collections import defaultdict, deque
        
        windows = defaultdict(deque)
        config = {"requests": 2, "window": 5}
        
        # Fill up to limit
        self.rate_limiter._is_rate_limited("test_key", windows, config)
        self.rate_limiter._is_rate_limited("test_key", windows, config)
        
        # Third request should be limited
        limited, remaining = self.rate_limiter._is_rate_limited("test_key", windows, config)
        assert limited
        assert remaining == 0
    
    def test_get_client_ip_forwarded_for(self):
        """Test extracting client IP from X-Forwarded-For header"""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        request.client = None
        
        ip = self.rate_limiter._get_client_ip(request)
        assert ip == "192.168.1.1"
    
    def test_get_client_ip_real_ip(self):
        """Test extracting client IP from X-Real-IP header"""
        request = Mock(spec=Request)
        request.headers = {"X-Real-IP": "192.168.1.2"}
        request.client = None
        
        ip = self.rate_limiter._get_client_ip(request)
        assert ip == "192.168.1.2"
    
    def test_get_client_ip_direct(self):
        """Test extracting client IP directly from request"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.3"
        
        ip = self.rate_limiter._get_client_ip(request)
        assert ip == "192.168.1.3"
    
    def test_get_client_ip_unknown(self):
        """Test fallback when client IP cannot be determined"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None
        
        ip = self.rate_limiter._get_client_ip(request)
        assert ip == "unknown"
    
    @patch('app.auth.jwt_handler.verify_token')
    def test_get_user_id_from_jwt(self, mock_verify_token):
        """Test extracting user ID from JWT token"""
        mock_verify_token.return_value = {"sub": "test_user_123"}
        
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer valid_token"}
        request.query_params = {}
        
        user_id = self.rate_limiter._get_user_id(request)
        assert user_id == "test_user_123"
        mock_verify_token.assert_called_once_with("valid_token")
    
    def test_get_user_id_from_query_params(self):
        """Test extracting user ID from query parameters"""
        request = Mock(spec=Request)
        request.headers = {}
        request.query_params = {"user_id": "query_user_456"}
        
        user_id = self.rate_limiter._get_user_id(request)
        assert user_id == "query_user_456"
    
    def test_get_user_id_none(self):
        """Test when no user ID is available"""
        request = Mock(spec=Request)
        request.headers = {}
        request.query_params = {}
        
        user_id = self.rate_limiter._get_user_id(request)
        assert user_id is None
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_ip_exceeded(self):
        """Test rate limiting when IP limit is exceeded"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.query_params = {}
        
        # Exceed IP limit for guess endpoint
        for _ in range(4):  # Limit is 3
            response = await self.rate_limiter.check_rate_limit(request, "guess")
        
        # Should be rate limited
        assert response is not None
        assert response.status_code == 429
        assert "X-RateLimit-Limit" in response.headers
        assert "Retry-After" in response.headers
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_user_exceeded(self):
        """Test rate limiting when user limit is exceeded"""
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer valid_token"}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.query_params = {}
        
        with patch('app.auth.jwt_handler.verify_token') as mock_verify:
            mock_verify.return_value = {"sub": "test_user"}
            
            # Exceed user limit for guess endpoint
            for _ in range(3):  # User limit is 2
                response = await self.rate_limiter.check_rate_limit(request, "guess")
            
            # Should be rate limited
            assert response is not None
            assert response.status_code == 429
            assert "user" in response.body.decode().lower()
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_within_limits(self):
        """Test rate limiting when within limits"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.2"
        request.query_params = {}
        
        # Should not be rate limited
        response = await self.rate_limiter.check_rate_limit(request, "guess")
        assert response is None
    
    def test_get_rate_limit_info(self):
        """Test getting rate limit information"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.query_params = {}
        
        # Make a request to populate windows
        self.rate_limiter._is_rate_limited(
            "192.168.1.1", 
            self.rate_limiter.ip_windows, 
            self.rate_limiter.limits["guess"]["ip"]
        )
        
        info = self.rate_limiter.get_rate_limit_info(request, "guess")
        
        assert "ip" in info
        assert "user" in info
        assert info["ip"]["current"] == 1
        assert info["ip"]["limit"] == 3
        assert info["ip"]["remaining"] == 2
        assert info["user"] is None  # No user identified

class TestRateLimitMiddleware:
    """Test the rate limiting middleware"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_middleware_guess_endpoint(self):
        """Test middleware applies correct limits to guess endpoint"""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/guess"
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.query_params = {}
        
        async def mock_call_next(req):
            mock_response = Mock()
            mock_response.headers = {}
            return mock_response
        
        # Should process normally within limits
        response = await rate_limit_middleware(request, mock_call_next)
        assert "X-RateLimit-Limit" in response.headers
    
    @pytest.mark.asyncio
    async def test_rate_limit_middleware_default_endpoint(self):
        """Test middleware applies default limits to other endpoints"""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/user/123"
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.query_params = {}
        
        async def mock_call_next(req):
            mock_response = Mock()
            mock_response.headers = {}
            return mock_response
        
        # Should process normally
        response = await rate_limit_middleware(request, mock_call_next)
        assert response is not None

class TestRateLimitDependency:
    """Test the rate limit dependency function"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_dependency_success(self):
        """Test dependency allows request within limits"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.query_params = {}
        
        dependency = rate_limit_dependency("default")
        
        # Should not raise exception
        result = await dependency(request)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_dependency_exceeded(self):
        """Test dependency raises exception when limits exceeded"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.1"
        request.query_params = {}
        
        # Create rate limiter with very low limits
        with patch('app.middleware.rate_limiting.rate_limiter') as mock_limiter:
            from fastapi.responses import JSONResponse
            
            async def mock_check_rate_limit(req, endpoint_type):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": "Too many requests",
                        "retry_after": 60,
                        "limit_type": "ip"
                    }
                )
            
            mock_limiter.check_rate_limit = mock_check_rate_limit
            
            dependency = rate_limit_dependency("default")
            
            # Should raise RateLimitException
            with pytest.raises(RateLimitException) as exc_info:
                await dependency(request)
            
            assert exc_info.value.status_code == 429
            assert "Too many requests" in str(exc_info.value.detail)

class TestRateLimitException:
    """Test the custom RateLimitException"""
    
    def test_rate_limit_exception_creation(self):
        """Test creating RateLimitException with proper headers"""
        exception = RateLimitException(
            detail="Too many requests",
            retry_after=60,
            limit_type="user"
        )
        
        assert exception.status_code == 429
        assert exception.detail == "Too many requests"
        assert exception.headers["Retry-After"] == "60"
        assert exception.headers["X-RateLimit-Type"] == "user"

class TestRateLimitingIntegration:
    """Integration tests for rate limiting with actual FastAPI app"""
    
    def test_rate_limiting_integration_setup(self):
        """Test that rate limiting can be integrated with FastAPI"""
        from fastapi import FastAPI, Depends
        from app.middleware.rate_limiting import guess_rate_limit
        
        app = FastAPI()
        
        @app.post("/test-guess")
        async def test_endpoint(_rate_limit: bool = Depends(guess_rate_limit)):
            return {"message": "success"}
        
        # Should be able to create the app without errors
        assert app is not None
    
    def test_sliding_window_behavior(self):
        """Test that sliding window properly expires old requests"""
        rate_limiter = RateLimiter()
        rate_limiter.limits["test"] = {
            "ip": {"requests": 2, "window": 1},  # 2 requests per second
            "user": {"requests": 1, "window": 1}
        }
        
        from collections import defaultdict, deque
        windows = defaultdict(deque)
        config = rate_limiter.limits["test"]["ip"]
        
        # Make 2 requests (should be allowed)
        limited1, _ = rate_limiter._is_rate_limited("test_ip", windows, config)
        limited2, _ = rate_limiter._is_rate_limited("test_ip", windows, config)
        
        assert not limited1
        assert not limited2
        
        # Third request should be limited
        limited3, _ = rate_limiter._is_rate_limited("test_ip", windows, config)
        assert limited3
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again after window expires
        limited4, _ = rate_limiter._is_rate_limited("test_ip", windows, config)
        assert not limited4

@pytest.mark.asyncio
async def test_concurrent_rate_limiting():
    """Test rate limiting under concurrent requests"""
    rate_limiter = RateLimiter()
    rate_limiter.limits["concurrent"] = {
        "ip": {"requests": 5, "window": 10},
        "user": {"requests": 3, "window": 10}
    }
    
    async def make_request(ip_suffix: int):
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = f"192.168.1.{ip_suffix}"
        request.query_params = {}
        
        return await rate_limiter.check_rate_limit(request, "concurrent")
    
    # Make concurrent requests from different IPs
    tasks = [make_request(i) for i in range(1, 6)]  # 5 different IPs
    results = await asyncio.gather(*tasks)
    
    # All should be allowed (different IPs)
    assert all(result is None for result in results)
    
    # Make concurrent requests from same IP
    tasks = [make_request(1) for _ in range(7)]  # Same IP, exceeds limit
    results = await asyncio.gather(*tasks)
    
    # Some should be rate limited
    rate_limited_count = sum(1 for result in results if result is not None)
    assert rate_limited_count > 0