from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
from pydantic import Field, field_validator

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./bigfarma.db"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # SMTP Configuration
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = False
    
    # SMS Configuration (Twilio example)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # OTP Configuration
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6
    
    # Application
    APP_NAME: str = "BigFarma"
    DEBUG: bool = False

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()