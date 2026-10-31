from functools import lru_cache
from typing import Optional

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    # Template settings
    TEMPLATES_DIR: str = "templates/emails"

    # Database
    DATABASE_URL: str = "sqlite:///./bigfarma.db"

    # JWT
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Brevo Transactional Emails API
    BREVO_API_KEY: Optional[str] = None
    MAIL_FROM: Optional[str] = None
    APP_DOMAIN: str = "https://jellyfish-app-2-i2mfu.ondigitalocean.app/"

    # IP geolocation for login alerts (ipwho.is works without a key at a low monthly limit)
    IPWHOIS_KEY: Optional[str] = None

    # SMS Configuration (Twilio example)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Paystack (checkout payments). Use the sk_test_... key until going live.
    PAYSTACK_SECRET_KEY: Optional[str] = None
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    # Charged on top of the items at checkout (delivery only for door delivery)
    CHECKOUT_DELIVERY_FEE: float = 1500.0
    CHECKOUT_TAX_RATE: float = 0.075
    # Hosts Paystack may send the buyer back to after paying (comma-separated)
    PAYMENT_CALLBACK_HOSTS: str = (
        "bigfarma.ng,www.bigfarma.ng,big-farma-frontend.vercel.app,"
        "big-farma-frontend-omega.vercel.app,localhost,127.0.0.1"
    )

    # Notifications older than this are deleted automatically
    NOTIFICATION_RETENTION_DAYS: int = 30

    # OTP Configuration
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6

    # Application
    APP_NAME: str = "BigFarma"
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _coerce_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "debug"}
        return bool(value)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
