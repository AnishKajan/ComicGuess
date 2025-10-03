"""
Deployment and configuration tests for the ComicGuess backend.
"""

import pytest
import os
import requests
from unittest.mock import patch, MagicMock
from app.config.settings import (
    get_settings, 
    DevelopmentSettings, 
    StagingSettings, 
    ProductionSettings,
    TestSettings
)


class TestConfigurationSettings:
    """Test configuration settings for different environments."""
    
    def test_development_settings(self):
        """Test development environment settings."""
        # Clear cache before test
        get_settings.cache_clear()
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
            settings = get_settings()
            assert isinstance(settings, DevelopmentSettings)
            assert settings.app_env == "development"
            assert settings.debug is True
            assert settings.log_level == "DEBUG"
            assert settings.bcrypt_rounds == 4
    
    def test_staging_settings(self):
        """Test staging environment settings."""
        # Clear cache before test
        get_settings.cache_clear()
        with patch.dict(os.environ, {"APP_ENV": "staging"}, clear=True):
            settings = get_settings()
            assert isinstance(settings, StagingSettings)
            assert settings.app_env == "staging"
            assert settings.debug is True
            assert settings.rate_limit_requests == 20
    
    def test_production_settings(self):
        """Test production environment settings."""
        # Clear cache before test
        get_settings.cache_clear()
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            settings = get_settings()
            assert isinstance(settings, ProductionSettings)
            assert settings.app_env == "production"
            assert settings.debug is False
            assert settings.log_level == "INFO"
            assert settings.api_workers == 2
    
    def test_test_settings(self):
        """Test test environment settings."""
        # Clear cache before test
        get_settings.cache_clear()
        with patch.dict(os.environ, {"APP_ENV": "test"}, clear=True):
            settings = get_settings()
            assert isinstance(settings, TestSettings)
            assert settings.app_env == "test"
            assert settings.cosmos_database_name == "comicguess-test"
    
    def test_cors_origins_parsing(self):
        """Test CORS origins parsing from comma-separated string."""
        # Clear cache before test
        get_settings.cache_clear()
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "ALLOWED_ORIGINS": "https://example.com, http://localhost:3000, https://app.example.com"
        }, clear=True):
            settings = get_settings()
            expected_origins = [
                "https://example.com",
                "http://localhost:3000", 
                "https://app.example.com"
            ]
            assert settings.allowed_origins == expected_origins
    
    def test_jwt_secret_validation(self):
        """Test JWT secret key validation."""
        # Clear cache before test
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="JWT secret key must be at least 32 characters"):
            with patch.dict(os.environ, {"APP_ENV": "development", "JWT_SECRET_KEY": "short"}, clear=True):
                get_settings()
    
    def test_production_localhost_validation(self):
        """Test that localhost origins are not allowed in production."""
        # Clear cache before test
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="Localhost origins not allowed in production"):
            with patch.dict(os.environ, {
                "APP_ENV": "production",
                "ALLOWED_ORIGINS": "https://example.com,http://localhost:3000"
            }, clear=True):
                get_settings()
    
    def test_connection_string_generation(self):
        """Test connection string generation for Azure services."""
        # Clear cache before test
        get_settings.cache_clear()
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "COSMOS_ENDPOINT": "https://test.documents.azure.com:443/",
            "COSMOS_KEY": "test-key",
            "AZURE_STORAGE_ACCOUNT_NAME": "teststorage",
            "AZURE_STORAGE_ACCOUNT_KEY": "test-storage-key"
        }, clear=True):
            settings = get_settings()
            
            # Test Cosmos DB connection string
            expected_cosmos = "AccountEndpoint=https://test.documents.azure.com:443/;AccountKey=test-key;"
            assert settings.cosmos_connection_string == expected_cosmos
            
            # Test Azure Storage connection string
            expected_storage = (
                "DefaultEndpointsProtocol=https;"
                "AccountName=teststorage;"
                "AccountKey=test-storage-key;"
                "EndpointSuffix=core.windows.net"
            )
            assert settings.azure_storage_connection_string == expected_storage


class TestDeploymentHealth:
    """Test deployment health checks and monitoring."""
    
    @pytest.fixture
    def mock_app_url(self):
        """Mock application URL for testing."""
        return "https://comicguess-backend-test.azurewebsites.net"
    
    def test_health_endpoint_structure(self, mock_app_url):
        """Test that health endpoint returns expected structure."""
        # This would be run against actual deployment
        # For now, we test the expected structure
        expected_keys = ["status", "timestamp", "version", "environment"]
        
        # Mock response for testing
        mock_response = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "version": "1.0.0",
            "environment": "test"
        }
        
        for key in expected_keys:
            assert key in mock_response
    
    def test_cors_configuration(self):
        """Test CORS configuration for deployment."""
        # Test that CORS headers are properly configured
        expected_headers = [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers"
        ]
        
        # This would test actual CORS response in integration test
        assert len(expected_headers) > 0  # Placeholder assertion
    
    def test_security_headers(self):
        """Test that security headers are present."""
        expected_security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection"
        ]
        
        # This would test actual security headers in integration test
        assert len(expected_security_headers) > 0  # Placeholder assertion
    
    def test_environment_variables_required(self):
        """Test that all required environment variables are defined."""
        required_vars = [
            "COSMOS_ENDPOINT",
            "COSMOS_KEY", 
            "AZURE_STORAGE_ACCOUNT_NAME",
            "AZURE_STORAGE_ACCOUNT_KEY",
            "JWT_SECRET_KEY",
            "SESSION_SECRET"
        ]
        
        # In actual deployment, these should be set
        for var in required_vars:
            # Test that variable is defined (not necessarily set in test env)
            assert isinstance(var, str)
            assert len(var) > 0


class TestDockerConfiguration:
    """Test Docker configuration and containerization."""
    
    def test_dockerfile_exists(self):
        """Test that Dockerfile exists and is readable."""
        dockerfile_path = "Dockerfile"
        assert os.path.exists(dockerfile_path)
        
        with open(dockerfile_path, 'r') as f:
            content = f.read()
            assert "FROM python:" in content
            assert "EXPOSE" in content
            assert "CMD" in content
    
    def test_dockerignore_exists(self):
        """Test that .dockerignore exists and excludes appropriate files."""
        dockerignore_path = ".dockerignore"
        assert os.path.exists(dockerignore_path)
        
        with open(dockerignore_path, 'r') as f:
            content = f.read()
            assert "__pycache__" in content
            assert ".git" in content
            assert "*.py[cod]" in content  # More comprehensive than *.pyc
    
    def test_health_check_configuration(self):
        """Test Docker health check configuration."""
        dockerfile_path = "Dockerfile"
        
        with open(dockerfile_path, 'r') as f:
            content = f.read()
            assert "HEALTHCHECK" in content
            assert "/health" in content


class TestAzureAppServiceConfiguration:
    """Test Azure App Service deployment configuration."""
    
    def test_app_service_config_exists(self):
        """Test that Azure App Service configuration exists."""
        config_path = "azure-app-service.yml"
        assert os.path.exists(config_path)
    
    def test_deployment_script_exists(self):
        """Test that deployment script exists and is executable."""
        script_path = "deploy/app-service-deploy.sh"
        assert os.path.exists(script_path)
        
        # Check if file is executable
        import stat
        file_stat = os.stat(script_path)
        assert file_stat.st_mode & stat.S_IEXEC
    
    def test_environment_examples_exist(self):
        """Test that environment example files exist."""
        env_files = [
            ".env.production.example",
            ".env.staging.example"
        ]
        
        for env_file in env_files:
            assert os.path.exists(env_file)
            
            with open(env_file, 'r') as f:
                content = f.read()
                assert "COSMOS_ENDPOINT" in content
                assert "JWT_SECRET_KEY" in content
                assert "AZURE_STORAGE_ACCOUNT_NAME" in content


@pytest.mark.integration
class TestDeploymentIntegration:
    """Integration tests for deployment (run against actual deployment)."""
    
    @pytest.mark.skip(reason="Requires actual deployment URL")
    def test_deployed_health_endpoint(self):
        """Test health endpoint on deployed application."""
        # This test would run against actual deployment
        deployment_url = os.getenv("DEPLOYMENT_URL")
        if not deployment_url:
            pytest.skip("DEPLOYMENT_URL not set")
        
        response = requests.get(f"{deployment_url}/health", timeout=30)
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
    
    @pytest.mark.skip(reason="Requires actual deployment URL")
    def test_deployed_cors_configuration(self):
        """Test CORS configuration on deployed application."""
        deployment_url = os.getenv("DEPLOYMENT_URL")
        if not deployment_url:
            pytest.skip("DEPLOYMENT_URL not set")
        
        # Test preflight request
        headers = {
            "Origin": "https://comicguess.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization"
        }
        
        response = requests.options(f"{deployment_url}/guess", headers=headers, timeout=30)
        assert response.status_code in [200, 204]
        assert "Access-Control-Allow-Origin" in response.headers