from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum

Base = declarative_base()


class UserCategory(str, Enum):
    FARMER = "farmer"
    CONSUMER = "consumer"


class User(Base):
    """User model for authentication and basic user information."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=False)
    user_category = Column(Enum(UserCategory), nullable=True)
    is_active = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = relationship("Profile", back_populates="user", uselist=False)
    farmer_profile = relationship("FarmerProfile", back_populates="user", uselist=False)
    consumer_profile = relationship("ConsumerProfile", back_populates="user", uselist=False)
    otps = relationship("OTP", back_populates="user", cascade="all, delete-orphan")


class OTP(Base):
    """OTP model for email and phone verification."""
    __tablename__ = "otps"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    otp_code = Column(String, nullable=False)
    otp_type = Column(String, nullable=False)  # email or phone
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="otps")



class FarmerProfile(Base):
    """Farmer-specific profile information."""
    __tablename__ = "farmer_profiles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    valid_id_url = Column(String, nullable=False)
    farm_type = Column(String, nullable=False)
    farm_image_url = Column(String)
    farm_location = Column(Text, nullable=False)
    farm_size = Column(String)
    years_experience = Column(Integer)
    is_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="farmer_profile")


class ConsumerProfile(Base):
    """Consumer-specific profile information."""
    __tablename__ = "consumer_profiles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    product_preferences = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="consumer_profile") 