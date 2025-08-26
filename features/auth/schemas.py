from pydantic import BaseModel, EmailStr, validator, constr
from typing import Optional, Union
from datetime import datetime
from features.auth.models import UserCategory, OTPMedium

class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    category: UserCategory

    @validator('phone_number')
    def validate_phone_or_email(cls, v, values):
        if v is None and values.get('email') is None:
            raise ValueError('Either email or phone number must be provided')
        return v

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    login: str  # Can be email or phone number
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
    medium: OTPMedium  # email or phone
    otp_type: str = "verification"  # verification, password_reset, etc.

    @validator('medium')
    def validate_medium_based_on_fields(cls, v, values):
        if v == OTPMedium.EMAIL and not values.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not values.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v

    @validator('email', 'phone')
    def validate_at_least_one_contact_method(cls, v, values):
        if not values.get('email') and not values.get('phone'):
            raise ValueError('Either email or phone must be provided')
        return v

class OTPVerify(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium
    code: str
    otp_type: str = "verification"

    @validator('medium')
    def validate_medium_based_on_fields(cls, v, values):
        if v == OTPMedium.EMAIL and not values.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not values.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v

    @validator('email', 'phone')
    def validate_at_least_one_contact_method(cls, v, values):
        if not values.get('email') and not values.get('phone'):
            raise ValueError('Either email or phone must be provided')
        return v

class PasswordResetRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium

    @validator('medium')
    def validate_medium_based_on_fields(cls, v, values):
        if v == OTPMedium.EMAIL and not values.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not values.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v

    @validator('email', 'phone')
    def validate_at_least_one_contact_method(cls, v, values):
        if not values.get('email') and not values.get('phone'):
            raise ValueError('Either email or phone must be provided')
        return v

class PasswordReset(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    medium: OTPMedium
    code: str
    new_password: str

    @validator('medium')
    def validate_medium_based_on_fields(cls, v, values):
        if v == OTPMedium.EMAIL and not values.get('email'):
            raise ValueError('Email is required when medium is email')
        if v == OTPMedium.PHONE and not values.get('phone'):
            raise ValueError('Phone is required when medium is phone')
        return v

    @validator('email', 'phone')
    def validate_at_least_one_contact_method(cls, v, values):
        if not values.get('email') and not values.get('phone'):
            raise ValueError('Either email or phone must be provided')
        return v