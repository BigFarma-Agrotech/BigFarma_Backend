from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime


# Base schemas
class UserBase(BaseModel):
    email: EmailStr
    phone: Optional[str] = None


class ProfileBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


# Request schemas
class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class OTPRequest(BaseModel):
    email: EmailStr
    otp_type: str = "email"  # email, phone
    
    @validator('otp_type')
    def validate_otp_type(cls, v):
        if v not in ['email', 'phone']:
            raise ValueError('OTP type must be either email or phone')
        return v


class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str
    otp_type: str = "email"


class PasswordReset(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


# Response schemas
class UserResponse(UserBase):
    id: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProfileResponse(ProfileBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserWithProfileResponse(UserResponse):
    profile: Optional[ProfileResponse] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OTPResponse(BaseModel):
    message: str
    otp_type: str


class MessageResponse(BaseModel):
    message: str


# Auth schemas
class AuthResponse(BaseModel):
    user: UserWithProfileResponse
    token: TokenResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v 