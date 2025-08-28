from pydantic import BaseModel, EmailStr, field_validator, FieldValidationInfo
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

class UserCreate(UserBase):
    password: str

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

class OTPRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium
    otp_type: str = "verification"

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
    otp_type: str = "verification"

    @field_validator('medium')
    @classmethod
    def validate_medium(cls, v, info: FieldValidationInfo):
        if v == OTPMedium.EMAIL and not info.data.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not info.data.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v

class PasswordResetRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium

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
    code: str
    new_password: str

    @field_validator('medium')
    @classmethod
    def validate_medium(cls, v, info: FieldValidationInfo):
        if v == OTPMedium.EMAIL and not info.data.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not info.data.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v