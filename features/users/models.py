from sqlalchemy import Boolean, Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class UserCategory(str, enum.Enum):
    FARMER = "farmer"
    CONSUMER = "consumer"

class FarmType(str, enum.Enum):
    CROP = "crop"
    LIVESTOCK = "livestock"
    MIXED = "mixed"

class CropPreference(str, enum.Enum):
    VEGETABLES = "vegetables"
    FRUITS = "fruits"
    GRAINS = "grains"
    MEAT = "meat"
    DAIRY = "dairy"
    POULTRY = "poultry"
    FISH = "fish"

class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Personal Information
    full_name = Column(String, nullable=False)
    home_address = Column(Text, nullable=False)
    profile_picture = Column(String, nullable=True)  # URL to stored image
    id_document = Column(String, nullable=False)  # URL to stored ID document
    
    
    # Farm Information
    farm_name = Column(String, nullable=False)
    farm_type = Column(Enum(FarmType), nullable=False)
    farm_image = Column(String, nullable=True)  # URL to stored farm image
    farm_location = Column(Text, nullable=False)  # Address or GPS coordinates
    farm_size = Column(String, nullable=False)  # e.g., "10 acres", "5 hectares"
    years_experience = Column(Integer, nullable=True)
    
    # Verification Status
    is_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="farmer_profile")

class ConsumerProfile(Base):
    __tablename__ = "consumer_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Personal Information
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    address = Column(Text, nullable=False)  # Address or GPS coordinates
    profile_picture = Column(String, nullable=True)  # URL to stored image
    
    
    # Preferences
    crop_preferences = Column(String, nullable=True)  # Comma-separated preferences
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="consumer_profile")