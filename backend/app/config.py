"""
Configuration settings for OIC NetRadar
Uses Pydantic Settings for environment variable management
"""

import json
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden with environment variables.
    Example: DATABASE_URL=postgresql://... uvicorn app.main:app
    """
    
    # ================================================================
    # Application Settings
    # ================================================================
    
    APP_NAME: str = "OIC NetRadar"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", description="development, staging, production")
    BASE_URL: str = Field(default="http://localhost:8000", description="Base URL for the application")
    
    # ================================================================
    # Database Settings
    # ================================================================
    
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/netradar",
        description="PostgreSQL connection string"
    )
    
    # ================================================================
    # Security Settings
    # ================================================================
    
    SECRET_KEY: str = Field(
        default="your-secret-key-here-change-in-production",
        description="JWT secret key"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # ================================================================
    # SMS Gateway Settings (Section 7)
    # ================================================================
    
    SMS_GATEWAY_URL: Optional[str] = Field(
        default=None,
        description="SMS gateway API URL"
    )
    SMS_API_KEY: Optional[str] = Field(
        default=None,
        description="SMS gateway API key"
    )
    SMS_FROM: Optional[str] = Field(
        default="NetRadar",
        description="SMS sender name"
    )
    
    # ================================================================
    # Email Settings (SMTP)
    # ================================================================
    
    SMTP_HOST: Optional[str] = Field(
        default=None,
        description="SMTP server hostname"
    )
    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port"
    )
    SMTP_USER: Optional[str] = Field(
        default=None,
        description="SMTP username"
    )
    SMTP_PASSWORD: Optional[str] = Field(
        default=None,
        description="SMTP password"
    )
    SMTP_FROM: Optional[str] = Field(
        default=None,
        description="From email address"
    )
    
    # ================================================================
    # Polling Configuration (Section 3)
    # ================================================================
    
    POLL_INTERVAL_SECONDS: int = Field(
        default=60,
        description="How often to poll devices (seconds)"
    )
    DEBOUNCE_WAIT_SECONDS: int = Field(
        default=180,
        description="Wait time before confirming failure (seconds)"
    )
    
    # ================================================================
    # SNMP Settings
    # ================================================================
    
    SNMP_COMMUNITY: str = Field(
        default="public",
        description="SNMP community string"
    )
    SNMP_TIMEOUT: int = Field(
        default=2,
        description="SNMP timeout in seconds"
    )
    SNMP_RETRIES: int = Field(
        default=1,
        description="SNMP retry count"
    )
    
    # ================================================================
    # Logging
    # ================================================================
    
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    # ================================================================
    # Fallback Notification
    # ================================================================
    
    FALLBACK_WEBHOOK: Optional[str] = Field(
        default=None,
        description="Fallback webhook URL (Telegram, Slack, etc.)"
    )
    
    # ================================================================
    # CORS
    # ================================================================
    
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """
        Accepts either:
          CORS_ORIGINS=["http://localhost:5500", "http://127.0.0.1:5500"]
        or:
          CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
        """
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


# Create global settings instance
settings = Settings()


# ================================================================
# Helper functions for settings
# ================================================================

def get_settings() -> Settings:
    """Get settings instance (dependency injection)."""
    return settings


def is_development() -> bool:
    """Check if running in development mode."""
    return settings.ENVIRONMENT == "development"


def is_production() -> bool:
    """Check if running in production mode."""
    return settings.ENVIRONMENT == "production"


def is_testing() -> bool:
    """Check if running in testing mode."""
    return settings.ENVIRONMENT == "testing"


def get_database_url() -> str:
    """Get database URL with proper async driver."""
    return settings.DATABASE_URL


def get_sms_config() -> dict:
    """Get SMS configuration."""
    return {
        "url": settings.SMS_GATEWAY_URL,
        "api_key": settings.SMS_API_KEY,
        "from": settings.SMS_FROM
    }


def get_email_config() -> dict:
    """Get email configuration."""
    return {
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "user": settings.SMTP_USER,
        "password": settings.SMTP_PASSWORD,
        "from": settings.SMTP_FROM
    }


def get_polling_config() -> dict:
    """Get polling configuration."""
    return {
        "interval": settings.POLL_INTERVAL_SECONDS,
        "debounce": settings.DEBOUNCE_WAIT_SECONDS
    }


def get_snmp_config() -> dict:
    """Get SNMP configuration."""
    return {
        "community": settings.SNMP_COMMUNITY,
        "timeout": settings.SNMP_TIMEOUT,
        "retries": settings.SNMP_RETRIES
    }