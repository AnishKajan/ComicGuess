"""
Tests for monitoring API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json
import os

# Mock the problematic imports before importing main
with patch.dict('sys.modules', {
    'app.auth.middleware': MagicMock(),
    'app.repositories.user_repository': MagicMock(),
    'app.config.settings': MagicMock()
}):
    from app.api.monitoring import router
    from fastapi import FastAPI
    
    # Create a minimal test app with just the monitoring router
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/monitor")

client = TestClient(test_app)

class TestMonitoringEndpoints:
    """Test monitoring API endpoints."""
    
    def test_liveness_check(self):
        """Test liveness probe endpoint."""
        response = client.get("/api/monitor/health/liveness")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
    
    def test_readiness_check_healthy(self):
        """Test readiness probe when healthy."""
        with patch("app.api.monitoring.health_checker.run_health_checks") as mock_health:
            mock_health.return_value = {"overall_status": "healthy", "checks": {}}
            
            response = client.get("/api/monitor/health/readiness")
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            
            data = response.json()
            assert data["status"] == "ready"
            assert "timestamp" in data
    
    def test_readiness_check_basic(self):
        """Test readiness probe basic functionality."""
        response = client.get("/api/monitor/health/readiness")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    def test_metrics_basic_format(self):
        """Test metrics endpoint basic format."""
        response = client.get("/api/monitor/metrics")
        
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        
        content = response.text
        assert "app_up 1" in content
        assert "# HELP" in content
        assert "# TYPE" in content
    
    def test_detailed_health_basic(self):
        """Test detailed health check basic functionality."""
        response = client.get("/api/monitor/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
    
    def test_version_endpoint(self):
        """Test version endpoint."""
        response = client.get("/api/monitor/version")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert "version" in data
        assert "build_time" in data
        assert "commit_hash" in data
        
        # Should default to 'dev' if no environment variable
        assert data["version"] == "dev"
    
    def test_version_endpoint_with_env(self):
        """Test version endpoint with environment variables."""
        with patch.dict("os.environ", {
            "APP_VERSION": "1.2.3",
            "BUILD_TIME": "2024-01-01T00:00:00Z",
            "COMMIT_HASH": "abc123"
        }):
            response = client.get("/api/monitor/version")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["version"] == "1.2.3"
            assert data["build_time"] == "2024-01-01T00:00:00Z"
            assert data["commit_hash"] == "abc123"
    
    def test_ping_endpoint(self):
        """Test ping endpoint."""
        response = client.get("/api/monitor/ping")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert data["pong"] is True
    


class TestMonitoringIntegration:
    """Integration tests for monitoring endpoints."""
    
    def test_all_endpoints_return_200(self):
        """Test that all monitoring endpoints return 200 status."""
        endpoints = [
            "/api/monitor/health/liveness",
            "/api/monitor/health/readiness", 
            "/api/monitor/metrics",
            "/api/monitor/version",
            "/api/monitor/ping",
            "/api/monitor/health/detailed"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed with status {response.status_code}"
    
    def test_json_endpoints_content_type(self):
        """Test that JSON endpoints return correct content type."""
        json_endpoints = [
            "/api/monitor/health/liveness",
            "/api/monitor/health/readiness",
            "/api/monitor/version", 
            "/api/monitor/ping",
            "/api/monitor/health/detailed"
        ]
        
        for endpoint in json_endpoints:
            response = client.get(endpoint)
            assert "application/json" in response.headers["content-type"], \
                f"Endpoint {endpoint} should return JSON content type"
    
    def test_metrics_content_type(self):
        """Test that metrics endpoint returns text/plain."""
        response = client.get("/api/monitor/metrics")
        assert "text/plain" in response.headers["content-type"], \
            "Metrics endpoint should return text/plain content type"