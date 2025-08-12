from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.database import UserCategory


# Base schemas
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    @field_validator('email', 'phone')
    @classmethod
    def validate_contact_info(cls, v, info):
        if info.field_name == 'email' and v is None and info.data.get('phone') is None:
            raise ValueError('Either email or phone must be provided')
        if info.field_name == 'phone' and v is None and info.data.get('email') is None:
            raise ValueError('Either email or phone must be provided')
        return v


class ProfileBase(BaseModel):
    first_name: str
    last_name: str
    address: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    user_category: UserCategory


# Request schemas
class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserLogin(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str

    @field_validator('email', 'phone')
    @classmethod
    def validate_contact_info(cls, v, info):
        if info.field_name == 'email' and v is None and info.data.get('phone') is None:
            raise ValueError('Either email or phone must be provided')
        if info.field_name == 'phone' and v is None and info.data.get('email') is None:
            raise ValueError('Either email or phone must be provided')
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None


# Farmer Profile Schemas
class FarmerProfileCreate(ProfileBase):
    valid_id_url: str 
    farm_type: str
    farm_image_url: Optional[str] = None
    farm_location: str
    farm_size: Optional[str] = None
    years_experience: Optional[int] = None


class FarmerProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    valid_id_url: Optional[str] = None
    farm_type: Optional[str] = None
    farm_image_url: Optional[str] = None
    farm_location: Optional[str] = None
    farm_size: Optional[str] = None
    years_experience: Optional[int] = None


# Consumer Profile Schemas
class ConsumerProfileCreate(ProfileBase):
    product_preferences: List[str] = []  # List of product types interested in


class ConsumerProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None
    product_preferences: Optional[List[str]] = None


class OTPRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    otp_type: str = "email"  # email or phone
    
    @field_validator('email', 'phone')
    @classmethod
    def validate_contact_info(cls, v, info):
        if info.field_name == 'email' and v is None and info.data.get('phone') is None:
            raise ValueError('Either email or phone must be provided')
        if info.field_name == 'phone' and v is None and info.data.get('email') is None:
            raise ValueError('Either email or phone must be provided')
        return v
    
    @field_validator('otp_type')
    @classmethod
    def validate_otp_type(cls, v):
        if v not in ['email', 'phone', 'password_reset']:
            raise ValueError('OTP type must be either email, phone, or password_reset')
        return v


class OTPVerify(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    otp_code: str
    otp_type: str = "email"
    
    @field_validator('email', 'phone')
    @classmethod
    def validate_contact_info(cls, v, info):
        if info.field_name == 'email' and v is None and info.data.get('phone') is None:
            raise ValueError('Either email or phone must be provided')
        if info.field_name == 'phone' and v is None and info.data.get('email') is None:
            raise ValueError('Either email or phone must be provided')
        return v
    
    @field_validator('otp_type')
    @classmethod
    def validate_otp_type(cls, v):
        if v not in ['email', 'phone', 'password_reset']:
            raise ValueError('OTP type must be either email, phone, or password_reset')
        return v


class ForgotPasswordRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    @field_validator('email', 'phone')
    @classmethod
    def validate_contact_info(cls, v, info):
        if info.field_name == 'email' and v is None and info.data.get('phone') is None:
            raise ValueError('Either email or phone must be provided')
        if info.field_name == 'phone' and v is None and info.data.get('email') is None:
            raise ValueError('Either email or phone must be provided')
        return v


class PasswordReset(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    otp_code: str
    new_password: str
    
    @field_validator('email', 'phone')
    @classmethod
    def validate_contact_info(cls, v, info):
        if info.field_name == 'email' and v is None and info.data.get('phone') is None:
            raise ValueError('Either email or phone must be provided')
        if info.field_name == 'phone' and v is None and info.data.get('email') is None:
            raise ValueError('Either email or phone must be provided')
        return v
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


# Response schemas
class UserResponse(UserBase):
    id: str
    user_category: Optional[UserCategory] = None  # Make this optional in response
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProfileResponse(ProfileBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class FarmerProfileResponse(ProfileBase):
    id: str
    user_id: str
    valid_id_url: str
    farm_type: str
    farm_image_url: Optional[str] = None
    farm_location: str
    farm_size: Optional[str] = None
    years_experience: Optional[int] = None
    is_verified: bool
    verification_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ConsumerProfileResponse(ProfileBase):
    id: str
    user_id: str
    product_preferences: List[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserWithProfileResponse(UserResponse):
    profile: Optional[ProfileResponse] = None
    farmer_profile: Optional[FarmerProfileResponse] = None
    consumer_profile: Optional[ConsumerProfileResponse] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OTPResponse(BaseModel):
    message: str
    otp_type: str


class MessageResponse(BaseModel):
    message: str


# Profile Setup Response Schemas
class ProfileSetupResponse(BaseModel):
    message: str
    user_id: str
    profile_type: str
    next_steps: Optional[str] = None


# Auth schemas
class AuthResponse(BaseModel):
    user: UserWithProfileResponse
    token: TokenResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v 