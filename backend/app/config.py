from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Azure Cosmos DB Configuration
    cosmos_db_endpoint: str = ""
    cosmos_db_key: str = ""
    cosmos_db_database_name: str = "comicguess"
    cosmos_db_container_users: str = "users"
    cosmos_db_container_puzzles: str = "puzzles"
    cosmos_db_container_guesses: str = "guesses"
    
    # Azure Blob Storage Configuration
    azure_storage_connection_string: str = ""
    azure_storage_container_name: str = "character-images"
    
    # JWT Configuration
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # CORS Configuration
    frontend_url: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()