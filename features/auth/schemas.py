import re

from pydantic import BaseModel, EmailStr, field_validator, FieldValidationInfo, Field
from typing import Optional
from datetime import datetime
from features.auth.models import UserCategory, OTPMedium

class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    category: UserCategory

    @field_validator('phone_number')
    @classmethod
    def validate_phone_or_email(cls, v, info: FieldValidationInfo):
        if v is None and info.data.get('email') is None:
            raise ValueError('Either email or phone number must be provided')
        return v

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72


def _validate_strong_password(v: str) -> str:
    if len(v) < MIN_PASSWORD_LENGTH:
        raise ValueError(f'Password must be at least {MIN_PASSWORD_LENGTH} characters long')
    if len(v.encode('utf-8')) > MAX_PASSWORD_BYTES:
        raise ValueError(f'Password must be at most {MAX_PASSWORD_BYTES} bytes long')
    if not re.search(r'[a-z]', v):
        raise ValueError('Password must contain at least one lowercase letter')
    if not re.search(r'[A-Z]', v):
        raise ValueError('Password must contain at least one uppercase letter')
    if not re.search(r'\d', v):
        raise ValueError('Password must contain at least one digit')
    if not re.search(r'[^A-Za-z0-9]', v):
        raise ValueError('Password must contain at least one special character')
    return v


class UserCreate(UserBase):
    password: str

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        return _validate_strong_password(v)

class UserLogin(BaseModel):
    login: str
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str
    user_category: str
    profile_setup: bool

class OTPRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium
    otp_type: str  # verification or password_reset

    @field_validator('medium')
    @classmethod
    def validate_medium(cls, v, info: FieldValidationInfo):
        if v == OTPMedium.EMAIL and not info.data.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not info.data.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v

class OTPVerify(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium
    code: str
    otp_type: str  # verification or password_reset

    @field_validator('medium')
    @classmethod
    def validate_medium(cls, v, info: FieldValidationInfo):
        if v == OTPMedium.EMAIL and not info.data.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not info.data.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v

class PasswordReset(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password_strength(cls, v):
        return _validate_strong_password(v)

    @field_validator('medium')
    @classmethod
    def validate_medium(cls, v, info: FieldValidationInfo):
        if v == OTPMedium.EMAIL and not info.data.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not info.data.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v
