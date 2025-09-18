from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from features.auth.models import UserCategory
from features.users.models import FarmType, CropPreference

class FarmerProfileBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    home_address: str = Field(..., min_length=5, max_length=500)
    profile_picture: Optional[str] = None
    id_document: str  # URL to stored ID document
    
    # Farm Information
    farm_name: str = Field(..., min_length=2, max_length=150)
    farm_type: FarmType
    farm_image: Optional[str] = None
    farm_location: str = Field(..., min_length=5, max_length=500)
    farm_size: str = Field(..., min_length=2, max_length=50)
    years_experience: Optional[int] = Field(None, ge=0)

class FarmerProfileCreate(FarmerProfileBase):
    # Contact Information (to update user table if needed)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class FarmerProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    home_address: str
    profile_picture: Optional[str] = None
    id_document: str
    farm_name: str
    farm_type: FarmType
    farm_image: Optional[str] = None
    farm_location: str
    farm_size: str
    years_experience: Optional[int] = None
    is_verified: bool
    verification_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class FarmerProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    home_address: Optional[str] = Field(None, min_length=5, max_length=500)
    profile_picture: Optional[str] = None
    farm_name: Optional[str] = None
    farm_type: Optional[FarmType] = None
    farm_image: Optional[str] = None
    farm_location: Optional[str] = Field(None, min_length=5, max_length=500)
    farm_size: Optional[str] = Field(None, min_length=2, max_length=50)
    years_experience: Optional[int] = Field(None, ge=0)
    
    # Optional fields that will be used to update User model
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    
    class Config:
        from_attributes = True

class ConsumerProfileBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    address: str = Field(..., min_length=5, max_length=500)
    profile_picture: Optional[str] = None
    crop_preferences: Optional[List[CropPreference]] = None

class ConsumerProfileCreate(ConsumerProfileBase):
    # Contact Information (to update user table if needed)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class ConsumerProfileResponse(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    address: str
    profile_picture: Optional[str] = None
    crop_preferences: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ConsumerProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    address: Optional[str] = Field(None, min_length=5, max_length=500)
    profile_picture: Optional[str] = None
    crop_preferences: Optional[List[CropPreference]] = None
    
    # Optional fields that will be used to update User model
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class UserProfileResponse(BaseModel):
    id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    category: UserCategory
    profile_setup: bool
    is_verified: bool
    is_active: bool
    created_at: datetime
    farmer_profile: Optional[FarmerProfileResponse] = None
    consumer_profile: Optional[ConsumerProfileResponse] = None
    
    class Config:
        from_attributes = True

class FarmerVerificationResponse(BaseModel):
    message: str = "Thank you! Your profile has been submitted for verification. We'll notify you once you're verified."
    profile_id: int
    user_id: int