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
    medium: OTPMedium  # email or phone
    destination: str  # email address or phone number
    otp_type: str = "verification"  # verification, password_reset, etc.

class OTPVerify(BaseModel):
    medium: OTPMedium
    destination: str
    code: str
    otp_type: str = "verification"

class PasswordResetRequest(BaseModel):
    medium: OTPMedium
    destination: str

class PasswordReset(BaseModel):
    medium: OTPMedium
    destination: str
    code: str
    new_password: str