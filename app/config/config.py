import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "BigFarma Backend API"
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Database (Supabase)
    DB_USER: str = Field(..., validation_alias="DB_USER")
    DB_PASSWORD: str = Field(..., validation_alias="DB_PASSWORD")
    DB_HOST: str = Field(..., validation_alias="DB_HOST")
    DB_PORT: str = Field(..., validation_alias="DB_PORT")
    DB_NAME: str = Field(..., validation_alias="DB_NAME")
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email (for OTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = Field(default="", validation_alias="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", validation_alias="SMTP_PASSWORD")
    SMTP_PASSWORD: str = Field(default="", validation_alias="SMTP_PASSWORD")

    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @field_validator("ALLOWED_HOSTS", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"  # Ignore extra fields from environment
    }


# Create settings instance
settings = Settings() 