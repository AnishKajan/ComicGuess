"""
Application configuration management for different environments.
"""

import os
from typing import List, Optional
from pydantic import field_validator, ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment-specific configurations."""
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Application Configuration
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    
    # CORS Configuration
    allowed_origins: str = "http://localhost:3000"
    
    # Database Configuration (Azure Cosmos DB)
    cosmos_endpoint: str = "https://localhost:8081"
    cosmos_key: str = "test-key-for-development"
    cosmos_database_name: str = "comicguess"
    cosmos_container_users: str = "users"
    cosmos_container_puzzles: str = "puzzles"
    cosmos_container_guesses: str = "guesses"
    cosmos_container_governance: str = "governance"
    
    # Storage Configuration (Azure Blob Storage)
    azure_storage_account_name: str = "devstorageaccount1"
    azure_storage_account_key: str = "test-key-for-development"
    azure_storage_container_name: str = "character-images"
    
    # Authentication Configuration
    jwt_secret_key: str = "test-jwt-secret-key-for-development-min-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Rate Limiting Configuration
    rate_limit_requests: int = 10
    rate_limit_window: int = 60
    rate_limit_storage: str = "memory"
    
    # Security Configuration
    bcrypt_rounds: int = 12
    session_secret: str = "test-session-secret-for-development"
    
    # Monitoring Configuration
    enable_metrics: bool = True
    metrics_port: int = 9090
    health_check_timeout: int = 30
    
    # Azure Key Vault Configuration (Optional)
    azure_key_vault_url: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    azure_tenant_id: Optional[str] = None
    
    # Logging Configuration
    log_format: str = "json"
    log_file: str = "/app/logs/app.log"
    log_max_size: str = "10MB"
    log_backup_count: int = 5
    
    # Cloudflare Configuration
    cloudflare_zone_id: Optional[str] = None
    cloudflare_api_token: Optional[str] = None
    cloudflare_cache_ttl: int = 3600  # 1 hour default TTL
    
    @field_validator("allowed_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    
    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT secret is sufficiently long."""
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long")
        return v
    
    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment name."""
        valid_envs = ["development", "staging", "production", "test"]
        if v not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "development"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.app_env == "staging"
    
    @property
    def cosmos_connection_string(self) -> str:
        """Generate Cosmos DB connection string."""
        return f"AccountEndpoint={self.cosmos_endpoint};AccountKey={self.cosmos_key};"
    
    @property
    def azure_storage_connection_string(self) -> str:
        """Generate Azure Storage connection string."""
        return (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={self.azure_storage_account_name};"
            f"AccountKey={self.azure_storage_account_key};"
            f"EndpointSuffix=core.windows.net"
        )
    



class DevelopmentSettings(Settings):
    """Development environment specific settings."""
    
    app_env: str = "development"
    debug: bool = True
    log_level: str = "DEBUG"
    bcrypt_rounds: int = 4  # Faster for development
    rate_limit_requests: int = 100  # More lenient for development


class StagingSettings(Settings):
    """Staging environment specific settings."""
    
    app_env: str = "staging"
    debug: bool = True
    log_level: str = "DEBUG"
    bcrypt_rounds: int = 10
    rate_limit_requests: int = 20


class ProductionSettings(Settings):
    """Production environment specific settings."""
    
    app_env: str = "production"
    debug: bool = False
    log_level: str = "INFO"
    bcrypt_rounds: int = 12
    api_workers: int = 2
    
    @field_validator("allowed_origins")
    @classmethod
    def validate_production_origins(cls, v: List[str]) -> List[str]:
        """Ensure no localhost origins in production."""
        for origin in v:
            if "localhost" in origin or "127.0.0.1" in origin:
                raise ValueError("Localhost origins not allowed in production")
        return v


class TestSettings(Settings):
    """Test environment specific settings."""
    
    app_env: str = "test"
    debug: bool = True
    log_level: str = "DEBUG"
    bcrypt_rounds: int = 4
    cosmos_database_name: str = "comicguess-test"
    azure_storage_container_name: str = "test-images"


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings based on environment.
    Uses caching to avoid re-reading environment variables.
    """
    env = os.getenv("APP_ENV", "development").lower()
    
    settings_map = {
        "development": DevelopmentSettings,
        "staging": StagingSettings,
        "production": ProductionSettings,
        "test": TestSettings,
    }
    
    settings_class = settings_map.get(env, DevelopmentSettings)
    return settings_class()


# Global settings instance - only create if not in test environment
if os.getenv("APP_ENV") != "test":
    settings = get_settings()
else:
    settings = None