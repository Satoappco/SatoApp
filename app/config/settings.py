"""
Application settings and configuration management
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App Configuration
    app_name: str = "Sato AI SEO Assistant"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    
    # Database Configuration
    database_url: Optional[str] = None
    database_echo: bool = False
    
    # Redis Configuration
    redis_url: Optional[str] = None
    
    # API Keys
    gemini_api_key: Optional[str] = None
    ga4_service_account_key: Optional[str] = None
    facebook_app_secret: Optional[str] = None
    
    # Authentication
    api_token: Optional[str] = None  # Primary API token
    secret_key: str = "your-secret-key-here"
    
    # JWT Token Configuration
    jwt_access_token_expire_minutes: int = 480  # 8 hours (same as development)
    jwt_refresh_token_expire_days: int = 30    # 30 days
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    
    # Facebook OAuth
    facebook_app_id: Optional[str] = None
    facebook_app_secret: Optional[str] = None
    facebook_redirect_uri: Optional[str] = None
    facebook_api_version: str = "v18.0"
    
    # Frontend Configuration
    frontend_url: str = "https://localhost:3000"  # Default for local development
    
    # Master Agent Configuration
    master_agent_max_iterations: int = 3
    master_agent_timeout: int = 120
    parallel_specialists: bool = True
    cache_specialist_results: bool = True
    cache_ttl_seconds: int = 3600
    
    # Performance Configuration
    max_concurrent_analyses: int = 10
    request_timeout_seconds: int = 30
    
    # Monitoring
    sentry_dsn: Optional[str] = None
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()
