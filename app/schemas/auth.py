"""
Authentication schemas for API requests and responses.
"""
from pydantic import BaseModel

from app.models.user import (
    UserCreate,
    UserLogin,
    PasswordReset,
    PasswordResetConfirm,
    UserResponse
)


class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data model."""
    user_id: str | None = None


# Re-export user models for convenience
__all__ = [
    "Token",
    "TokenData",
    "UserCreate",
    "UserLogin",
    "PasswordReset",
    "PasswordResetConfirm",
    "UserResponse",
] 